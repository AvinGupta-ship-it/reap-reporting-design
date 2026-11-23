"""Accuracy-burden optimisation over data-element specifications.

A specification is a set of optional data elements plus a collection mode. Its
accuracy is evaluated on simulated applicants: validation rules that can run under
the specification flag submissions, flagged erroneous submissions are corrected,
and the verified quantity is computed by the best estimator the specification
supports. The frontier is computed by exhaustive enumeration and, as a check of
the method intended for larger element sets, by a surrogate integer programme
solved with HiGHS.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any

import linopy
import numpy as np
import pandas as pd

from reapschema import burden as burden_model
from reapschema import competition
from reapschema.config import Config
from reapschema.validate import OPTIONAL_ELEMENTS, RULES, Rule

DEPENDENCIES: dict[str, tuple[str, ...]] = {
    # element -> at least one of these must also be collected
    "weather_normalization": ("billing_dates", "utility_interval"),
    "export_channel": ("res_post_bills",),
}
MODES = ("manual_transcription", "utility_file_upload", "green_button_download",
         "automated_utility_access")
ARE_CAP = 1.0


def feasible(elements: frozenset[str] | set[str]) -> bool:
    return all(any(d in elements for d in deps)
               for e, deps in DEPENDENCIES.items() if e in elements)


def all_specifications() -> list[frozenset[str]]:
    specs = []
    for bits in itertools.product((0, 1), repeat=len(OPTIONAL_ELEMENTS)):
        s = frozenset(e for e, b in zip(OPTIONAL_ELEMENTS, bits, strict=True) if b)
        if feasible(s):
            specs.append(s)
    return specs


def spec_vector(elements: frozenset[str] | set[str]) -> np.ndarray:
    return np.array([1.0 if e in elements else 0.0 for e in OPTIONAL_ELEMENTS])


def robust_scale(x: np.ndarray) -> tuple[float, float]:
    """Median and MAD-based scale of the finite values of ``x``."""
    v = x[np.isfinite(x)]
    if v.size == 0:
        return 0.0, 1.0
    med = float(np.median(v))
    return med, max(1.4826 * float(np.median(np.abs(v - med))), 1e-6)


@dataclass(frozen=True)
class SpecResult:
    verified_energy: np.ndarray
    verified_pre: np.ndarray
    flagged: np.ndarray
    corrected: np.ndarray
    are: np.ndarray  # absolute relative error of the verified energy quantity


class SpecEvaluator:
    """Evaluates specifications on a table of simulated applicant records."""

    def __init__(self, records: pd.DataFrame, cfg: Config) -> None:
        self.cfg = cfg
        self.records = records.reset_index(drop=True)
        r = self.records
        self.n = len(r)
        self.is_res = (r["category"] == "RES").to_numpy()
        self.has_error = (r["error_class"] != "none").to_numpy()
        self.target = np.where(self.is_res, r["true_production"], r["true_savings_normal"])
        self.true_pre = r["true_pre_consumption"].to_numpy()
        bill_targets = r["error_target"].isin(["pre_bill", "post_bill", "bills"]).to_numpy()
        transcription = r["error_class"].isin(["unit", "transposed_digits"]).to_numpy()
        self.bill_transcription = self.has_error & bill_targets & transcription
        # errors that interval data tied to an account and dates cannot carry
        self.bill_error = self.has_error & r["error_target"].isin(
            ["pre_bill", "post_bill", "bills", "pre_bills", "post_bills"]).to_numpy()
        self.rules: tuple[Rule, ...] = RULES
        self.scales: dict[str, tuple[float, float]] = {}
        self.thresholds: dict[str, float] = {}
        flags_r = np.zeros((self.n, len(self.rules)), dtype=bool)
        flags_c = np.zeros((self.n, len(self.rules)), dtype=bool)
        self.z_reported: dict[str, np.ndarray] = {}
        self.z_clean: dict[str, np.ndarray] = {}
        for j, rule in enumerate(self.rules):
            rep = r[f"r_rule_{rule.key}"].to_numpy(dtype=float)
            cln = r[f"c_rule_{rule.key}"].to_numpy(dtype=float)
            if rule.standardize:
                med, scale = robust_scale(cln)
                self.scales[rule.key] = (med, scale)
                rep, cln = np.abs(rep - med) / scale, np.abs(cln - med) / scale
            self.z_reported[rule.key], self.z_clean[rule.key] = rep, cln
            if rule.kind == "statistical":
                # threshold at the target false-positive rate on error-free evidence
                finite = cln[np.isfinite(cln)]
                thr = (float(np.quantile(finite, 1.0 - cfg.validation.statistical_rule_fpr))
                       if finite.size else np.inf)
            elif rule.threshold is not None:
                thr = float(getattr(cfg.validation, rule.threshold))
            else:
                thr = 0.5
            self.thresholds[rule.key] = thr
            flags_r[:, j] = np.nan_to_num(rep, nan=-np.inf) > thr
            flags_c[:, j] = np.nan_to_num(cln, nan=-np.inf) > thr
        self.flags_reported = flags_r
        self.flags_clean = flags_c
        self._col = {name: r[name].to_numpy(dtype=float) for name in r.columns
                     if name.startswith(("c_", "r_")) and "_rule_" not in name}

    def rule_mask(self, elements: frozenset[str] | set[str]) -> np.ndarray:
        return np.array([rule.requires <= set(elements) and rule.kind != "diagnostic"
                         for rule in self.rules])

    def _pick(self, name: str, use_reported: np.ndarray) -> np.ndarray:
        return np.where(use_reported, self._col[f"r_{name}"], self._col[f"c_{name}"])

    def evaluate(self, elements: frozenset[str] | set[str], mode: str = "manual_transcription",
                 apply_rules: bool = True, with_errors: bool = True) -> SpecResult:
        el = set(elements)
        mask = self.rule_mask(el)
        flagged_err = self.flags_reported[:, mask].any(axis=1)
        flagged_clean = self.flags_clean[:, mask].any(axis=1)
        erroneous = self.has_error.copy() if with_errors else np.zeros(self.n, dtype=bool)
        if mode != "manual_transcription":
            erroneous &= ~self.bill_transcription
        corrected = erroneous & flagged_err if apply_rules else np.zeros(self.n, dtype=bool)
        use_rep = erroneous & ~corrected
        flagged = np.where(erroneous, flagged_err, flagged_clean)
        if not apply_rules:
            flagged = np.zeros(self.n, dtype=bool)

        if "utility_interval" in el:
            pre = self._col["c_cpre_interval"]
        elif "billing_dates" in el:
            pre = self._pick("cpre_dated", use_rep)
        else:
            pre = self._pick("cpre_undated", use_rep)

        if "inverter_interval" in el:
            p = self._col["c_p_interval"]
        elif "inverter_monthly" in el:
            p = self._pick("p_inverter", use_rep)
        else:
            p = self._pick("p_claim", use_rep)

        if "utility_interval" in el:
            s = (self._col["c_s_interval_norm"] if "weather_normalization" in el
                 else self._col["c_s_dated"])
        elif "weather_normalization" in el and "billing_dates" in el:
            s = self._pick("s_norm_merged_guarded" if "read_type" in el else "s_norm_guarded",
                           use_rep)
        elif "billing_dates" in el:
            s = self._pick("s_dated", use_rep)
        else:
            s = self._pick("s_undated", use_rep)

        energy = np.where(self.is_res, p, s)
        are = np.abs(energy - self.target) / np.abs(self.target)
        return SpecResult(energy, pre, flagged, corrected, are)

    def losses(self, result: SpecResult) -> dict[str, float]:
        capped = np.minimum(result.are, ARE_CAP)
        out = {
            "mare": float(capped.mean()),
            "mare_se": float(capped.std(ddof=1) / np.sqrt(self.n)),
            "mare_res": float(capped[self.is_res].mean()),
            "mare_eei": float(capped[~self.is_res].mean()),
            "median_are": float(np.median(result.are)),
            "median_are_res": float(np.median(result.are[self.is_res])),
            "median_are_eei": float(np.median(result.are[~self.is_res])),
            "flag_rate": float(result.flagged.mean()),
            "false_positive_rate": float(result.flagged[~self.has_error].mean()),
            "detection_rate": float(result.corrected[self.has_error].mean())
            if self.has_error.any() else 0.0,
        }
        return out


class SelectionEvaluator:
    """Probability that verification error changes award selection."""

    def __init__(self, evaluator: SpecEvaluator, rng: np.random.Generator) -> None:
        self.ev = evaluator
        cfg = evaluator.cfg.competition
        r = evaluator.records
        self.cfg = cfg
        self.tables = competition.scoring_tables()
        self.cost = r["project_cost"].to_numpy(dtype=float)
        self.request = r["amount_requested"].to_numpy(dtype=float)
        self.price = r["energy_price"].to_numpy(dtype=float)
        self.life = r["useful_life"].to_numpy(dtype=float)
        self.storage = r["has_storage"].to_numpy(dtype=bool)
        self.design = competition.design_competitions(
            rng, r["state"].to_numpy(), evaluator.is_res, cfg)
        self._true: dict[float, np.ndarray] = {}
        self._cache: dict[tuple[bytes, float], tuple[float, float]] = {}

    def _selected(self, energy: np.ndarray, pre: np.ndarray, ratio: float) -> np.ndarray:
        is_res = self.ev.is_res
        score = competition.energy_dependent_score(is_res, energy, pre, self.cost, self.request,
                                                   self.price, self.tables)
        ok = competition.eligible(is_res, energy, pre, self.cost, self.price, self.life,
                                  self.storage)
        return competition.selections(self.design, score, ok, self.request, self.cfg, ratio)

    def true_selection(self, ratio: float | None = None) -> np.ndarray:
        ratio = self.cfg.funding_ratio if ratio is None else ratio
        if ratio not in self._true:
            self._true[ratio] = self._selected(self.ev.target, self.ev.true_pre, ratio)
        return self._true[ratio]

    def change_probability(self, result: SpecResult, ratio: float | None = None
                           ) -> tuple[float, float]:
        """Mean share of truly selected applications displaced, and its standard error."""
        ratio = self.cfg.funding_ratio if ratio is None else ratio
        key = (np.round(result.verified_energy, 3).tobytes()
               + np.round(result.verified_pre, 3).tobytes(), ratio)
        if key not in self._cache:
            sel = self._selected(result.verified_energy, result.verified_pre, ratio)
            change = competition.selection_change(self.true_selection(ratio), sel)
            self._cache[key] = (float(change.mean()),
                                float(change.std(ddof=1) / np.sqrt(change.size))
                                if change.size > 1 else 0.0)
        return self._cache[key]


def pareto_front(cost: np.ndarray, loss: np.ndarray) -> np.ndarray:
    """Indices of non-dominated points (minimise both), ordered by increasing cost."""
    order = np.lexsort((loss, cost))
    best = np.inf
    keep = []
    for i in order:
        if loss[i] < best - 1e-12:
            keep.append(i)
            best = loss[i]
    return np.asarray(keep, dtype=int)


def frontier_at_budgets(cost: np.ndarray, loss: np.ndarray, budgets: np.ndarray) -> np.ndarray:
    """Minimum loss attainable within each budget (NaN when nothing is feasible)."""
    order = np.argsort(cost)
    c, running = cost[order], np.minimum.accumulate(loss[order])
    idx = np.searchsorted(c, budgets, side="right") - 1
    return np.where(idx >= 0, running[np.clip(idx, 0, None)], np.nan)


# --- surrogate-assisted integer programme -------------------------------------------------


@dataclass(frozen=True)
class Surrogate:
    intercept: float
    linear: np.ndarray
    pairs: list[tuple[int, int]]
    pair_coef: np.ndarray
    r2: float


def fit_surrogate(x: np.ndarray, y: np.ndarray, ridge: float = 1e-6) -> Surrogate:
    """Quadratic pseudo-Boolean surrogate ``w0 + sum w_j x_j + sum w_jk x_j x_k``."""
    k = x.shape[1]
    pairs = [(i, j) for i in range(k) for j in range(i + 1, k)]
    cross = np.column_stack([x[:, i] * x[:, j] for i, j in pairs])
    design = np.column_stack([np.ones(len(x)), x, cross])
    gram = design.T @ design + ridge * np.eye(design.shape[1])
    coef = np.linalg.solve(gram, design.T @ y)
    pred = design @ coef
    r2 = 1.0 - float(((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum())
    return Surrogate(float(coef[0]), coef[1:k + 1], pairs, coef[k + 1:], r2)


def surrogate_value(s: Surrogate, x: np.ndarray) -> float:
    return float(s.intercept + s.linear @ x
                 + sum(c * x[i] * x[j] for (i, j), c in zip(s.pairs, s.pair_coef, strict=True)))


def solve_surrogate_ilp(s: Surrogate, tau: np.ndarray, budget: float,
                        mip_gap: float = 1e-4) -> dict[str, Any]:
    """Minimise the surrogate loss subject to a burden budget and element dependencies."""
    names = list(OPTIONAL_ELEMENTS)
    k = len(names)
    m = linopy.Model()
    xv = m.add_variables(binary=True, coords=[pd.Index(names, name="element")], name="x")
    pair_index = pd.Index([f"{names[i]}|{names[j]}" for i, j in s.pairs], name="pair")
    yv = m.add_variables(lower=0, upper=1, coords=[pair_index], name="y")
    for (i, j), label in zip(s.pairs, pair_index, strict=True):
        m.add_constraints(yv.loc[label] <= xv.loc[names[i]])
        m.add_constraints(yv.loc[label] <= xv.loc[names[j]])
        m.add_constraints(yv.loc[label] >= xv.loc[names[i]] + xv.loc[names[j]] - 1)
    for element, deps in DEPENDENCIES.items():
        m.add_constraints(xv.loc[element] <= sum(xv.loc[d] for d in deps))
    m.add_constraints(sum(float(tau[i]) * xv.loc[names[i]] for i in range(k)) <= budget)
    objective = sum(float(s.linear[i]) * xv.loc[names[i]] for i in range(k)) + sum(
        float(c) * yv.loc[label] for c, label in zip(s.pair_coef, pair_index, strict=True))
    m.add_objective(objective)
    status, condition = m.solve(solver_name="highs", mip_rel_gap=mip_gap, output_flag=False)
    sol = np.round(np.asarray(xv.solution.values, dtype=float))
    chosen = frozenset(n for n, v in zip(names, sol, strict=True) if v > 0.5)
    spent = float(tau @ sol)
    return {
        "status": status, "condition": condition, "elements": chosen,
        "objective": float(m.objective.value) + s.intercept,
        "surrogate_at_solution": surrogate_value(s, sol),
        "burden": spent,
        "primal_feasible": bool(spent <= budget + 1e-9 and feasible(chosen)),
        "mip_gap": mip_gap,
    }


def element_tau(cfg: Config, res_share: float, times: dict[str, Any], kappa: float,
                mode: str = "manual_transcription") -> np.ndarray:
    """Marginal burden (minutes) of each optional element; burden is additive in elements."""
    base = burden_model.mean_burden(frozenset(), mode, res_share, times, cfg.burden, kappa)
    return np.array([
        float(burden_model.mean_burden(frozenset([e]), mode, res_share, times, cfg.burden,
                                       kappa) - base)
        for e in OPTIONAL_ELEMENTS])
