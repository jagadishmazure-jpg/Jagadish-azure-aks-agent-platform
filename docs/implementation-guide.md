# Implementation guide (for adopters)

1. **Fork and run offline.** `pip install -e ".[dev]" && pytest -q && python scripts/run_measurements.py`.
2. **Swap the domain.** Replace `data.py` (policies, claims) and `Coverage` with your rules. Keep `risk_reasons` explicit and testable.
3. **Pick the model.** `MODEL_PROVIDER=azure` with your deployment. Keep `parse_triage` strict; add fields to the schema and tests together.
4. **Tune the gates.** `AUTO_PAY_LIMIT`, `FRAUD_REVIEW`, the token and dollar cap. Add your own attack and benign texts to `sim.py` and keep both block rate and false-positive rate in CI.
5. **Move checkpoints to a shared store.** Replace `FileCheckpointStorage` with a Postgres-backed storage before running more than one replica on AKS without RWX volumes.
6. **Run kind.** `./deploy/kind/smoke.sh` proves deploy, pod kill and resume.
7. **Provision.** Review the Terraform, fill tfvars, add a backend, plan, get approval, apply.
8. **GitOps.** Point Argo CD at your fork; keep the canary analysis query on a metric you trust.
9. **Evaluate.** Register a Foundry evaluation on recorded, redacted triage outputs before raising the auto-pay limit.
