# Deploying to Azure (not done)

Nothing here has been deployed. CI runs `terraform validate` only. A deploy costs real money and needs the owner's explicit yes.

Resources Terraform would create (rough monthly list-price order, dev sizes, verify with the Azure pricing calculator before approving): AKS Free tier control plane + 2x D2s_v5 nodes (largest cost), Front Door Premium (fixed monthly base fee, second largest), Postgres flexible B1ms, ACR Standard, Service Bus Standard, Log Analytics + App Insights (usage based), Azure OpenAI (pay per token), Foundry hub + storage, Key Vault, managed Prometheus. A resource-group budget alert at $100/month is included.

Gated steps once approved:
1. `terraform init` with a remote state backend, then `terraform plan` and review.
2. `terraform apply`.
3. Install Argo CD and Argo Rollouts on the cluster; apply `deploy/argocd/application.yaml`.
4. Set Helm values `workloadIdentity.clientId`, `model.endpoint` from Terraform outputs; `MODEL_PROVIDER=azure`.
5. Point Front Door at the AKS ingress; configure the Entra ID app roles.

## GitHub Actions deploy (not run against a subscription)

CI (lint, pytest, `scripts/run_measurements.py --check`, Terraform validate, image build, Trivy, kind, CodeQL, gitleaks) does not log in to Azure. `cd.yml` deploys. It finishes successfully and prints `Azure CD skipped` when `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `ACR_NAME`, `AKS_NAME`, or `AKS_RESOURCE_GROUP` is unset.

GitHub Actions is the default deployer for the `claims` namespace. `deploy/argocd/application.yaml` has no automated sync. Apply it only after disabling `.github/workflows/cd.yml`.

One-time setup, after `terraform apply`:

1. Create GitHub Environments `dev` (no required reviewers) and `prod` (required reviewers) before the first prod run.
2. Set the repository variables in the table in the README. `AZURE_CLIENT_ID` is `terraform output -raw gha_deploy_client_id`. There is no client secret.
3. A cluster admin applies `deploy/k8s/claims-namespace.yaml`.

A push to `main` builds and pushes `claims-agent:<sha>` to ACR, then helm-upgrades namespace `claims` in the `dev` environment. **Actions → cd → Run workflow** with environment `prod` and that same `image_sha` promotes the tag. Prod does not build. The chart values file sets `env: prod` and `checkpoints.storageClass: azurefile-csi`. Helm waits until the workloads are ready. The service stays on the labelled stub until Azure OpenAI can be called without an API key. This workflow does not inject one.

`.github/workflows/azure-deploy.yml` is the reusable workflow other repositories can call.
