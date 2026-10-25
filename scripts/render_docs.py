"""Regenerate the numbers block in README.md from results/metrics.json and the real test count.
python scripts/render_docs.py          # rewrite
python scripts/render_docs.py --check  # fail if README is stale (CI)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from count_tests import count  # noqa: E402

START, END = "<!-- numbers:start -->", "<!-- numbers:end -->"


def block() -> str:
    m = json.loads((ROOT / "results" / "metrics.json").read_text())
    c, inj, rb, cost, pii = m["claims_run"], m["injection"], m["rollback_simulated"], m["cost"], m["pii_leaks"]
    base = m["pod_kill_baseline_pod_local_storage"]
    live = ROOT / "results" / "live_metrics.json"
    live_line = (
        "| Live model run | see `results/live_metrics.json` |"
        if live.exists()
        else "| Live model run | **not done**: the provided key had no API credit (HTTP 429 insufficient_quota) |"
    )
    rows = [
        "| Measure (simulated / synthetic, stub model) | Result |",
        "| --- | --- |",
        f"| Automated tests | **{count()}** |",
        f"| Synthetic claims run end to end | {c['claims']} ({', '.join(f'{k} {v}' for k, v in c['outcomes'].items())}) |",
        f"| Paused for a human adjuster | {c['paused_for_adjuster']} of {c['claims']} |",
        f"| Trace continuity after pod kill, shared checkpoints | {c['trace_continuity']:.0%} ({c['finished_on_other_pod']} of {c['paused_for_adjuster']} finished on another pod) |",
        f"| Same test, pod-local disk (baseline) | {base['trace_continuity']:.0%} ({base['finished_on_other_pod']} of {base['paused_for_adjuster']}) |",
        f"| Injection block rate | {inj['block_rate']:.0%} of {inj['attacks']} attacks; false positives {inj['false_positives']} of {inj['benign']} benign |",
        f"| Canary auto-rollback time (simulated, {rb['trials']} bad releases) | p50 {rb['p50_s']} s, p95 {rb['p95_s']} s |",
        f"| Cost per request (stub token estimate x list price as of {cost['prices_as_of']}) | ${cost['per_request_usd']:.6f} (${cost['per_1000_requests_usd']} per 1,000) |",
        f"| Raw PII in outputs / spans / logs+errors | {pii['outputs']} / {pii['spans']} / {pii['logs_and_errors']} |",
        live_line,
    ]
    return START + "\n" + "\n".join(rows) + "\n" + END


def render(text: str) -> str:
    return re.sub(re.escape(START) + ".*?" + re.escape(END), block(), text, flags=re.S)


if __name__ == "__main__":
    p = ROOT / "README.md"
    old = p.read_text()
    new = render(old)
    if "--check" in sys.argv:
        if new != old:
            sys.exit("README numbers are stale: run python scripts/render_docs.py")
        print("README numbers match")
    else:
        p.write_text(new)
        print("README updated")
