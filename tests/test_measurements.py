import json
from pathlib import Path

from nfclaims.sim import log_leaks, pii_leaks, simulate_rollback

ROOT = Path(__file__).resolve().parents[1]
M = json.loads((ROOT / "results" / "metrics.json").read_text())


def test_rollback_sim_deterministic():
    assert simulate_rollback() == simulate_rollback()


def test_rollback_lower_bound():
    r = simulate_rollback(p_detect=1.0)
    assert r["p50_s"] >= 30 + 12  # at least one full interval plus abort


def test_pii_leak_counter():
    assert pii_leaks(["a@b.com", "ok"]) == 1


def test_log_leaks_zero():
    assert log_leaks() == 0


def test_committed_metrics_safety_bars():
    assert M["injection"]["block_rate"] == 1.0
    assert M["injection"]["false_positives"] == 0
    assert all(v == 0 for v in M["pii_leaks"].values())
    assert M["claims_run"]["trace_continuity"] == 1.0
    assert M["pod_kill_baseline_pod_local_storage"]["finished_on_other_pod"] == 0
    assert M["cost"]["model"] == "stub" or M["cost"]["model"].startswith("azure-openai")


def test_label_says_simulated():
    assert "simulated" in M["label"]
