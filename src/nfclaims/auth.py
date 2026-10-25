"""Entra ID style token checks.

In Azure, Front Door/APIM validates the Entra ID JWT signature (validate-jwt) before traffic reaches AKS,
and the service re-checks the claims below. Locally and in CI, tokens are HS256 dev tokens signed with
DEV_TOKEN_KEY so the same claim checks run without a tenant. Dev tokens are refused when APP_ENV=prod.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

ISSUER = "https://login.microsoftonline.com/northfield-tenant/v2.0"
AUDIENCE = "api://nf-claims"
ROLE_SUBMIT, ROLE_ADJUST = "Claims.Submit", "Claims.Adjust"


class AuthError(Exception):
    pass


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _key() -> bytes:
    k = os.environ.get("DEV_TOKEN_KEY", "")
    if len(k) < 16:
        raise AuthError("DEV_TOKEN_KEY not configured")
    return k.encode()


def mint_dev_token(sub: str, roles: list[str], ttl: int = 600, aud: str = AUDIENCE, iss: str = ISSUER) -> str:
    head = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64(json.dumps({"sub": sub, "roles": roles, "aud": aud, "iss": iss, "exp": int(time.time()) + ttl}).encode())
    sig = _b64(hmac.new(_key(), f"{head}.{body}".encode(), hashlib.sha256).digest())
    return f"{head}.{body}.{sig}"


def check_claims(claims: dict, role: str, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    if claims.get("iss") != ISSUER:
        raise AuthError("bad issuer")
    if claims.get("aud") != AUDIENCE:
        raise AuthError("bad audience")
    if float(claims.get("exp", 0)) <= now:
        raise AuthError("token expired")
    if role not in claims.get("roles", []):
        raise AuthError(f"missing role {role}")
    return claims


def verify(token: str, role: str) -> dict:
    if os.environ.get("APP_ENV") == "prod":
        raise AuthError("dev tokens are disabled in prod; Entra ID validation happens at the gateway")
    try:
        head, body, sig = token.split(".")
        hdr = json.loads(_unb64(head))
    except ValueError as e:
        raise AuthError("malformed token") from e
    if hdr.get("alg") != "HS256":
        raise AuthError("unexpected alg")
    good = _b64(hmac.new(_key(), f"{head}.{body}".encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(good, sig):
        raise AuthError("bad signature")
    return check_claims(json.loads(_unb64(body)), role)
