"""The connector contract.

Reference: docs/02-architecture.md ("Failure semantics") and
docs/03-mesh.md ("Connector interface").

Eight methods, one error taxonomy, one conformance suite. A connector that
cannot pass `conformance.run_conformance()` does not ship, because "four
connectors to one contract" is only true if the contract is enforced by a test
rather than by a reviewer's memory.

Nothing here reaches the network. A production connector wraps an HTTP client;
this module defines what it must return and how it must fail.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


# ---------------------------------------------------------------------------
# Errors - the taxonomy is closed
# ---------------------------------------------------------------------------

class ConnectorError(Exception):
    """Base for every error a connector may raise."""


class TransientError(ConnectorError):
    """Network or server fault. Retryable. Counts toward the circuit breaker."""


class RateLimited(ConnectorError):
    """The node is throttling. Carries retry_after. Never counts as a failure."""

    def __init__(self, message: str, retry_after: float = 1.0):
        super().__init__(message)
        self.retry_after = retry_after


class AuthError(ConnectorError):
    """Credentials rejected. Halts the connector; never retried automatically."""


class SchemaDrift(ConnectorError):
    """A field the canonical map expects is missing or retyped."""


class PartialFailure(ConnectorError):
    """A batch read returned some records. The connector must report the set."""

    def __init__(self, message: str, succeeded: list | None = None):
        super().__init__(message)
        self.succeeded = succeeded or []


class ContractError(ConnectorError):
    """The connector returned a shape the canonical schema forbids."""


ERROR_TAXONOMY = (
    TransientError,
    RateLimited,
    AuthError,
    SchemaDrift,
    PartialFailure,
    ContractError,
)


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------

@dataclass
class ReadResult:
    records: list[dict]
    cursor: str | None = None
    partial: bool = False

    def __post_init__(self):
        if not isinstance(self.records, list):
            raise ContractError("read() must return a list of records")


@dataclass
class WriteResult:
    ok: bool
    external_id: str | None = None
    error: str | None = None


@dataclass
class Health:
    status: str            # online | degraded | offline | buffering
    detail: str = ""

    def __post_init__(self):
        if self.status not in ("online", "degraded", "offline", "buffering"):
            raise ContractError(f"unknown node status {self.status!r}")


@dataclass
class RateLimit:
    requests_per_minute: int
    burst: int = 1

    def __post_init__(self):
        if self.requests_per_minute <= 0:
            raise ContractError("requests_per_minute must be positive")
        if self.burst < 1:
            raise ContractError("burst must be at least 1")


@dataclass
class Capability:
    """What a node can do. The router's capability_match reads this."""
    objects: tuple[str, ...]
    operations: tuple[str, ...] = ("read", "write")
    categories: tuple[str, ...] = ()

    def supports(self, object_name: str, operation: str) -> bool:
        return object_name in self.objects and operation in self.operations


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """Per-node breaker: closed, open, half-open.

    A node that fails repeatedly is not retried forever. It is opened, then
    given one trial request after a cooldown. Rate limits do not trip it: a
    throttled node is healthy and rude, not broken.
    """

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: float = 30.0,
                 clock=time.monotonic):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._clock = clock
        self.failures = 0
        self.opened_at: float | None = None

    @property
    def state(self) -> str:
        if self.opened_at is None:
            return "closed"
        if self._clock() - self.opened_at >= self.cooldown_seconds:
            return "half_open"
        return "open"

    def allow(self) -> bool:
        return self.state != "open"

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold and self.opened_at is None:
            self.opened_at = self._clock()

    def record_rate_limit(self) -> None:
        """A throttle is not a failure. It must not open the breaker."""
        return


# ---------------------------------------------------------------------------
# The interface
# ---------------------------------------------------------------------------

class Connector:
    """What every connector implements. Subclass and override all of it.

    Deliberately not an ABC: a missing method should fail the conformance suite
    with a clear message, not at import time with a TypeError.
    """

    node_id: str = ""
    category: str = "custom"

    def capabilities(self) -> Capability:
        raise NotImplementedError

    def schema(self) -> dict:
        """Map canonical field name -> this node's field name.

        A field absent from the map is a field this node does not carry. The map
        may not contain a name that is not in the canonical schema for the
        object, and the conformance suite checks that.
        """
        raise NotImplementedError

    def read(self, object_name: str, cursor: str | None = None) -> ReadResult:
        raise NotImplementedError

    def write(self, object_name: str, payload: dict, idempotency_key: str) -> WriteResult:
        raise NotImplementedError

    def subscribe(self) -> None:
        """Push subscription. Not implemented by any v1 connector."""
        raise NotImplementedError("subscribe() is not implemented in the reference core")

    def health(self) -> Health:
        raise NotImplementedError

    def rate_limit(self) -> RateLimit:
        raise NotImplementedError

    def cost_estimate(self, operation: str, count: int = 1) -> float:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Retry wrapper
# ---------------------------------------------------------------------------

def call_with_retry(fn, breaker: CircuitBreaker, attempts: int = 3,
                    base_delay: float = 0.05, sleep=time.sleep):
    """Call `fn`, applying the taxonomy.

    TransientError retries with exponential backoff. RateLimited waits what the
    node asked for and does not count as a failure. Everything else raises
    immediately, because a broken contract does not improve with repetition.
    """
    if not breaker.allow():
        raise TransientError("circuit breaker is open; the node is not being called")

    last: Exception | None = None
    for attempt in range(attempts):
        try:
            result = fn()
            breaker.record_success()
            return result
        except RateLimited as exc:
            breaker.record_rate_limit()
            sleep(exc.retry_after)
            last = exc
        except TransientError as exc:
            breaker.record_failure()
            last = exc
            if attempt < attempts - 1:
                sleep(base_delay * (2 ** attempt))
        except ConnectorError:
            breaker.record_failure()
            raise
    raise last if last else TransientError("call failed with no recorded error")
