"""Token accounting and per-request cost caps.

Prices are list prices for a gpt-4o-mini class deployment (USD per 1M tokens) as assumed on 2026-10-25.
They are inputs to a simulation; check the current Azure price sheet before quoting a client.
"""

from __future__ import annotations

from dataclasses import dataclass, field

PRICES_AS_OF = "2026-10-25"
PRICE_PER_M = {"input": 0.15, "output": 0.60}


class BudgetExceeded(RuntimeError):
    pass


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def cost_usd(tokens_in: int, tokens_out: int) -> float:
    return tokens_in * PRICE_PER_M["input"] / 1e6 + tokens_out * PRICE_PER_M["output"] / 1e6


@dataclass
class TokenBudget:
    max_tokens: int = 4000
    max_usd: float = 0.01
    used_in: int = 0
    used_out: int = 0
    calls: list[tuple[int, int]] = field(default_factory=list)

    def charge(self, tokens_in: int, tokens_out: int) -> None:
        if self.used_in + self.used_out + tokens_in + tokens_out > self.max_tokens:
            raise BudgetExceeded(f"token cap {self.max_tokens} reached")
        if cost_usd(self.used_in + tokens_in, self.used_out + tokens_out) > self.max_usd:
            raise BudgetExceeded(f"cost cap ${self.max_usd} reached")
        self.used_in += tokens_in
        self.used_out += tokens_out
        self.calls.append((tokens_in, tokens_out))

    @property
    def usd(self) -> float:
        return cost_usd(self.used_in, self.used_out)
