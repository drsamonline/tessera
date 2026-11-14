"""The migration wizard.

Reference: docs/07-experience.md ("Migration as experience"). Deliverable 13.

A migration is three things the importer already knows how to do, in front of it:

    auto_map     read a source export's headers and guess the canonical mapping
    transform    rewrite the file with canonical columns, so the importer stays simple
    dry_run      validate the whole thing and write nothing

Plus the two pieces that make switching cost less than an hour rather than less
than a day: a keyboard shortcut translator and a template gallery.

The honesty rule for the wizard is the same one the dry run has: it must show what
the commit will do. A migration preview that reports a different number from the
migration is worse than no preview, because somebody signs off on it.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from . import bulk, canonical

SOURCES = ("hubspot", "salesforce", "zendesk")

# Canonical field -> the header spellings the three sources actually export. The
# keys are normalised: lowercase, punctuation collapsed to a single underscore.
ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "Contact": {
        "full_name": ("full_name", "name", "full name", "contact name",
                      "first name last name"),
        "email": ("email", "e_mail", "email address", "e mail address", "primary email"),
        "phone": ("phone", "phone number", "mobile", "mobile phone", "telephone",
                  "work phone"),
        "valid_from": ("created at", "created date", "create date", "created",
                       "created date time"),
        # `owner_seat_id` is deliberately absent. A source system's owner is a name
        # or a foreign identifier, not a canonical seat uuid, and auto-mapping it
        # produces a column that fails validation on every row - which looks like
        # a broken file rather than a mapping the wizard should not have guessed.
    },
    "Company": {
        "name": ("name", "company", "company name", "account name", "organization",
                 "organisation"),
        "domain": ("domain", "website", "web site", "company domain", "url"),
        "industry": ("industry", "sector", "vertical"),
        "valid_from": ("created at", "created date", "create date"),
    },
    "Deal": {
        "name": ("name", "deal name", "opportunity name", "subject", "title"),
        "amount_minor": ("amount", "deal value", "value", "amount in company currency",
                         "opportunity value"),
        "currency": ("currency", "currency code", "deal currency", "currencyisocode"),
        "stage": ("stage", "deal stage", "opportunity stage", "status", "stagename"),
        "close_date": ("close date", "expected close date", "closedate"),
        "valid_from": ("created at", "created date", "create date"),
    },
    "Ticket": {
        "subject": ("subject", "ticket subject", "title", "summary"),
        "status": ("status", "ticket status", "state"),
        "priority": ("priority", "urgency"),
        "valid_from": ("created at", "created date", "create date"),
    },
}

# Columns that carry a source system's own identifier. They have no canonical home
# - a provider id is not a canonical uuid - and the wizard says so rather than
# pretending they mapped.
SOURCE_ID_COLUMNS = {"record id", "id", "hs_object_id", "salesforce id", "zendesk id",
                     "external id"}

# Two source columns that join into one canonical field.
COMPOSITES = {
    "full_name": (("first name", "last name"), ("firstname", "lastname")),
}

# Columns whose value is in major units and must be stored in minor units.
MINOR_UNIT_FIELDS = {"amount_minor"}


def normalise(header: str) -> str:
    text = header.strip().lower()
    for character in "-_/.":
        text = text.replace(character, " ")
    return " ".join(text.split())


@dataclass
class Mapping:
    object_name: str
    columns: dict[str, str] = field(default_factory=dict)     # source column -> field
    composites: dict[str, tuple[str, str]] = field(default_factory=dict)
    unmapped: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)

    @property
    def coverage(self) -> dict:
        required = {name for name, (_kind, req) in canonical.SCHEMA[self.object_name].items()
                    if req}
        mapped = set(self.columns.values()) | set(self.composites)
        needed = required - {"id", "tenant_id", "tx_time", "consent_state",
                             "lawful_basis", "purpose_id", "retention_policy_id"}
        covered = needed & mapped
        return {
            "required": sorted(needed),
            "mapped": sorted(covered),
            "missing": sorted(needed - covered),
            "percent": round(100.0 * len(covered) / len(needed), 1) if needed else 100.0,
        }


def auto_map(headers: list[str], object_name: str) -> Mapping:
    """Guess the mapping. Returns what it found, what it did not, and the coverage."""
    if object_name not in ALIASES:
        raise bulk.BulkError(f"no migration map for {object_name!r}")

    aliases = ALIASES[object_name]
    normalised = {header: normalise(header) for header in headers}
    mapping = Mapping(object_name=object_name)

    for header, text in normalised.items():
        if text in SOURCE_ID_COLUMNS:
            mapping.source_ids.append(header)
            continue
        matched = None
        for field_name, spellings in aliases.items():
            if text in spellings and field_name not in mapping.columns.values():
                matched = field_name
                break
        if matched:
            mapping.columns[header] = matched
        else:
            mapping.unmapped.append(header)

    for field_name, pairs in COMPOSITES.items():
        if field_name in mapping.columns.values() or field_name not in aliases:
            continue
        for first, last in pairs:
            first_header = _find(normalised, first)
            last_header = _find(normalised, last)
            if first_header and last_header:
                mapping.composites[field_name] = (first_header, last_header)
                for header in (first_header, last_header):
                    if header in mapping.unmapped:
                        mapping.unmapped.remove(header)
                break

    return mapping


def _find(normalised: dict[str, str], text: str) -> str | None:
    for header, value in normalised.items():
        if value == text:
            return header
    return None


def transform(csv_text: str, mapping: Mapping) -> str:
    """Rewrite the file with canonical headers, joining composites and scaling money.

    The importer stays simple because this does the awkward part: a migration is
    where source quirks belong, not in the thing every import shares.
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    fields = list(mapping.columns.values()) + list(mapping.composites)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()

    for row in reader:
        out = {}
        for column, field_name in mapping.columns.items():
            value = row.get(column)
            if value in (None, ""):
                continue
            if field_name in MINOR_UNIT_FIELDS:
                try:
                    value = str(int(round(float(value) * 100)))
                except ValueError:
                    continue  # an amount that is not a number is left to validation
            out[field_name] = value
        for field_name, (first, last) in mapping.composites.items():
            parts = [row.get(first, "").strip(), row.get(last, "").strip()]
            joined = " ".join(part for part in parts if part)
            if joined:
                out[field_name] = joined
        if out:
            writer.writerow(out)
    return buffer.getvalue()


