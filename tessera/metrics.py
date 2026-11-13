"""Metrics, defined once.

Every score in the product has exactly one definition and it lives here, in
code, next to the document that specifies it: docs/10-metrics.md.

If this module and that document disagree, one of them is a defect. The tests
in tests/test_metrics.py are the tie-breaker.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

# Half-lives, in days. Changing one changes every historical score, so they are
# versioned alongside the metric itself.
TRUST_HALF_LIFE_DAYS = 21.0
TRUST_WINDOW_DAYS = 90.0
TRUST_MIN_SAMPLE = 20
TRUST_PRIOR = 0.5

RVS_HALF_LIFE_DAYS = 21.0
RVS_TYPE_WEIGHTS = {
    "meeting": 1.0,
    "call": 0.8,
    "email": 0.5,
    "ticket": 0.4,
    "note": 0.2,
    "marketing_touch": 0.1,
}

FRESHNESS_HALF_LIFE_HOURS = {"sales": 24.0, "support": 4.0}
METRICS_VERSION = "1.0.0"


def clamp(low: float, high: float, value: float) -> float:
    return max(low, min(high, value))


# ---------------------------------------------------------------------------
# Routing terms  (docs/10-metrics.md, "Normalization transforms")
# ---------------------------------------------------------------------------

def capability_match(required: list[str], manifest: list[str]) -> float:
    """|required ∩ manifest| / |required|. An empty requirement matches fully."""
    if not required:
        return 1.0
    have = set(manifest)
    return len([r for r in required if r in have]) / len(required)


def authority_match(mode: str) -> float:
    """authority or delegate 1.0, bidirectional 0.5, mirror 0.2."""
    return {"authority": 1.0, "delegate": 1.0, "bidirectional": 0.5, "mirror": 0.2}.get(
        mode, 0.0
    )


def sla_headroom(deadline: datetime, assigned_at: datetime, now: datetime) -> float:
    """clamp(0, 1, (deadline - now) / (deadline - assigned_at))."""
    total = (deadline - assigned_at).total_seconds()
    if total <= 0:
        return 0.0
    return clamp(0.0, 1.0, (deadline - now).total_seconds() / total)


def utilization(current_load: float, capacity: float) -> float:
    """1 - clamp(0, 1, load / capacity). A full node scores zero."""
    if capacity <= 0:
        return 0.0
    return 1.0 - clamp(0.0, 1.0, current_load / capacity)


def cost_efficiency(estimated_cost: float, budget: float) -> float:
    """1 - clamp(0, 1, cost / budget)."""
    if budget <= 0:
        return 0.0
    return 1.0 - clamp(0.0, 1.0, estimated_cost / budget)


def data_freshness(age_hours: float, category: str = "sales") -> float:
    """exp(-ln2 * age / half_life). Half-life 24 h for sales nodes, 4 h for support.

    The exponent carries ln(2) so that "half-life" means what it says: at one
    half-life the score is 0.5. The specification's first draft omitted it,
    which produced a 1/e life of 0.368 and made the term disagree with the
    relationship score's decay, which does halve. Fixed here; recorded in
    docs/20-reference-core.md.
    """
    half_life = FRESHNESS_HALF_LIFE_HOURS.get(category, 24.0)
    if age_hours < 0:
        age_hours = 0.0
    return math.exp(-math.log(2) * age_hours / half_life)


def cross_boundary_penalty(crosses: bool) -> float:
    return 1.0 if crosses else 0.0


def escalation_penalty(is_fallback_seat: bool) -> float:
    return 0.3 if is_fallback_seat else 0.0


# ---------------------------------------------------------------------------
# trust_score
# ---------------------------------------------------------------------------

def _age_days(observation_at: datetime, now: datetime) -> float:
    if observation_at.tzinfo is None:
        observation_at = observation_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return max(0.0, (now - observation_at).total_seconds() / 86400.0)


def trust_score(observations: list[dict], now: datetime | None = None) -> dict:
    """Clamped EWMA over 90 days of four rates, prior 0.5 below 20 samples.

    Each observation is a dict with `at` (datetime) and booleans:
    `success`, `escalated`, `conflict`, `audit_complete`.

    Returns {"score": float, "provisional": bool, "sample": int, "version": str}.
    """
    now = now or datetime.now(timezone.utc)
    recent = [o for o in observations if _age_days(o["at"], now) <= TRUST_WINDOW_DAYS]

    if len(recent) < TRUST_MIN_SAMPLE:
        return {
            "score": TRUST_PRIOR,
            "provisional": True,
            "sample": len(recent),
            "version": METRICS_VERSION,
        }

    num = 0.0
    den = 0.0
    for o in recent:
        weight = 0.5 ** (_age_days(o["at"], now) / TRUST_HALF_LIFE_DAYS)
        value = (
            0.40 * (1.0 if o.get("success") else 0.0)
            + 0.25 * (0.0 if o.get("escalated") else 1.0)
            + 0.20 * (0.0 if o.get("conflict") else 1.0)
            + 0.15 * (1.0 if o.get("audit_complete") else 0.0)
        )
        num += weight * value
        den += weight

    return {
        "score": clamp(0.0, 1.0, num / den if den else TRUST_PRIOR),
        "provisional": False,
        "sample": len(recent),
        "version": METRICS_VERSION,
    }


# ---------------------------------------------------------------------------
# Relationship Velocity Score
# ---------------------------------------------------------------------------

def rvs(
    interactions: list[tuple[str, datetime]],
    centrality: float,
    latency_asymmetry: float,
    now: datetime | None = None,
) -> float:
    """sum(decay * weight) * centrality / (1 + latency_asymmetry), normalized later.

    Reference implementation: a direct loop, in the order given.
    """
    now = now or datetime.now(timezone.utc)
    total = 0.0
    for kind, at in interactions:
        age = _age_days(at, now)
        weight = RVS_TYPE_WEIGHTS.get(kind, 0.0)
        total += (0.5 ** (age / RVS_HALF_LIFE_DAYS)) * weight
    asym = clamp(0.0, 3.0, latency_asymmetry)
    return total * clamp(0.0, 1.0, centrality) / (1.0 + asym)


def rvs_alt(
    interactions: list[tuple[str, datetime]],
    centrality: float,
    latency_asymmetry: float,
    now: datetime | None = None,
) -> float:
    """The same score computed a different way: fsum over a materialised list.

    This exists to be compared against `rvs`. Two implementations that agree to
    six decimal places on the same fixture are the acceptance criterion for
    deliverable 7; one implementation agreeing with itself is not a test.
    """
    now = now or datetime.now(timezone.utc)
    terms = [
        math.pow(0.5, _age_days(at, now) / RVS_HALF_LIFE_DAYS)
        * RVS_TYPE_WEIGHTS.get(kind, 0.0)
        for kind, at in interactions
    ]
    asym = min(3.0, max(0.0, latency_asymmetry))
    return math.fsum(terms) * min(1.0, max(0.0, centrality)) / (1.0 + asym)


def normalize_to_p95(value: float, p95: float) -> float:
    """Tenant-relative normalisation, so scores compare across tenant sizes."""
    if p95 <= 0:
        return 0.0
    return value / p95


# ---------------------------------------------------------------------------
# Forecast
# ---------------------------------------------------------------------------

def stage_probability(conversions: int, opportunities: int) -> float:
    """Trailing 12-month conversion for a stage. No smoothing, no overrides."""
    if opportunities <= 0:
        return 0.0
    return clamp(0.0, 1.0, conversions / opportunities)


def weighted_pipeline(rows: list[dict]) -> dict:
    """rows: [{"amount_minor": int, "probability": float, "override": float|None}]

    Returns the weighted total and the override delta, kept separate so an
    override is visible rather than folded silently into the number.
    """
    total = 0
    override_delta = 0
    for r in rows:
        base = r["amount_minor"] * r["probability"]
        total += base
        if r.get("override") is not None:
            override_delta += r["amount_minor"] * (r["override"] - r["probability"])
    return {
        "weighted_minor": int(round(total + override_delta)),
        "override_delta_minor": int(round(override_delta)),
        "rows": len(rows),
    }
