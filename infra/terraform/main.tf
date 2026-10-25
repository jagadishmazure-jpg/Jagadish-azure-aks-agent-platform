data "azurerm_client_config" "me" {}

resource "azurerm_resource_group" "rg" {
  name     = "${var.prefix}-rg"
  location = var.location
  tags     = var.tags
}

# ---------- observability
resource "azurerm_log_analytics_workspace" "law" {
  name                = "${var.prefix}-law"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

resource "azurerm_application_insights" "ai" {
  name                = "${var.prefix}-appi"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  workspace_id        = azurerm_log_analytics_workspace.law.id
  application_type    = "web"
  tags                = var.tags
}

resource "azurerm_monitor_workspace" "prom" {
  name                = "${var.prefix}-amw"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  tags                = var.tags
}

# ---------- registry and runtime
resource "azurerm_container_registry" "acr" {
  name                          = "${var.prefix}acr"
  location                      = azurerm_resource_group.rg.location
  resource_group_name           = azurerm_resource_group.rg.name
  sku                           = "Standard"
  admin_enabled                 = false
  public_network_access_enabled = true
  tags                          = var.tags
}

resource "azurerm_kubernetes_cluster" "aks" {
  name                      = "${var.prefix}-aks"
  location                  = azurerm_resource_group.rg.location
  resource_group_name       = azurerm_resource_group.rg.name
  dns_prefix                = var.prefix
  oidc_issuer_enabled       = true
  workload_identity_enabled = true
  azure_policy_enabled      = true
  local_account_disabled    = true
  sku_tier                  = "Free"

  default_node_pool {
    name                 = "system"
    vm_size              = var.aks_node_size
    auto_scaling_enabled = true
    min_count            = 2
    max_count            = 5
    zones                = ["1", "2", "3"]
  }

  identity { type = "SystemAssigned" }

  azure_active_directory_role_based_access_control {
    azure_rbac_enabled = true
    tenant_id          = data.azurerm_client_config.me.tenant_id
  }

  key_vault_secrets_provider { secret_rotation_enabled = true }
  oms_agent { log_analytics_workspace_id = azurerm_log_analytics_workspace.law.id }
  monitor_metrics {}

  network_profile {
    network_plugin = "azure"
    network_policy = "azure"
  }
  tags = var.tags
}

resource "azurerm_role_assignment" "aks_pull" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_kubernetes_cluster.aks.kubelet_identity[0].object_id
}

# ---------- workload identity for the claims pods (no keys in pods)
resource "azurerm_user_assigned_identity" "claims" {
  name                = "${var.prefix}-claims-id"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  tags                = var.tags
}

resource "azurerm_federated_identity_credential" "claims" {
  name                = "claims-agent"
  resource_group_name = azurerm_resource_group.rg.name
  parent_id           = azurerm_user_assigned_identity.claims.id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = azurerm_kubernetes_cluster.aks.oidc_issuer_url
  subject             = "system:serviceaccount:claims:claims-agent"
}

# ---------- secrets
resource "azurerm_key_vault" "kv" {
  name                       = "${var.prefix}-kv"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  tenant_id                  = data.azurerm_client_config.me.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  purge_protection_enabled   = true
  soft_delete_retention_days = 30
  tags                       = var.tags
}

resource "azurerm_role_assignment" "claims_kv" {
  scope                = azurerm_key_vault.kv.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.claims.principal_id
}

# ---------- messaging: one broker (Service Bus) instead of a queue plus a separate log platform
resource "azurerm_servicebus_namespace" "sb" {
  name                = "${var.prefix}-sb"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "Standard"
  local_auth_enabled  = false
  tags                = var.tags
}

resource "azurerm_servicebus_queue" "claims" {
  name                                 = "claims-intake"
  namespace_id                         = azurerm_servicebus_namespace.sb.id
  max_delivery_count                   = 5
  dead_lettering_on_message_expiration = true
}

resource "azurerm_role_assignment" "claims_sb" {
  scope                = azurerm_servicebus_namespace.sb.id
  role_definition_name = "Azure Service Bus Data Owner"
  principal_id         = azurerm_user_assigned_identity.claims.principal_id
}

# ---------- data: Postgres with pgvector (one store for state, checkpoints and vectors)
resource "azurerm_postgresql_flexible_server" "pg" {
  name                          = "${var.prefix}-pg"
  location                      = azurerm_resource_group.rg.location
  resource_group_name           = azurerm_resource_group.rg.name
  version                       = "16"
  sku_name                      = "B_Standard_B1ms"
  storage_mb                    = 32768
  backup_retention_days         = 14
  public_network_access_enabled = false
  authentication {
    active_directory_auth_enabled = true
    password_auth_enabled         = false
    tenant_id                     = data.azurerm_client_config.me.tenant_id
  }
  tags = var.tags
  lifecycle { ignore_changes = [zone] }
}

