"""Tiny client for deploy/kind/smoke.sh. Usage: smoke_client.py <dev-key> submit|decide"""

import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ["DEV_TOKEN_KEY"] = sys.argv[1]
from nfclaims.auth import ROLE_ADJUST, ROLE_SUBMIT, mint_dev_token  # noqa: E402
from nfclaims.data import make_policies  # noqa: E402

TP = "00-" + "c" * 32 + "-" + "d" * 16 + "-01"
URL = "http://127.0.0.1:8080"


def post(path, body, role):
    req = urllib.request.Request(
        URL + path,
        json.dumps(body).encode(),
        {"Content-Type": "application/json", "traceparent": TP, "Authorization": "Bearer " + mint_dev_token("smoke", [role])},
    )
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


if sys.argv[2] == "submit":
    pol = next(p for p in make_policies().values() if p.active and p.line == "auto" and p.limit >= 50000)
    r = post(
        "/claims",
        {
            "claim_id": "CLM-42",
            "policy_id": pol.policy_id,
            "line": "auto",
            "amount": 30000,
            "description": "Collision on the highway.",
            "prior_claims": 0,
        },
        ROLE_SUBMIT,
    )
    print(r)
    assert r["status"] == "awaiting_adjuster", r
else:
    r = post("/claims/CLM-42/decision", {"approved": True}, ROLE_ADJUST)
    print(r)
    assert r["status"] == "paid_after_review" and r["traceparent"] == TP, r
print("smoke ok")
