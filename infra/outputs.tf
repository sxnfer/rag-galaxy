output "api_url" {
  value       = one(azurerm_container_app.api[*].ingress[0].fqdn) == null ? null : "https://${one(azurerm_container_app.api[*].ingress[0].fqdn)}"
  description = "Where the API answers. Empty until var.api_image is set."
}

output "frontend_url" {
  value = "https://${azurerm_static_web_app.frontend.default_host_name}"
}

output "database_host" {
  value = module.database.host
}

output "key_vault_name" {
  value = azurerm_key_vault.main.name
}

output "static_web_app_deploy_token" {
  value     = azurerm_static_web_app.frontend.api_key
  sensitive = true
}
