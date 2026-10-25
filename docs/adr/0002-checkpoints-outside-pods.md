# ADR 0002: workflow checkpoints outside the pod

Status: accepted. A paused claim can wait hours for a human. Pods restart in that time. Measured: pod-local checkpoints lose every paused claim on restart. Today a shared volume; Postgres is planned.
