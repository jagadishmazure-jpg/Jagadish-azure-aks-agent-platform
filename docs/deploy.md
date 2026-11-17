# Deploying to Azure (not done)

Nothing here has been deployed. CI runs `terraform validate` only. A deploy costs real money and needs the owner's explicit yes.

Resources Terraform would create (rough monthly list-price order, dev sizes, verify with the Azure pricing calculator before approving): AKS Free tier control plane + 2x D2s_v5 nodes (largest cost), Front Door Premium (fixed monthly base fee, second largest), Postgres flexible B1ms, ACR Standard, Service Bus Standard, Log Analytics + App Insights (usage based), Azure OpenAI (pay per token), Foundry hub + storage, Key Vault, managed Prometheus. A resource-group budget alert at $100/month is included.

Gated steps once approved:
1. `terraform init` with a remote state backend, then `terraform plan` and review.
2. `terraform apply`.
3. Install Argo CD and Argo Rollouts on the cluster; apply `deploy/argocd/application.yaml`.
4. Set Helm values `workloadIdentity.clientId`, `model.endpoint` from Terraform outputs; `MODEL_PROVIDER=azure`.
5. Point Front Door at the AKS ingress; configure the Entra ID app roles.

## Jenkins on AKS (not run)

The Jenkinsfile and `deploy/helm/jenkins-aks` have been linted and templated offline. Running them needs the cluster from the steps above, plus an operator creating two Key Vault secrets whose **names** are `jenkins-admin-user` and `jenkins-admin-password`. The values are typed into Key Vault. They are not in git, Terraform, or the Helm values.

What a live cluster has to provide before the deploy stages can succeed:

- AKS from this Terraform (OIDC issuer, workload identity, Key Vault CSI, Azure RBAC, local accounts off).
- The two Key Vault secrets above.
- The release pod template's `dind` container is privileged. Azure Policy on the cluster has to allow that in the `jenkins` namespace, or the docker build stage cannot start. Lint and pytest pods are not privileged.
- Outbound network from the agent pods to ACR, Entra ID, and the Helm and Docker download URLs used by the release stages.

```bash
helm upgrade --install jenkins-aks deploy/helm/jenkins-aks \
  --namespace jenkins --create-namespace \
  --set workloadIdentity.clientId="$(terraform output -raw jenkins_controller_identity_client_id)" \
  --set workloadIdentity.agentClientId="$(terraform output -raw jenkins_agent_identity_client_id)" \
  --set keyVault.name="$(terraform output -raw key_vault_name)" \
  --set keyVault.tenantId="<entra tenant id>"

# Wait until secret jenkins-keyvault exists, then:
helm repo add jenkins https://charts.jenkins.io
helm upgrade --install jenkins jenkins/jenkins \
  --namespace jenkins --version 5.13.3 -f deploy/jenkins/values.yaml
```

Point a Pipeline-from-SCM job at this repo's `Jenkinsfile`. Leave `DEPLOY_TO_AKS` false to run lint, pytest and the eval gate. Set it true, and set `CLAIMS_IDENTITY_CLIENT_ID` from `terraform output -raw claims_identity_client_id`, to build, push to ACR and `helm upgrade` the claims chart. ACR admin stays disabled. The release pod logs in with the federated token the workload identity webhook mounts.
