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

CI does not log in to Azure. `cd.yml` starts after `container.yml` succeeds on `main`, then deploys only if the CI checks for that commit succeeded. It prints `Azure CD skipped` and finishes successfully when the Azure variables for that environment are unset.

Dev and prod are separate. Dev uses identity `gha_dev`, namespace `claims-dev`, and may push to ACR. Prod uses identity `gha_prod`, namespace `claims`, and may only pull from ACR. A dev run cannot change the prod namespace. Both GitHub Environments should be limited to the `main` branch, and `prod` needs required reviewers before the first promotion. The workflow also rejects a ref that is not `main`.

The claims pods are separate too. `claims_identity_client_id` is federated only to `system:serviceaccount:claims:claims-agent`. `claims_dev_identity_client_id` is a second identity federated only to `system:serviceaccount:claims-dev:claims-agent`, with the same Key Vault, Service Bus, and Azure OpenAI data roles. Set `CLAIMS_IDENTITY_CLIENT_ID` and `CLAIMS_DEV_IDENTITY_CLIENT_ID` from those outputs. The dev helm release writes the dev client id. The prod release writes the prod client id.

The image deployed is the one `container.yml` built, scanned, and signed in GHCR. CD verifies that signature, copies the digest into ACR, and will not replace an existing SHA tag with different bytes. After the copy it locks that tag with `az acr repository update --write-enabled false`. That lock works on the Standard SKU this registry uses. Turning on immutable tags for the whole registry (`policies.immutableTags`) needs Premium, so Terraform does not enable it. Tags pushed before this change stay writable until a later deploy of that SHA locks them, or until you run the same `az` command by hand. Prod promotes that digest only after the dev GitHub deployment for the SHA succeeded. Helm uses `HELM_DRIVER=configmap` because the namespace Writer role does not read Secrets, and it waits for an Argo Rollout to become Healthy when that resource exists. `APP_ENV` is left at `dev`. Setting it to `prod` makes the service reject every token, including a real Entra token, until signature checks exist in the service.

`deploy/argocd/application.yaml` has no automated sync. Apply it only after disabling `.github/workflows/cd.yml`. If Argo already created the chart resources, set repository variable `HELM_ADOPT_EXISTING` to `true` for one run so `deploy/k8s/adopt-for-helm.sh` adds Helm ownership, then unset it.

`.github/workflows/azure-deploy.yml` is the reusable workflow other repositories can call.
