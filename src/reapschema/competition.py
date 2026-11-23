"""Scoring under 7 CFR 4280.140(d) and award selection under 4280.150.

Scores are computed from annual energy produced or saved, pre-installation use,
project cost, amount requested and energy price, plus criteria that do not depend
on energy evidence. Selection applies the reserve for small requests, the
top-applications-per-State step and rank order. The competition parameters are
hypothetical scenario values.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from reapschema.burden import load_transcribed
from reapschema.config import CompetitionConfig
from reapschema.units import BTU_PER_KWH


@dataclass(frozen=True)
class ScoringTables:
    pct_eei_bounds: np.ndarray
    pct_eei_points: np.ndarray
    pct_res_bounds: np.ndarray
    pct_res_points: np.ndarray
    payback_eei_bounds: np.ndarray
    payback_eei_points: np.ndarray
    payback_res_bounds: np.ndarray
    payback_res_points: np.ndarray
    energy_divisor: float
    energy_cap: float


def scoring_tables() -> ScoringTables:
    num: dict[str, Any] = load_transcribed("scoring_4280_140.yaml")["numeric"]

    def arr(key: str, field: str) -> np.ndarray:
        return np.asarray(num[key][field], dtype=float)

    return ScoringTables(
        arr("percent_saved_eei", "lower_bounds"), arr("percent_saved_eei", "points"),
        arr("percent_replaced_res", "lower_bounds"), arr("percent_replaced_res", "points"),
        arr("payback_eei", "upper_bounds"), arr("payback_eei", "points"),
        arr("payback_res", "upper_bounds"), arr("payback_res", "points"),
        float(num["energy_per_dollar"]["divisor_btu_per_dollar"]),
        float(num["energy_per_dollar"]["cap"]),
    )


def percent_points(percent: np.ndarray, bounds: np.ndarray, points: np.ndarray) -> np.ndarray:
    """Points for a percentage rounded to one decimal place (lower-bound bands)."""
    raw = np.nan_to_num(np.asarray(percent, dtype=float), nan=0.0, posinf=1e9, neginf=-1e9)
    p = np.floor(raw * 10.0 + 0.5 + 1e-9) / 10.0  # round half up
    idx = np.clip(np.searchsorted(bounds, p, side="right") - 1, 0, points.size - 1)
    return np.asarray(points[idx])


def payback_points(payback: np.ndarray, bounds: np.ndarray, points: np.ndarray) -> np.ndarray:
    """Points for simple payback in years: below the first bound, then successive bands."""
    pb = np.nan_to_num(np.asarray(payback, dtype=float), nan=np.inf)
    idx = np.searchsorted(bounds, pb, side="right")
    idx = np.where(pb == bounds[-1], bounds.size - 1, idx)  # last band includes its bound
    return points[np.clip(idx, 0, points.size - 1)]


def energy_points(energy_kwh: np.ndarray, request: np.ndarray, tables: ScoringTables
                  ) -> np.ndarray:
    """Equation 1/2 of 4280.140(d)(2): BTU per award dollar / 100, capped."""
    pts = np.maximum(energy_kwh, 0.0) * BTU_PER_KWH / request / tables.energy_divisor
    return np.asarray(np.minimum(np.round(pts, 2), tables.energy_cap))


def simple_payback(cost: np.ndarray, energy_kwh: np.ndarray, price: np.ndarray) -> np.ndarray:
    value = np.maximum(energy_kwh, 0.0) * price
    with np.errstate(divide="ignore"):
        return np.where(value > 0, cost / np.maximum(value, 1e-12), np.inf)


def energy_dependent_score(is_res: np.ndarray, energy_kwh: np.ndarray, pre_kwh: np.ndarray,
                           cost: np.ndarray, request: np.ndarray, price: np.ndarray,
                           tables: ScoringTables) -> np.ndarray:
    """Sum of the criteria that depend on energy evidence: (d)(2), (d)(3) and (d)(6)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        percent = 100.0 * energy_kwh / np.where(pre_kwh > 0, pre_kwh, np.nan)
    pb = simple_payback(cost, energy_kwh, price)
    pct = np.where(is_res,
                   percent_points(percent, tables.pct_res_bounds, tables.pct_res_points),
                   percent_points(percent, tables.pct_eei_bounds, tables.pct_eei_points))
    pay = np.where(is_res,
                   payback_points(pb, tables.payback_res_bounds, tables.payback_res_points),
                   payback_points(pb, tables.payback_eei_bounds, tables.payback_eei_points))
    return energy_points(energy_kwh, request, tables) + pct + pay


def eligible(is_res: np.ndarray, energy_kwh: np.ndarray, pre_kwh: np.ndarray,
             cost: np.ndarray, price: np.ndarray, useful_life: np.ndarray,
             has_storage: np.ndarray) -> np.ndarray:
    """Eligibility conditions that depend on energy evidence: 4280.122(a)(18) and (a)(19)."""
    ok = simple_payback(cost, energy_kwh, price) <= useful_life
    storage_ok = ~(is_res & has_storage) | (energy_kwh <= 1.2 * pre_kwh)
    return np.asarray(ok & storage_ok)


