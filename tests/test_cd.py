"""GitHub Actions is the Azure deploy path. Jenkins is not part of this repo."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"
CD = (WF / "cd.yml").read_text()
DEPLOY = (WF / "azure-deploy.yml").read_text()
TF = (ROOT / "infra" / "terraform" / "main.tf").read_text()
TEXT = {".py", ".md", ".yml", ".yaml", ".tf", ".txt"}


def test_actionlint_clean():
    exe = shutil.which("actionlint")
    if exe is None:
        if os.environ.get("CI"):
            raise AssertionError("actionlint is installed in CI before pytest")
        pytest.skip("actionlint is not on PATH; CI installs it and runs this test")
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
    assert "workflow_dispatch" in CD and "workflow_run" in CD
    assert "branches: [main]" in CD
    assert "cancel-in-progress: false" in CD
    assert "group: azure-cd-claims-agent" in CD
    assert "Azure CD skipped. Repository variables are unset" in CD
    assert "ready=false" in CD
    assert "needs.gate.outputs.ready == 'true'" in CD
    assert "CD only runs from main" in CD
    assert "CI checks failed or were cancelled" in CD
    assert "claims-dev" in CD and 'namespace="claims"' in CD
    for name in (
        "AZURE_CLIENT_ID_DEV",
        "AZURE_CLIENT_ID_PROD",
        "AZURE_TENANT_ID",
        "AZURE_SUBSCRIPTION_ID",
        "ACR_NAME",
        "AKS_NAME",
        "AKS_RESOURCE_GROUP",
    ):
        assert name in CD


def test_prod_promotes_the_same_sha_without_a_rebuild():
    assert 'push_image="false"' in CD
    assert "prod promotes an image already deployed to dev" in CD
    assert "push_image: ${{ needs.gate.outputs.push_image == 'true' }}" in CD
    loaded = yaml.safe_load(DEPLOY)
    inputs = loaded[True]["workflow_call"]["inputs"]
    assert inputs["push_image"]["type"] == "boolean"
    assert inputs["image_sha"]["required"] is True
    assert "docker build" not in DEPLOY
    assert "docker pull" in DEPLOY
    assert "if: inputs.push_image" in DEPLOY
    assert "if: ${{ !inputs.push_image }}" in DEPLOY
    assert "Refusing to overwrite" in DEPLOY
    assert "No successful dev deployment" in DEPLOY


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
    assert "NAMESPACE: ${{ inputs.namespace }}" in DEPLOY
    assert '--namespace "$NAMESPACE"' in DEPLOY
    assert "--create-namespace" not in DEPLOY
    assert "--set" not in DEPLOY
    assert "printf 'env:" not in DEPLOY
    assert "APP_ENV=prod rejects every" in DEPLOY
    assert "HELM_DRIVER=configmap" in DEPLOY
    assert "cosign verify" in DEPLOY
    assert "cosign sign --yes" in DEPLOY
    assert 'az acr repository update --name "$ACR_NAME" --image "claims-agent:${IMAGE_SHA}" --write-enabled false' in DEPLOY
    assert "CLAIMS_DEV_IDENTITY_CLIENT_ID" in DEPLOY
    assert "inputs.environment == 'prod' && vars.CLAIMS_IDENTITY_CLIENT_ID || vars.CLAIMS_DEV_IDENTITY_CLIENT_ID" in DEPLOY
    assert "rollout did not become Healthy" in DEPLOY
    assert "status.phase" in DEPLOY
    assert "azurefile-csi" in DEPLOY
    assert "creds:" not in DEPLOY
    assert "client_secret" not in DEPLOY.lower()
    assert "--password " not in DEPLOY
    assert "password-stdin" in DEPLOY
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
    assert 'resource "azurerm_user_assigned_identity" "gha_dev"' in TF
    assert 'resource "azurerm_user_assigned_identity" "gha_prod"' in TF
    assert "repo:${var.github_repository}:environment:dev" in TF
    assert "repo:${var.github_repository}:environment:prod" in TF
    issuers = [line.split("=", 1)[1].strip().strip('"') for line in TF.splitlines() if line.strip().startswith("issuer") and '"' in line]
    assert issuers == ["https://token.actions.githubusercontent.com", "https://token.actions.githubusercontent.com"]
    assert "AcrPush" in TF and "AcrPull" in TF
    assert "Azure Kubernetes Service Cluster User Role" in TF
    assert "Azure Kubernetes Service RBAC Writer" in TF
    assert "${azurerm_kubernetes_cluster.aks.id}/namespaces/claims-dev" in TF
    assert '${azurerm_kubernetes_cluster.aks.id}/namespaces/claims"' in TF
    assert "azurerm_key_vault_secret" not in TF
    assert 'resource "azurerm_user_assigned_identity" "claims_dev"' in TF
    assert "system:serviceaccount:claims-dev:claims-agent" in TF
    assert "system:serviceaccount:claims:claims-agent" in TF
    assert "Premium SKU" in TF and "write-enabled false" in TF


def test_cd_gate_waits_for_ci_and_rejects_failures(tmp_path: Path):
    def run(payload: dict) -> str:
        path = tmp_path / "checks.json"
        path.write_text(json.dumps(payload))
        out = subprocess.run(  # noqa: S603
            [sys.executable, str(ROOT / "scripts" / "cd_gate.py"), "checks", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
        return out.stdout.strip()

    assert run({"check_runs": []}) == "wait"
    names = ("test", "helm", "secrets", "validate", "build-scan-kind", "sign", "analyze (python)")
    runs = [{"name": name, "status": "completed", "conclusion": "success"} for name in names]
    assert run({"check_runs": runs}) == "ready"
    runs[0]["conclusion"] = "failure"
    assert run({"check_runs": runs}) == "fail"


def test_argocd_does_not_auto_sync():
    app = yaml.safe_load((ROOT / "deploy/argocd/application.yaml").read_text())
    assert app["spec"]["source"]["path"] == "deploy/helm/claims-agent"
    assert "automated" not in app["spec"].get("syncPolicy", {})
