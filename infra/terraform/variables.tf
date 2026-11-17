variable "prefix" {
  type    = string
  default = "nfclaims"
}
variable "location" {
  type    = string
  default = "eastus2"
}
variable "aks_node_size" {
  type    = string
  default = "Standard_D2s_v5"
}
variable "model_deployment" {
  type    = string
  default = "gpt-4o-mini"
}
variable "model_version" {
  type    = string
  default = "2024-07-18"
}
variable "pg_admin_login" {
  type    = string
  default = "nfadmin"
}
variable "github_repository" {
  type        = string
  default     = "jagadishmazure-jpg/Jagadish-azure-aks-agent-platform"
  description = "GitHub repository allowed to deploy through OIDC. Subjects are environment:dev and environment:prod."
}

variable "tags" {
  type    = map(string)
  default = { workload = "claims-agents", owner = "platform", env = "dev" }
}
