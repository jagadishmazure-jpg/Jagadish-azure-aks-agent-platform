"""OpenTelemetry tracing and Prometheus metrics. The trace id rides in the W3C traceparent header and
in the checkpointed claim state, so a claim resumed on another pod continues the same trace."""

from __future__ import annotations

import os
import secrets

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags
from prometheus_client import CollectorRegistry, Counter, Histogram

EXPORTER = InMemorySpanExporter()
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(EXPORTER))
if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):  # pragma: no cover - cluster only
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
tracer = _provider.get_tracer("nfclaims")

REGISTRY = CollectorRegistry()
CLAIMS = Counter("nf_claims_total", "Claims by outcome", ["status"], registry=REGISTRY)
TOKENS = Counter("nf_model_tokens_total", "Model tokens", ["direction"], registry=REGISTRY)
LATENCY = Histogram("nf_claim_seconds", "Claim handling time", registry=REGISTRY)
BLOCKED = Counter("nf_injection_blocked_total", "Inputs blocked by the injection screen", registry=REGISTRY)


def new_traceparent() -> str:
    return f"00-{secrets.token_hex(16)}-{secrets.token_hex(8)}-01"


def parse_traceparent(tp: str) -> tuple[int, int] | None:
    parts = (tp or "").split("-")
    if len(parts) != 4 or len(parts[1]) != 32 or len(parts[2]) != 16:
        return None
    try:
        return int(parts[1], 16), int(parts[2], 16)
    except ValueError:
        return None


def parent_context(tp: str):
    ids = parse_traceparent(tp)
    if not ids:
        return None
    sc = SpanContext(trace_id=ids[0], span_id=ids[1], is_remote=True, trace_flags=TraceFlags(1))
    return trace.set_span_in_context(NonRecordingSpan(sc))


def trace_id_hex(tp: str) -> str:
    return (tp or "").split("-")[1] if parse_traceparent(tp) else ""
