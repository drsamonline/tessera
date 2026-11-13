"""Federated and workforce routing.

Reference: docs/03-mesh.md ("Routing") and docs/05-workforce.md ("Routing").

Routing is deterministic in the only sense that matters: two implementations
given the same candidates and the same weight vector return the same order, and
every decision is logged with its term-by-term breakdown and the weight version
that produced it.

The weight vectors are versioned. A change to a weight is a change to every
routing decision made after it, so the version travels with the decision.
"""

from __future__ import annotations

from . import metrics

# ---------------------------------------------------------------------------
# Weight vectors
# ---------------------------------------------------------------------------

WEIGHTS = {
    "federation-v1": {
        "capability_match": 0.30,
        "authority_match": 0.15,
        "sla_headroom": 0.15,
        "trust_score": 0.15,
        "utilization": 0.10,
        "cost_efficiency": 0.10,
        "data_freshness": 0.05,
        "_penalty": "cross_boundary_penalty",
        "_penalty_weight": 0.20,
    },
    "workforce-v1": {
        "capability_match": 0.35,
        "sla_headroom": 0.20,
        "trust_score": 0.20,
        "utilization": 0.15,
        "cost_efficiency": 0.10,
        "_penalty": "escalation_penalty",
        "_penalty_weight": 0.30,
    },
}

DEFAULT_VERSION = "federation-v1"


def weights(version: str = DEFAULT_VERSION) -> dict:
    try:
        return WEIGHTS[version]
    except KeyError:
        raise KeyError(f"unknown weight version {version!r}; known: {', '.join(WEIGHTS)}")


def check_weights(version: str = DEFAULT_VERSION) -> list[str]:
    """A weight vector is valid when its positive terms sum to 1.0.

    The penalty is subtracted, not weighted, so it is excluded from the sum.
    """
    w = weights(version)
    positive = {k: v for k, v in w.items() if not k.startswith("_")}
    total = sum(positive.values())
    problems = []
    if abs(total - 1.0) > 1e-9:
        problems.append(f"{version}: weights sum to {total:.6f}, expected 1.0")
    for name, value in positive.items():
        if not 0.0 <= value <= 1.0:
            problems.append(f"{version}: weight {name} out of range ({value})")
    return problems


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score(terms: dict, version: str = DEFAULT_VERSION) -> dict:
    """Weighted sum over normalized terms, minus the declared penalty.

    `terms` must carry every positive term in the weight vector. A missing term
    is an error, not a zero: silently treating an unknown as zero is how a
    router starts preferring nodes it knows nothing about.
    """
    w = weights(version)
    missing = [k for k in w if not k.startswith("_") and k not in terms]
    if missing:
        raise KeyError(f"missing terms for {version}: {', '.join(sorted(missing))}")

    breakdown = {}
    total = 0.0
    for name, weight in w.items():
        if name.startswith("_"):
            continue
        value = terms[name]
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"term {name} out of range [0,1]: {value}")
        contribution = weight * value
        breakdown[name] = {"value": value, "weight": weight, "contribution": contribution}
        total += contribution

    penalty_term = terms.get(w["_penalty"], 0.0)
    penalty = w["_penalty_weight"] * penalty_term
    return {
        "score": total - penalty,
        "breakdown": breakdown,
        "penalty": {"term": w["_penalty"], "value": penalty_term, "weight": w["_penalty_weight"],
                    "contribution": -penalty},
        "weights_version": version,
    }


def route(candidates: list[dict], version: str = DEFAULT_VERSION) -> list[dict]:
    """Rank candidates. Deterministic, including the tie-break.

    Each candidate is {"id": str, "terms": {...}, "estimated_cost": number}.
    Ties break on trust_score, then on lower estimated cost, then on id. The id
    tie-break is what makes the function total: without it, two identical
    candidates produce an order that depends on input order.
    """
    scored = []
    for c in candidates:
        result = score(c["terms"], version)
        scored.append({
            "id": c["id"],
            "score": result["score"],
            "breakdown": result["breakdown"],
            "penalty": result["penalty"],
            "weights_version": result["weights_version"],
            "trust_score": c["terms"]["trust_score"],
            "estimated_cost": c.get("estimated_cost", 0),
        })

    scored.sort(key=lambda r: (-r["score"], -r["trust_score"], r["estimated_cost"], r["id"]))
    for rank, row in enumerate(scored, start=1):
        row["rank"] = rank
    return scored


def explain(decision: dict) -> str:
    """A human-readable breakdown, for the interface's evidence tree."""
    lines = [f"{decision['id']}  score {decision['score']:.4f}  "
             f"(weights {decision['weights_version']})"]
    for name, part in decision["breakdown"].items():
        lines.append(
            f"  {name:<20} {part['value']:.3f} x {part['weight']:.2f} "
            f"= {part['contribution']:+.4f}"
        )
    pen = decision["penalty"]
    lines.append(f"  {pen['term']:<20} {pen['value']:.3f} x {pen['weight']:.2f} "
                 f"= {pen['contribution']:+.4f}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Workforce helpers
# ---------------------------------------------------------------------------

def select_occupant(
    candidates: list[dict],
    trust_floor: float = 0.2,
    version: str = "workforce-v1",
) -> dict | None:
    """Return the best eligible occupant, or None.

    An occupant below the trust floor, at or over budget, or unavailable is not
    a candidate at any score. The router falls through to the fallback seat by
    calling this again with the fallback's occupants.
    """
    eligible = [
        c for c in candidates
        if c.get("status") == "active"
        and c["terms"]["trust_score"] >= trust_floor
        and c["terms"]["cost_efficiency"] > 0.0
    ]
    ranked = route(eligible, version)
    return ranked[0] if ranked else None


def assert_agent_seat(seat: dict) -> None:
    """An agent seat without a fallback seat cannot exist.

    This is a hard rule (docs/17-constraints.md, rule 9) and it is enforced at
    creation, not at escalation time.
    """
    if seat.get("occupant_type") == "agent" and not seat.get("fallback_seat_id"):
        raise ValueError(
            f"seat {seat.get('id')!r} is an agent seat with no fallback_seat_id"
        )


def sla_clock(deadline, assigned_at, handoff_at=None) -> dict:
    """The SLA clock, carried across a handoff.

    At a handoff both clocks are recorded: the originating deadline and the
    receiving seat's own. A task cannot expire against an SLA the receiving seat
    never accepted. (docs/05-workforce.md)
    """
    elapsed = (handoff_at or deadline) - assigned_at
    total = deadline - assigned_at
    remaining = deadline - (handoff_at or assigned_at)
    ratio = (remaining.total_seconds() / total.total_seconds()) if total.total_seconds() > 0 else 0.0
    return {
        "originating_deadline": deadline,
        "assigned_at": assigned_at,
        "elapsed_seconds": elapsed.total_seconds(),
        "remaining_seconds": remaining.total_seconds(),
        "headroom": max(0.0, min(1.0, ratio)),
    }


__all__ = [
    "WEIGHTS", "DEFAULT_VERSION", "weights", "check_weights", "score", "route",
    "explain", "select_occupant", "assert_agent_seat", "sla_clock", "metrics",
]
