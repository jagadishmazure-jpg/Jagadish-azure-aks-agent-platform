"""Synthetic claims and policies for Northfield Mutual (a fictional insurer). Seeded, so every run is identical."""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass

LINES = ("auto", "home", "travel")
FIRST = ("Avery", "Jordan", "Riley", "Morgan", "Casey", "Quinn", "Rowan", "Sage", "Emery", "Finley")
LAST = ("Hollis", "Marsh", "Penrose", "Calloway", "Ashdown", "Brightley", "Thorne", "Wexley")


@dataclass(frozen=True)
class Policy:
    policy_id: str
    line: str
    limit: float
    deductible: float
    active: bool


@dataclass(frozen=True)
class Claim:
    claim_id: str
    policy_id: str
    line: str
    amount: float
    description: str
    prior_claims: int

    def to_dict(self) -> dict:
        return asdict(self)


def make_policies(n: int = 120, seed: int = 7) -> dict[str, Policy]:
    rng = random.Random(seed)
    out = {}
    for i in range(n):
        line = LINES[i % 3]
        pid = f"NM-{line[:2].upper()}-{1000 + i}"
        out[pid] = Policy(
            pid, line, float(rng.choice([5000, 15000, 50000, 250000])), float(rng.choice([250, 500, 1000])), rng.random() > 0.08
        )
    return out


def _desc(rng: random.Random, line: str) -> str:
    who = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
    phone = f"555-{rng.randint(100, 999)}-{rng.randint(1000, 9999)}"
    base = {
        "auto": "Rear-ended at a stop light, bumper and tail lamp damaged.",
        "home": "Pipe burst in the kitchen, water damage to the floor and cabinets.",
        "travel": "Checked bag lost on a connecting flight, clothes and a camera inside.",
    }[line]
    # Synthetic PII on purpose so redaction is exercised on every claim.
    return f"{base} Contact {who} at {phone} or {who.split()[0].lower()}@example.com."


def make_claims(n: int = 300, seed: int = 11) -> list[Claim]:
    rng = random.Random(seed)
    pols = list(make_policies().values())
    claims = []
    for i in range(n):
        p = rng.choice(pols)
        amount = round(rng.choice([rng.uniform(200, 4000), rng.uniform(4000, 20000), rng.uniform(20000, 90000)]), 2)
        claims.append(Claim(f"CLM-{5000 + i}", p.policy_id, p.line, amount, _desc(rng, p.line), rng.choice([0, 0, 0, 1, 1, 2, 4])))
    return claims
