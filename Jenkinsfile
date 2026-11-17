// Declarative pipeline. Same offline gates as .github/workflows/ci.yml, plus a
// gated ACR push and Helm upgrade. The side-by-side map is in README.md.
//
// DEPLOY_TO_AKS defaults to false. beforeAgent skips the privileged pod when
// the flag is off. A separate input step approves the release, and a pull
// request build cannot take it. Docker build, push and helm upgrade need a
// live AKS cluster. This file holds no secret values. az login reads the
// federated token with xtrace off so the build log does not print it.
//
// Helm upgrade and the Argo CD application are alternatives. If Argo is
// auto-syncing deploy/helm/claims-agent, it will put back the git revision
// after this upgrade. Do not run both against the same namespace.

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
      description: 'Build the image, push it to ACR and helm-upgrade claims-agent. Needs a live AKS cluster and a release approval. Leave false to run lint, pytest and the eval gate only.'
    )
    string(name: 'ACR_NAME', defaultValue: 'nfclaimsacr', description: 'ACR name. Terraform prefix nfclaims produces nfclaimsacr. Not a secret.')
    string(name: 'AKS_RESOURCE_GROUP', defaultValue: 'nfclaims-rg', description: 'Resource group of the AKS cluster.')
    string(name: 'AKS_NAME', defaultValue: 'nfclaims-aks', description: 'AKS cluster name.')
    string(name: 'CLAIMS_IDENTITY_CLIENT_ID', defaultValue: '', description: 'Terraform output claims_identity_client_id. Required only when DEPLOY_TO_AKS is true. An identifier, not a secret.')
    string(name: 'IMAGE_TAG', defaultValue: '', description: 'Optional prefix. The pushed tag is always this prefix plus GIT_COMMIT, or GIT_COMMIT alone.')
    string(name: 'AZURE_OPENAI_ENDPOINT', defaultValue: '', description: 'Optional https endpoint for the claims chart. Not a secret. The service stays on the labelled stub until it can call Azure OpenAI without an API key.')
  }
  stages {
    stage('Lint') {
      agent { label 'python' }
      steps {
        container('python') {
          sh '''
            set -eu
            python -m pip install --no-cache-dir -e ".[dev]"
            ruff check .
            ruff format --check .
            python scripts/check_brands.py
          '''
        }
        container('helm') {
          sh '''
            set -eu
            helm lint deploy/helm/claims-agent
            helm template t deploy/helm/claims-agent >/dev/null
            helm template t deploy/helm/claims-agent --api-versions argoproj.io/v1alpha1 >/dev/null
            helm lint deploy/helm/jenkins-aks --namespace jenkins
            helm template j deploy/helm/jenkins-aks --namespace jenkins >/dev/null
          '''
        }
        container('terraform') {
          sh '''
            set -eu
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
            set -eu
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
            set -eu
            python -m pip install --no-cache-dir -e ".[dev]"
            # Fresh stub eval must match the committed results. Drift fails the
            # build, which is the same rule GitHub Actions uses.
            python scripts/run_measurements.py --check
            python scripts/render_docs.py --check
          '''
        }
      }
    }

    // beforeAgent: the privileged release pod is not requested when this is skipped.
    // The approval stage has no agent. The ship stage allocates the release pod
    // only after the input step.
    stage('Release') {
      when {
        beforeAgent true
        allOf {
          expression { return params.DEPLOY_TO_AKS }
          expression { return !env.CHANGE_ID && (env.BRANCH_NAME == null || env.BRANCH_NAME == 'main') }
        }
      }
      agent none
      stages {
        stage('Approve release') {
          steps {
            input message: 'Push the image to ACR and helm-upgrade claims-agent on AKS? Starting the build does not approve this.', ok: 'Release'
          }
        }
        stage('Ship') {
          agent { label 'release' }
          environment {
            ACR_NAME = "${params.ACR_NAME}"
            AKS_RESOURCE_GROUP = "${params.AKS_RESOURCE_GROUP}"
            AKS_NAME = "${params.AKS_NAME}"
            CLAIMS_IDENTITY_CLIENT_ID = "${params.CLAIMS_IDENTITY_CLIENT_ID}"
            IMAGE_TAG = "${params.IMAGE_TAG}"
            AZURE_OPENAI_ENDPOINT = "${params.AZURE_OPENAI_ENDPOINT}"
          }
          stages {
            stage('Docker build') {
              steps {
                container('deploy') {
                  sh '''
                    set -eu
                    printf '%s\n' "$ACR_NAME" | grep -Eq '^[a-z0-9]{5,50}$'
                    test -n "${GIT_COMMIT:-}"
                    tag="$GIT_COMMIT"
                    if [ -n "${IMAGE_TAG:-}" ]; then
                      printf '%s\n' "$IMAGE_TAG" | grep -Eq '^[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}$'
                      tag="${IMAGE_TAG}-${GIT_COMMIT}"
                    fi
                    printf '%s\n' "$tag" > "$WORKSPACE/.image-tag"
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
                    docker build -t "${ACR_NAME}.azurecr.io/claims-agent:${tag}" .
                  '''
                }
              }
            }
            stage('Push to ACR') {
              steps {
                container('deploy') {
                  sh '''
                    set -eu
                    test -n "${AZURE_CLIENT_ID:-}"
                    test -n "${AZURE_TENANT_ID:-}"
                    test -n "${AZURE_FEDERATED_TOKEN_FILE:-}"
                    test -s "$AZURE_FEDERATED_TOKEN_FILE"
                    tag=$(cat "$WORKSPACE/.image-tag")
                    test -n "$tag"
                    set +x
                    token=$(cat "$AZURE_FEDERATED_TOKEN_FILE")
                    az login --service-principal --username "$AZURE_CLIENT_ID" --tenant "$AZURE_TENANT_ID" --federated-token "$token"
                    unset token
                    set -x
                    az acr login --name "$ACR_NAME"
                    docker push "${ACR_NAME}.azurecr.io/claims-agent:${tag}"
                  '''
                }
              }
            }
            stage('Helm upgrade to AKS') {
              steps {
                container('deploy') {
                  sh '''
                    set -eu
                    printf '%s\n' "$CLAIMS_IDENTITY_CLIENT_ID" | grep -Eq '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
                    printf '%s\n' "$ACR_NAME" | grep -Eq '^[a-z0-9]{5,50}$'
                    printf '%s\n' "$AKS_NAME" | grep -Eq '^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$'
                    printf '%s\n' "$AKS_RESOURCE_GROUP" | grep -Eq '^[A-Za-z0-9._()-]{1,90}$'
                    if [ -n "${AZURE_OPENAI_ENDPOINT:-}" ]; then
                      printf '%s\n' "$AZURE_OPENAI_ENDPOINT" | grep -Eq '^https://[A-Za-z0-9.-]+/?$'
                    fi
                    test -n "${AZURE_CLIENT_ID:-}"
                    test -n "${AZURE_TENANT_ID:-}"
                    test -n "${AZURE_FEDERATED_TOKEN_FILE:-}"
                    test -s "$AZURE_FEDERATED_TOKEN_FILE"
                    tag=$(cat "$WORKSPACE/.image-tag")
                    test -n "$tag"
                    set +x
                    token=$(cat "$AZURE_FEDERATED_TOKEN_FILE")
                    az login --service-principal --username "$AZURE_CLIENT_ID" --tenant "$AZURE_TENANT_ID" --federated-token "$token"
                    unset token
                    set -x
                    az aks install-cli
                    az aks get-credentials --resource-group "$AKS_RESOURCE_GROUP" --name "$AKS_NAME" --overwrite-existing
                    kubelogin convert-kubeconfig -l workloadidentity
                    if ! command -v helm >/dev/null 2>&1; then
                      curl -fsSL -o /tmp/helm.tgz "https://get.helm.sh/helm-v3.16.2-linux-amd64.tar.gz"
                      tar -xzf /tmp/helm.tgz -C /tmp
                      cp /tmp/linux-amd64/helm /usr/local/bin/helm
                      chmod +x /usr/local/bin/helm
                    fi
                    # Values go through a file so a comma in a parameter cannot
                    # become another Helm assignment. env=prod refuses dev
                    # tokens. azurefile-csi is ReadWriteMany so every replica can
                    # mount the checkpoint claim. The namespace is applied by a
                    # cluster admin (deploy/k8s/claims-namespace.yaml); this
                    # identity cannot create it. The chart keeps the labelled
                    # stub until Azure OpenAI works without an API key.
                    {
                      printf 'image:\n  repository: %s.azurecr.io/claims-agent\n  tag: "%s"\n  pullPolicy: Always\n' "$ACR_NAME" "$tag"
                      printf 'env: prod\n'
                      printf 'workloadIdentity:\n  clientId: "%s"\n' "$CLAIMS_IDENTITY_CLIENT_ID"
                      printf 'checkpoints:\n  storageClass: azurefile-csi\n'
                      if [ -n "${AZURE_OPENAI_ENDPOINT:-}" ]; then
                        printf 'model:\n  endpoint: "%s"\n' "$AZURE_OPENAI_ENDPOINT"
                      fi
                    } > /tmp/claims-release.yaml
                    helm upgrade --install claims-agent deploy/helm/claims-agent \
                      --namespace claims \
                      --values /tmp/claims-release.yaml \
                      --wait --timeout 5m
                  '''
                }
              }
            }
          }
        }
      }
    }
  }
}
