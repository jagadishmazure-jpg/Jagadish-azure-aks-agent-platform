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
    flag = JENKINSFILE.find("return params.DEPLOY_TO_AKS")
    assert flag != -1
    assert "defaultValue: false" in JENKINSFILE
    for name in ("Lint", "Pytest", "Eval gate"):
        assert JENKINSFILE.find(f"stage('{name}')") < flag
    for name in ("Docker build", "Push to ACR", "Helm upgrade to AKS"):
        assert JENKINSFILE.find(f"stage('{name}')") > flag


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
    assert "kubelogin convert-kubeconfig -l workloadidentity" in upgrade
    assert "helm upgrade --install claims-agent" in upgrade
    assert "--password" not in JENKINSFILE
    assert "client_secret" not in JENKINSFILE.lower()


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
    assert "azure.workload.identity/use" not in python_tpl[0]["yaml"]


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
    mounts = JENKINS_VALUES["persistence"]["volumes"]
    assert mounts[0]["csi"]["volumeAttributes"]["secretProviderClass"] == "jenkins-keyvault"
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


def test_jenkins_aks_templates_wire_identity_and_key_vault():
    sa = (ROOT / "deploy/helm/jenkins-aks/templates/serviceaccount.yaml").read_text()
    spc = (ROOT / "deploy/helm/jenkins-aks/templates/secretproviderclass.yaml").read_text()
    sync = (ROOT / "deploy/helm/jenkins-aks/templates/secret-sync.yaml").read_text()
    assert "name: jenkins-ci" in sa and "automountServiceAccountToken: false" in sa
    assert "azure.workload.identity/client-id" in sa
    assert 'usePodIdentity: "false"' in spc
    assert "secretName: jenkins-keyvault" in spc
    assert "objectType: secret" in spc
    assert "secretProviderClass: jenkins-keyvault" in sync
    assert 'azure.workload.identity/use: "true"' in sync
    assert "runAsNonRoot: true" in sync
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
    assert 'resource "azurerm_key_vault_secret"' not in TF


def test_ci_lints_the_jenkins_chart_and_upstream_values():
    assert "helm lint deploy/helm/jenkins-aks --namespace jenkins" in CI
    assert "helm template j deploy/helm/jenkins-aks --namespace jenkins" in CI
    assert "helm pull jenkins/jenkins --version 5.13.3" in CI
    assert "helm lint /tmp/jenkins --namespace jenkins -f deploy/jenkins/values.yaml" in CI
    assert "-f deploy/jenkins/values.yaml" in CI
