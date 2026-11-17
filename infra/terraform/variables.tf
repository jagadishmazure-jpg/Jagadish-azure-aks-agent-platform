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
variable "jenkins_secret_scopes" {
  type        = bool
  default     = false
  description = "Grant the Jenkins controller Key Vault Secrets User on jenkins-admin-user and jenkins-admin-password only. Set true after those secrets exist. There is no vault-wide grant for Jenkins."
}

variable "tags" {
  type    = map(string)
  default = { workload = "claims-agents", owner = "platform", env = "dev" }
}
