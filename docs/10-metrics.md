# 10 - Metric dictionary

**Status: Frozen**

Every score has one definition, one normalization and one owner. This document is the only place a metric is
defined. A second definition anywhere else is a defect.

## Why this document exists

Seven scores drove routing, trust, forecasting and conflict resolution in the source document with no formula
that two engineers would implement identically. That is the largest single source of hidden rework, because
"deterministic" is exactly the property that was missing. *(Closes B-02, B-03.)*

## Normalization transforms

| Term | Transform | Range |
|---|---|---|
| `capability_match` | `|required ∩ manifest| / |required|` | `[0,1]` |
| `authority_match` | 1.0 if the field's authority map gives this node authority or delegate; 0.5 if bidirectional; 0.2 if mirror | `[0,1]` |
| `sla_headroom` | `clamp(0, 1, (deadline - now) / (deadline - assigned_at))` | `[0,1]` |
| `utilization` | `1 - clamp(0, 1, current_load / capacity)` | `[0,1]` |
| `cost_efficiency` | `1 - clamp(0, 1, estimated_cost / cost_budget)` | `[0,1]` |
| `trust_score` | see below | `[0,1]` |
| `data_freshness` | `exp(-age_hours / half_life_hours)`; half-life 24 h for sales nodes, 4 h for support | `[0,1]` |
| `cross_boundary_penalty` | 1.0 if the write crosses a declared privacy boundary, else 0 | `{0,1}` |
| `escalation_penalty` | 0.3 if the candidate is itself a fallback seat, else 0 | `{0, 0.3}` |

## trust_score

`trust_score` is consumed by routing, by conflict resolution and by the workforce router, and was never defined.
Definition: *(Closes B-02.)*

```
trust_score = clamp(0, 1, EWMA_90d(
      0.40 * success_rate
    + 0.25 * (1 - escalation_rate)
    + 0.20 * (1 - conflict_rate)
    + 0.15 * audit_completeness
))
```

- `success_rate` &mdash; completed tasks without rework or reversal.
- `escalation_rate` &mdash; tasks that reached an escalation trigger.
- `conflict_rate` &mdash; writes that lost a conflict resolution.
- `audit_completeness` &mdash; fraction of actions with a complete evidence set.
- Minimum sample 20 observations. Below that the prior 0.5 applies and the seat is marked provisional.
- Window 90 days with a 21-day EWMA half-life. Every recomputation is versioned, and the version is recorded on
  every decision that used it.

## Relationship Velocity Score

RVS was five adjectives. Definition: *(Closes B-03.)*

```
RVS = sum over interactions i of [ decay(Δt_i) * w_type(type_i) ]
      * centrality(entity) / (1 + latency_asymmetry)
```

- `decay(Δt) = 0.5 ^ (Δt_days / 21)` &mdash; half-life 21 days.
- `w_type`: meeting 1.0, call 0.8, email 0.5, ticket 0.4, note 0.2, marketing touch 0.1.
- `latency_asymmetry = |mean(response_hours_sent) - mean(response_hours_received)| / 24`, capped at 3.
- `centrality` &mdash; normalized degree in the relationship graph, computed nightly, range `[0,1]`.
- Output is normalized against the tenant's p95 RVS so the score is comparable across tenants of different size.
- Two independent implementations must agree to six decimal places on the published fixture. That is the
  acceptance test.

## Forecast

Weighted pipeline uses stage probability from trailing 12-month conversion per stage, recomputed nightly, with
each number linked to its evidence tree. Manual overrides are recorded as events and shown as overrides rather
than silently folded into the number.

## Definition of done for a metric

A metric is defined when it has all six: a formula, a normalization, a window, a minimum sample, a version, and
a reproducible fixture. Anything less is a label.