resource "azurerm_postgresql_flexible_server_configuration" "pgvector" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.pg.id
  value     = "VECTOR"
}

# ---------- AI layer: Azure OpenAI deployment + Foundry hub/project for evals
resource "azurerm_cognitive_account" "aoai" {
  name                          = "${var.prefix}-aoai"
  location                      = azurerm_resource_group.rg.location
  resource_group_name           = azurerm_resource_group.rg.name
  kind                          = "OpenAI"
  sku_name                      = "S0"
  custom_subdomain_name         = "${var.prefix}-aoai"
  local_auth_enabled            = false
  public_network_access_enabled = true
  tags                          = var.tags
}

resource "azurerm_cognitive_deployment" "model" {
  name                 = var.model_deployment
  cognitive_account_id = azurerm_cognitive_account.aoai.id
  model {
    format  = "OpenAI"
    name    = var.model_deployment
    version = var.model_version
  }
  sku {
    name     = "GlobalStandard"
    capacity = 10
  }
}

resource "azurerm_role_assignment" "claims_aoai" {
  scope                = azurerm_cognitive_account.aoai.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_user_assigned_identity.claims.principal_id
}

resource "azurerm_storage_account" "foundry" {
  name                            = "${var.prefix}fdst"
  location                        = azurerm_resource_group.rg.location
  resource_group_name             = azurerm_resource_group.rg.name
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = false
  tags                            = var.tags
}

resource "azurerm_ai_foundry" "hub" {
  name                    = "${var.prefix}-foundry"
  location                = azurerm_resource_group.rg.location
  resource_group_name     = azurerm_resource_group.rg.name
  storage_account_id      = azurerm_storage_account.foundry.id
  key_vault_id            = azurerm_key_vault.kv.id
  application_insights_id = azurerm_application_insights.ai.id
  identity { type = "SystemAssigned" }
  tags = var.tags
}

resource "azurerm_ai_foundry_project" "evals" {
  name               = "${var.prefix}-evals"
  location           = azurerm_resource_group.rg.location
  ai_services_hub_id = azurerm_ai_foundry.hub.id
  identity { type = "SystemAssigned" }
  tags = var.tags
}

# ---------- front door: Entra-authenticated edge with a managed WAF
resource "azurerm_cdn_frontdoor_profile" "fd" {
  name                = "${var.prefix}-fd"
  resource_group_name = azurerm_resource_group.rg.name
  sku_name            = "Premium_AzureFrontDoor"
  tags                = var.tags
}

resource "azurerm_cdn_frontdoor_firewall_policy" "waf" {
  name                = "${var.prefix}waf"
  resource_group_name = azurerm_resource_group.rg.name
  sku_name            = azurerm_cdn_frontdoor_profile.fd.sku_name
  mode                = "Prevention"
  managed_rule {
    type    = "Microsoft_DefaultRuleSet"
    version = "2.1"
    action  = "Block"
  }
  managed_rule {
    type    = "Microsoft_BotManagerRuleSet"
    version = "1.1"
    action  = "Block"
  }
  tags = var.tags
}

resource "azurerm_cdn_frontdoor_security_policy" "waf" {
  name                     = "${var.prefix}-waf-binding"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.fd.id
  security_policies {
    firewall {
      cdn_frontdoor_firewall_policy_id = azurerm_cdn_frontdoor_firewall_policy.waf.id
      association {
        patterns_to_match = ["/*"]
        domain { cdn_frontdoor_domain_id = azurerm_cdn_frontdoor_endpoint.api.id }
      }
    }
  }
}

resource "azurerm_cdn_frontdoor_endpoint" "api" {
  name                     = "${var.prefix}-api"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.fd.id
  tags                     = var.tags
}

# Budget guard for the whole resource group (alerts only; does not stop resources).
resource "azurerm_consumption_budget_resource_group" "budget" {
  name              = "${var.prefix}-budget"
  resource_group_id = azurerm_resource_group.rg.id
  amount            = 100
  time_grain        = "Monthly"
  time_period { start_date = "2026-11-01T00:00:00Z" }
  notification {
    enabled        = true
    threshold      = 80
    operator       = "GreaterThan"
    contact_emails = ["platform-alerts@northfield-mutual.example"]
  }
}
