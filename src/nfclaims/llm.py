"""Model clients.

* MODEL_PROVIDER=azure: Azure OpenAI through MAF's OpenAIChatClient (AZURE_OPENAI_ENDPOINT,
  AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_VERSION). The target on AKS, where
  the key is replaced by workload identity; see docs/architecture.md.
* MODEL_PROVIDER=openai: the OpenAI API with gpt-4o-mini (OPENAI_API_KEY, falling back to
  AZURE_OPENAI_API_KEY). Used for the local live runs in results/live_metrics.json.
* Offline / CI: StubChatClient, a deterministic stand-in. Every result produced with it is labelled
  model="stub" so nobody mistakes it for a live model run.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from agent_framework import BaseChatClient, ChatResponse, FunctionInvocationLayer, Message

from .cost import estimate_tokens

ENV_VARS = ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT", "AZURE_OPENAI_API_VERSION")
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"


def live_configured(env: dict[str, str] | None = None) -> bool:
    """True when all four Azure OpenAI variables are set."""
    env = os.environ if env is None else env
    return all(env.get(k) for k in ENV_VARS)


def openai_key(env) -> str:
    return env.get("OPENAI_API_KEY") or env.get("AZURE_OPENAI_API_KEY") or ""


def pick_provider(env: dict[str, str] | None = None) -> str:
    """MODEL_PROVIDER=azure|openai|stub wins. Unset: azure if fully configured, openai if a key exists, else stub."""
    env = os.environ if env is None else env
    p = (env.get("MODEL_PROVIDER") or "").lower()
    if p in ("azure", "openai", "stub"):
        return p
    if live_configured(env):
        return "azure"
    return "openai" if openai_key(env) else "stub"


class StubChatClient(FunctionInvocationLayer, BaseChatClient):
    """Deterministic triage model. Reads the claim facts from the prompt and returns JSON."""

    OTEL_PROVIDER_NAME = "stub"
    model_label = "stub"

    async def _inner_get_response(self, *, messages, stream, options, **kwargs: Any):  # type: ignore[override]
        prompt = " ".join(m.text or "" for m in messages)
        amount = float(re.search(r"amount=([\d.]+)", prompt).group(1)) if "amount=" in prompt else 0.0
        prior = int(re.search(r"prior_claims=(\d+)", prompt).group(1)) if "prior_claims=" in prompt else 0
        severity = "high" if amount >= 20000 else "medium" if amount >= 4000 else "low"
        fraud = round(min(0.95, 0.05 + 0.18 * prior + (0.2 if amount >= 50000 else 0.0)), 2)
        body = json.dumps({"severity": severity, "fraud_score": fraud, "summary": f"{severity} severity claim"})
        return ChatResponse(
            messages=Message("assistant", [body]),
            usage_details={"input_token_count": estimate_tokens(prompt), "output_token_count": estimate_tokens(body)},
            model="stub",
        )


def make_client(env: dict[str, str] | None = None):
    """Return (client, label). The key is read from the environment and never logged or stored."""
    env = os.environ if env is None else env
    provider = pick_provider(env)
    if provider == "stub":
        return StubChatClient(), "stub"
    from agent_framework.openai import OpenAIChatCompletionClient as OpenAIChatClient  # Chat Completions API

    if provider == "azure":
        missing = [k for k in ENV_VARS if not env.get(k)]
        if missing:
            raise RuntimeError(f"MODEL_PROVIDER=azure needs {', '.join(missing)}")
        client = OpenAIChatClient(
            model=env["AZURE_OPENAI_DEPLOYMENT"],
            api_key=env["AZURE_OPENAI_API_KEY"],
            azure_endpoint=env["AZURE_OPENAI_ENDPOINT"],
            api_version=env["AZURE_OPENAI_API_VERSION"],
        )
        return client, f"azure-openai:{env['AZURE_OPENAI_DEPLOYMENT']}"
    key = openai_key(env)
    if not key:
        raise RuntimeError("MODEL_PROVIDER=openai needs OPENAI_API_KEY (or AZURE_OPENAI_API_KEY)")
    model = env.get("OPENAI_MODEL") or OPENAI_DEFAULT_MODEL
    return OpenAIChatClient(model=model, api_key=key), f"openai:{model}"


def parse_triage(text: str) -> dict:
    """Strict parse of the triage JSON: exact keys, typed, bounded. Raises ValueError otherwise."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in model output")
    data = json.loads(m.group(0), parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
    if set(data) != {"severity", "fraud_score", "summary"}:
        raise ValueError("unexpected keys")
    if data["severity"] not in ("low", "medium", "high"):
        raise ValueError("bad severity")
    score = float(data["fraud_score"])
    if not 0.0 <= score <= 1.0:
        raise ValueError("fraud_score out of range")
    return {"severity": data["severity"], "fraud_score": score, "summary": str(data["summary"])[:200]}
