# How it works

1. `POST /claims` with `Authorization: Bearer <token>` and optional `traceparent`.
2. `auth.verify` checks signature (dev), issuer, audience, expiry and role.
3. `ClaimsService.submit` opens span `claim.submit` as a child of the caller's trace and runs the workflow.
4. `Intake`: `injection_hits` on normalised text (NFKC, zero-width characters removed). A hit ends the run with `rejected_injection` before any model call.
5. `Triage`: prompt carries the redacted text inside `<claim_text>` tags, with instructions to treat it as data. Usage is charged to a `TokenBudget`; over the cap the claim is `escalated_budget`.
6. `Coverage`: missing, lapsed or wrong-line policy ends in `denied_no_coverage`.
7. `Decision`: risky when payable is above 5,000, fraud score at least 0.5, or severity high. Risky claims pause with `request_info`.
8. `POST /claims/{id}/decision` (role `Claims.Adjust`) on any pod: load the newest checkpoint, re-surface the pending request, apply the decision.

Real output of `python scripts/run_measurements.py` (excerpt, stub model):

```json
"claims_run": {"claims": 300, "paused_for_adjuster": 178, "finished_on_other_pod": 178, "trace_continuity": 1.0}
```
