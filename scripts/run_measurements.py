"""Run every measurement and write results/metrics.json (or --check it against a fresh run)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import os  # noqa: E402

os.environ["MODEL_PROVIDER"] = "stub"  # committed metrics are always the labelled stub run
from nfclaims.sim import main  # noqa: E402

OUT = ROOT / "results" / "metrics.json"

if __name__ == "__main__":
    fresh = json.dumps(main(), indent=2, sort_keys=True) + "\n"
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text() != fresh:
            sys.exit("results/metrics.json is stale: run python scripts/run_measurements.py")
        print("metrics.json matches a fresh run")
    else:
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(fresh)
        print(fresh)
