# ADR 0004: labelled stub model in CI

Status: accepted. CI must be free, deterministic and keyless. Every stub result carries `model: "stub"`. Live runs use `scripts/live_run.py`, are capped, and write a separate file labelled live.
