"""GitHub Actions is the Azure deploy path. Jenkins is not part of this repo."""

import shutil
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"
CD = (WF / "cd.yml").read_text()
DEPLOY = (WF / "azure-deploy.yml").read_text()
TF = (ROOT / "infra" / "terraform" / "main.tf").read_text()
TEXT = {".py", ".md", ".yml", ".yaml", ".tf", ".txt"}


def test_actionlint_clean():
    exe = shutil.which("actionlint")
    assert exe, "actionlint is installed in CI before pytest"
    subprocess.run([exe], cwd=ROOT, check=True)  # noqa: S603


def test_no_jenkins_files():
    assert not (ROOT / "Jenkinsfile").exists()
    assert not (ROOT / "deploy" / "jenkins").exists()
    assert not (ROOT / "deploy" / "helm" / "jenkins-aks").exists()
    assert "jenkins_secret_scopes" not in (ROOT / "infra" / "terraform" / "variables.tf").read_text()


def test_no_jenkins_references():
    needle = "jen" + "kins"
    skip = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
    hits = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT:
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        if any(part in skip or part.endswith(".egg-info") for part in path.parts):
            continue
        if needle in path.read_text(errors="ignore").lower():
            hits.append(str(path.relative_to(ROOT)))
    assert hits == []


def test_cd_skips_when_azure_vars_are_unset():
    assert "workflow_dispatch" in CD and "branches: [main]" in CD
    assert "cancel-in-progress: false" in CD
    assert "azure-cd-${{ github.event.inputs.environment || 'dev' }}" in CD
    assert "Azure CD skipped. Repository variables are unset" in CD
    assert "ready=false" in CD
    assert "needs.gate.outputs.ready == 'true'" in CD
    for name in ("AZURE_CLIENT_ID", "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID", "ACR_NAME", "AKS_NAME", "AKS_RESOURCE_GROUP"):
        assert name in CD
    assert "prod promotes an image already in ACR" in CD


def test_prod_promotes_the_same_sha_without_a_rebuild():
    assert "push_image=false" in CD
    assert "prod promotes an image already in ACR" in CD
    assert "push_image: ${{ needs.gate.outputs.push_image == 'true' }}" in CD
    loaded = yaml.safe_load(DEPLOY)
    inputs = loaded[True]["workflow_call"]["inputs"]
    assert inputs["push_image"]["type"] == "boolean"
    assert inputs["image_sha"]["required"] is True
    assert "if: inputs.push_image" in DEPLOY
    assert "if: ${{ !inputs.push_image }}" in DEPLOY
    assert "az acr repository show" in DEPLOY


def test_deploy_uses_oidc_and_a_values_file():
    assert "azure/login@" in DEPLOY
    assert "Azure/use-kubelogin@" in DEPLOY
    assert "azure/aks-set-context@" in DEPLOY
    assert 'admin: "false"' in DEPLOY
    assert 'use-kubelogin: "true"' in DEPLOY
    assert "id-token: write" in DEPLOY
    assert "environment: ${{ inputs.environment }}" in DEPLOY
    assert "--values /tmp/claims-release.yaml" in DEPLOY
    assert "--wait --timeout 5m" in DEPLOY
    assert "--namespace claims" in DEPLOY
    assert "--create-namespace" not in DEPLOY
    assert "--set" not in DEPLOY
    assert "env: prod" in DEPLOY
    assert "azurefile-csi" in DEPLOY
    assert "creds:" not in DEPLOY
    assert "client_secret" not in DEPLOY.lower()
    assert "--password" not in DEPLOY
    assert "OPENAI_API_KEY" not in DEPLOY


def test_azure_login_is_only_on_the_deploy_workflow():
    for path in (ROOT / ".github" / "workflows").glob("*.yml"):
        text = path.read_text()
        if path.name == "azure-deploy.yml":
            assert "azure/login@" in text
        else:
            assert "azure/login" not in text
        assert "terraform apply" not in text and "terraform plan" not in text


def test_github_oidc_identity_is_least_privilege():
    assert 'resource "azurerm_user_assigned_identity" "gha_deploy"' in TF
    assert "repo:${var.github_repository}:environment:dev" in TF
    assert "repo:${var.github_repository}:environment:prod" in TF
    assert "https://token.actions.githubusercontent.com" in TF
    assert "AcrPush" in TF
    assert "Azure Kubernetes Service Cluster User Role" in TF
    assert "Azure Kubernetes Service RBAC Writer" in TF
    assert "${azurerm_kubernetes_cluster.aks.id}/namespaces/claims" in TF
    assert "azurerm_key_vault_secret" not in TF


def test_argocd_does_not_auto_sync():
    app = yaml.safe_load((ROOT / "deploy/argocd/application.yaml").read_text())
    assert app["spec"]["source"]["path"] == "deploy/helm/claims-agent"
    assert "automated" not in app["spec"].get("syncPolicy", {})
