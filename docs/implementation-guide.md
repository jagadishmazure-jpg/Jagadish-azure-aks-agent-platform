# Implementation guide (for adopters)

1. **Fork and run offline.** `pip install -e ".[dev]" && pytest -q && python scripts/run_measurements.py`.
2. **Swap the domain.** Replace `data.py` (policies, claims) and `Coverage` with your rules. Keep `risk_reasons` explicit and testable.
3. **Pick the model.** `MODEL_PROVIDER=azure` with your deployment. Keep `parse_triage` strict; add fields to the schema and tests together.
4. **Tune the gates.** `AUTO_PAY_LIMIT`, `FRAUD_REVIEW`, the token and dollar cap. Add your own attack and benign texts to `sim.py` and keep both block rate and false-positive rate in CI.
5. **Move checkpoints to a shared store.** Replace `FileCheckpointStorage` with a Postgres-backed storage before running more than one replica on AKS without RWX volumes.
6. **Run kind.** `./deploy/kind/smoke.sh` proves deploy, pod kill and resume.
7. **Provision.** Review the Terraform, fill tfvars, add a backend, plan, get approval, apply.
8. **Deploy.** Follow [deploy.md](deploy.md). GitHub Actions is the default. Create the `dev` and `prod` environments first, with required reviewers on `prod`, then set the repository variables. A push to `main` deploys dev. `workflow_dispatch` with `environment=prod` and the dev image SHA promotes that same tag.
9. **Evaluate.** Register a Foundry evaluation on recorded, redacted triage outputs before raising the auto-pay limit.
10. **Argo CD, only if you turn GitHub Actions deploy off.** The application in `deploy/argocd/application.yaml` does not auto-sync. Apply it after disabling `.github/workflows/cd.yml`, and keep the canary analysis query on a metric you trust.
