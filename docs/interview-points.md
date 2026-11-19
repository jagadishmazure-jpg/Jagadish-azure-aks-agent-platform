# Interview points

- Why the human gate is enforced in the graph (`request_info`) and not in the prompt.
- Why pods must be stateless for agents: the pod-kill result, 100% vs 0% with shared vs pod-local checkpoints.
- Why I removed the second broker and the second search store, and when I would add search back.
- Workload identity vs keys: what an attacker gets from a stolen pod in each case.
- Why the model only scores: payout math stays in code, so a successful injection cannot set an amount.
- Cost control at three levels: per-claim cap, dashboard cost panel, resource-group budget.
- Release safety chain: Trivy, cosign keyless (identity of the workflow, not a stored key), canary with automatic abort.
- Kubernetes manifests and Helm charts are in this repo (`deploy/helm/claims-agent`, `deploy/helm/foundry-on-aks`, the namespaces, Argo CD as a manual option, kind, the collector). GitHub Actions is the deploy path: OIDC, an immutable SHA in ACR, helm upgrade. Prod reuses that SHA and waits for required reviewers. The dev deploy identity can push images and change `claims-dev` and `foundry-sessions-dev`. The prod deploy identity can change `claims` and `foundry-sessions`.
- Honesty: what is simulated (rollback, cost) and what is real (workflow, guards, resume), and why the live run did not happen.
- Foundry on AKS: Foundry keeps the agent API and the session lifecycle; the platform team keeps the cluster, the registry, storage, identity, and the network boundary. One session is one pod. The NetworkPolicy is what stops that pod from talking to the session next to it.
- Why the model identity and the session identity are different. The model identity can read blobs. The session identity has no Azure role, and the session pod does not mount a Kubernetes API token. A sandbox that runs generated code should not be the principal that reads weights.
- Why session ingress is closed in this chart. The preview has not named the peer that is allowed to call the pod. Opening "any session" would erase the isolation. The gap is marked [verify] in docs/foundry-on-aks.md.
- Why the mock model reuses the signed claims image. A second unsigned image would skip the cosign gate. The process is a fixed JSON stub, and the test shows the prompt is not copied into the response.
- Why the Kata pool and the GPU pool default to count 0. They change the bill and the node image. `terraform validate` still type-checks them. CD does not set `runtimeClassName`, so a cluster without the pool is not left with Pending session pods.
