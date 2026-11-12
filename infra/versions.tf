terraform {
  required_version = ">= 1.6"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.10"
    }
  }
  # State stays local for now. Before sharing this, move it to an Azure
  # Storage backend so state (which can hold secrets) isn't on one laptop.
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy = true # lets `terraform destroy` fully clean up
    }
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }
  subscription_id = var.subscription_id
}
