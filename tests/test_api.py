import pytest
from fastapi.testclient import TestClient

from nfclaims import app as appmod
from nfclaims.auth import ROLE_ADJUST, ROLE_SUBMIT, mint_dev_token
from nfclaims.data import make_policies
from nfclaims.service import ClaimsService


@pytest.fixture
def client(tmp_path):
    appmod._svc = ClaimsService(str(tmp_path), pod="api")
    return TestClient(appmod.app)


def body(**kw):
    pol = next(p for p in make_policies().values() if p.active and p.line == "auto" and p.limit >= 50000)
    return {
        "claim_id": "CLM-7",
        "policy_id": pol.policy_id,
        "line": "auto",
        "amount": 700.0,
        "description": "dent",
        "prior_claims": 0,
        **kw,
    }


def h(*roles):
    return {"Authorization": "Bearer " + mint_dev_token("user-1", list(roles))}


def test_health(client):
    assert client.get("/healthz").json()["model"] == "stub"


def test_metrics(client):
    client.post("/claims", json=body(), headers=h(ROLE_SUBMIT))
    assert "nf_claims_total" in client.get("/metrics").text


def test_requires_token(client):
    assert client.post("/claims", json=body()).status_code == 401


def test_requires_role(client):
    assert client.post("/claims", json=body(), headers=h("Other")).status_code == 403


def test_submit_ok_and_traceparent_kept(client):
    tp = "00-" + "a" * 32 + "-" + "b" * 16 + "-01"
    r = client.post("/claims", json=body(), headers={**h(ROLE_SUBMIT), "traceparent": tp}).json()
    assert r["status"] == "auto_paid" and r["traceparent"] == tp


@pytest.mark.parametrize("kw", [{"extra": 1}, {"amount": -1}, {"line": "pet"}, {"claim_id": "x"}, {"description": "x" * 5000}])
def test_schema_rejects(client, kw):
    assert client.post("/claims", json=body(**kw), headers=h(ROLE_SUBMIT)).status_code == 422


def test_adjuster_flow_needs_adjust_role(client):
    r = client.post("/claims", json=body(amount=40000.0), headers=h(ROLE_SUBMIT)).json()
    assert r["status"] == "awaiting_adjuster"
    assert client.post("/claims/CLM-7/decision", json={"approved": True}, headers=h(ROLE_SUBMIT)).status_code == 403
    d = client.post("/claims/CLM-7/decision", json={"approved": True}, headers={**h(ROLE_ADJUST), "traceparent": r["traceparent"]}).json()
    assert d["status"] == "paid_after_review" and d["adjuster"] == "user-1"
