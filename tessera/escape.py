"""Escape hatches.

Reference: docs/17-constraints.md ("The escape hatches"). Deliverable 10.

Four hatches, and the point of each is that a buyer who cannot leave will not
arrive:

    schema export      the canonical schema as JSON
    record export      every record, bypassing field rules, for a role that may
    query              a read-only, SELECT-shaped query over the projection
    break-glass        time-boxed admin, for a stated reason

Three rules hold for all four:

* a role check runs first, and it is `admin` for every hatch
* every use is written to the ledger, including a refused one
* nothing here can write, except break-glass, which writes only its own grant

The query hatch is **not** SQL. It is a SELECT-shaped grammar over the projection
with the automation condition language in the WHERE clause. Calling it raw SQL
would be a lie, and shipping a real SQL engine over a dictionary would be a
worse one.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from . import automation, canonical

HATCHES = ("schema_export", "record_export", "query", "break_glass")

SELECT = re.compile(
    r"^\s*select\s+(?P<fields>\*|[a-z_,\s]+?)\s+from\s+(?P<object>[A-Za-z]+)"
    r"(?:\s+where\s+(?P<where>.+?))?(?:\s+limit\s+(?P<limit>\d+))?\s*;?\s*$",
    re.IGNORECASE | re.DOTALL,
)


class EscapeDenied(Exception):
    """Raised when a caller without the role reaches for a hatch."""


class EscapeHatch:
    def __init__(self, log=None, tenant_id: str = "", policy=None, projection=None):
        self.log = log
        self.tenant_id = tenant_id
        self.policy = policy
        self.projection = projection
        self.grants: dict[str, dict] = {}

    # -- the gate every hatch goes through --------------------------------
    def _authorise(self, principal, hatch: str, allowed: bool, detail: str = "") -> None:
        if self.log:
            self.log.append(
                self.tenant_id,
                getattr(principal, "kind", "human"),
                "escape.use" if allowed else "escape.denied",
                {"hatch": hatch, "principal": getattr(principal, "id", "?"),
                 "detail": detail},
                source_node_id="escape",
            )
        if not allowed:
            raise EscapeDenied(
                f"{getattr(principal, 'id', '?')!r} may not use the {hatch} hatch"
            )

    def _is_admin(self, principal) -> bool:
        return getattr(principal, "role", "") == "admin"

    # -- the four hatches -------------------------------------------------
    def schema_export(self, principal) -> dict:
        self._authorise(principal, "schema_export", self._is_admin(principal))
        return {
            "version": canonical.SCHEMA_VERSION,
            "objects": {name: {field: {"kind": kind, "required": required}
                               for field, (kind, required) in spec.items()}
                        for name, spec in canonical.SCHEMA.items()},
        }

    def record_export(self, principal, object_name: str) -> list[dict]:
        """Every field of every record, for a role that may see them.

        This is the hatch that exists because a screen is not a database: an
        admin with a legitimate reason needs the whole record, and the honest way
        to give it is one audited door rather than a widening of every other.
        """
        self._authorise(principal, "record_export", self._is_admin(principal),
                        detail=object_name)
        if self.projection is None:
            return []
        return [dict(record) for _id, record in
                sorted(self.projection.state.get(object_name, {}).items())]

    def query(self, principal, statement: str) -> dict:
        """A SELECT-shaped read over the projection. Not SQL, and it says so."""
        self._authorise(principal, "query", self._is_admin(principal), detail=statement[:80])
        match = SELECT.match(statement)
        if not match:
            raise EscapeDenied(
                "only SELECT <fields> FROM <object> [WHERE <condition>] [LIMIT n] is accepted"
            )
        object_name = match.group("object")
        if object_name not in canonical.SCHEMA:
            raise EscapeDenied(f"unknown object {object_name!r}")

        rows = [dict(r) for _id, r in self.projection.state.get(object_name, {}).items()] \
            if self.projection else []

        where = match.group("where")
        if where:
            rows = [r for r in rows if _matches(where, r)]

        limit = match.group("limit")
        if limit:
            rows = rows[:int(limit)]

        fields = match.group("fields").strip()
        if fields != "*":
            wanted = [f.strip() for f in fields.split(",") if f.strip()]
            unknown = [f for f in wanted if f not in canonical.SCHEMA[object_name]]
            if unknown:
                raise EscapeDenied(f"unknown fields: {unknown}")
            rows = [{k: r.get(k) for k in wanted} for r in rows]

        return {"object": object_name, "rows": rows, "count": len(rows),
                "note": "SELECT-shaped over the projection; not a SQL engine"}

    def break_glass(self, principal, reason: str, minutes: int = 15) -> dict:
        """A time-boxed grant, with a reason and an expiry that needs no action.

        The grant expires by clock, not by anybody remembering to revoke it. An
        admin who forgets is the normal case, not the exceptional one.
        """
        self._authorise(principal, "break_glass", self._is_admin(principal), detail=reason)
        if not reason or len(reason.strip()) < 8:
            raise EscapeDenied("break-glass needs a reason, not a word")
        if not 1 <= minutes <= 60:
            raise EscapeDenied("a break-glass window is between 1 and 60 minutes")

        token = canonical.uuid7()
        expires = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        grant = {"token": token, "principal": getattr(principal, "id", "?"),
                 "reason": reason, "expires_at": expires.isoformat(),
                 "minutes": minutes}
        self.grants[token] = grant
        if self.log:
            self.log.append(self.tenant_id, "human", "escape.break_glass", grant,
                            source_node_id="escape")
        return grant

    def grant_active(self, token: str, now: datetime | None = None) -> bool:
        grant = self.grants.get(token)
        if not grant:
            return False
        expires = datetime.fromisoformat(grant["expires_at"])
        return (now or datetime.now(timezone.utc)) < expires


def _matches(condition: str, record: dict) -> bool:
    try:
        return automation.evaluate(condition, record)
    except automation.AutomationError:
        return False
