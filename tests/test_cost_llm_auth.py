import asyncio
import json
import time

import pytest

from nfclaims import auth
from nfclaims.cost import BudgetExceeded, TokenBudget, cost_usd, estimate_tokens
from nfclaims.llm import ENV_VARS, StubChatClient, live_configured, make_client, parse_triage, pick_provider


def test_cost_math():
    assert cost_usd(1_000_000, 0) == pytest.approx(0.15) and cost_usd(0, 1_000_000) == pytest.approx(0.60)


def test_estimate_tokens_min_one():
    assert estimate_tokens("") == 1 and estimate_tokens("a" * 40) == 10


def test_budget_token_cap():
    b = TokenBudget(max_tokens=100)
    b.charge(50, 40)
    with pytest.raises(BudgetExceeded):
        b.charge(10, 1)


def test_budget_usd_cap():
    with pytest.raises(BudgetExceeded):
        TokenBudget(max_tokens=10**9, max_usd=0.0001).charge(1000, 1000)


def test_env_detection():
    assert not live_configured({})
    assert live_configured(dict.fromkeys(ENV_VARS, "x"))
    assert not live_configured({**dict.fromkeys(ENV_VARS, "x"), "AZURE_OPENAI_API_KEY": ""})


def test_make_client_falls_back_to_stub():
    c, label = make_client({"MODEL_PROVIDER": ""})
    assert isinstance(c, StubChatClient) and label == "stub"


def test_make_client_live_shape():
    c, label = make_client(
        {
            "AZURE_OPENAI_ENDPOINT": "https://nf-example.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "dummy",
            "AZURE_OPENAI_DEPLOYMENT": "gpt-4o-mini",
            "AZURE_OPENAI_API_VERSION": "2024-10-21",
        }
    )
    assert label == "azure-openai:gpt-4o-mini" and not isinstance(c, StubChatClient)


@pytest.mark.parametrize("amount,sev", [(100, "low"), (5000, "medium"), (25000, "high")])
def test_stub_severity(amount, sev):
    from agent_framework import Message

    r = asyncio.run(StubChatClient().get_response([Message("user", [f"amount={amount} prior_claims=0"])]))
    assert parse_triage(r.text)["severity"] == sev and r.usage_details["input_token_count"] > 0


@pytest.mark.parametrize(
    "bad",
    [
        "no json",
        '{"severity":"low"}',
        '{"severity":"huge","fraud_score":0.1,"summary":""}',
        '{"severity":"low","fraud_score":2,"summary":""}',
        '{"severity":"low","fraud_score":NaN,"summary":""}',
        '{"severity":"low","fraud_score":0.1,"summary":"","extra":1}',
    ],
)
def test_parse_triage_rejects(bad):
    with pytest.raises(ValueError):
        parse_triage(bad)


def test_parse_triage_ok():
    assert parse_triage('x {"severity":"low","fraud_score":0.2,"summary":"ok"} y')["fraud_score"] == 0.2


def _claims(**kw):
    return {"iss": auth.ISSUER, "aud": auth.AUDIENCE, "exp": time.time() + 60, "roles": [auth.ROLE_SUBMIT], **kw}


def test_token_roundtrip():
    assert auth.verify(auth.mint_dev_token("u1", [auth.ROLE_SUBMIT]), auth.ROLE_SUBMIT)["sub"] == "u1"


@pytest.mark.parametrize("kw,msg", [({"iss": "x"}, "issuer"), ({"aud": "x"}, "audience"), ({"exp": 1}, "expired"), ({"roles": []}, "role")])
def test_claim_checks(kw, msg):
    with pytest.raises(auth.AuthError, match=msg):
        auth.check_claims(_claims(**kw), auth.ROLE_SUBMIT)


def test_tampered_signature():
    t = auth.mint_dev_token("u1", [auth.ROLE_SUBMIT])
    h, b, s = t.split(".")
    body = json.loads(auth._unb64(b))
    body["roles"].append(auth.ROLE_ADJUST)
    forged = f"{h}.{auth._b64(json.dumps(body).encode())}.{s}"
    with pytest.raises(auth.AuthError, match="signature"):
        auth.verify(forged, auth.ROLE_ADJUST)


def test_alg_none_rejected():
    none = auth._b64(b'{"alg":"none"}') + "." + auth._b64(json.dumps(_claims()).encode()) + "."
    with pytest.raises(auth.AuthError):
        auth.verify(none, auth.ROLE_SUBMIT)


def test_malformed():
    with pytest.raises(auth.AuthError):
        auth.verify("abc", auth.ROLE_SUBMIT)


def test_prod_refuses_dev_tokens(monkeypatch):
    t = auth.mint_dev_token("u1", [auth.ROLE_SUBMIT])
    monkeypatch.setenv("APP_ENV", "prod")
    with pytest.raises(auth.AuthError, match="prod"):
        auth.verify(t, auth.ROLE_SUBMIT)


def test_short_key_refused(monkeypatch):
    monkeypatch.setenv("DEV_TOKEN_KEY", "short")
    with pytest.raises(auth.AuthError):
        auth.mint_dev_token("u", [])


@pytest.mark.parametrize(
    "env,want",
    [
        ({}, "stub"),
        ({"AZURE_OPENAI_API_KEY": "k"}, "openai"),
        ({"OPENAI_API_KEY": "k"}, "openai"),
        (dict.fromkeys(ENV_VARS, "x"), "azure"),
        ({"MODEL_PROVIDER": "stub", "OPENAI_API_KEY": "k"}, "stub"),
        ({"MODEL_PROVIDER": "AZURE"}, "azure"),
    ],
)
def test_pick_provider(env, want):
    assert pick_provider(env) == want


def test_openai_client_label():
    c, label = make_client({"MODEL_PROVIDER": "openai", "AZURE_OPENAI_API_KEY": "dummy"})
    assert label == "openai:gpt-4o-mini" and not isinstance(c, StubChatClient)


def test_azure_requires_all_vars():
    with pytest.raises(RuntimeError, match="AZURE_OPENAI_ENDPOINT"):
        make_client({"MODEL_PROVIDER": "azure", "AZURE_OPENAI_API_KEY": "k"})


def test_openai_requires_key():
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        make_client({"MODEL_PROVIDER": "openai"})
