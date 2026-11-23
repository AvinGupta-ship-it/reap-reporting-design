"""Burden-estimate audit and element-level respondent time model.

The audit checks the arithmetic of the burden figures published in the Paperwork
Reduction Act notice. The time model assigns respondent minutes to data elements by
collection mode; element times are scenario assumptions expressed as triangular
distributions and calibrated to the notice's per-response average.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from reapschema.config import BurdenConfig
from reapschema.provenance import REPO_ROOT
from reapschema.validate import OPTIONAL_ELEMENTS

TRANSCRIBED = REPO_ROOT / "data" / "transcribed"
N_PRE_BILLS = 12
N_POST_BILLS = 12
# elements whose content is contained in a utility billing-history file
BILL_FILE_ELEMENTS = ("billing_dates", "read_type", "bill_charges", "meter_ids",
                      "res_post_bills", "export_channel")


def load_transcribed(name: str) -> dict[str, Any]:
    """Load a double-entered transcription and require that both entries agree."""
    loaded: dict[str, Any] = yaml.safe_load((TRANSCRIBED / name).read_text())
    if loaded["entry_a"] != loaded["entry_b"]:
        raise ValueError(f"double-entry mismatch in {name}")
    return loaded


def _interval_contains(lo: float, hi: float, value: float) -> bool:
    return lo <= value < hi


def audit_notice(notice: dict[str, Any], inventory: dict[str, Any] | None = None
                 ) -> dict[str, Any]:
    """Arithmetic reconciliation of the published burden estimate.

    Checks whether respondents x responses-per-respondent reproduces the number of
    responses and whether responses x hours-per-response reproduces total hours,
    exactly and under two-decimal rounding or truncation of the published ratios.
    """
    n_resp = float(notice["respondents"])
    per_resp = float(notice["responses_per_respondent"])
    responses = float(notice["responses"])
    hours_each = float(notice["hours_per_response"])
    total = float(notice["total_hours"])
    product_responses = n_resp * per_resp
    product_hours = responses * hours_each
    implied_per_resp = responses / n_resp
    implied_hours_each = total / responses
    step = 0.01
    out: dict[str, Any] = {
        "respondents": n_resp,
        "responses_per_respondent": per_resp,
        "responses": responses,
        "hours_per_response": hours_each,
        "total_hours": total,
        "product_responses": product_responses,
        "responses_discrepancy": responses - product_responses,
        "product_hours": product_hours,
        "hours_discrepancy": total - product_hours,
        "hours_discrepancy_percent": 100.0 * (total - product_hours) / total,
        "implied_responses_per_respondent": implied_per_resp,
        "implied_hours_per_response": implied_hours_each,
        "hours_per_respondent": total / n_resp,
        "chained_product_hours": n_resp * per_resp * hours_each,
        # consistency of each published ratio with the published totals
        "responses_consistent_with_rounding": _interval_contains(
            per_resp - step / 2, per_resp + step / 2, implied_per_resp),
        "responses_consistent_with_truncation": _interval_contains(
            per_resp, per_resp + step, implied_per_resp),
        "hours_consistent_with_rounding": _interval_contains(
            hours_each - step / 2, hours_each + step / 2, implied_hours_each),
        "hours_consistent_with_truncation": _interval_contains(
            hours_each, hours_each + step, implied_hours_each),
        "rounded_implied_responses_per_respondent": round(implied_per_resp + 1e-12, 2),
        "rounded_implied_hours_per_response": round(implied_hours_each + 1e-12, 2),
        "truncated_implied_responses_per_respondent": math.floor(implied_per_resp * 100) / 100,
        "truncated_implied_hours_per_response": math.floor(implied_hours_each * 100) / 100,
        "type_of_request": notice.get("type_of_request", ""),
        "respondent_description": notice.get("respondent_description", ""),
    }
    if inventory is not None:
        inv_resp = float(inventory["annual_responses"])
        inv_hours = float(inventory["annual_hours"])
        out.update({
            "inventory_responses": inv_resp,
            "inventory_hours": inv_hours,
            "inventory_respondents": float(inventory["respondents"]),
            "inventory_hours_per_response": inv_hours / inv_resp,
            "inventory_responses_per_respondent": inv_resp / float(inventory["respondents"]),
            "inventory_hours_per_respondent": inv_hours / float(inventory["respondents"]),
            "change_responses_percent": 100.0 * (responses / inv_resp - 1.0),
            "change_hours_percent": 100.0 * (total / inv_hours - 1.0),
            "change_respondents_percent": 100.0 * (
                n_resp / float(inventory["respondents"]) - 1.0),
        })
    return out


def run_audit(notice_path: Path | None = None) -> dict[str, Any]:
    notice = load_transcribed("pra_notice_91FR62610.yaml")["entry_a"]
    inventory = load_transcribed("omb_inventory_0570-0067.yaml")["entry_a"]
    return audit_notice(notice, inventory)


# --- element time model -------------------------------------------------------------------


@dataclass(frozen=True)
class TimeParameter:
    name: str
    low: float
    mode: float
    high: float

    def sample(self, u: np.ndarray) -> np.ndarray:
        """Inverse-CDF sample of the triangular distribution at uniform draws ``u``."""
        if self.high <= self.low:
            return np.full_like(u, self.mode, dtype=float)
        c = (self.mode - self.low) / (self.high - self.low)
        left = self.low + np.sqrt(u * (self.high - self.low) * (self.mode - self.low))
        right = self.high - np.sqrt((1 - u) * (self.high - self.low) * (self.high - self.mode))
        return np.where(u < c, left, right)


def time_parameters(cfg: BurdenConfig) -> list[TimeParameter]:
    """Flat list of all triangular time parameters of the burden model."""
    params: list[TimeParameter] = []
    for name, tri in cfg.elements["required_evidence"].items():
        params.append(TimeParameter(f"required.{name}", *map(float, tri)))
    for name, spec in cfg.elements["optional"].items():
        for kind in ("per_bill", "per_post_bill", "fixed"):
            if kind in spec:
                params.append(TimeParameter(f"optional.{name}.{kind}", *map(float, spec[kind])))
    for mode, spec in cfg.modes.items():
        if "bill_block_minutes" in spec:
            params.append(TimeParameter(f"mode.{mode}.bill_block",
                                        *map(float, spec["bill_block_minutes"])))
    params.append(TimeParameter("rework", *map(float, cfg.rework_minutes)))
    return params


def modal_times(cfg: BurdenConfig) -> dict[str, float]:
    return {p.name: p.mode for p in time_parameters(cfg)}


def sample_times(cfg: BurdenConfig, rng: np.random.Generator, n: int) -> dict[str, np.ndarray]:
    return {p.name: p.sample(rng.random(n)) for p in time_parameters(cfg)}


def _applies(cfg: BurdenConfig, element: str, category: str) -> bool:
    target = cfg.elements["optional"][element].get("applies_to")
    return target is None or target == category


def burden_minutes(elements: frozenset[str] | set[str], mode: str, category: str,
                   times: dict[str, Any], cfg: BurdenConfig) -> Any:
    """Respondent minutes for the evidence under a specification, before calibration.

    ``times`` maps parameter names to scalars or arrays (Monte Carlo draws). Per-bill
    times apply to the twelve pre-installation bills, plus the twelve
    post-installation bills for EEI projects; post-installation utility bills of an
    RES are a separate optional element.
    """
    n_bills = N_PRE_BILLS + (N_POST_BILLS if category == "EEI" else 0)
    manual = mode == "manual_transcription"
    total: Any = times["required.annual_claim"] + times["required.energy_price"]
    if category == "RES":
        total = total + times["required.rated_capacity"]
    if manual:
        total = total + times["required.locate_bills"] + (
            n_bills * times["required.bill_energy_per_bill"])
    else:
        total = total + times[f"mode.{mode}.bill_block"]
    includes_interval = bool(cfg.modes[mode].get("includes_interval", False))
    for element in OPTIONAL_ELEMENTS:
        if element not in elements or not _applies(cfg, element, category):
            continue
        if not manual and element in BILL_FILE_ELEMENTS:
            continue
        if element == "utility_interval" and includes_interval:
            continue
        spec = cfg.elements["optional"][element]
        if "per_bill" in spec:
            total = total + n_bills * times[f"optional.{element}.per_bill"]
        if "per_post_bill" in spec:
            total = total + N_POST_BILLS * times[f"optional.{element}.per_post_bill"]
        if "fixed" in spec:
            total = total + times[f"optional.{element}.fixed"]
    return total


def calibration_factor(cfg: BurdenConfig, times: dict[str, Any], res_share: float,
                       hours_per_response: float) -> Any:
    """Scale that sets the current specification's mean burden to the notice's average.

    The pre- and post-installation energy evidence is treated as
    ``anchor_responses`` responses of the notice's average size.
    """
    if not cfg.calibrate_to_notice:
        return 1.0
    base = (res_share * burden_minutes(frozenset(), "manual_transcription", "RES", times, cfg)
            + (1 - res_share) * burden_minutes(frozenset(), "manual_transcription", "EEI",
                                               times, cfg))
    return cfg.anchor_responses * hours_per_response * 60.0 / base


def mean_burden(elements: frozenset[str] | set[str], mode: str, res_share: float,
                times: dict[str, Any], cfg: BurdenConfig, kappa: Any = 1.0,
                flag_rate: float = 0.0) -> Any:
    """Category-weighted burden in minutes including expected rework for flagged records."""
    mix = (res_share * burden_minutes(elements, mode, "RES", times, cfg)
           + (1 - res_share) * burden_minutes(elements, mode, "EEI", times, cfg))
    return kappa * (mix + flag_rate * times["rework"])
