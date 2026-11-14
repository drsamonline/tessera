"""Saved views and the report builder.

Reference: docs/17-constraints.md ("list view customisation", "report builder").
Deliverable 10.

Both reuse the automation condition language rather than inventing a second
filter grammar: a saved view and a workflow condition that mean the same thing
must parse the same way, or one of them is wrong and nobody knows which.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from . import automation


class ViewError(Exception):
    """Raised when a view or a report is not admissible."""


@dataclass
class SavedView:
    """A named filter over one object type, with a sort and a limit."""
    name: str
    object_name: str
    condition: str | None = None
    sort_by: str | None = None
    descending: bool = False
    limit: int | None = None

    def __post_init__(self):
        if self.condition:
            automation.parse(self.condition)  # a view that cannot parse is not a view
        if self.limit is not None and self.limit < 1:
            raise ViewError("a limit below one is not a limit")

    def apply(self, records: list[dict]) -> list[dict]:
        rows = records
        if self.condition:
            rows = [r for r in rows if self._matches(r)]
        if self.sort_by:
            rows = sorted(rows, key=lambda r: (r.get(self.sort_by) is None,
                                               r.get(self.sort_by)),
                          reverse=self.descending)
        if self.limit:
            rows = rows[:self.limit]
        return rows

    def _matches(self, record: dict) -> bool:
        try:
            return automation.evaluate(self.condition, record)
        except automation.AutomationError:
            # A record missing the field does not match the view. It is not an
            # error at this level: a list has to render something.
            return False


AGGREGATES = ("count", "sum", "mean", "min", "max")


@dataclass
class Report:
    """Group, aggregate, export. Three columns and a total, not a pivot engine."""
    object_name: str
    group_by: str
    aggregate: str = "count"
    field_name: str | None = None
    condition: str | None = None

    def __post_init__(self):
        if self.aggregate not in AGGREGATES:
            raise ViewError(f"unknown aggregate {self.aggregate!r}")
        if self.aggregate != "count" and not self.field_name:
            raise ViewError(f"{self.aggregate!r} needs a field to aggregate")
        if self.condition:
            automation.parse(self.condition)

    def run(self, records: list[dict]) -> list[dict]:
        rows = [r for r in records if self._matches(r)]
        groups: dict[str, list[dict]] = {}
        for row in rows:
            groups.setdefault(str(row.get(self.group_by, "—")), []).append(row)

        out = []
        for key in sorted(groups):
            members = groups[key]
            out.append({"group": key, "count": len(members),
                        "value": self._aggregate(members)})
        return out

    def _matches(self, record: dict) -> bool:
        if not self.condition:
            return True
        try:
            return automation.evaluate(self.condition, record)
        except automation.AutomationError:
            return False

    def _aggregate(self, members: list[dict]) -> float | None:
        if self.aggregate == "count":
            return len(members)
        values = [m.get(self.field_name) for m in members]
        values = [v for v in values if isinstance(v, (int, float))]
        if not values:
            return None
        if self.aggregate == "sum":
            return sum(values)
        if self.aggregate == "mean":
            return sum(values) / len(values)
        if self.aggregate == "min":
            return min(values)
        return max(values)

    def to_csv(self, records: list[dict]) -> str:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([self.group_by, "count", self.aggregate])
        for row in self.run(records):
            writer.writerow([row["group"], row["count"], row["value"]])
        return buffer.getvalue()


@dataclass
class ViewStore:
    """Saved views, per tenant, in memory."""
    views: dict[str, SavedView] = field(default_factory=dict)

    def save(self, view: SavedView) -> SavedView:
        self.views[view.name] = view
        return view

    def get(self, name: str) -> SavedView:
        if name not in self.views:
            raise ViewError(f"no saved view named {name!r}")
        return self.views[name]

    def names(self) -> list[str]:
        return sorted(self.views)
