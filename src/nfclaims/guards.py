"""Input and output guardrails: PII redaction (text, logs, errors) and a prompt-injection screen."""

from __future__ import annotations

import logging
import re
import unicodedata

PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("PHONE", re.compile(r"\b(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]\d{4}\b")),
    ("CARD", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
]
NAME_HINT = re.compile(r"\b(Contact|Insured|Claimant|Name:)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)")


def _luhn(digits: str) -> bool:
    d = [int(c) for c in digits if c.isdigit()]
    if not 13 <= len(d) <= 19:
        return False
    total = 0
    for i, x in enumerate(reversed(d)):
        if i % 2:
            x *= 2
            x -= 9 if x > 9 else 0
        total += x
    return total % 10 == 0


def redact(text: str) -> str:
    """Replace PII with typed placeholders. Card numbers only when the Luhn checksum passes."""
    out = text
    for label, pat in PII_PATTERNS:
        if label == "CARD":
            out = pat.sub(lambda m: "[CARD]" if _luhn(m.group()) else m.group(), out)
        else:
            out = pat.sub(f"[{label}]", out)
    return NAME_HINT.sub(lambda m: f"{m.group(1)} [NAME]", out)


def has_pii(text: str) -> bool:
    return redact(text) != text


INJECTION_RULES = [
    r"ignore (all |any |the )?(previous|prior|above) (instructions|rules)",
    r"disregard (your|the) (system|previous) (prompt|instructions)",
    r"you are now (in )?(developer|dan|admin) mode",
    r"reveal (your|the) (system prompt|instructions|api key|secrets?)",
    r"(approve|pay) (this|the) claim (immediately|without review)",
    r"set (the )?(amount|payout) to",
    r"act as (the )?(adjuster|administrator|supervisor)",
    r"print (the )?(environment|env) (variables|vars)",
    r"</?(system|assistant)>",
    r"base64:",
    r"override (the )?(policy|limit|approval)",
    r"skip (the )?(human|manual) (review|approval)",
]
_INJ = re.compile("|".join(INJECTION_RULES), re.I)
_ZW = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"))


def normalise(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).translate(_ZW)
    return re.sub(r"\s+", " ", t)


def injection_hits(text: str) -> list[str]:
    return [m.group(0) for m in _INJ.finditer(normalise(text))]


def is_injection(text: str) -> bool:
    return bool(injection_hits(text))


class RedactingFilter(logging.Filter):
    """Attach to every handler so log lines never carry raw PII, including exception text."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(str(record.getMessage()))
        record.args = ()
        if record.exc_info and record.exc_info[1] is not None:
            record.exc_text = redact(repr(record.exc_info[1]))
            record.exc_info = None
        return True


def safe_error(exc: BaseException) -> str:
    """Error text that is safe to return to a client or write to a log."""
    return f"{type(exc).__name__}: {redact(str(exc))}"[:300]
