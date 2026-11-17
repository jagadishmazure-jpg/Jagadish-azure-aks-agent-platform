"""Pure helpers for the Azure CD gate. No network.

python scripts/cd_gate.py checks checks.json     -> ready | wait | fail
python scripts/cd_gate.py deployment-ids deps.json
python scripts/cd_gate.py statuses-ok statuses.json
"""

from __future__ import annotations

import json
import sys
from typing import Any

REQUIRED = ("test", "helm", "secrets", "validate", "build-scan-kind", "sign")
BAD = {"failure", "cancelled", "timed_out", "startup_failure", "action_required"}
SKIP_NAMES = {"gate", "deploy"}


def _state(run: dict[str, Any]) -> str:
    if run.get("status") != "completed":
        return "pending"
    return run.get("conclusion") or "pending"


def decide(payload: dict[str, Any]) -> str:
    by: dict[str, str] = {}
    for run in payload.get("check_runs", []):
        name = run.get("name") or ""
        if name in SKIP_NAMES:
            continue
        by[name] = _state(run)
    for name in REQUIRED:
        state = by.get(name, "pending")
        if state in BAD:
            return "fail"
        if state != "success":
            return "wait"
    analyzes = [state for name, state in by.items() if name.startswith("analyze")]
    if not analyzes:
        return "wait"
    for state in analyzes:
        if state in BAD:
            return "fail"
        if state != "success":
            return "wait"
    return "ready"


def deployment_ids(payload: list[dict[str, Any]] | dict[str, Any]) -> list[int]:
    rows = payload if isinstance(payload, list) else payload.get("deployments", [])
    return [int(row["id"]) for row in rows if "id" in row]


def statuses_ok(payload: list[dict[str, Any]] | dict[str, Any]) -> bool:
    rows = payload if isinstance(payload, list) else payload.get("statuses", [])
    return any(row.get("state") == "success" for row in rows)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: cd_gate.py checks|deployment-ids|statuses-ok FILE", file=sys.stderr)
        return 2
    command, path = argv[1], argv[2]
    with open(path, encoding="utf-8") as handle:
        payload = json.loads(handle.read())
    if command == "checks":
        print(decide(payload))
        return 0
    if command == "deployment-ids":
        for item in deployment_ids(payload):
            print(item)
        return 0
    if command == "statuses-ok":
        return 0 if statuses_ok(payload) else 1
    print("unknown command", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
