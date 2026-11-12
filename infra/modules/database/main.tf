# The database: Azure Database for PostgreSQL (Flexible Server) with pgvector.
#
# Nobody signs in to it with a password. The app proves who it is with its
# managed identity (Microsoft Entra ID) and gets a short-lived token instead
# (backend/pipeline/db.py). A password that doesn't exist can't leak.
#
# Sized to fit the Azure free account: the smallest burstable server (B1ms)
# and 32 GB of storage are free for the first 12 months.

variable "name" { type = string }
variable "resource_group_name" { type = string }
variable "location" { type = string }
variable "app_principal_id" { type = string }
variable "app_principal_name" { type = string }
variable "admin_principal_name" { type = string }
variable "tags" { type = map(string) }

# Who is running Terraform: used for the directory (tenant) the identities live in.
data "azurerm_client_config" "current" {}

# 1. The server itself.
resource "azurerm_postgresql_flexible_server" "main" {
  name                = "psql-${var.name}"
  resource_group_name = var.resource_group_name
  location            = var.location
  version             = "16"
  sku_name            = "B_Standard_B1ms" # 1 core, 2 GB of memory: the free-account size
  storage_mb          = 32768             # 32 GB, the free allowance
  auto_grow_enabled   = false             # the allowance counts storage as provisioned: never let it grow past 32 GB by itself
  tags                = var.tags

  backup_retention_days = 7

  authentication {
    active_directory_auth_enabled = true
    password_auth_enabled         = false # identities only
    tenant_id                     = data.azurerm_client_config.current.tenant_id
  }

  lifecycle {
    ignore_changes = [zone] # Azure picks the zone; don't treat its choice as a change
  }
}

# 2. Allow the pgvector extension, which stores embeddings and searches them.
#    Azure only lets a database switch on extensions that are on this list.
resource "azurerm_postgresql_flexible_server_configuration" "extensions" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "VECTOR"
}

# 3. The database inside the server that the app uses.
resource "azurerm_postgresql_flexible_server_database" "rag" {
  name      = "rag"
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# 4. Make the app's identity an administrator, so it can sign in with a token,
#    create its tables and switch on pgvector (python -m pipeline init-db).
resource "azurerm_postgresql_flexible_server_active_directory_administrator" "app" {
  server_name         = azurerm_postgresql_flexible_server.main.name
  resource_group_name = var.resource_group_name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  object_id           = var.app_principal_id
  principal_name      = var.app_principal_name
  principal_type      = "ServicePrincipal"
}

# 4b. Make the person running Terraform an administrator too, so the passages
#     can be loaded from their own computer. One administrator is added at a
#     time: the server refuses two changes at once.
resource "azurerm_postgresql_flexible_server_active_directory_administrator" "me" {
  server_name         = azurerm_postgresql_flexible_server.main.name
  resource_group_name = var.resource_group_name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  object_id           = data.azurerm_client_config.current.object_id
  principal_name      = var.admin_principal_name
  principal_type      = "User"
  depends_on          = [azurerm_postgresql_flexible_server_active_directory_administrator.app]

  lifecycle {
    # Postgres cuts role names off at 63 characters, so a long sign-in name comes back shortened. That is not a change.
    ignore_changes = [principal_name]
  }
}

# 5. Let other Azure services reach the server (the API runs in Azure Container Apps).
#    0.0.0.0 to 0.0.0.0 is Azure's special value for "anything inside Azure", not "the whole internet".
resource "azurerm_postgresql_flexible_server_firewall_rule" "azure_services" {
  name             = "allow-azure-services"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

output "host" {
  value       = azurerm_postgresql_flexible_server.main.fqdn
  description = "The database server's address."
}

output "connection_url" {
  value       = "postgresql://${var.app_principal_name}@${azurerm_postgresql_flexible_server.main.fqdn}:5432/${azurerm_postgresql_flexible_server_database.rag.name}?sslmode=require"
  description = "Postgres URL without a password; the app fetches an Entra token at connect time."
}