def other_points(rng: np.random.Generator, is_res: np.ndarray, cfg: CompetitionConfig
                 ) -> np.ndarray:
    """Hypothetical points for criteria that do not use energy evidence."""
    n = is_res.size
    p = cfg.points
    pts = 5.0 * (rng.random(n) < p.employees_prob) + 5.0 * (rng.random(n) < p.critical_service_prob)
    pts = pts + 3.0 + 1.0 * (rng.random(n) < p.forest_point_prob)
    pts = pts + np.where(is_res, 0.0, 1.0 * (rng.random(n) < p.water_point_prob))
    prior = rng.choice([15.0, 5.0, 0.0], size=n, p=[
        p.prior_award_probs["never"], p.prior_award_probs["not_within_two_years"],
        p.prior_award_probs["within_two_years"]])
    priority = rng.choice(np.asarray(p.priority_points_values, dtype=float), size=n,
                          p=p.priority_points_probs)
    return np.asarray(pts + prior + priority)


def select(score: np.ndarray, is_eligible: np.ndarray, state_code: np.ndarray,
           request: np.ndarray, tiebreak: np.ndarray, *, funds: float,
           cfg: CompetitionConfig) -> np.ndarray:
    """Award selection (4280.150). Returns a boolean array of funded applications.

    Applications requesting no more than the small-request threshold compete first
    for the reserve; those not funded join the general competition. The general
    competition funds the top applications per State in rank order, then all
    remaining applications in rank order, while funds permit and scores are at
    least the minimum. Funding stops at the first application that does not fit.
    Ties are broken by a fixed random key.
    """
    n = score.size
    funded = np.zeros(n, dtype=bool)
    ok = is_eligible & (score >= cfg.minimum_score)
    order = np.lexsort((tiebreak, -score))
    order = order[ok[order]]
    reserve = funds * cfg.small_request_reserve_share
    small = order[request[order] <= cfg.small_request_threshold]
    fits = np.cumsum(request[small]) <= reserve
    n_fit = int(np.argmin(fits)) if not fits.all() else fits.size
    funded[small[:n_fit]] = True
    remaining = funds - float(request[small[:n_fit]].sum())
    general = order[~funded[order]]
    if general.size == 0:
        return funded
    if cfg.top_per_state > 0:
        st = state_code[general]
        by_state = np.argsort(st, kind="stable")
        ranks = np.empty(general.size, dtype=int)
        sorted_states = st[by_state]
        starts = np.r_[0, np.flatnonzero(sorted_states[1:] != sorted_states[:-1]) + 1]
        group_start = np.repeat(starts, np.diff(np.r_[starts, general.size]))
        ranks[by_state] = np.arange(general.size) - group_start
        first = general[ranks < cfg.top_per_state]
        fits = np.cumsum(request[first]) <= remaining
        n_fit = int(np.argmin(fits)) if not fits.all() else fits.size
        funded[first[:n_fit]] = True
        remaining -= float(request[first[:n_fit]].sum())
        general = general[~funded[general]]
    fits = np.cumsum(request[general]) <= remaining
    n_fit = int(np.argmin(fits)) if not fits.all() else fits.size
    funded[general[:n_fit]] = True
    return funded


@dataclass(frozen=True)
class CompetitionDesign:
    """Fixed composition of the simulated competitions (common random numbers)."""

    members: np.ndarray  # (n_competitions, n_applicants) indices into the applicant pool
    tiebreak: np.ndarray  # (pool,)
    other: np.ndarray  # (pool,)
    state_code: np.ndarray  # (pool,)


def design_competitions(rng: np.random.Generator, pool_states: np.ndarray, is_res: np.ndarray,
                        cfg: CompetitionConfig) -> CompetitionDesign:
    pool = pool_states.size
    size = min(cfg.n_applicants, pool)
    members = np.stack([rng.choice(pool, size=size, replace=False)
                        for _ in range(cfg.n_competitions)])
    _, codes = np.unique(pool_states, return_inverse=True)
    return CompetitionDesign(members, rng.random(pool), other_points(rng, is_res, cfg), codes)


def selections(design: CompetitionDesign, score: np.ndarray, is_eligible: np.ndarray,
               request: np.ndarray, cfg: CompetitionConfig, funding_ratio: float | None = None
               ) -> np.ndarray:
    """Funded indicator for each competition; shape (n_competitions, n_applicants)."""
    ratio = cfg.funding_ratio if funding_ratio is None else funding_ratio
    out = np.zeros(design.members.shape, dtype=bool)
    total = score + design.other
    for c, idx in enumerate(design.members):
        funds = ratio * float(request[idx].sum())
        out[c] = select(total[idx], is_eligible[idx], design.state_code[idx], request[idx],
                        design.tiebreak[idx], funds=funds, cfg=cfg)
    return out


def selection_change(true_sel: np.ndarray, verified_sel: np.ndarray) -> np.ndarray:
    """Per-competition share of truly selected applications not selected after verification."""
    n_true = true_sel.sum(axis=1)
    displaced = (true_sel & ~verified_sel).sum(axis=1)
    return np.asarray(displaced / np.maximum(n_true, 1))
