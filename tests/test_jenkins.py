"""Jenkinsfile structure and the Jenkins-on-AKS config. No cluster, no secret values."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
JENKINSFILE = (ROOT / "Jenkinsfile").read_text()
JENKINS_VALUES = yaml.safe_load((ROOT / "deploy/jenkins/values.yaml").read_text())
AKS_VALUES = yaml.safe_load((ROOT / "deploy/helm/jenkins-aks/values.yaml").read_text())
TF = (ROOT / "infra/terraform/main.tf").read_text()
CI = (ROOT / ".github/workflows/ci.yml").read_text()

STAGES = (
    "Lint",
    "Pytest",
    "Eval gate",
    "Release",
    "Approve release",
    "Ship",
    "Docker build",
    "Push to ACR",
    "Helm upgrade to AKS",
)


def _slice(text: str, start: str, end: str | None) -> str:
    i = text.find(start)
    assert i != -1, start
    if end is None:
        return text[i:]
    j = text.find(end, i + len(start))
    assert j != -1, end
    return text[i:j]


def test_jenkinsfile_is_declarative_and_stages_are_ordered():
    assert "pipeline {" in JENKINSFILE
    assert "agent none" in JENKINSFILE
    assert "node {" not in JENKINSFILE
    names = re.findall(r"stage\('([^']+)'\)", JENKINSFILE)
    assert names == list(STAGES)


def test_deploy_stages_are_behind_the_flag():
    release = _slice(JENKINSFILE, "stage('Release')", "stage('Approve release')")
    gate = _slice(JENKINSFILE, "stage('Eval gate')", "stage('Release')")
    assert "beforeAgent true" in release
    assert "return params.DEPLOY_TO_AKS" in release
    assert "BRANCH_NAME == 'main'" in release
    assert "DEPLOY_TO_AKS" not in gate
    assert "defaultValue: false" in JENKINSFILE
    approve = _slice(JENKINSFILE, "stage('Approve release')", "stage('Ship')")
    assert "input message:" in approve
    ship = _slice(JENKINSFILE, "stage('Ship')", "stage('Docker build')")
    assert "label 'release'" in ship


def test_lint_pytest_and_eval_gate_call_the_ci_commands():
    lint = _slice(JENKINSFILE, "stage('Lint')", "stage('Pytest')")
    pytest_stage = _slice(JENKINSFILE, "stage('Pytest')", "stage('Eval gate')")
    gate = _slice(JENKINSFILE, "stage('Eval gate')", "stage('Release')")
    assert "ruff check ." in lint and "ruff format --check ." in lint
    assert "python scripts/check_brands.py" in lint
    assert "helm lint deploy/helm/jenkins-aks --namespace jenkins" in lint
    assert "terraform validate" in lint
    assert "pytest -q" in pytest_stage
    assert "python scripts/run_measurements.py --check" in gate
    assert "python scripts/render_docs.py --check" in gate
    assert "docker build" not in gate


def test_release_stages_build_push_and_upgrade_without_a_password():
    build = _slice(JENKINSFILE, "stage('Docker build')", "stage('Push to ACR')")
    push = _slice(JENKINSFILE, "stage('Push to ACR')", "stage('Helm upgrade to AKS')")
    upgrade = _slice(JENKINSFILE, "stage('Helm upgrade to AKS')", None)
    assert "docker build -t" in build
    assert "az acr login --name" in push and "docker push" in push
    assert "az login --service-principal" in push
    assert "--federated-token" in push
    assert 'token=$(cat "$AZURE_FEDERATED_TOKEN_FILE")' in push
    assert "set +x" in push
    for line in JENKINSFILE.splitlines():
        if "federated-token" in line:
            assert "cat" not in line and "$token" in line
    assert "kubelogin convert-kubeconfig -l workloadidentity" in upgrade
    assert "helm upgrade --install claims-agent" in upgrade
    assert "--values /tmp/claims-release.yaml" in upgrade
    assert "--wait --timeout 5m" in upgrade
    assert "--set" not in upgrade
    assert "--create-namespace" not in upgrade
    assert "env: prod" in upgrade
    assert "azurefile-csi" in upgrade
    assert "--password" not in JENKINSFILE
    assert "client_secret" not in JENKINSFILE.lower()
    assert "set -o pipefail" not in JENKINSFILE


def test_pod_templates_split_ci_from_the_release_identity():
    python_tpl = yaml.safe_load(JENKINS_VALUES["agent"]["podTemplates"]["python"])
    release_tpl = yaml.safe_load(JENKINS_VALUES["agent"]["podTemplates"]["release"])
    assert python_tpl[0]["label"] == "python"
    assert python_tpl[0]["serviceAccount"] == "jenkins-ci"
    assert all(c["privileged"] is False for c in python_tpl[0]["containers"])
    assert {c["name"] for c in python_tpl[0]["containers"]} == {"python", "helm", "terraform"}
    assert release_tpl[0]["label"] == "release"
    assert release_tpl[0]["serviceAccount"] == "jenkins-release"
    privileged = [c["name"] for c in release_tpl[0]["containers"] if c.get("privileged")]
    assert privileged == ["dind"]
    assert "azure.workload.identity/use" in release_tpl[0]["yaml"]
    assert "jenkins.io/release" in release_tpl[0]["yaml"]
    assert "azure.workload.identity/use" not in python_tpl[0]["yaml"]
    dind = next(c for c in release_tpl[0]["containers"] if c["name"] == "dind")
    assert dind["args"] == "--host=tcp://127.0.0.1:2375"


def test_jenkins_values_use_the_key_vault_secret_and_no_admin_password():
    admin = JENKINS_VALUES["controller"]["admin"]
    assert admin["createSecret"] is False
    assert admin["existingSecret"] == "jenkins-keyvault"
    assert admin["userKey"] == "jenkins-admin-user"
    assert admin["passwordKey"] == "jenkins-admin-password"
    assert "password" not in admin
    assert "username" not in admin
    assert JENKINS_VALUES["serviceAccount"]["create"] is False
    assert JENKINS_VALUES["serviceAccount"]["name"] == "jenkins"
    assert JENKINS_VALUES["serviceAccountAgent"]["name"] == "jenkins-release"
    assert JENKINS_VALUES["controller"]["JCasC"]["defaultConfig"] is True
    assert JENKINS_VALUES["controller"]["numExecutors"] == 0
    assert "volumes" not in JENKINS_VALUES["persistence"]
    blob = yaml.safe_dump(JENKINS_VALUES)
    assert "sk-" not in blob
    assert not re.search(r"password:\s*\S", blob)


def test_jenkins_aks_values_hold_names_only():
    assert AKS_VALUES["workloadIdentity"]["clientId"] == ""
    assert AKS_VALUES["workloadIdentity"]["agentClientId"] == ""
    assert AKS_VALUES["keyVault"]["name"] == ""
    assert AKS_VALUES["keyVault"]["tenantId"] == ""
    assert AKS_VALUES["secretNames"] == {
        "adminUser": "jenkins-admin-user",
        "adminPassword": "jenkins-admin-password",
    }


def _sa_blocks() -> dict[str, str]:
    text = (ROOT / "deploy/helm/jenkins-aks/templates/serviceaccount.yaml").read_text()
    blocks = {}
    for chunk in text.split("---"):
        match = re.search(r"^  name: (\S+)\s*$", chunk, re.M)
        if match:
            blocks[match.group(1)] = chunk
    return blocks


def test_jenkins_aks_templates_wire_identity_and_key_vault():
    blocks = _sa_blocks()
    assert "workloadIdentity.clientId" in blocks["jenkins"]
    assert "azure.workload.identity/client-id" in blocks["jenkins"]
    assert "workloadIdentity.agentClientId" in blocks["jenkins-release"]
    assert "azure.workload.identity/client-id" in blocks["jenkins-release"]
    assert "client-id" not in blocks["jenkins-ci"]
    assert "automountServiceAccountToken: false" in blocks["jenkins-ci"]
    spc = (ROOT / "deploy/helm/jenkins-aks/templates/secretproviderclass.yaml").read_text()
    sync = (ROOT / "deploy/helm/jenkins-aks/templates/secret-sync.yaml").read_text()
    policy = (ROOT / "deploy/helm/jenkins-aks/templates/networkpolicy.yaml").read_text()
    assert 'usePodIdentity: "false"' in spc
    assert "secretName: jenkins-keyvault" in spc
    assert "objectType: secret" in spc
    assert "secretProviderClass: jenkins-keyvault" in sync
    assert 'azure.workload.identity/use: "true"' in sync
    assert "runAsNonRoot: true" in sync
    assert 'jenkins.io/release: "true"' in policy
    assert "ingress: []" in policy
    rendered = "\n".join(p.read_text() for p in (ROOT / "deploy/helm/jenkins-aks").rglob("*.yaml"))
    assert "sk-" not in rendered
    assert not re.search(r"(?i)password:\s*['\"][^'\"]+['\"]", rendered)


def test_terraform_jenkins_identity_has_no_secret_resource():
    assert 'resource "azurerm_user_assigned_identity" "jenkins_controller"' in TF
    assert 'resource "azurerm_user_assigned_identity" "jenkins_agent"' in TF
    assert "system:serviceaccount:jenkins:jenkins" in TF
    assert "system:serviceaccount:jenkins:jenkins-release" in TF
    assert "AcrPush" in TF
    assert "Azure Kubernetes Service Cluster User Role" in TF
    assert "Azure Kubernetes Service RBAC Writer" in TF
    assert "${azurerm_kubernetes_cluster.aks.id}/namespaces/claims" in TF
    assert "${azurerm_key_vault.kv.id}/secrets/jenkins-admin-user" in TF
    assert "${azurerm_key_vault.kv.id}/secrets/jenkins-admin-password" in TF
    assert "var.jenkins_secret_scopes" in TF
    assert 'resource "azurerm_key_vault_secret"' not in TF


def test_ci_lints_the_jenkins_chart_and_upstream_values():
    assert "helm lint deploy/helm/jenkins-aks --namespace jenkins" in CI
    assert "helm template j deploy/helm/jenkins-aks --namespace jenkins" in CI
    assert "helm pull jenkins/jenkins --version 5.13.3" in CI
    assert "helm lint /tmp/jenkins --namespace jenkins -f deploy/jenkins/values.yaml" in CI
    assert "-f deploy/jenkins/values.yaml" in CI
