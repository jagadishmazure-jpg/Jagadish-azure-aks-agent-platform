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

The Jenkinsfile and `deploy/helm/jenkins-aks` have been linted and templated offline. Running them needs the cluster from the steps above, plus an operator creating two Key Vault secrets whose **names** are `jenkins-admin-user` and `jenkins-admin-password`. The values are typed into Key Vault. They are not in git, Terraform, or the Helm values. After they exist, set `jenkins_secret_scopes = true` and apply again so the controller identity can read those two secrets and no others.

Jenkins helm upgrade and the Argo CD application are alternatives. If Argo is auto-syncing `deploy/helm/claims-agent`, it will put the git revision back after Jenkins upgrades the release. Install one of them for the `claims` namespace.

What a live cluster has to provide before the deploy stages can succeed:

- AKS from this Terraform (OIDC issuer, workload identity, Key Vault CSI, Azure RBAC, local accounts off).
- The two Key Vault secrets above, then `jenkins_secret_scopes = true`.
- A cluster admin applies `deploy/k8s/claims-namespace.yaml`. The release identity is Azure RBAC Writer on that namespace only, so it cannot create the namespace and it cannot change other namespaces.
- The release pod template's `dind` container is privileged and listens on `127.0.0.1` only. A NetworkPolicy on `jenkins.io/release=true` allows no ingress. Azure Policy on the cluster has to allow the privileged container in the `jenkins` namespace, or the docker build stage cannot start. Lint and pytest pods are not privileged.
- Outbound network from the release pod to ACR, Entra ID, the Kubernetes API, and the Helm and Docker download URLs.
- `DEPLOY_TO_AKS` on `main` (not on a pull request), then the `Approve release` input. The checkbox alone does not allocate the release pod (`beforeAgent`).

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

Point a Pipeline-from-SCM job at this repo's `Jenkinsfile`. Leave `DEPLOY_TO_AKS` false to run lint, pytest and the eval gate. On `main`, set it true and set `CLAIMS_IDENTITY_CLIENT_ID` from `terraform output -raw claims_identity_client_id`. The job then waits for `Approve release` before it builds, pushes to ACR, and helm-upgrades. The image tag includes the git commit. Chart values are written to a file (`env: prod`, `checkpoints.storageClass: azurefile-csi`) so a comma in a parameter cannot add another Helm assignment. ACR admin stays disabled. The release pod logs in with the federated token with shell tracing off. `AZURE_OPENAI_ENDPOINT`, when set, must be an `https://` host. The service still uses the labelled stub until Azure OpenAI can be called without an API key; this pipeline does not inject one.
