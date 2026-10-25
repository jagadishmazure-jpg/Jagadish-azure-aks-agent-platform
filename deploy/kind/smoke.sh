#!/usr/bin/env bash
# kind smoke test: build image, load into kind, helm install with the stub model, submit one claim,
# delete a pod, then finish a paused claim on the surviving pod. Used by CI; free and local.
set -euo pipefail
NS=claims
docker build -t claims-agent:ci .
kind load docker-image claims-agent:ci --name "${KIND_CLUSTER:-nf-claims}"
kubectl create namespace $NS --dry-run=client -o yaml | kubectl apply -f -
kubectl -n $NS create secret generic claims-agent-dev --from-literal=dev-token-key="$(openssl rand -hex 24)" --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install claims-agent deploy/helm/claims-agent -n $NS \
  --set image.repository=claims-agent --set image.tag=ci --set replicas=1 --set autoscaling.minReplicas=1 --wait --timeout 180s
kubectl -n $NS port-forward svc/claims-agent 8080:80 >/tmp/pf.log 2>&1 &
PF=$!; trap 'kill $PF' EXIT; sleep 4
python3 scripts/smoke_client.py "$(kubectl -n $NS get secret claims-agent-dev -o jsonpath='{.data.dev-token-key}' | base64 -d)" submit
kubectl -n $NS delete pod -l app.kubernetes.io/name=claims-agent --wait=true
kubectl -n $NS rollout status deploy/claims-agent --timeout 120s
kill $PF; sleep 1
kubectl -n $NS port-forward svc/claims-agent 8080:80 >/tmp/pf.log 2>&1 &
PF=$!; sleep 4
python3 scripts/smoke_client.py "$(kubectl -n $NS get secret claims-agent-dev -o jsonpath='{.data.dev-token-key}' | base64 -d)" decide
