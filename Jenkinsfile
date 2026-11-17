// Declarative pipeline. Same offline gates as .github/workflows/ci.yml, plus a
// gated ACR push and Helm upgrade. The side-by-side map is in README.md.
//
// DEPLOY_TO_AKS defaults to false. Docker build, push to ACR and helm upgrade
// need a live AKS cluster: the workload identity webhook, Key Vault secrets
// created by an operator, ACR and kubelogin. This file holds no secret values.
// az login reads the federated token the webhook mounts at
// AZURE_FEDERATED_TOKEN_FILE. That token is not written here.

pipeline {
  agent none
  options {
    timestamps()
    timeout(time: 45, unit: 'MINUTES')
    disableConcurrentBuilds()
  }
  parameters {
    booleanParam(
      name: 'DEPLOY_TO_AKS',
      defaultValue: false,
      description: 'Build the image, push it to ACR and helm-upgrade claims-agent. Needs a live AKS cluster. Leave false to run lint, pytest and the eval gate only.'
    )
    string(name: 'ACR_NAME', defaultValue: 'nfclaimsacr', description: 'ACR name. Terraform prefix nfclaims produces nfclaimsacr. Not a secret.')
    string(name: 'AKS_RESOURCE_GROUP', defaultValue: 'nfclaims-rg', description: 'Resource group of the AKS cluster.')
    string(name: 'AKS_NAME', defaultValue: 'nfclaims-aks', description: 'AKS cluster name.')
    string(name: 'CLAIMS_IDENTITY_CLIENT_ID', defaultValue: '', description: 'Terraform output claims_identity_client_id. Required only when DEPLOY_TO_AKS is true. An identifier, not a secret.')
    string(name: 'IMAGE_TAG', defaultValue: '', description: 'Image tag. Empty means GIT_COMMIT.')
  }
  stages {
    stage('Lint') {
      agent { label 'python' }
      steps {
        container('python') {
          sh '''
            set -euo pipefail
            python -m pip install --no-cache-dir -e ".[dev]"
            ruff check .
            ruff format --check .
            python scripts/check_brands.py
          '''
        }
        container('helm') {
          sh '''
            set -euo pipefail
            helm lint deploy/helm/claims-agent
            helm template t deploy/helm/claims-agent >/dev/null
            helm template t deploy/helm/claims-agent --api-versions argoproj.io/v1alpha1 >/dev/null
            helm lint deploy/helm/jenkins-aks --namespace jenkins
            helm template j deploy/helm/jenkins-aks --namespace jenkins >/dev/null
          '''
        }
        container('terraform') {
          sh '''
            set -euo pipefail
            cd infra/terraform
            terraform fmt -check -recursive
            terraform init -backend=false -input=false
            terraform validate
          '''
        }
      }
    }

    stage('Pytest') {
      agent { label 'python' }
      steps {
        container('python') {
          sh '''
            set -euo pipefail
            python -m pip install --no-cache-dir -e ".[dev]"
            pytest -q
            python scripts/count_tests.py
          '''
        }
      }
    }

    stage('Eval gate') {
      agent { label 'python' }
      steps {
        container('python') {
          sh '''
            set -euo pipefail
            python -m pip install --no-cache-dir -e ".[dev]"
            # Fresh stub eval must match the committed results. Drift fails the
            # build, which is the same rule GitHub Actions uses.
            python scripts/run_measurements.py --check
            python scripts/render_docs.py --check
          '''
        }
      }
    }

    // One pod so the image built in dind is still there for the push, and the
    // Azure CLI login survives into the helm stage. Nested so the three names
    // stay separate stages. Skipped unless DEPLOY_TO_AKS is true.
    stage('Release') {
      when { expression { return params.DEPLOY_TO_AKS } }
      agent { label 'release' }
      environment {
        ACR_NAME = "${params.ACR_NAME}"
        AKS_RESOURCE_GROUP = "${params.AKS_RESOURCE_GROUP}"
        AKS_NAME = "${params.AKS_NAME}"
        CLAIMS_IDENTITY_CLIENT_ID = "${params.CLAIMS_IDENTITY_CLIENT_ID}"
        IMAGE_TAG = "${params.IMAGE_TAG}"
      }
      stages {
        stage('Docker build') {
          steps {
            container('deploy') {
              sh '''
                set -euo pipefail
                if ! command -v docker >/dev/null 2>&1; then
                  curl -fsSL -o /tmp/docker.tgz "https://download.docker.com/linux/static/stable/x86_64/docker-27.4.1.tgz"
                  tar -xzf /tmp/docker.tgz -C /tmp
                  cp /tmp/docker/docker /usr/local/bin/docker
                  chmod +x /usr/local/bin/docker
                fi
                ok=0
                for _ in $(seq 1 30); do
                  if docker info >/dev/null 2>&1; then
                    ok=1
                    break
                  fi
                  sleep 2
                done
                test "$ok" = 1
                TAG="${IMAGE_TAG:-$GIT_COMMIT}"
                test -n "$TAG"
                docker build -t "${ACR_NAME}.azurecr.io/claims-agent:${TAG}" .
              '''
            }
          }
        }
        stage('Push to ACR') {
          steps {
            container('deploy') {
              sh '''
                set -euo pipefail
                test -n "${AZURE_CLIENT_ID:-}"
                test -n "${AZURE_TENANT_ID:-}"
                test -n "${AZURE_FEDERATED_TOKEN_FILE:-}"
                test -s "$AZURE_FEDERATED_TOKEN_FILE"
                az login --service-principal \
                  --username "$AZURE_CLIENT_ID" \
                  --tenant "$AZURE_TENANT_ID" \
                  --federated-token "$(cat "$AZURE_FEDERATED_TOKEN_FILE")"
                az acr login --name "$ACR_NAME"
                TAG="${IMAGE_TAG:-$GIT_COMMIT}"
                test -n "$TAG"
                docker push "${ACR_NAME}.azurecr.io/claims-agent:${TAG}"
              '''
            }
          }
        }
        stage('Helm upgrade to AKS') {
          steps {
            container('deploy') {
              sh '''
                set -euo pipefail
                test -n "${CLAIMS_IDENTITY_CLIENT_ID:-}"
                test -n "${AZURE_CLIENT_ID:-}"
                test -n "${AZURE_TENANT_ID:-}"
                test -n "${AZURE_FEDERATED_TOKEN_FILE:-}"
                test -s "$AZURE_FEDERATED_TOKEN_FILE"
                az login --service-principal \
                  --username "$AZURE_CLIENT_ID" \
                  --tenant "$AZURE_TENANT_ID" \
                  --federated-token "$(cat "$AZURE_FEDERATED_TOKEN_FILE")"
                az aks install-cli
                az aks get-credentials --resource-group "$AKS_RESOURCE_GROUP" --name "$AKS_NAME" --overwrite-existing
                kubelogin convert-kubeconfig -l workloadidentity
                if ! command -v helm >/dev/null 2>&1; then
                  curl -fsSL -o /tmp/helm.tgz "https://get.helm.sh/helm-v3.16.2-linux-amd64.tar.gz"
                  tar -xzf /tmp/helm.tgz -C /tmp
                  cp /tmp/linux-amd64/helm /usr/local/bin/helm
                  chmod +x /usr/local/bin/helm
                fi
                TAG="${IMAGE_TAG:-$GIT_COMMIT}"
                test -n "$TAG"
                helm upgrade --install claims-agent deploy/helm/claims-agent \
                  --namespace claims --create-namespace \
                  --set "image.repository=${ACR_NAME}.azurecr.io/claims-agent" \
                  --set "image.tag=${TAG}" \
                  --set "workloadIdentity.clientId=${CLAIMS_IDENTITY_CLIENT_ID}"
              '''
            }
          }
        }
      }
    }
  }
}
