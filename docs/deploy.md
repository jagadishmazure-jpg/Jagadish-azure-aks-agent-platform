# Deploying to Azure (not done)

Nothing here has been deployed. CI runs `terraform validate` only. A deploy costs real money and needs the owner's explicit yes.

Resources Terraform would create (rough monthly list-price order, dev sizes, verify with the Azure pricing calculator before approving): AKS Free tier control plane + 2x D2s_v5 nodes (largest cost), Front Door Premium (fixed monthly base fee, second largest), Postgres flexible B1ms, ACR Standard, Service Bus Standard, Log Analytics + App Insights (usage based), Azure OpenAI (pay per token), Foundry hub + storage, Key Vault, managed Prometheus. A resource-group budget alert at $100/month is included.

Gated steps once approved:
1. `terraform init` with a remote state backend, then `terraform plan` and review.
2. `terraform apply`.
3. Install Argo CD and Argo Rollouts on the cluster; apply `deploy/argocd/application.yaml`.
4. Set Helm values `workloadIdentity.clientId`, `model.endpoint` from Terraform outputs; `MODEL_PROVIDER=azure`.
5. Point Front Door at the AKS ingress; configure the Entra ID app roles.
