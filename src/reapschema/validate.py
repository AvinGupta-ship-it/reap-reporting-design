"""Validation of performance evidence: schema validation and a rule layer.

Each rule returns a score for a submission; a submission is flagged when the score
exceeds the rule's threshold. Deterministic rules return 0 or 1. Statistical rules
return a continuous statistic so that operating characteristics can be traced over
thresholds. Rules declare which optional data elements they need, which determines
whether they can run under a given evidence specification.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jsonschema
import numpy as np

from reapschema.config import Config
from reapschema.mv import default_model
from reapschema.schema.build import GENERATED
from reapschema.synth.billing import Bills
from reapschema.synth.evidence import Evidence

OPTIONAL_ELEMENTS = (
    "billing_dates", "read_type", "bill_charges", "meter_ids", "res_post_bills",
    "export_channel", "inverter_monthly", "pv_geometry", "inverter_interval", "enduse_share",
    "claim_method", "utility_interval", "weather_normalization",
)


@dataclass(frozen=True)
class Rule:
    key: str
    description: str
    requires: frozenset[str]
    applies_to: str  # "RES", "EEI" or "both"
    # "deterministic" (score 0 or 1), "statistical" (threshold set to a target
    # false-positive rate) or "diagnostic" (reported, not used to flag errors)
    kind: str
    threshold: str | None = None  # name of a fixed ValidationConfig threshold, if any
    standardize: bool = False  # score is divided by a population scale before thresholding


def _r(key: str, description: str, requires: tuple[str, ...], applies_to: str,
       kind: str = "deterministic", threshold: str | None = None,
       standardize: bool = False) -> Rule:
    return Rule(key, description, frozenset(requires), applies_to, kind, threshold, standardize)


RULES: tuple[Rule, ...] = (
    _r("cf_range_claim", "Claimed production implies a capacity factor within bounds "
       "relative to modelled yield at the site", (), "RES"),
    _r("cf_range_inverter", "Sum of production-meter readings implies a capacity factor "
       "within bounds", ("inverter_monthly",), "RES"),
    _r("sum_check_pre", "Monthly pre-installation quantities sum to the stated annual "
       "pre-installation energy", (), "both"),
    _r("claim_recompute", "Claimed value equals the value recomputed from the submitted "
       "records", (), "EEI"),
    _r("claim_recompute_inverter", "Claimed production equals the sum of production-meter "
       "readings", ("inverter_monthly",), "RES"),
    _r("billing_continuity", "Billing periods are contiguous without gaps or overlaps",
       ("billing_dates",), "both"),
    _r("billing_days", "Each period and the twelve-period total have a plausible number of "
       "days", ("billing_dates",), "both"),
    _r("period_alignment", "Pre-installation periods end before, and post-installation "
       "periods begin after, the in-service date", ("billing_dates",), "both"),
    _r("account_consistency", "All records come from one dedicated account in both periods",
       ("meter_ids",), "both"),
    _r("charge_consistency", "Implied unit price per bill is consistent across bills and "
       "with the stated energy price", ("bill_charges",), "both"),
    _r("bill_outlier", "No billed quantity departs sharply from its neighbours", (), "both",
       "statistical"),
    _r("bill_outlier_dated", "No average daily use departs sharply from its neighbours",
       ("billing_dates",), "both", "statistical"),
    _r("export_consistency", "Exports are consistent with the metering arrangement and do "
       "not exceed or equal claimed production", ("res_post_bills", "export_channel"), "RES"),
    _r("bill_difference_unlabelled", "Claimed production agrees with the change in billed "
       "energy (billed quantity basis unknown)", ("res_post_bills",), "RES", "statistical",
       None, True),
    _r("bill_difference", "Claimed production agrees with pre-installation use minus "
       "delivered energy plus exports", ("res_post_bills", "export_channel"), "RES",
       "statistical", None, True),
    _r("plausibility_z", "Claimed production agrees with modelled production for the rated "
       "capacity and location (default array geometry)", (), "RES", "statistical", None, True),
    _r("plausibility_z_geometry", "Claimed production agrees with modelled production for "
       "the declared array geometry", ("pv_geometry",), "RES", "statistical", None, True),
    _r("monthly_shape", "Monthly production readings follow the modelled seasonal shape",
       ("inverter_monthly",), "RES", "statistical"),
    _r("enduse_bound", "Savings do not exceed the share of use in the affected end uses",
       ("enduse_share",), "EEI"),
    _r("payback_bounds", "Simple payback is neither implausibly short nor a large multiple "
       "of useful life", (), "both"),
    _r("model_fit", "Baseline degree-day model meets the CV(RMSE) criterion",
       ("billing_dates", "weather_normalization"), "EEI", "diagnostic", "cvrmse_max"),
)
RULE_BY_KEY = {r.key: r for r in RULES}

# compliance checks reported with the rule set but not used to detect reporting errors
COMPLIANCE_RULES = ("storage_120", "payback_useful_life", "estimated_share")


@lru_cache(maxsize=1)
def _json_schema() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((GENERATED / "reap_evidence.schema.json").read_text())
    return loaded


def schema_errors(package: dict[str, Any]) -> list[str]:
    """JSON Schema violations of an ``EvidencePackage`` instance (empty when valid)."""
    validator = jsonschema.Draft201909Validator(
        _json_schema(), format_checker=jsonschema.FormatChecker())
    return sorted(f"{'/'.join(str(p) for p in e.absolute_path)}: {e.message}"
                  for e in validator.iter_errors(package))


def _outlier_score(values: np.ndarray, scale_floor: float) -> float:
    v = np.log(np.maximum(np.asarray(values, dtype=float), 1e-9))
    if v.size < 4:
        return 0.0
    neighbours = np.empty_like(v)
    neighbours[1:-1] = 0.5 * (v[:-2] + v[2:])
    neighbours[0], neighbours[-1] = v[1], v[-2]
    d = v - neighbours
    scale = max(1.4826 * float(np.median(np.abs(d - np.median(d)))), scale_floor)
    return float(np.max(np.abs(d - np.median(d))) / scale)


def _contiguous(b: Bills) -> bool:
    return bool(np.all(b.start[1:] == b.end[:-1] + 1))


def rule_scores(ev: Evidence, cfg: Config, *, model_post_declared: float) -> dict[str, float]:
    """Scores of every applicable rule for one submission (NaN when not applicable)."""
    v = cfg.validation
    res = ev.category == "RES"
    out: dict[str, float] = {r.key: float("nan") for r in RULES}
    pre, post = ev.pre_bills, ev.post_bills
    pre_sum = float(pre.printed.sum())
    post_sum = float(post.printed.sum())

    out["sum_check_pre"] = float(
        abs(pre_sum - ev.claim_pre_energy) > v.claim_recompute_tolerance * max(
            abs(ev.claim_pre_energy), 1e-9))
    sets = [pre] if res else [pre, post]
    out["billing_continuity"] = float(not all(_contiguous(b) for b in sets))
    lo_t, hi_t = v.billing_days_total
    lo_e, hi_e = v.billing_days_each
    out["billing_days"] = float(any(
        not (lo_t <= int(b.days.sum()) <= hi_t) or bool(np.any((b.days < lo_e) | (b.days > hi_e)))
        for b in sets))
    gap = ev.in_service_day - int(pre.end.max())
    misaligned = gap < 1 or gap > v.period_alignment_days
    if not res:
        lead = int(post.start.min()) - ev.in_service_day
        misaligned = misaligned or lead < 0 or lead > v.period_alignment_days
    out["period_alignment"] = float(misaligned)
    out["account_consistency"] = float(
        bool(np.any(pre.n_accounts != 1)) or bool(np.any(post.n_accounts != 1)))
    tol = v.charge_consistency_tolerance
    inconsistent = False
    for b in sets:
        with np.errstate(divide="ignore", invalid="ignore"):
            implied = b.charge / np.where(b.delivered > 0, b.delivered, np.nan)
        med = float(np.nanmedian(implied))
        inconsistent = inconsistent or bool(np.nanmax(np.abs(implied / med - 1.0)) > tol)
        inconsistent = inconsistent or abs(med / ev.energy_price - 1.0) > tol
    out["charge_consistency"] = float(inconsistent)
    out["bill_outlier"] = max(_outlier_score(b.delivered, v.outlier_scale_floor) for b in sets)
    out["bill_outlier_dated"] = max(
        _outlier_score(b.delivered / b.days, v.outlier_scale_floor) for b in sets)
    value = ev.claim_value
    payback = ev.project_cost / max(value * ev.energy_price, 1e-9) if value > 0 else float("inf")
    out["payback_bounds"] = float(
        payback < v.payback_lower_bound_years
        or payback > v.payback_upper_multiple * ev.useful_life_years)

    if res:
        daily = default_model(ev.state, cfg.mv, cfg.population.res)
        d0 = ev.in_service_day
        model_default = ev.capacity_kw * float(daily[d0:d0 + 365].sum())
        lo, hi = v.capacity_factor_bounds_rel
        inv_sum = float(ev.inverter_kwh.sum())
        out["cf_range_claim"] = float(not (lo <= value / model_default <= hi))
        out["cf_range_inverter"] = float(not (lo <= inv_sum / model_default <= hi))
        out["claim_recompute_inverter"] = float(
            abs(value - inv_sum) > v.claim_recompute_tolerance * max(inv_sum, 1e-9))
        exported = float(post.export.sum())
        bad_export = (ev.arrangement == "none" and exported > 0) or exported > (
            1.0 + v.export_excess_tolerance) * value
        bad_export = bad_export or (exported > 0 and abs(value - exported)
                                    < v.export_equal_tolerance * exported)
        out["export_consistency"] = float(bad_export)
        util_unlabelled = pre_sum - post_sum
        util = pre_sum - float(post.delivered.sum()) + exported
        out["bill_difference_unlabelled"] = _log_ratio(value, util_unlabelled)
        out["bill_difference"] = _log_ratio(value, util)
        out["plausibility_z"] = _log_ratio(value, model_default)
        out["plausibility_z_geometry"] = _log_ratio(value, model_post_declared)
        monthly_model = np.array([daily[a:b + 1].sum() for a, b in
                                  zip(ev.inverter_start, ev.inverter_end, strict=True)])
        ratio = np.log(np.maximum(ev.inverter_kwh, 1e-9)
                       / np.maximum(ev.capacity_kw * monthly_model, 1e-9))
        out["monthly_shape"] = float(np.max(np.abs(ratio - np.median(ratio))))
    else:
        recomputed = pre_sum - post_sum
        out["claim_recompute"] = float(
            abs(value - recomputed) > v.claim_recompute_tolerance * max(abs(pre_sum), 1e-9))
        fraction = value / max(ev.claim_pre_energy, 1e-9)
        out["enduse_bound"] = float(fraction > ev.enduse_share + v.enduse_bound_tolerance)
    return out


def _log_ratio(a: float, b: float) -> float:
    """Signed log ratio; a large sentinel when either quantity is not positive."""
    if a <= 0 or b <= 0:
        return 20.0
    return float(np.log(a / b))


def active_rules(elements: frozenset[str] | set[str], category: str) -> list[Rule]:
    """Rules that can run when the given optional elements are collected."""
    return [r for r in RULES if r.requires <= set(elements)
            and r.applies_to in ("both", category)]
