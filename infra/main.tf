# RAG Galaxy on Azure. Everything lives in ONE resource group, so
# `terraform destroy` (or deleting the group) removes it all. See README.md.
#
# Built to cost as little as possible: the database fits the free account's
# allowance, the API sleeps when nobody is visiting, the site files are on the
# free tier, and the API's image is kept on GitHub's free registry.

locals {
  name = var.prefix
  tags = { project = "rag-galaxy", owner = "san", managed_by = "terraform" }
  # Two names (the database server and the Key Vault) must be unique across all
  # of Azure. Six characters worked out from the subscription ID make ours
  # unique, and come out the same on every run.
  unique = substr(sha1(var.subscription_id), 0, 6)
}

resource "azurerm_resource_group" "main" {
  name     = "rg-${local.name}"
  location = var.location
  tags     = local.tags
}

# --- 1. Budget alert first: email at 50%, 80% and 100% of the monthly budget ---
resource "azurerm_consumption_budget_resource_group" "main" {
  name              = "budget-${local.name}"
  resource_group_id = azurerm_resource_group.main.id
  amount            = var.monthly_budget
  time_grain        = "Monthly"
  time_period {
    start_date = var.budget_start_date
  }
  dynamic "notification" {
    for_each = [50, 80, 100]
    content {
      enabled        = true
      threshold      = notification.value
      operator       = "GreaterThanOrEqualTo"
      contact_emails = [var.alert_email]
    }
  }
  lifecycle {
    ignore_changes = [time_period] # start date is fixed at creation
  }
}

# --- 2. Identity: one user-assigned managed identity for the API.
# Azure gives it tokens automatically, so no keys or passwords live in our code.
resource "azurerm_user_assigned_identity" "app" {
  name                = "id-${local.name}"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  tags                = local.tags
}

# --- 3. Database: Postgres with pgvector, signed into with identities only ---
module "database" {
  source               = "./modules/database"
  name                 = "${local.name}-${local.unique}"
  resource_group_name  = azurerm_resource_group.main.name
  location             = var.location
  app_principal_id     = azurerm_user_assigned_identity.app.principal_id
  app_principal_name   = azurerm_user_assigned_identity.app.name
  admin_principal_name = var.admin_principal_name
  tags                 = local.tags
}

# --- 4. Secrets: Key Vault with RBAC; the app identity may read secrets only ---
data "azurerm_client_config" "me" {}

resource "azurerm_key_vault" "main" {
  name                       = "kv-${local.name}-${local.unique}"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = var.location
  tenant_id                  = data.azurerm_client_config.me.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  soft_delete_retention_days = 7
  tags                       = local.tags
}

resource "azurerm_role_assignment" "me_kv_admin" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.me.object_id
}

resource "azurerm_role_assignment" "app_kv_reader" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

# The Anthropic API key. Terraform only makes the slot, with a placeholder in it:
# the real key is put in afterwards with one command (see README.md), so it is
# never written into Terraform's state file on this computer.
resource "azurerm_key_vault_secret" "anthropic" {
  name         = "anthropic-api-key"
  value        = "not-set-yet"
  key_vault_id = azurerm_key_vault.main.id
  depends_on   = [azurerm_role_assignment.me_kv_admin]
  lifecycle {
    ignore_changes = [value, tags, content_type] # the real key is set outside Terraform: leave it, and the labels the Azure tool adds, alone
  }
}

# --- 5. Logs: where the API's output goes, kept for 30 days ---
resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-${local.name}"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.tags
}

# --- 6. The API: a Container App that sleeps when nobody is visiting ---
# There is no registry here on purpose. The API's image is kept on GitHub's
# registry (ghcr.io), which is free, instead of an Azure Container Registry
# (about 4 GBP a month). The image is public, so Azure needs no password to
# download it: var.api_image is simply its address.
resource "azurerm_container_app_environment" "main" {
  name                       = "cae-${local.name}"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = var.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  tags                       = local.tags

  # "Consumption" is the pay-only-while-running plan: nothing reserved, nothing billed while asleep.
  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }
}

locals {
  app_env = {
    DATABASE_URL    = module.database.connection_url # no password: the app signs in with its identity
    AZURE_CLIENT_ID = azurerm_user_assigned_identity.app.client_id
    CORS_ORIGINS    = "https://${azurerm_static_web_app.frontend.default_host_name}"
    TRUSTED_PROXIES = "1" # the Container Apps ingress: the rate limiter reads the visitor's address from it
  }
}

# Created only once var.api_image is set: Azure can't start an API whose image doesn't exist yet.
resource "azurerm_container_app" "api" {
  count                        = var.api_image == "" ? 0 : 1
  name                         = "ca-${local.name}-api"
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"
  tags                         = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  secret {
    name                = "anthropic-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.anthropic.versionless_id
    identity            = azurerm_user_assigned_identity.app.id
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 0 # scale to zero when nobody is visiting: costs nothing idle
    max_replicas = 1 # one copy only: the rate limits are counted in its memory (backend/app/guard.py)
    container {
      name   = "api"
      image  = var.api_image
      cpu    = 1.0
      memory = "2Gi" # the embedding model needs room
      env {
        name        = "ANTHROPIC_API_KEY"
        secret_name = "anthropic-api-key"
      }
      dynamic "env" {
        for_each = local.app_env
        content {
          name  = env.key
          value = env.value
        }
      }
    }
  }
  depends_on = [azurerm_role_assignment.app_kv_reader]
}

# --- 7. Frontend: Static Web Apps (free tier) serves the built React app ---
resource "azurerm_static_web_app" "frontend" {
  name                = "swa-${local.name}"
  resource_group_name = azurerm_resource_group.main.name
  location            = "eastus2" # Static Web Apps is offered in a few regions only, and West Europe is closed to new accounts. The files are served worldwide either way.
  sku_tier            = "Free"
  sku_size            = "Free"
  tags                = local.tags

  lifecycle {
    # GitHub's publish step (.github/workflows/site.yml) records which repository the files came from. Leave that alone.
    ignore_changes = [repository_url, repository_branch]
  }
}
