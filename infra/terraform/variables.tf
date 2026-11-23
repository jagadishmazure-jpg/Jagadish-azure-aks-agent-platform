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

variable "foundry_sandbox_pool_enabled" {
  type        = bool
  default     = false
  description = "Create the Azure Linux KataVmIsolation pool for session pods. Off until the VM size and region are confirmed. [verify]"
}

variable "foundry_sandbox_vm_size" {
  type        = string
  default     = "Standard_D2s_v5"
  description = "Placeholder size for the sandbox pool. It must support nested virtualization. [verify]"
}

variable "foundry_gpu_pool_enabled" {
  type        = bool
  default     = false
  description = "Create the GPU pool for open-weight serving. Off because it changes the bill. [verify]"
}

variable "foundry_gpu_vm_size" {
  type        = string
  default     = "Standard_NC4as_T4_v3"
  description = "Placeholder GPU size for the model pool. Confirm availability before apply. [verify]"
}

variable "tags" {
  type    = map(string)
  default = { workload = "claims-agents", owner = "platform", env = "dev" }
}
