"""Energy efficiency measures as fractional reductions of affected end uses."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from reapschema.config import EeiConfig


@dataclass(frozen=True)
class Measure:
    technology: str
    end_uses: tuple[str, ...]
    reduction: float


def eligible_measures(shares: dict[str, float], cfg: EeiConfig, min_share: float
                      ) -> list[str]:
    """Measures whose affected end uses carry at least ``min_share`` of annual energy."""
    out = []
    for name, m in cfg.measures.items():
        if sum(shares.get(e, 0.0) for e in m.end_uses) >= min_share:
            out.append(name)
    return out


def draw_measure(rng: np.random.Generator, shares: dict[str, float], cfg: EeiConfig) -> Measure:
    lo_hi = {name: m.reduction for name, m in cfg.measures.items()}
    candidates = [
        name for name in eligible_measures(shares, cfg, 0.0)
        if lo_hi[name][0] * sum(shares.get(e, 0.0) for e in cfg.measures[name].end_uses)
        >= cfg.min_savings_fraction
    ]
    if not candidates:
        candidates = [max(cfg.measures, key=lambda n: sum(
            shares.get(e, 0.0) for e in cfg.measures[n].end_uses))]
    name = str(rng.choice(sorted(candidates)))
    lo, hi = lo_hi[name]
    return Measure(name, tuple(cfg.measures[name].end_uses), float(rng.uniform(lo, hi)))


def savings_series(end_uses: dict[str, np.ndarray], measure: Measure) -> np.ndarray:
    """Hourly load reduction (same units as the end-use arrays) when the measure is active."""
    affected = [end_uses[e] for e in measure.end_uses if e in end_uses]
    if not affected:
        return np.zeros_like(next(iter(end_uses.values())))
    return measure.reduction * np.sum(affected, axis=0)
