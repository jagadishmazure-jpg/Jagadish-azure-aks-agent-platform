output "aks_name" { value = azurerm_kubernetes_cluster.aks.name }
output "acr_login_server" { value = azurerm_container_registry.acr.login_server }
output "claims_identity_client_id" { value = azurerm_user_assigned_identity.claims.client_id }
output "openai_endpoint" { value = azurerm_cognitive_account.aoai.endpoint }
output "key_vault_uri" { value = azurerm_key_vault.kv.vault_uri }
output "frontdoor_endpoint" { value = azurerm_cdn_frontdoor_endpoint.api.host_name }
