"""Three-layer access control: object, field, row.

Reference: docs/04-core.md ("Security") and docs/09-cross-cutting.md.

    object-level   which object types a role may touch at all
    field-level    which fields a role may read, and which it may edit
    row-level      which records a role may see

All three are enforced **at the read path**, in one place, so every surface goes
through the same gate. That is the only way the "no client, API or MCP tool
bypasses it" claim in the specification is true rather than aspirational: if the
redaction happens in the handler, the next handler forgets.

The default is least privilege. A principal with no declared role is an auditor:
it may read every row and edit nothing. A default of "admin" would be convenient
and wrong, and the convenience is exactly how these layers rot.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import canonical

# Field classes. A field belongs to at most one class; anything not listed is
# "standard" and follows the role's standard rule.
FIELD_CLASSES = {
    "billing": {
        "Deal": ("amount_minor", "currency"),
        "Invoice": ("amount_minor", "currency", "number"),
    },
    "sensitive": {
        "Contact": ("email", "phone", "consent_state", "lawful_basis"),
        "Company": (),
        "Ticket": (),
        "Activity": (),
        "Task": (),
        "Seat": (),
        "Event": (),
        "Document": (),
        "Invoice": (),
        "Deal": (),
    },
}

OBJECTS_BY_ROLE = {
    "admin": set(canonical.OBJECTS),
    "manager": set(canonical.OBJECTS),
    "rep": {"Contact", "Company", "Deal", "Activity", "Task", "Document"},
    "support": {"Contact", "Company", "Ticket", "Activity", "Task", "Document"},
    "auditor": set(canonical.OBJECTS),
}

READ_CLASSES = {
    "admin": {"standard", "sensitive", "billing"},
    "manager": {"standard", "sensitive", "billing"},
    "rep": {"standard", "sensitive"},
    "support": {"standard", "sensitive"},
    "auditor": {"standard", "sensitive", "billing"},
}

EDIT_CLASSES = {
    "admin": {"standard", "sensitive", "billing"},
    "manager": {"standard", "sensitive", "billing"},
    "rep": {"standard"},
    "support": {"standard"},
    "auditor": set(),
}

ROW_SCOPE = {
    "admin": "all",
    "manager": "all",
    "rep": "owned",
    "support": "owned",
    "auditor": "all",
}

ROLES = tuple(OBJECTS_BY_ROLE)


class AccessDenied(Exception):
    """Raised when a caller asks for something its role does not allow."""


def field_class(object_name: str, field_name: str) -> str:
    for klass, table in FIELD_CLASSES.items():
        if field_name in table.get(object_name, ()):
            return klass
    return "standard"


@dataclass
class AccessPolicy:
    """The rules. One instance per deployment, passed to the read path."""

    roles: dict = field(default_factory=lambda: {
        role: {
            "objects": OBJECTS_BY_ROLE[role],
            "read": READ_CLASSES[role],
            "edit": EDIT_CLASSES[role],
            "rows": ROW_SCOPE[role],
        }
        for role in ROLES
    })

    def role_of(self, principal) -> dict:
        name = getattr(principal, "role", "auditor") or "auditor"
        if name not in self.roles:
            raise AccessDenied(f"unknown role {name!r}")
        return self.roles[name]

    # -- object level -----------------------------------------------------
    def can_touch_object(self, principal, object_name: str) -> bool:
        return object_name in self.role_of(principal)["objects"]

    # -- field level ------------------------------------------------------
    def can_read_field(self, principal, object_name: str, field_name: str) -> bool:
        if not self.can_touch_object(principal, object_name):
            return False
        return field_class(object_name, field_name) in self.role_of(principal)["read"]

    def can_edit_field(self, principal, object_name: str, field_name: str) -> bool:
        if not self.can_touch_object(principal, object_name):
            return False
        return field_class(object_name, field_name) in self.role_of(principal)["edit"]

    # -- row level --------------------------------------------------------
    def can_read_row(self, principal, object_name: str, record: dict) -> bool:
        if not self.can_touch_object(principal, object_name):
            return False
        scope = self.role_of(principal)["rows"]
        if scope == "all":
            return True
        if scope == "none":
            return False
        seat = getattr(principal, "seat_id", None)
        owner = record.get("owner_seat_id")
        # a record with no owner is not visible to an owner-scoped role: the
        # alternative is showing every unassigned record to every rep
        return bool(seat) and owner == seat

    # -- the one gate every read path calls -------------------------------
    def redact(self, principal, object_name: str, record: dict) -> dict:
        """Drop every field this role may not read.

        Silently dropping is deliberate: a 403 on a field tells an unauthorised
        caller that the field exists and holds something. The response simply
        does not contain it.
        """
        return {
            name: value for name, value in record.items()
            if self.can_read_field(principal, object_name, name)
        }

    def redact_or_deny(self, principal, object_name: str, record: dict) -> dict:
        if not self.can_read_row(principal, object_name, record):
            raise AccessDenied(f"{principal.id!r} may not read this {object_name}")
        return self.redact(principal, object_name, record)

    def filter_rows(self, principal, object_name: str, records: dict) -> dict:
        """`records` maps id -> record. Returns the visible subset, redacted."""
        out = {}
        for record_id, record in records.items():
            if not self.can_read_row(principal, object_name, record):
                continue
            out[record_id] = self.redact(principal, object_name, record)
        return out

    def denied_fields(self, principal, object_name: str) -> set[str]:
        """Every field this role cannot read. Used by the export and history paths."""
        spec = canonical.SCHEMA.get(object_name, {})
        return {name for name in spec
                if not self.can_read_field(principal, object_name, name)}


DEFAULT_POLICY = AccessPolicy()
