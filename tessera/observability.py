"""Measurement, so a performance claim can be checked.

Defect B-07 in the audit: "no measurement harness, no percentile window and no
regression gate for any latency target". This is the harness and the window. The
gate is `bench.py` plus whatever CI runs it.

A `Histogram` keeps raw samples in a bounded reservoir, so percentiles are exact
within the reservoir rather than estimated from buckets. Nearest-rank, not
interpolation: p95 means the smallest value at or above the 95th percentile, and
a reader can reproduce it with sorted samples and one index.
"""

from __future__ import annotations

import math
import time
from contextlib import contextmanager


class Histogram:
    """Bounded sample reservoir with exact percentiles over what it kept."""

    def __init__(self, name: str, capacity: int = 10_000):
        self.name = name
        self.capacity = capacity
        self.samples: list[float] = []
        self.total = 0
        self.overflow = 0

    def observe(self, value: float) -> None:
        self.total += 1
        if len(self.samples) < self.capacity:
            self.samples.append(float(value))
        else:
            # Deterministic reservoir: replace every k-th sample. Not uniform
            # random sampling, and it does not claim to be - it keeps the window
            # representative without a random source, so two runs at the same
            # scale produce the same percentiles.
            self.overflow += 1
            index = self.overflow % self.capacity
            self.samples[index] = float(value)

    def percentile(self, p: float) -> float:
        """Nearest-rank percentile over the retained samples. p in (0, 100]."""
        if not 0 < p <= 100:
            raise ValueError("p must be in (0, 100]")
        if not self.samples:
            return 0.0
        ordered = sorted(self.samples)
        # Nearest rank: the smallest sample at or above the p-th percentile.
        rank = max(1, math.ceil((p / 100.0) * len(ordered)))
        return ordered[min(rank - 1, len(ordered) - 1)]

    def snapshot(self) -> dict:
        if not self.samples:
            return {"name": self.name, "count": 0, "p50": 0.0, "p95": 0.0, "p99": 0.0,
                    "min": 0.0, "max": 0.0, "mean": 0.0, "overflow": self.overflow}
        ordered = sorted(self.samples)
        return {
            "name": self.name,
            "count": self.total,
            "retained": len(self.samples),
            "p50": self.percentile(50),
            "p95": self.percentile(95),
            "p99": self.percentile(99),
            "min": ordered[0],
            "max": ordered[-1],
            "mean": sum(ordered) / len(ordered),
            "overflow": self.overflow,
        }


class Registry:
    """Named histograms plus a timer. One registry per process is enough."""

    def __init__(self):
        self._h: dict[str, Histogram] = {}

    def histogram(self, name: str) -> Histogram:
        if name not in self._h:
            self._h[name] = Histogram(name)
        return self._h[name]

    def observe(self, name: str, value: float) -> None:
        self.histogram(name).observe(value)

    @contextmanager
    def timer(self, name: str):
        """`with registry.timer("ledger.append"): ...` records milliseconds."""
        start = time.perf_counter()
        try:
            yield
        finally:
            self.observe(name, (time.perf_counter() - start) * 1000.0)

    def snapshot(self) -> list[dict]:
        return [h.snapshot() for h in self._h.values()]

    def reset(self) -> None:
        self._h.clear()


REGISTRY = Registry()


def check_against_targets(snapshot: list[dict], targets: dict[str, dict]) -> list[dict]:
    """Compare measured percentiles to declared targets.

    `targets` maps a histogram name to {"p95": 100.0, ...} in milliseconds. A
    missing histogram is reported as `unmeasured`, never as passing: a gate that
    treats absence as success is not a gate.
    """
    by_name = {row["name"]: row for row in snapshot}
    results = []
    for name, limits in targets.items():
        row = by_name.get(name)
        if row is None or row.get("count", 0) == 0:
            results.append({"name": name, "status": "unmeasured", "detail": "no samples"})
            continue
        breaches = [
            f"{metric} {row[metric]:.2f}ms > {limit}ms"
            for metric, limit in limits.items()
            if row[metric] > limit
        ]
        results.append({
            "name": name,
            "status": "fail" if breaches else "pass",
            "detail": "; ".join(breaches),
        })
    return results
