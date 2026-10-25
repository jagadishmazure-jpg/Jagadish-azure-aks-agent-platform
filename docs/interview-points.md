# Interview points

- Why the human gate is enforced in the graph (`request_info`) and not in the prompt.
- Why pods must be stateless for agents: the pod-kill result, 100% vs 0% with shared vs pod-local checkpoints.
- Why I removed the second broker and the second search store, and when I would add search back.
- Workload identity vs keys: what an attacker gets from a stolen pod in each case.
- Why the model only scores: payout math stays in code, so a successful injection cannot set an amount.
- Cost control at three levels: per-claim cap, dashboard cost panel, resource-group budget.
- Release safety chain: Trivy, cosign keyless (identity of the workflow, not a stored key), canary with automatic abort.
- Honesty: what is simulated (rollback, cost) and what is real (workflow, guards, resume), and why the live run did not happen.
