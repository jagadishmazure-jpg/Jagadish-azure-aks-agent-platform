"""Live run against a real model (MODEL_PROVIDER=openai or azure). Not used by CI.

Hard cap on model calls (default 120, max 200). Writes results/live_metrics.json labelled "live".
Usage: MODEL_PROVIDER=openai python scripts/live_run.py --max-calls 120
The key is read from the environment only; it is never printed or written.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nfclaims.cost import cost_usd  # noqa: E402
from nfclaims.data import make_claims  # noqa: E402
from nfclaims.service import ClaimsService  # noqa: E402
from nfclaims.workflow import AdjusterDecision  # noqa: E402


async def main(max_calls: int) -> dict:
    shared = tempfile.mkdtemp()
    svc, other = ClaimsService(shared, pod="live-0"), ClaimsService(shared, pod="live-1")
    if svc.model_label == "stub":
        sys.exit("no live provider configured (set MODEL_PROVIDER and a key)")
    calls = errors = 0
    tin = tout = 0
    lat = []
    for c in make_claims(max_calls):
        t0 = time.perf_counter()
        r = await svc.submit(c)
        lat.append(time.perf_counter() - t0)
        calls += 1
        if r["status"] == "awaiting_adjuster":
            r = await other.decide(c.claim_id, AdjusterDecision(True, "live-adj"), r["traceparent"])
        errors += r["status"] == "error"
        tin += r.get("tokens_in", 0)
        tout += r.get("tokens_out", 0)
    lat.sort()
    return {
        "label": "live",
        "model": svc.model_label,
        "run_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "model_calls": calls,
        "errors": errors,
        "tokens_in": tin,
        "tokens_out": tout,
        "cost_usd_list_price": round(cost_usd(tin, tout), 6),
        "latency_p50_s": round(lat[len(lat) // 2], 3),
        "latency_p95_s": round(lat[int(0.95 * len(lat)) - 1], 3),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-calls", type=int, default=120)
    n = min(ap.parse_args().max_calls, 200)
    out = asyncio.run(main(n))
    (ROOT / "results" / "live_metrics.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
