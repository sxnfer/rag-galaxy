variable "subscription_id" {
  type        = string
  description = "Azure subscription to deploy into (az account show --query id -o tsv)."
}

variable "prefix" {
  type        = string
  default     = "raggalaxy"
  description = "Short lowercase name used in every resource name."
}

variable "location" {
  type    = string
  default = "uksouth" # London
}

variable "alert_email" {
  type        = string
  description = "Where budget alerts go."
}

variable "admin_principal_name" {
  type        = string
  description = "Your own sign-in name in Azure (az ad signed-in-user show --query userPrincipalName -o tsv). Makes you a database administrator, so you can load data from your computer."
}

variable "monthly_budget" {
  type        = number
  default     = 20
  description = "Monthly budget for the alert emails, in the subscription's billing currency."
}

variable "api_image" {
  type        = string
  default     = "" # empty until the image has been published: the API is created once this is set
  description = "Address of the API's container image, e.g. ghcr.io/<github-user>/rag-galaxy-api:<version>. The image must be public."
}

variable "budget_start_date" {
  type        = string
  default     = "2026-11-01T00:00:00Z"
  description = "First day of the budget period (must be the 1st of a month)."
}
