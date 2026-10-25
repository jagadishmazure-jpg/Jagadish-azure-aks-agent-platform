import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WF = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
TF = (ROOT / "infra" / "terraform" / "main.tf").read_text()
ROLL = (ROOT / "deploy" / "helm" / "claims-agent" / "templates" / "rollout.yaml").read_text()
VALUES = yaml.safe_load((ROOT / "deploy" / "helm" / "claims-agent" / "values.yaml").read_text())


@pytest.mark.parametrize("wf", WF, ids=lambda p: p.name)
def test_actions_pinned_to_sha(wf):
    for line in wf.read_text().splitlines():
        m = re.search(r"uses:\s*([^\s#]+)", line)
        if m:
            assert re.search(r"@[0-9a-f]{40}$", m.group(1)), line


@pytest.mark.parametrize("wf", WF, ids=lambda p: p.name)
def test_workflows_parse_and_have_permissions(wf):
    assert "permissions" in yaml.safe_load(wf.read_text())


def test_no_apply_or_plan_in_ci():
    text = "\n".join(w.read_text() for w in WF)
    assert "terraform apply" not in text and "terraform plan" not in text and "azure/login" not in text


def test_ci_has_no_model_key():
    text = "\n".join(w.read_text() for w in WF)
    assert "OPENAI_API_KEY" not in text


def test_cosign_keyless():
    c = (ROOT / ".github/workflows/container.yml").read_text()
    assert "cosign sign --yes" in c and "id-token: write" in c and "--key" not in c


def test_trivy_gate():
    assert 'exit-code: "1"' in (ROOT / ".github/workflows/container.yml").read_text()


@pytest.mark.parametrize(
    "resource",
    [
        "azurerm_kubernetes_cluster",
        "azurerm_container_registry",
        "azurerm_key_vault",
        "azurerm_federated_identity_credential",
        "azurerm_servicebus_namespace",
        "azurerm_postgresql_flexible_server",
        "azurerm_cognitive_deployment",
        "azurerm_ai_foundry",
        "azurerm_ai_foundry_project",
        "azurerm_cdn_frontdoor_firewall_policy",
        "azurerm_log_analytics_workspace",
        "azurerm_monitor_workspace",
        "azurerm_consumption_budget_resource_group",
    ],
)
def test_terraform_has(resource):
    assert f'resource "{resource}"' in TF


@pytest.mark.parametrize(
    "pattern",
    [
        r"workload_identity_enabled\s*=\s*true",
        r"local_account_disabled\s*=\s*true",
        r"admin_enabled\s*=\s*false",
        r"rbac_authorization_enabled\s*=\s*true",
        r"password_auth_enabled\s*=\s*false",
        r'value\s*=\s*"VECTOR"',
        r'mode\s*=\s*"Prevention"',
    ],
)
def test_terraform_hardening(pattern):
    assert re.search(pattern, TF)


def test_local_auth_off_for_aoai_and_sb():
    assert len(re.findall(r"local_auth_enabled\s*=\s*false", TF)) >= 2


def test_no_kafka_or_second_search_engine():
    assert "kafka" not in TF.lower() and "opensearch" not in TF.lower()


def test_values_hold_no_secret():
    assert VALUES["model"]["keySecretName"] == "" and "sk-" not in yaml.safe_dump(VALUES)


@pytest.mark.parametrize(
    "needle", ["runAsNonRoot: true", "readOnlyRootFilesystem: true", "drop: [ALL]", "allowPrivilegeEscalation: false", "RuntimeDefault"]
)
def test_pod_hardening(needle):
    assert needle in ROLL


def test_canary_matches_simulation_params():
    a = (ROOT / "deploy/helm/claims-agent/templates/analysis.yaml").read_text()
    assert "interval: 30s" in a and "failureLimit: 2" in a


def test_argocd_points_at_chart():
    app = yaml.safe_load((ROOT / "deploy/argocd/application.yaml").read_text())
    assert app["spec"]["source"]["path"] == "deploy/helm/claims-agent" and app["spec"]["syncPolicy"]["automated"]["selfHeal"]


def test_dashboard_queries_real_metrics():
    d = json.loads((ROOT / "dashboards/claims-agents.json").read_text())
    exprs = " ".join(t["expr"] for p in d["panels"] for t in p["targets"])
    for m in ("nf_claims_total", "nf_injection_blocked_total", "nf_model_tokens_total", "nf_claim_seconds_bucket"):
        assert m in exprs


def test_env_example_has_empty_secrets():
    env = (ROOT / ".env.example").read_text()
    assert re.search(r"^AZURE_OPENAI_API_KEY=$", env, re.M) and re.search(r"^OPENAI_API_KEY=$", env, re.M)


def test_gitignore_env():
    assert ".env" in (ROOT / ".gitignore").read_text().split()
