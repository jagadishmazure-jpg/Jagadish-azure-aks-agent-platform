#!/bin/sh
# One-time adoption when an earlier Argo CD sync created the chart resources
# without Helm ownership. CD runs this only when HELM_ADOPT_EXISTING=true.
set -eu
ns="${1:-claims}"
for kind in deployment rollout service serviceaccount horizontalpodautoscaler poddisruptionbudget networkpolicy persistentvolumeclaim; do
  kubectl -n "$ns" get "$kind" -o name 2>/dev/null | while read -r obj; do
    [ -n "$obj" ] || continue
    kubectl -n "$ns" annotate "$obj" \
      meta.helm.sh/release-name=claims-agent \
      meta.helm.sh/release-namespace="$ns" --overwrite
    kubectl -n "$ns" label "$obj" app.kubernetes.io/managed-by=Helm --overwrite
  done
done
