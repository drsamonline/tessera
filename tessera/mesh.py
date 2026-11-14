"""The federation mesh.

Reference: docs/03-mesh.md. This module is the smallest thing that can honestly
be called a mesh: nodes register, records sync into a canonical store, fields
merge by the authority map, conflicts resolve with a recorded rule, and every
action lands in the ledger.

It does not do write-back scheduling, backpressure, or push subscription. It does
produce the activation event in docs/01-product.md, which is the only product
claim that has to be true on day one:

    a tenant connects two nodes of different categories, and the first canonical
    Contact renders in the unified view with at least one linked Activity
    sourced from each node.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from . import canonical, conflict
from .connector import Connector, ConnectorError
from .ledger import EventLog

MAX_PAGES = 100


@dataclass
class Node:
    """A registered node: a connector plus the policy the mesh applies to it."""
    id: str
    connector: Connector
    category: str
    authority: dict[str, str] = field(default_factory=dict)  # field -> mode
    trust: float = 0.5
    cost_per_write: float = 0.0


class Mesh:
    def __init__(self, tenant_id: str, log: EventLog | None = None):
        self.tenant_id = tenant_id
        self.log = log
        self.nodes: dict[str, Node] = {}
        # object -> record id -> node id -> payload
        self._store: dict[str, dict[str, dict[str, dict]]] = {}

    # -- registration ------------------------------------------------------
    def register(self, node: Node) -> None:
        if node.id in self.nodes:
            raise ValueError(f"node {node.id!r} is already registered")
        self.nodes[node.id] = node

    def nodes_for(self, object_name: str) -> list[Node]:
        out = []
        for node in self.nodes.values():
            caps = node.connector.capabilities()
            if caps and caps.supports(object_name, "read"):
                out.append(node)
        return out

    # -- sync --------------------------------------------------------------
    def sync(self, object_name: str) -> dict:
        """Pull every page from every node that carries the object.

        A record that fails canonical validation is counted and skipped, never
        stored: the canonical layer is where a bad shape stops.
        """
        counts: dict[str, int] = {}
        rejected: dict[str, int] = {}

        for node in self.nodes_for(object_name):
            stored = 0
            bad = 0
            cursor, pages = None, 0
            while True:
                try:
                    page = node.connector.read(object_name, cursor)
                except ConnectorError:
                    break
                for record in page.records:
                    problems = canonical.validate(object_name, record)
                    if problems:
                        bad += 1
                        continue
                    self._store.setdefault(object_name, {}).setdefault(
                        record["id"], {})[node.id] = record
                    stored += 1
                    if self.log:
                        self.log.append(
                            self.tenant_id, "system", f"{object_name.lower()}.sync",
                            {"fields": sorted(record)},
                            canonical_ref=canonical.make_ref(object_name, record["id"]),
                            source_node_id=node.id,
                        )
                cursor = page.cursor
                pages += 1
                if cursor is None or pages > MAX_PAGES:
                    break
            counts[node.id] = stored
            if bad:
                rejected[node.id] = bad

        return {"stored": counts, "rejected": rejected}

    # -- the unified view --------------------------------------------------
    def unified_view(self, object_name: str, record_id: str) -> dict:
        """One record, merged across nodes, with provenance on every field.

        This is the screen the product sells. Every field carries where it came
        from and which rule chose it; a field nobody could settle is reported as
        blocked rather than guessed.
        """
        candidates = self._store.get(object_name, {}).get(record_id, {})
        if not candidates:
            raise KeyError(f"no synced record {object_name}:{record_id}")

        fields: dict[str, dict] = {}
        conflicts: list[dict] = []
        blocked: list[str] = []

        all_fields = sorted({f for payload in candidates.values() for f in payload})

        for name in all_fields:
            options = []
            for node_id, payload in candidates.items():
                if name not in payload:
                    continue
                node = self.nodes[node_id]
                options.append(conflict.Conflict(
                    node_id=node_id,
                    value=payload[name],
                    valid_from=payload.get("valid_from", ""),
                    trust_score=node.trust,
                ))
            if not options:
                continue

            # Two nodes reporting the same value are not in conflict. Recording
            # that as one would bury the real disagreements in noise.
            distinct = {json.dumps(o.value, sort_keys=True, default=str) for o in options}
            if len(distinct) == 1:
                fields[name] = {
                    "value": options[0].value,
                    "source": "+".join(sorted(o.node_id for o in options)),
                    "rule": "agreement",
                    "blocked": False,
                }
                continue

            mode_map = {
                node_id: self.nodes[node_id].authority.get(name, "bidirectional")
                for node_id in candidates
            }
            record = conflict.resolve(name, options, authority_map=mode_map)

            if record["blocked"]:
                blocked.append(name)
                fields[name] = {
                    "value": None,
                    "source": None,
                    "rule": record["rule"],
                    "blocked": True,
                    "candidates": record["candidates"],
                }
            else:
                fields[name] = {
                    "value": record["value"],
                    "source": record["winner"],
                    "rule": record["rule"],
                    "blocked": False,
                }
            if record["rule"] not in ("single_source",):
                conflicts.append({
                    "field": name,
                    "rule": record["rule"],
                    "winner": record["winner"],
                    "blocked": record["blocked"],
                    "values": {row["node_id"]: row["value"] for row in record["candidates"]},
                })

        return {
            "object": object_name,
            "id": record_id,
            "nodes": sorted(candidates),
            "fields": fields,
            "conflicts": conflicts,
            "blocked_fields": blocked,
        }

    def record_ids(self, object_name: str) -> list[str]:
        return sorted(self._store.get(object_name, {}))

    # -- write -------------------------------------------------------------
    def write_field(self, object_name: str, record_id: str, name: str, value,
                    actor: str = "human") -> dict:
        """Write one field to the node that owns it.

        The owner is the node whose authority map claims the field. With no
        declared owner the write is refused: a mesh that guesses which system is
        authoritative is a mesh that corrupts one of them.
        """
        owners = [
            node for node in self.nodes.values()
            if node.authority.get(name) in ("authority", "delegate")
        ]
        if not owners:
            raise PermissionError(
                f"no node declares authority for {object_name}.{name}; "
                "declare one in the authority map before writing"
            )
        owner = owners[0]

        payload = dict(self._store[object_name][record_id][owner.id])
        payload[name] = value
        problems = canonical.validate(object_name, payload)
        if problems:
            raise ValueError("; ".join(problems[:3]))

        result = owner.connector.write(
            object_name, payload, f"{object_name}:{record_id}:{name}:{value}"
        )
        if not getattr(result, "ok", False):
            raise ConnectorError(f"write to {owner.id} failed: {result.error}")

        self._store[object_name][record_id][owner.id] = payload
        if self.log:
            self.log.append(
                self.tenant_id, actor, f"{object_name.lower()}.{name}.write",
                {"field": name, "value": value, "node": owner.id},
                canonical_ref=canonical.make_ref(object_name, record_id),
                source_node_id=owner.id,
            )
        return {"node": owner.id, "field": name, "value": value}

    # -- the activation event ---------------------------------------------
    def activation(self) -> dict:
        """Has the tenant reached the event defined in docs/01-product.md?

        Two nodes of different categories, one Contact visible in the unified
        view, and an Activity for that Contact sourced from each of them.
        """
        categories = {node.category for node in self.nodes.values()}
        if len(self.nodes) < 2 or len(categories) < 2:
            return {"reached": False, "reason": "fewer than two node categories",
                    "nodes": sorted(self.nodes)}

        for contact_id in self.record_ids("Contact"):
            by_node = self._store.get("Contact", {}).get(contact_id, {})
            if len(by_node) < 2:
                continue
            ref = canonical.make_ref("Contact", contact_id)
            sources = set()
            for activity in self._store.get("Activity", {}).values():
                for node_id, payload in activity.items():
                    if payload.get("subject_ref") == ref:
                        sources.add(node_id)
            if len(sources) >= 2:
                return {
                    "reached": True,
                    "contact": contact_id,
                    "categories": sorted(categories),
                    "activity_sources": sorted(sources),
                    "evidence": "contact in two nodes, activity from two nodes",
                }

        return {"reached": False, "reason": "no contact has activity from two nodes",
                "nodes": sorted(self.nodes)}