class Migration:
    """One migration: map, preview, commit, roll back."""

    def __init__(self, log, tenant_id: str):
        self.log = log
        self.tenant_id = tenant_id
        self.importer = bulk.Importer(log, tenant_id)
        self.mapping: Mapping | None = None

    def prepare(self, csv_text: str, object_name: str,
                defaults: dict | None = None) -> dict:
        reader = csv.DictReader(io.StringIO(csv_text))
        headers = list(reader.fieldnames or [])
        self.mapping = auto_map(headers, object_name)
        normalised = transform(csv_text, self.mapping)
        preview = bulk.preview(normalised, object_name, {f: f for f in
                                                          (list(self.mapping.columns.values())
                                                           + list(self.mapping.composites))},
                               defaults)
        return {
            "object": object_name,
            "mapping": dict(self.mapping.columns),
            "composites": dict(self.mapping.composites),
            "unmapped": list(self.mapping.unmapped),
            "source_ids": list(self.mapping.source_ids),
            "coverage": self.mapping.coverage,
            "preview": {"ready": preview["ready"], "rejected": preview["rejected"],
                        "problems": preview["problems"]},
        }

    def commit(self, csv_text: str, object_name: str, defaults: dict | None = None,
               actor: str = "human") -> dict:
        # Always re-derive the mapping from the file being committed. Caching it
        # meant a second migration on the same object silently reused the first
        # file's headers and imported nothing, which reads as a broken file rather
        # than a stale map. (R-15)
        self.prepare(csv_text, object_name, defaults)
        normalised = transform(csv_text, self.mapping)
        identity = {f: f for f in (list(self.mapping.columns.values())
                                   + list(self.mapping.composites))}
        result = self.importer.commit(normalised, object_name, identity, defaults, actor)
        if self.log:
            self.log.append(self.tenant_id, actor, "migration.committed",
                            {"object": object_name, "batch": result["batch"],
                             "imported": result["imported"],
                             "coverage": self.mapping.coverage["percent"]},
                            source_node_id="migration")
        return result

    def rollback(self, batch_id: str, actor: str = "human") -> dict:
        result = self.importer.rollback(batch_id, actor)
        if self.log:
            self.log.append(self.tenant_id, actor, "migration.rolled_back",
                            {"batch": batch_id, "count": result["rolled_back"]},
                            source_node_id="migration")
        return result


# ---------------------------------------------------------------------------
# Keyboard shortcut translator
# ---------------------------------------------------------------------------

SHORTCUTS = {
    "hubspot": {"c": "n", "e": "e", "/": "/", "g then c": "g then c"},
    "salesforce": {"ctrl+s": "ctrl+s", "ctrl+n": "n", "/": "/", "shift+?": "?"},
    "zendesk": {"n": "n", "e": "e", "/": "/", "esc": "esc"},
}


def translate_shortcut(source: str, keys: str) -> str:
    """Map a shortcut from a source system to the one this product uses.

    Unknown shortcuts are returned unchanged rather than silently dropped: a
    translator that hides what it did not understand is a translator nobody
    trusts on the second day.
    """
    if source not in SHORTCUTS:
        raise bulk.BulkError(f"no shortcut map for {source!r}")
    return SHORTCUTS[source].get(keys.strip().lower(), keys.strip())


# ---------------------------------------------------------------------------
# Template gallery
# ---------------------------------------------------------------------------

TEMPLATES = {
    "pipeline.agency": {
        "kind": "pipeline",
        "name": "Agency retainer pipeline",
        "stages": ["Enquiry", "Scoping", "Proposal", "Negotiation", "Won", "Lost"],
    },
    "seat.support_triage": {
        "kind": "seat",
        "name": "Support triage",
        "capability_manifest": ["email", "triage"],
        "sla_seconds": 900,
        "escalation_ladder": ["seat.support_specialist"],
    },
    "org.support_desk": {
        "kind": "org",
        "name": "Support desk",
        "seats": ["seat.support_triage", "seat.support_specialist"],
        "escalation": {"seat.support_triage": ["seat.support_specialist"]},
    },
}


def install_template(template_id: str) -> dict:
    """One click, one object graph. The gallery is the cheapest onboarding there is."""
    if template_id not in TEMPLATES:
        raise bulk.BulkError(f"unknown template {template_id!r}")
    template = TEMPLATES[template_id]
    return dict(template, installed=True, template_id=template_id)


def gallery() -> list[dict]:
    return [dict(template, template_id=key) for key, template in TEMPLATES.items()]
