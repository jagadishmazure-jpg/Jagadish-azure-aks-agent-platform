"""Claims service: runs the workflow inside an OpenTelemetry span, keyed by the request traceparent.

Pods are stateless. Workflow checkpoints live in shared storage (a directory here, a ReadWriteMany
volume on kind; Postgres is the planned store on AKS). Any pod can resume any paused claim.
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from agent_framework import FileCheckpointStorage

from .data import Claim, make_policies
from .guards import safe_error
from .llm import make_client
from .telemetry import BLOCKED, CLAIMS, LATENCY, TOKENS, new_traceparent, parent_context, tracer
from .workflow import CHECKPOINT_TYPES, AdjusterDecision, ClaimState, build_workflow


class ClaimsService:
    def __init__(self, checkpoint_dir: str | None = None, client=None, pod: str | None = None) -> None:
        d = Path(checkpoint_dir or os.environ.get("CHECKPOINT_DIR", str(Path(tempfile.gettempdir()) / "nf-checkpoints")))
        d.mkdir(parents=True, exist_ok=True)
        self.storage = FileCheckpointStorage(str(d), allowed_checkpoint_types=CHECKPOINT_TYPES)
        if client is None:
            client, self.model_label = make_client()
        else:
            self.model_label = getattr(client, "model_label", "custom")
        self.client = client
        self.policies = make_policies()
        self.pod = pod or os.environ.get("HOSTNAME", "local")

    def _wf(self, claim_id: str):
        return build_workflow(self.client, self.policies, self.storage, name=f"nf-claims-{claim_id}")

    def _record(self, result, claim_id: str) -> dict:
        outs = result.get_outputs()
        if outs:
            o = dict(outs[-1])
            CLAIMS.labels(o["status"]).inc()
            if o["status"] == "rejected_injection":
                BLOCKED.inc()
            TOKENS.labels("in").inc(o.get("tokens_in", 0))
            TOKENS.labels("out").inc(o.get("tokens_out", 0))
            o["model"], o["pod"] = self.model_label, self.pod
            return o
        pend = result.get_request_info_events()
        if pend:
            r = pend[0].data
            return {
                "claim_id": claim_id,
                "status": "awaiting_adjuster",
                "request_id": pend[0].request_id,
                "reasons": r.reasons,
                "model": self.model_label,
                "pod": self.pod,
            }
        return {"claim_id": claim_id, "status": "no_outcome", "pod": self.pod}

    async def submit(self, claim: Claim, traceparent: str | None = None) -> dict:
        tp = traceparent or new_traceparent()
        t0 = time.perf_counter()
        with tracer.start_as_current_span("claim.submit", context=parent_context(tp)) as sp:
            sp.set_attribute("claim.id", claim.claim_id)
            sp.set_attribute("k8s.pod.name", self.pod)
            try:
                res = await self._wf(claim.claim_id).run(ClaimState(**claim.to_dict(), traceparent=tp))
                out = self._record(res, claim.claim_id)
            except Exception as e:  # never leak raw claim text in errors
                sp.set_attribute("error", safe_error(e))
                out = {"claim_id": claim.claim_id, "status": "error", "error": safe_error(e)}
            sp.set_attribute("claim.status", out["status"])
        LATENCY.observe(time.perf_counter() - t0)
        out["traceparent"] = tp
        return out

    async def decide(self, claim_id: str, decision: AdjusterDecision, traceparent: str) -> dict:
        """Resume from the latest checkpoint (works on any pod), then apply the adjuster decision."""
        with tracer.start_as_current_span("claim.decide", context=parent_context(traceparent)) as sp:
            sp.set_attribute("claim.id", claim_id)
            sp.set_attribute("k8s.pod.name", self.pod)
            wf = self._wf(claim_id)
            latest = await self.storage.get_latest(workflow_name=wf.name)
            if latest is None:
                return {"claim_id": claim_id, "status": "not_found"}
            res = await wf.run(checkpoint_id=latest.checkpoint_id, checkpoint_storage=self.storage)
            pend = res.get_request_info_events()
            if not pend:
                return {"claim_id": claim_id, "status": "nothing_pending"}
            out = self._record(await wf.run(responses={pend[0].request_id: decision}), claim_id)
            sp.set_attribute("claim.status", out["status"])
        out["traceparent"] = traceparent
        return out
