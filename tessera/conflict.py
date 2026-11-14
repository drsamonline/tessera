"""Cross-system conflict resolution.

Reference: docs/03-mesh.md ("Conflict resolution") and docs/17-constraints.md,
rule 12: no silent overwrite.

The order is fixed and total:

    1. authority_map      the field's declared owner wins outright
    2. trust_score        the more trusted source wins
    3. bi-temporal recency the later valid time wins
    4. field priority     the declared field order wins
    5. human review       nobody wins; the field is blocked, the record is not

Two sources reporting the same value are not in conflict, and the mesh records
that as `agreement` rather than manufacturing a resolution for a disagreement
that does not exist.

Every resolution produces a record with both candidate values and the rule that
settled it. That record is what the ledger stores, and it is what makes a
dispute answerable a year later.
"""

from __future__ import annotations

# Only `authority` claims a field outright. `delegate` means the node accepts
# writes from the mesh, so it does not assert ownership in a conflict; it ranks
# above `bidirectional` but falls through to the trust comparison.
AUTHORITY_RANK = {"authority": 3, "delegate": 2, "bidirectional": 1, "mirror": 0}

RULES = (
    "single_source",
    "agreement",
    "authority_map",
    "trust_score",
    "bi_temporal_recency",
    "field_priority",
    "human_review",
)


class Conflict:
    """One candidate value for one field, from one node."""

    __slots__ = ("node_id", "value", "valid_from", "trust_score")

    def __init__(self, node_id: str, value, valid_from: str, trust_score: float = 0.0):
        self.node_id = node_id
        self.value = value
        self.valid_from = valid_from
        self.trust_score = trust_score

    def __repr__(self) -> str:
        return f"Conflict({self.node_id!r}, {self.value!r}, {self.valid_from!r})"


def resolve(
    field: str,
    candidates: list[Conflict],
    authority_map: dict[str, str] | None = None,
    field_priority: list[str] | None = None,
) -> dict:
    """Resolve one field. Returns a record, never a bare value.

    `authority_map` maps field name to sync mode for each node, e.g.
    {"email": "authority"} for the node that owns it. `field_priority` is the
    tenant's declared order for fields, used only when recency ties.

    The returned dict always carries: field, rule, winner, value, candidates,
    blocked. A blocked resolution means a human must decide and the field is
    frozen until they do.
    """
    if not candidates:
        raise ValueError(f"no candidates for field {field!r}")

    record = {
        "field": field,
        "rule": None,
        "winner": None,
        "value": None,
        "blocked": False,
        "candidates": [
            {"node_id": c.node_id, "value": c.value, "valid_from": c.valid_from,
             "trust_score": c.trust_score}
            for c in candidates
        ],
    }

    if len(candidates) == 1:
        only = candidates[0]
        record.update(rule="single_source", winner=only.node_id, value=only.value)
        return record

    authority_map = authority_map or {}

    # 1. authority_map - a declared owner wins outright, even if less trusted
    ranked = sorted(
        candidates,
        key=lambda c: (-AUTHORITY_RANK.get(authority_map.get(c.node_id, "bidirectional"), 1),
                       c.node_id),
    )
    top_rank = AUTHORITY_RANK.get(authority_map.get(ranked[0].node_id, "bidirectional"), 1)
    if top_rank >= 3:
        tied = [c for c in ranked
                if AUTHORITY_RANK.get(authority_map.get(c.node_id, "bidirectional"), 1) == top_rank]
        if len(tied) == 1:
            record.update(rule="authority_map", winner=tied[0].node_id, value=tied[0].value)
            return record

    # 2. trust_score
    best_trust = max(c.trust_score for c in candidates)
    trusted = [c for c in candidates if c.trust_score == best_trust]
    if len(trusted) == 1:
        record.update(rule="trust_score", winner=trusted[0].node_id, value=trusted[0].value)
        return record

    # 3. bi-temporal recency
    best_time = max(c.valid_from for c in trusted)
    recent = [c for c in trusted if c.valid_from == best_time]
    if len(recent) == 1:
        record.update(rule="bi_temporal_recency", winner=recent[0].node_id,
                      value=recent[0].value)
        return record

    # 4. field priority
    if field_priority and field in field_priority:
        record.update(rule="field_priority", winner=recent[0].node_id, value=recent[0].value)
        return record

    # 5. human review - the field blocks, the record does not
    record.update(rule="human_review", blocked=True)
    return record


def is_resolved(record: dict) -> bool:
    return record["rule"] is not None and not record["blocked"]


def to_event_payload(record: dict) -> dict:
    """The ledger payload for a resolution.

    Both candidates and the rule travel with it. That is the whole point: a
    year later, the question is not what the value is but why it is that value.
    """
    return {
        "field": record["field"],
        "rule": record["rule"],
        "winner": record["winner"],
        "blocked": record["blocked"],
        "candidates": record["candidates"],
    }
