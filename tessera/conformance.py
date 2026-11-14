"""The connector conformance suite.

Reference: docs/16-acceptance-criteria.md, deliverable 3 - "4 connectors pass one
shared conformance suite".

This is that suite. It is not a linter and it is not a code review: it calls the
connector and checks what came back. A connector that fails here does not ship,
whatever it looks like.

Every check is independent and reported by name, so a failing connector produces
a list rather than a boolean.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import canonical
from .connector import ERROR_TAXONOMY, ConnectorError

MAX_PAGES = 100


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class Report:
    connector: str
    checks: list[Check] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append(Check(name, ok, detail))

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.ok]

    def summary(self) -> str:
        passed = sum(1 for c in self.checks if c.ok)
        head = f"{self.connector}: {passed}/{len(self.checks)} checks passed"
        if self.ok:
            return head
        lines = [head]
        for c in self.failures:
            lines.append(f"  FAIL {c.name}: {c.detail}")
        return "\n".join(lines)


def _contact(node_id: str, index: int) -> dict:
    return {
        "id": canonical.uuid7(ms=1_700_000_000_000 + index, rand=bytes([index] * 10)),
        "tenant_id": "018f0000-0000-7000-8000-000000000001",
        "valid_from": "2026-11-01T09:00:00Z",
        "tx_time": "2026-11-01T09:00:01Z",
        "consent_state": "granted",
        "lawful_basis": "consent",
        "purpose_id": "sales-outreach",
        "retention_policy_id": "rp-24m",
        "full_name": f"Conformance {index}",
        "email": f"conformance{index}@example.com",
    }


def run_conformance(connector, object_name: str = "Contact") -> Report:
    """Run every check against `connector`. Returns a Report, never raises."""
    report = Report(connector=connector.node_id or connector.__class__.__name__)

    # 1. capabilities
    caps = None
    try:
        caps = connector.capabilities()
    except Exception as exc:  # noqa: BLE001 - a broken connector may raise anything
        report.add("capabilities_present", False, f"{type(exc).__name__}: {exc}")
    else:
        report.add("capabilities_present", caps is not None,
                   "" if caps is not None else "capabilities() returned None")
    if caps is None:
        return report

    declared = tuple(getattr(caps, "objects", ()) or ())
    report.add("capabilities_declare_objects", bool(declared),
               "" if declared else "no objects declared")
    unknown = [o for o in declared if o not in canonical.SCHEMA]
    report.add("capabilities_use_canonical_objects", not unknown,
               f"unknown objects: {unknown}" if unknown else "")

    # 2. schema
    try:
        mapping = connector.schema()
    except Exception as exc:  # noqa: BLE001
        report.add("schema_present", False, f"{type(exc).__name__}: {exc}")
        mapping = {}
    else:
        report.add("schema_present", isinstance(mapping, dict) and bool(mapping),
                   "" if mapping else "schema() returned nothing")

    bad_fields: list[str] = []
    for obj, field_map in (mapping or {}).items():
        if obj not in canonical.SCHEMA:
            bad_fields.append(f"{obj} (not canonical)")
            continue
        for name in (field_map or {}):
            if name not in canonical.SCHEMA[obj]:
                bad_fields.append(f"{obj}.{name}")
    report.add("schema_maps_only_canonical_fields", not bad_fields,
               f"non-canonical fields: {bad_fields[:4]}" if bad_fields else "")

    missing_maps = [o for o in declared if o not in (mapping or {})]
    report.add("schema_covers_declared_objects", not missing_maps,
               f"no map for: {missing_maps}" if missing_maps else "")

    carries = object_name in declared
    if not carries:
        report.add("read_returns_valid_records", True, f"skipped: no {object_name}")
        report.add("read_pagination_terminates", True, f"skipped: no {object_name}")
        report.add("write_is_idempotent", True, f"skipped: no {object_name}")
        report.add("write_rejects_invalid_payload", True, f"skipped: no {object_name}")
        report.add("round_trip", True, f"skipped: no {object_name}")
        _check_environment(report, connector)
        return report

    # 3. seed three records through the connector's own write path
    seeded = []
    for i in range(3):
        payload = _contact(connector.node_id or "node", i)
        try:
            result = connector.write(object_name, payload, f"conformance-seed-{i}")
        except Exception as exc:  # noqa: BLE001
            report.add("write_accepts_valid_payload", False,
                       f"{type(exc).__name__}: {exc}")
            break
        else:
            if not getattr(result, "ok", False):
                report.add("write_accepts_valid_payload", False,
                           f"write() reported not ok: {getattr(result, 'error', '')}")
                break
            seeded.append(payload)
    else:
        report.add("write_accepts_valid_payload", True)

    # 4. read validates against the canonical schema
    invalid: list[str] = []
    try:
        page = connector.read(object_name)
        for record in getattr(page, "records", []):
            problems = canonical.validate(object_name, record)
            if problems:
                invalid.append(problems[0])
    except Exception as exc:  # noqa: BLE001
        report.add("read_returns_valid_records", False, f"{type(exc).__name__}: {exc}")
    else:
        report.add("read_returns_valid_records", not invalid,
                   f"{invalid[0]}" if invalid else "")

    # 5. pagination terminates and does not loop
    try:
        cursor, seen, pages = None, 0, 0
        while True:
            page = connector.read(object_name, cursor)
            pages += 1
            seen += len(getattr(page, "records", []))
            cursor = getattr(page, "cursor", None)
            if cursor is None:
                break
            if pages > MAX_PAGES:
                raise ConnectorError("pagination did not terminate within 100 pages")
    except Exception as exc:  # noqa: BLE001
        report.add("read_pagination_terminates", False, f"{type(exc).__name__}: {exc}")
    else:
        report.add("read_pagination_terminates", True, f"{seen} records over {pages} pages")

    # 6. idempotency: the same key twice must not create a second record
    payload = _contact(connector.node_id or "node", 99)
    try:
        first = connector.write(object_name, payload, "conformance-idempotency")
        second = connector.write(object_name, payload, "conformance-idempotency")
        same = getattr(first, "external_id", None) == getattr(second, "external_id", None)
        report.add("write_is_idempotent", same,
                   "" if same else "the same key produced two external ids")
    except Exception as exc:  # noqa: BLE001
        report.add("write_is_idempotent", False, f"{type(exc).__name__}: {exc}")

    # 7. an invalid payload is rejected, with a taxonomy error
    bad = _contact(connector.node_id or "node", 50)
    del bad["full_name"]
    try:
        connector.write(object_name, bad, "conformance-invalid")
    except ConnectorError:
        report.add("write_rejects_invalid_payload", True)
    except Exception as exc:  # noqa: BLE001
        report.add("write_rejects_invalid_payload", False,
                   f"raised {type(exc).__name__}, which is not in the taxonomy")
    else:
        report.add("write_rejects_invalid_payload", False, "accepted a payload missing full_name")

    # 8. round trip
    try:
        found = False
        cursor, pages = None, 0
        while not found and pages < MAX_PAGES:
            page = connector.read(object_name, cursor)
            pages += 1
            found = any(r.get("id") == payload["id"] for r in page.records)
            cursor = page.cursor
            if cursor is None:
                break
        report.add("round_trip", found, "" if found else "written record not returned by read")
    except Exception as exc:  # noqa: BLE001
        report.add("round_trip", False, f"{type(exc).__name__}: {exc}")

    _check_environment(report, connector)
    return report


def _check_environment(report: Report, connector) -> None:
    """Health, rate limit, cost and the error taxonomy."""
    try:
        health = connector.health()
        status = getattr(health, "status", None)
        ok = status in ("online", "degraded", "offline", "buffering")
        report.add("health_is_valid", ok, "" if ok else f"status {status!r}")
    except Exception as exc:  # noqa: BLE001
        report.add("health_is_valid", False, f"{type(exc).__name__}: {exc}")

    try:
        limit = connector.rate_limit()
        ok = getattr(limit, "requests_per_minute", 0) > 0
        report.add("rate_limit_is_positive", ok,
                   "" if ok else "requests_per_minute must be positive")
    except Exception as exc:  # noqa: BLE001
        report.add("rate_limit_is_positive", False, f"{type(exc).__name__}: {exc}")

    try:
        cost = connector.cost_estimate("read", 1)
        ok = isinstance(cost, (int, float)) and cost >= 0
        report.add("cost_estimate_non_negative", ok,
                   "" if ok else f"cost {cost!r}")
    except Exception as exc:  # noqa: BLE001
        report.add("cost_estimate_non_negative", False, f"{type(exc).__name__}: {exc}")

    # the taxonomy is closed: a connector may not invent an exception type
    try:
        connector.read("NotAnObject")
    except ConnectorError:
        report.add("errors_are_from_the_taxonomy", True)
    except Exception as exc:  # noqa: BLE001
        report.add("errors_are_from_the_taxonomy", False,
                   f"raised {type(exc).__name__}, which is not a ConnectorError")
    else:
        report.add("errors_are_from_the_taxonomy", False,
                   "reading an unknown object did not raise")


def assert_conforms(connector, object_name: str = "Contact") -> Report:
    """Run the suite and raise if anything failed. For use in a connector's tests."""
    report = run_conformance(connector, object_name)
    if not report.ok:
        raise AssertionError(report.summary())
    return report
