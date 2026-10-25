"""FastAPI front end for the claims agents. Behind Front Door + APIM in Azure; behind ingress on kind."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import generate_latest
from pydantic import BaseModel, ConfigDict, Field

from .auth import ROLE_ADJUST, ROLE_SUBMIT, AuthError, verify
from .data import Claim
from .guards import RedactingFilter, safe_error
from .service import ClaimsService
from .telemetry import REGISTRY
from .workflow import AdjusterDecision

log = logging.getLogger("nfclaims")
_handler = logging.StreamHandler()
_handler.addFilter(RedactingFilter())
log.addHandler(_handler)

app = FastAPI(title="Northfield Mutual claims agents (fictional)")
_svc: ClaimsService | None = None


def svc() -> ClaimsService:
    global _svc
    if _svc is None:
        _svc = ClaimsService()
    return _svc


class ClaimIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_id: str = Field(pattern=r"^CLM-\d{1,8}$")
    policy_id: str = Field(max_length=32)
    line: str = Field(pattern=r"^(auto|home|travel)$")
    amount: float = Field(gt=0, le=1_000_000, allow_inf_nan=False)
    description: str = Field(max_length=4000)
    prior_claims: int = Field(ge=0, le=50)


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved: bool
    note: str = Field(default="", max_length=500)


def _auth(authorization: str | None, role: str) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    try:
        return verify(authorization[7:], role)
    except AuthError as e:
        raise HTTPException(403, str(e)) from e


@app.exception_handler(Exception)
async def _err(_: Request, exc: Exception):
    log.error("unhandled %s", safe_error(exc))
    return JSONResponse({"error": "internal error"}, status_code=500)


@app.get("/healthz")
def healthz():
    return {"ok": True, "model": svc().model_label}


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(REGISTRY).decode())


@app.post("/claims")
async def submit(body: ClaimIn, authorization: str | None = Header(None), traceparent: str | None = Header(None)):
    _auth(authorization, ROLE_SUBMIT)
    return await svc().submit(Claim(**body.model_dump()), traceparent)


@app.post("/claims/{claim_id}/decision")
async def decide(claim_id: str, body: DecisionIn, authorization: str | None = Header(None), traceparent: str | None = Header(None)):
    who = _auth(authorization, ROLE_ADJUST)
    return await svc().decide(claim_id, AdjusterDecision(body.approved, who["sub"], body.note), traceparent or "")
