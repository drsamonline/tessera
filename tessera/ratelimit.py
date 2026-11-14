"""Rate limits and backpressure, per node.

Constraint 15 in docs/17-constraints.md: "Do not ship without backpressure and
circuit breakers per node." The breaker exists in connector.py. This is the other
half.

Two mechanisms, deliberately separate:

    TokenBucket   the node's declared budget. Refills at its declared rate.
    NodeBudget    admission control on top: a token, an in-flight cap, and a
                  bounded wait. This is what stops a fast producer from turning
                  a slow node into an unbounded queue in memory.

Backpressure surfaces as `RateLimited`, not as a new error type. The taxonomy is
closed (six types, docs/02-architecture.md) and from the caller's position a
node's throttle and our own admission control are the same event: wait, then
retry. Adding a seventh exception would make every caller learn a distinction
that does not change what they do.

Time is injected, so the tests do not sleep.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .connector import RateLimited


class TokenBucket:
    """Classic token bucket. `rate_per_minute` tokens accrue per minute, capped at `burst`."""

    def __init__(self, rate_per_minute: int, burst: int, clock=time.monotonic):
        if rate_per_minute <= 0:
            raise ValueError("rate_per_minute must be positive")
        if burst < 1:
            raise ValueError("burst must be at least 1")
        self.rate_per_second = rate_per_minute / 60.0
        self.capacity = float(burst)
        self.clock = clock
        self._tokens = float(burst)
        self._last = clock()

    def _refill(self) -> None:
        now = self.clock()
        elapsed = now - self._last
        if elapsed > 0:
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate_per_second)
            self._last = now

    @property
    def tokens(self) -> float:
        self._refill()
        return self._tokens

    def wait_time(self, tokens: int = 1) -> float:
        """Seconds until `tokens` are available. Zero when they already are."""
        self._refill()
        if self._tokens >= tokens:
            return 0.0
        return (tokens - self._tokens) / self.rate_per_second

    def try_acquire(self, tokens: int = 1) -> bool:
        self._refill()
        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False

    def acquire(self, tokens: int = 1) -> float:
        """Take `tokens` or raise RateLimited carrying the wait. Returns the wait (0 if immediate)."""
        wait = self.wait_time(tokens)
        if wait > 0:
            raise RateLimited(
                f"node budget exhausted; retry in {wait:.3f}s", retry_after=round(wait, 3)
            )
        self._tokens -= tokens
        return 0.0


@dataclass
class NodeBudget:
    """Admission control for one node.

    Two limits, each catching a different failure:

      * the bucket       the node's declared rate
      * max_in_flight    concurrency, so a slow node cannot be buried

    There was a third, `max_queue`, and it was removed rather than fixed: nothing
    in this runtime queues, so the counter could never rise and the limit could
    never fire. A limit that cannot fire is worse than no limit, because it
    appears in the documentation and in the operator's mental model. A bounded
    queue belongs to the caller that owns the work, not to the budget. (R-10)

    `snapshot()` is exposed rather than logged: a caller decides where it goes.
    """

    node_id: str
    rate_per_minute: int = 100
    burst: int = 5
    max_in_flight: int = 4
    clock: object = time.monotonic
    bucket: TokenBucket = field(init=False)
    in_flight: int = field(default=0, init=False)
    admitted: int = field(default=0, init=False)
    rejected: int = field(default=0, init=False)

    def __post_init__(self):
        self.bucket = TokenBucket(self.rate_per_minute, self.burst, self.clock)

    def admit(self) -> None:
        """Take one slot, or raise RateLimited explaining which limit was hit."""
        if self.in_flight >= self.max_in_flight:
            self.rejected += 1
            raise RateLimited(
                f"{self.node_id}: {self.in_flight} requests already in flight "
                f"(cap {self.max_in_flight})", retry_after=0.1,
            )
        self.bucket.acquire()
        self.in_flight += 1
        self.admitted += 1

    def release(self) -> None:
        if self.in_flight > 0:
            self.in_flight -= 1

    def snapshot(self) -> dict:
        return {
            "node_id": self.node_id,
            "tokens": round(self.bucket.tokens, 3),
            "in_flight": self.in_flight,
            "admitted": self.admitted,
            "rejected": self.rejected,
        }


class Budgets:
    """Every node's budget, in one place, so a mesh can ask before it calls."""

    def __init__(self):
        self._budgets: dict[str, NodeBudget] = {}

    def register(self, budget: NodeBudget) -> None:
        self._budgets[budget.node_id] = budget

    def get(self, node_id: str) -> NodeBudget:
        if node_id not in self._budgets:
            # An unregistered node gets a conservative default rather than an
            # unlimited pass. Silence is not permission.
            self._budgets[node_id] = NodeBudget(node_id=node_id)
        return self._budgets[node_id]

    def snapshot(self) -> list[dict]:
        return [b.snapshot() for b in self._budgets.values()]
