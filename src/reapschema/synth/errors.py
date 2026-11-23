"""Controlled injection of reporting errors with ground-truth labels.

Error classes follow the kinds of problem described in USDA OIG audit
34001-0001-21 and in the measurement literature. Class rates are scenario
parameters, not estimates of error prevalence in REAP submissions.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from reapschema.config import ErrorConfig
from reapschema.synth.billing import Bills
from reapschema.synth.evidence import Evidence

ERROR_CLASSES = ("unit", "transposed_digits", "wrong_period", "double_counting", "gross_net",
                 "nameplate_hours")
RES_ONLY = ("gross_net", "nameplate_hours")
# classes that arise when values are typed by hand from paper or PDF bills
TRANSCRIPTION_CLASSES = ("unit", "transposed_digits")


@dataclass(frozen=True)
class ErrorLabel:
    error_class: str  # "none" or one of ERROR_CLASSES
    variant: str = ""
    target: str = ""  # which evidence item carries the error
    magnitude: float = 0.0


def transpose_digits(value: float, rng: np.random.Generator) -> float:
    """Swap two adjacent, different digits of the integer part of ``value``."""
    digits = list(str(int(round(abs(value)))))
    pairs = [i for i in range(len(digits) - 1) if digits[i] != digits[i + 1]]
    if not pairs:
        return value
    i = int(rng.choice(pairs))
    digits[i], digits[i + 1] = digits[i + 1], digits[i]
    return float(int("".join(digits))) * (1.0 if value >= 0 else -1.0)


def draw_error_class(rng: np.random.Generator, category: str, cfg: ErrorConfig) -> str:
    classes = list(cfg.rates)
    probs = np.array([cfg.rates[c] for c in classes])
    u = rng.random()
    edges = np.cumsum(probs)
    k = int(np.searchsorted(edges, u, side="right"))
    if k >= len(classes):
        return "none"
    chosen = classes[k]
    if category == "EEI" and chosen in RES_ONLY:
        return "none"
    return chosen


def _scale_bills(bills: Bills, factor: float) -> Bills:
    return replace(bills, delivered=bills.delivered * factor, export=bills.export * factor)


def _with_value(bills: Bills, k: int, value: float) -> Bills:
    delivered = bills.delivered.copy()
    delivered[k] = value
    return replace(bills, delivered=delivered)


def inject(ev: Evidence, error_class: str, rng: np.random.Generator, cfg: ErrorConfig, *,
           earlier_bills: Bills, straddling: tuple[Bills, Bills],
           mean_daily_ghi_kwh: float) -> tuple[Evidence, ErrorLabel]:
    """Return erroneous evidence and its label.

    ``earlier_bills`` are the twelve bills preceding the correct pre-installation
    set; ``straddling`` holds alternative (pre, post) sets shifted across the
    in-service date.
    """
    if error_class == "none":
        return ev, ErrorLabel("none")
    res = ev.category == "RES"
    if error_class == "unit":
        factor = 1e-3 if rng.random() < 0.5 else 1e3
        variant = "entered_in_MWh" if factor < 1 else "entered_times_1000"
        if res:
            out = replace(ev, claim_value=ev.claim_value * factor,
                          inverter_kwh=ev.inverter_kwh * factor)
            return out, ErrorLabel("unit", variant, "production", factor)
        out = replace(ev, claim_value=ev.claim_value * factor,
                      claim_pre_energy=ev.claim_pre_energy * factor,
                      pre_bills=_scale_bills(ev.pre_bills, factor),
                      post_bills=_scale_bills(ev.post_bills, factor))
        return out, ErrorLabel("unit", variant, "bills", factor)
    if error_class == "transposed_digits":
        targets = ["claim", "inverter", "pre_bill"] if res else ["pre_bill", "post_bill"]
        probs = [0.4, 0.3, 0.3] if res else [0.5, 0.5]
        target = str(rng.choice(targets, p=probs))
        if target == "claim":
            new = transpose_digits(ev.claim_value, rng)
            return replace(ev, claim_value=new), ErrorLabel(
                "transposed_digits", "", "claim", new / ev.claim_value)
        if target == "inverter":
            k = int(rng.integers(0, ev.inverter_kwh.size))
            readings = ev.inverter_kwh.copy()
            readings[k] = transpose_digits(readings[k], rng)
            return replace(ev, inverter_kwh=readings), ErrorLabel(
                "transposed_digits", "", "inverter",
                readings.sum() / max(ev.inverter_kwh.sum(), 1e-9))
        bills = ev.pre_bills if target == "pre_bill" else ev.post_bills
        k = int(rng.integers(0, len(bills)))
        new_bills = _with_value(bills, k, transpose_digits(float(bills.delivered[k]), rng))
        ratio = new_bills.delivered.sum() / max(bills.delivered.sum(), 1e-9)
        if target == "pre_bill":
            return replace(ev, pre_bills=new_bills), ErrorLabel(
                "transposed_digits", "", "pre_bill", ratio)
        return replace(ev, post_bills=new_bills), ErrorLabel(
            "transposed_digits", "", "post_bill", ratio)
    if error_class == "wrong_period":
        if rng.random() < 0.5:
            out = replace(ev, pre_bills=earlier_bills,
                          claim_pre_energy=float(earlier_bills.printed.sum()))
            if not res:
                out = replace(out, claim_value=float(
                    earlier_bills.printed.sum() - ev.post_bills.printed.sum()))
            return out, ErrorLabel("wrong_period", "earlier_year", "pre_bills",
                                   earlier_bills.printed.sum() / ev.pre_bills.printed.sum())
        pre_shift, post_shift = straddling
        if res:
            out = replace(ev, pre_bills=pre_shift,
                          claim_pre_energy=float(pre_shift.printed.sum()))
            return out, ErrorLabel("wrong_period", "straddles_installation", "pre_bills",
                                   pre_shift.printed.sum() / ev.pre_bills.printed.sum())
        out = replace(ev, post_bills=post_shift, claim_value=float(
            ev.pre_bills.printed.sum() - post_shift.printed.sum()))
        return out, ErrorLabel("wrong_period", "straddles_installation", "post_bills",
                               post_shift.printed.sum() / ev.post_bills.printed.sum())
    if error_class == "double_counting":
        lo, hi = cfg.second_meter_fraction_range
        frac = float(rng.uniform(lo, hi))
        extra = ev.pre_bills.delivered * frac * (1.0 + rng.normal(0.0, 0.1, len(ev.pre_bills)))
        extra = np.maximum(extra, 0.0)
        pre = replace(ev.pre_bills, delivered=ev.pre_bills.delivered + extra,
                      charge=ev.pre_bills.charge * (1.0 + frac),
                      n_accounts=np.full(len(ev.pre_bills), 2))
        out = replace(ev, pre_bills=pre, claim_pre_energy=float(pre.printed.sum()))
        if not res:
            out = replace(out, claim_value=float(pre.printed.sum()
                                                 - ev.post_bills.printed.sum()))
        return out, ErrorLabel("double_counting", "second_meter", "pre_bills", 1.0 + frac)
    if error_class == "gross_net":
        exported = float(ev.post_bills.export.sum())
        if exported > 0 and rng.random() < 0.5:
            new, variant = exported, "exports_reported_as_production"
        else:
            new = float(ev.pre_bills.delivered.sum() - ev.post_bills.delivered.sum())
            variant = "bill_reduction_reported_as_production"
        new = max(new, 0.0)
        return replace(ev, claim_value=new, claim_method="billing_difference"), ErrorLabel(
            "gross_net", variant, "claim", new / ev.claim_value)
    if error_class == "nameplate_hours":
        psh = round(mean_daily_ghi_kwh * 2.0) / 2.0
        new = ev.capacity_kw * psh * 365.0
        return replace(ev, claim_value=new, claim_method="engineering_estimate"), ErrorLabel(
            "nameplate_hours", "capacity_times_peak_sun_hours", "claim", new / ev.claim_value)
    raise ValueError(f"unknown error class {error_class}")
