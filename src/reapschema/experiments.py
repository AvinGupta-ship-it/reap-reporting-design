"""Computational experiments E1-E8 and supporting analyses.

Every function takes the configuration and the table of simulated applicant
records and returns tables; ``run_all`` writes them to a results directory with
provenance sidecars.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from SALib.analyze import sobol as sobol_analyze
from SALib.sample import sobol as sobol_sample
from scipy import stats

from reapschema import burden as bm
from reapschema import mv
from reapschema.config import Config
from reapschema.evaluate import simulate
from reapschema.optimize import (
    MODES,
    SelectionEvaluator,
    SpecEvaluator,
    all_specifications,
    element_tau,
    fit_surrogate,
    frontier_at_budgets,
    pareto_front,
    solve_surrogate_ilp,
)
from reapschema.synth.errors import ERROR_CLASSES
from reapschema.synth.generator import generate_applicant, load_population, spawn_seeds
from reapschema.validate import OPTIONAL_ELEMENTS, RULES

# Named evidence specifications compared in E2, E7 and E8.
NAMED_SPECS: dict[str, tuple[str, frozenset[str]]] = {
    "current": ("Current rule: monthly quantities, annual claim", frozenset()),
    "dates": ("+ billing-period dates", frozenset({"billing_dates"})),
    "dates_norm": ("+ dates and weather normalization",
                   frozenset({"billing_dates", "weather_normalization"})),
    "dates_norm_read": ("+ dates, normalization, read type",
                        frozenset({"billing_dates", "weather_normalization", "read_type"})),
    "production_meter": ("+ monthly production-meter readings",
                         frozenset({"inverter_monthly"})),
    "netting": ("+ post-installation bills with export and netting basis",
                frozenset({"res_post_bills", "export_channel"})),
    "metadata": ("Monthly data with metadata (dates, normalization, read type, meter IDs, "
                 "production readings, netting basis, array geometry, end-use share)",
                 frozenset({"billing_dates", "weather_normalization", "read_type", "meter_ids",
                            "inverter_monthly", "res_post_bills", "export_channel",
                            "pv_geometry", "enduse_share"})),
    "interval": ("Interval data (utility and production) with normalization",
                 frozenset({"utility_interval", "inverter_interval",
                            "weather_normalization"})),
}

EEI_PATHS = {
    "eei_undated": ("s_undated", "Undated monthly difference"),
    "eei_dated": ("s_dated", "Dated, day-annualized difference"),
    "eei_normalized_monthly": ("s_norm", "Dated monthly, degree-day normalized"),
    "eei_normalized_guarded": ("s_norm_guarded", "Dated monthly, normalized when the models "
                               "meet the fit criterion"),
    "eei_normalized_merged": ("s_norm_merged_guarded", "As above, estimated reads merged"),
    "eei_interval": ("s_interval_norm", "Daily interval data, normalized"),
}
def savings_bands(cfg: Config) -> list[tuple[float, float, str]]:
    """Bands of true savings fraction used to stratify estimator error."""
    lo, hi = cfg.experiments.savings_bands
    return [(0.0, lo, f"below {lo:.0%}"), (lo, hi, f"{lo:.0%}-{hi:.0%}".replace("%-", "-")),
            (hi, 1.0, f"above {hi:.0%}")]


def accuracy_by_savings_fraction(records: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """EEI estimator error on error-free evidence by true savings fraction."""
    eei = records[records["category"] == "EEI"]
    truth = eei["true_savings_normal"].to_numpy()
    frac = eei["savings_fraction"].to_numpy()
    rows = []
    low_thr = cfg.experiments.error_share_thresholds[0]
    for lo, hi, label in savings_bands(cfg):
        m = (frac >= lo) & (frac < hi)
        for key, (col, _label) in EEI_PATHS.items():
            are = np.abs(eei[f"c_{col}"].to_numpy()[m] - truth[m]) / np.abs(truth[m])
            rows.append({"savings_fraction": label, "estimator": key, "n": int(m.sum()),
                         "median_are": float(np.median(are)) if m.any() else np.nan,
                         "share_above_10pct": float((are > low_thr).mean()) if m.any()
                         else np.nan})
    return pd.DataFrame(rows)
# (label, evidence contains injected errors, validation rules applied)
CONDITIONS = (("error_free", False, True), ("with_errors_validated", True, True),
              ("with_errors_unvalidated", True, False))
CPRE_PATHS = {
    "cpre_undated": ("cpre_undated", "Sum of twelve bills"),
    "cpre_dated": ("cpre_dated", "Day-annualized twelve bills"),
}


def _quantiles(x: np.ndarray) -> dict[str, float]:
    q = np.quantile(x, [0.05, 0.25, 0.5, 0.75, 0.95])
    return {"q05": float(q[0]), "q25": float(q[1]), "median": float(q[2]),
            "q75": float(q[3]), "q95": float(q[4])}


def _boot_se(x: np.ndarray, rng: np.random.Generator, stat: Any, reps: int) -> float:
    n = x.size
    draws = np.array([stat(x[rng.integers(0, n, n)]) for _ in range(reps)])
    return float(draws.std(ddof=1))


# --- E1 -------------------------------------------------------------------------------------


def e1_burden_audit() -> dict[str, Any]:
    return bm.run_audit()


# --- E2 -------------------------------------------------------------------------------------


def e2_accuracy(records: pd.DataFrame, cfg: Config, rng: np.random.Generator
                ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Error of the verified quantity by evidence specification.

    Two conditions are reported: error-free evidence (estimator error only) and
    evidence with injected errors after validation and correction.
    """
    ev = SpecEvaluator(records, cfg)
    reps = cfg.experiments.bootstrap_replicates
    thr_lo, thr_hi = cfg.experiments.error_share_thresholds
    rows = []
    samples = []
    for key, (label, elements) in NAMED_SPECS.items():
        for condition, with_errors, apply_rules in CONDITIONS:
            res = ev.evaluate(elements, with_errors=with_errors, apply_rules=apply_rules)
            for cat, mask in (("RES", ev.is_res), ("EEI", ~ev.is_res)):
                are = res.are[mask]
                rows.append({
                    "spec": key, "label": label, "condition": condition, "category": cat,
                    "n": int(are.size), **_quantiles(are),
                    "median_se": _boot_se(are, rng, np.median, reps),
                    "mare_capped": float(np.minimum(are, cfg.experiments.are_cap).mean()),
                    "mare_capped_se": float(np.minimum(are, cfg.experiments.are_cap).std(ddof=1)
                                            / np.sqrt(are.size)),
                    "mean_are": float(are.mean()),
                    "share_above_10pct": float((are > thr_lo).mean()),
                    "share_above_50pct": float((are > thr_hi).mean()),
                })
                if condition != "with_errors_unvalidated":
                    samples.append(pd.DataFrame({"spec": key, "condition": condition,
                                                 "category": cat, "are": are}))
    # estimator paths on error-free evidence (EEI savings and pre-installation use)
    eei = records[records["category"] == "EEI"]
    truth_n = eei["true_savings_normal"].to_numpy()
    truth_a = eei["true_savings_avoided"].to_numpy()
    for key, (col, label) in EEI_PATHS.items():
        est = eei[f"c_{col}"].to_numpy()
        for basis, truth in (("normal_year", truth_n), ("post_period", truth_a)):
            are = np.abs(est - truth) / np.abs(truth)
            rows.append({"spec": key, "label": label, "condition": f"path_vs_{basis}",
                         "category": "EEI", "n": int(are.size), **_quantiles(are),
                         "median_se": _boot_se(are, rng, np.median, reps),
                         "mare_capped": float(np.minimum(are, cfg.experiments.are_cap).mean()),
                         "mare_capped_se": float(
                             np.minimum(are, cfg.experiments.are_cap).std(ddof=1)
                             / np.sqrt(are.size)),
                         "mean_are": float(are.mean()),
                         "share_above_10pct": float((are > thr_lo).mean()),
                         "share_above_50pct": float((are > thr_hi).mean())})
    truth_c = records["true_pre_consumption"].to_numpy()
    for key, (col, label) in CPRE_PATHS.items():
        are = np.abs(records[f"c_{col}"].to_numpy() - truth_c) / truth_c
        rows.append({"spec": key, "label": label, "condition": "path_pre_consumption",
                     "category": "all", "n": int(are.size), **_quantiles(are),
                     "median_se": _boot_se(are, rng, np.median, reps),
                     "mare_capped": float(np.minimum(are, cfg.experiments.are_cap).mean()),
                     "mare_capped_se": float(are.std(ddof=1) / np.sqrt(are.size)),
                     "mean_are": float(are.mean()),
                     "share_above_10pct": float((are > thr_lo).mean()),
                     "share_above_50pct": float((are > thr_hi).mean())})
    return pd.DataFrame(rows), pd.concat(samples, ignore_index=True)


def hypothesis_tests(records: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Pre-specified paired Wilcoxon signed-rank tests with Holm correction."""
    eei = records[records["category"] == "EEI"]
    truth = eei["true_savings_normal"].to_numpy()

    def are(key: str) -> np.ndarray:
        if key in EEI_PATHS:
            return np.asarray(np.abs(eei[f"c_{EEI_PATHS[key][0]}"].to_numpy() - truth)
                              / np.abs(truth))
        col = CPRE_PATHS[key][0]
        t = records["true_pre_consumption"].to_numpy()
        return np.asarray(np.abs(records[f"c_{col}"].to_numpy() - t) / t)

    rows = []
    for test in cfg.hypothesis_tests.family:
        a, b = are(test.a), are(test.b)
        w = stats.wilcoxon(a, b, zero_method="wilcox")
        rows.append({"id": test.id, "description": test.description, "n": int(a.size),
                     "median_a": float(np.median(a)), "median_b": float(np.median(b)),
                     "median_difference": float(np.median(a - b)),
                     "statistic": float(w.statistic), "p_value": float(w.pvalue)})
    out = pd.DataFrame(rows)
    order = np.argsort(out["p_value"].to_numpy())
    m = len(out)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * out["p_value"].iloc[i])
        adj[i] = min(running, 1.0)
    out["p_holm"] = adj
    out["reject"] = out["p_holm"] < cfg.hypothesis_tests.alpha
    return out


# --- E3 -------------------------------------------------------------------------------------


def simulate_by_class(cfg: Config, n_per_class: int) -> pd.DataFrame:
    """Balanced design: applicants with each error class forced, for detection estimates."""
    frames = []
    for k, cls in enumerate(ERROR_CLASSES):
        frames.append(simulate(cfg, n_per_class, seed=cfg.seed + 101 + k, error_class=cls))
    return pd.concat(frames, ignore_index=True)


def _auc(pos: np.ndarray, neg: np.ndarray) -> float:
    if pos.size == 0 or neg.size == 0:
        return float("nan")
    u = stats.mannwhitneyu(pos, neg, alternative="greater").statistic
    return float(u / (pos.size * neg.size))


def e3_validation(class_records: pd.DataFrame, cfg: Config
                  ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Per-rule and ensemble detection and false-positive rates; ROC of statistical rules."""
    ev = SpecEvaluator(class_records, cfg)
    r = ev.records
    matrix_rows = []
    roc_rows = []
    cats = {"RES": ev.is_res, "EEI": ~ev.is_res}
    for j, rule in enumerate(ev.rules):
        for cat, cmask in cats.items():
            if rule.applies_to not in ("both", cat):
                continue
            clean_scores = ev.z_clean[rule.key][cmask]
            clean_flags = ev.flags_clean[cmask, j]
            fp = float(clean_flags.mean())
            row: dict[str, Any] = {"rule": rule.key, "category": cat, "kind": rule.kind,
                                   "requires": ", ".join(sorted(rule.requires)) or "(none)",
                                   "false_positive_rate": fp,
                                   "n_clean": int(cmask.sum()),
                                   "false_positives": int(clean_flags.sum())}
            for cls in ERROR_CLASSES:
                m = cmask & (r["error_class"] == cls).to_numpy()
                if m.sum() == 0:
                    row[cls] = np.nan
                    continue
                row[cls] = float(ev.flags_reported[m, j].mean())
                row[f"n_{cls}"] = int(m.sum())
                if rule.kind == "statistical":
                    pos = ev.z_reported[rule.key][m]
                    pos = pos[np.isfinite(pos)]
                    neg = clean_scores[np.isfinite(clean_scores)]
                    auc = _auc(pos, neg)
                    thr5 = float(np.quantile(neg, 1.0 - cfg.experiments.recall_fpr))
                    recall5 = float((pos > thr5).mean())
                    grid = np.quantile(np.concatenate([pos, neg]),
                                       np.linspace(0, 1, cfg.experiments.roc_points))
                    for t in grid:
                        roc_rows.append({"rule": rule.key, "category": cat, "error_class": cls,
                                         "threshold": float(t),
                                         "fpr": float((neg > t).mean()),
                                         "tpr": float((pos > t).mean()),
                                         "auc": auc, "recall_at_5pct_fpr": recall5})
            matrix_rows.append(row)
    ens_rows = []
    for key, (label, elements) in NAMED_SPECS.items():
        res = ev.evaluate(elements)
        for cat, cmask in cats.items():
            row = {"spec": key, "label": label, "category": cat,
                   "false_positive_rate": float(
                       ev.flags_clean[np.ix_(cmask, ev.rule_mask(elements))].any(axis=1).mean())}
            for cls in ERROR_CLASSES:
                m = cmask & (r["error_class"] == cls).to_numpy()
                row[cls] = float(res.corrected[m].mean()) if m.sum() else np.nan
            ens_rows.append(row)
    ens = pd.DataFrame(ens_rows)
    # positive predictive value of an ensemble flag at scaled class rates
    ppv_rows = []
    for mult in cfg.experiments.e3_rate_multipliers:
        for erow in ens.to_dict("records"):
            tp = sum(mult * cfg.errors.rates[c] * erow[c] for c in ERROR_CLASSES
                     if not np.isnan(erow[c]))
            p_err = sum(mult * cfg.errors.rates[c] for c in ERROR_CLASSES
                        if not np.isnan(erow[c]))
            fp = (1.0 - p_err) * erow["false_positive_rate"]
            ppv_rows.append({"spec": erow["spec"], "category": erow["category"],
                             "rate_multiplier": mult, "error_rate": p_err,
                             "recall": tp / p_err if p_err > 0 else np.nan,
                             "ppv": tp / (tp + fp) if tp + fp > 0 else np.nan})
    ens = ens.merge(pd.DataFrame(ppv_rows), on=["spec", "category"])
    return pd.DataFrame(matrix_rows), pd.DataFrame(roc_rows), ens


# --- E4 -------------------------------------------------------------------------------------


def e4_normalization(records: pd.DataFrame, cfg: Config) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Bias of unnormalized and normalized estimates against the weather difference."""
    rows = []
    summary = []
    eei = records[records["category"] == "EEI"]
    pre = eei["true_pre_consumption"].to_numpy()
    truth = eei["true_savings_normal"].to_numpy()
    x = eei["delta_mean_temp"].to_numpy()
    estimators = {"unnormalized": "c_s_dated", "normalized_avoided": "c_s_avoided",
                  "normalized_unguarded": "c_s_norm", "normalized_annual": "c_s_norm_guarded",
                  "interval_normalized": "c_s_interval_norm"}
    edges = np.quantile(x, np.linspace(0, 1, cfg.experiments.e4_bins + 1))
    for name, col in estimators.items():
        # error as a share of pre-installation use, so that projects are comparable
        err = (eei[col].to_numpy() - truth) / pre
        slope = stats.linregress(x, err)
        summary.append({"category": "EEI", "estimator": name, "bias": float(err.mean()),
                        "bias_se": float(err.std(ddof=1) / np.sqrt(err.size)),
                        "rmse": float(np.sqrt((err**2).mean())),
                        "slope_per_degC": float(slope.slope),
                        "slope_se": float(slope.stderr), "slope_p": float(slope.pvalue),
                        "r": float(slope.rvalue), "n": int(err.size)})
        for b in range(len(edges) - 1):
            m = (x >= edges[b]) & (x <= edges[b + 1] if b == len(edges) - 2 else x < edges[b + 1])
            if m.sum() < cfg.experiments.e4_min_per_bin:
                continue
            rows.append({"category": "EEI", "estimator": name, "x_mid": float(x[m].mean()),
                         "bias": float(err[m].mean()),
                         "bias_se": float(err[m].std(ddof=1) / np.sqrt(m.sum())),
                         "rmse": float(np.sqrt((err[m] ** 2).mean())), "n": int(m.sum())})
    res = records[records["category"] == "RES"]
    truth_n = res["true_production_normal"].to_numpy()
    measured = res["c_p_inverter"].to_numpy()
    xr = res["ghi_anomaly"].to_numpy()
    normalized = measured * res["model_normal_default"].to_numpy() / res[
        "model_post_default"].to_numpy()
    edges = np.quantile(xr, np.linspace(0, 1, cfg.experiments.e4_bins + 1))
    for name, est in (("unnormalized", measured), ("normalized_annual", normalized)):
        err = (est - truth_n) / truth_n
        slope = stats.linregress(xr, err)
        summary.append({"category": "RES", "estimator": name, "bias": float(err.mean()),
                        "bias_se": float(err.std(ddof=1) / np.sqrt(err.size)),
                        "rmse": float(np.sqrt((err**2).mean())),
                        "slope_per_degC": float(slope.slope), "slope_se": float(slope.stderr),
                        "slope_p": float(slope.pvalue), "r": float(slope.rvalue),
                        "n": int(err.size)})
        for b in range(len(edges) - 1):
            m = (xr >= edges[b]) & (xr <= edges[b + 1] if b == len(edges) - 2
                                    else xr < edges[b + 1])
            if m.sum() < cfg.experiments.e4_min_per_bin:
                continue
            rows.append({"category": "RES", "estimator": name, "x_mid": float(xr[m].mean()),
                         "bias": float(err[m].mean()),
                         "bias_se": float(err[m].std(ddof=1) / np.sqrt(m.sum())),
                         "rmse": float(np.sqrt((err[m] ** 2).mean())), "n": int(m.sum())})
    return pd.DataFrame(rows), pd.DataFrame(summary)


# --- E5 -------------------------------------------------------------------------------------


def _drop_bills(bills: Any, drop: np.ndarray) -> Any:
    keep = np.setdiff1d(np.arange(len(bills)), drop)
    return bills.take(keep)


def e5_incomplete(cfg: Config) -> pd.DataFrame:
    """Error of EEI savings and pre-installation use with missing or estimated months."""
    n = cfg.experiments.e5_subsample
    rows = []
    for p_est in cfg.experiments.e5_estimated_read_probs:
        seeds = spawn_seeds(cfg.seed + 501, n)
        apps = [generate_applicant(i, seeds[i], cfg, estimated_prob=p_est, error_class="none")
                for i in range(n)]
        for missing in cfg.experiments.e5_missing_months:
            if p_est != cfg.experiments.e5_estimated_read_probs[0] and missing > 0:
                continue
            acc: dict[str, list[float]] = {k: [] for k in (
                "s_undated", "s_dated", "s_norm", "s_norm_merged", "cpre_undated",
                "cpre_dated")}
            flagged = 0
            total = 0
            for i, app in enumerate(apps):
                rng = np.random.default_rng(seeds[i].spawn(2)[1])
                ev = app.clean
                pre, post = ev.pre_bills, ev.post_bills
                if missing:
                    pre = _drop_bills(pre, rng.choice(12, missing, replace=False))
                    post = _drop_bills(post, rng.choice(12, missing, replace=False))
                c_true = app.truth.pre_consumption
                acc["cpre_undated"].append(abs(pre.printed.sum() - c_true) / c_true)
                acc["cpre_dated"].append(
                    abs(pre.printed.sum() / pre.days.sum() * 365 - c_true) / c_true)
                gap = bool(np.any(pre.start[1:] != pre.end[:-1] + 1)) or not (
                    cfg.validation.billing_days_total[0] <= pre.days.sum()
                    <= cfg.validation.billing_days_total[1])
                flagged += int(gap)
                total += 1
                if app.category != "EEI":
                    continue
                t = app.truth.savings_normal
                table = mv.station_table(ev.state, cfg.mv.balance_grid_f)
                acc["s_undated"].append(abs(pre.printed.sum() - post.printed.sum() - t) / abs(t))
                acc["s_dated"].append(abs(365 * (pre.printed.sum() / pre.days.sum()
                                                 - post.printed.sum() / post.days.sum()) - t)
                                      / abs(t))
                est = mv.estimate_savings((pre.start, pre.end, pre.printed),
                                          (post.start, post.end, post.printed), table,
                                          cfg.mv.confidence, cfg.mv.min_nonzero_periods)
                acc["s_norm"].append(abs(est.normalized - t) / abs(t))
                merged = mv.estimate_savings(
                    mv.merge_estimated(pre.start, pre.end, pre.printed, pre.estimated),
                    mv.merge_estimated(post.start, post.end, post.printed, post.estimated),
                    table, cfg.mv.confidence, cfg.mv.min_nonzero_periods)
                acc["s_norm_merged"].append(abs(merged.normalized - t) / abs(t))
            for name, values in acc.items():
                arr = np.asarray(values)
                rows.append({"estimated_read_prob": p_est, "missing_months": missing,
                             "estimator": name, "n": int(arr.size),
                             "median_are": float(np.median(arr)),
                             "q95_are": float(np.quantile(arr, 0.95)),
                             "mare_capped": float(np.minimum(arr, cfg.experiments.are_cap).mean()),
                             "date_rules_flag_rate": flagged / total})
    return pd.DataFrame(rows)


# --- E6 -------------------------------------------------------------------------------------


def _res_share(cfg: Config) -> float:
    return load_population(tuple(cfg.population.size_fit_fiscal_years)).res_share


def e6_frontier(records: pd.DataFrame, cfg: Config, rng: np.random.Generator,
                hours_per_response: float) -> dict[str, pd.DataFrame]:
    """Exhaustive accuracy-burden frontier with Monte Carlo bands and a surrogate-ILP check."""
    ev = SpecEvaluator(records, cfg)
    sel = SelectionEvaluator(ev, np.random.default_rng(cfg.seed + 7))
    res_share = _res_share(cfg)
    modal = bm.modal_times(cfg.burden)
    kappa = float(bm.calibration_factor(cfg.burden, modal, res_share, hours_per_response))
    specs = all_specifications()
    rows = []
    for mode in ("manual_transcription", "utility_file_upload"):
        for elements in specs:
            res = ev.evaluate(elements, mode)
            loss = ev.losses(res)
            change, change_se = sel.change_probability(res)
            rows.append({
                "mode": mode, **{e: int(e in elements) for e in OPTIONAL_ELEMENTS},
                "n_elements": len(elements),
                "burden_min": float(bm.mean_burden(elements, mode, res_share, modal,
                                                   cfg.burden, kappa, loss["flag_rate"])),
                **loss, "selection_change": change, "selection_change_se": change_se,
            })
    table = pd.DataFrame(rows)
    table["on_frontier_mare"] = False
    table["on_frontier_selection"] = False
    for _mode, grp in table.groupby("mode"):
        idx = grp.index.to_numpy()
        table.loc[idx[pareto_front(grp["burden_min"].to_numpy(), grp["mare"].to_numpy())],
                  "on_frontier_mare"] = True
        table.loc[idx[pareto_front(grp["burden_min"].to_numpy(),
                                   grp["selection_change"].to_numpy())],
                  "on_frontier_selection"] = True

    # Monte Carlo bands over element times (manual mode)
    manual = table[table["mode"] == "manual_transcription"].reset_index(drop=True)
    x = manual[list(OPTIONAL_ELEMENTS)].to_numpy(dtype=float)
    draws = bm.sample_times(cfg.burden, rng, cfg.burden.monte_carlo_draws)
    kappa_d = np.asarray(bm.calibration_factor(cfg.burden, draws, res_share,
                                               hours_per_response))
    base_d = np.asarray(bm.mean_burden(frozenset(), "manual_transcription", res_share, draws,
                                       cfg.burden, kappa_d))
    tau_d = np.stack([
        np.asarray(bm.mean_burden(frozenset([e]), "manual_transcription", res_share, draws,
                                  cfg.burden, kappa_d)) - base_d for e in OPTIONAL_ELEMENTS])
    rework_d = kappa_d * draws["rework"]
    burden_draws = base_d[None, :] + x @ tau_d + np.outer(manual["flag_rate"].to_numpy(),
                                                          rework_d)
    budgets = np.linspace(float(manual["burden_min"].min()),
                          float(manual["burden_min"].quantile(0.9)),
                          cfg.experiments.frontier_budget_points)
    lo_q, hi_q = cfg.experiments.frontier_mc_bands
    band_rows = []
    for metric in ("mare", "selection_change"):
        loss_values = manual[metric].to_numpy(dtype=float)
        se = manual["mare_se" if metric == "mare" else "selection_change_se"].to_numpy()
        curves = np.empty((burden_draws.shape[1], budgets.size))
        for d in range(burden_draws.shape[1]):
            # sampling error of the loss is common to all specifications, which are
            # evaluated on the same applicants
            noisy = loss_values + rng.normal(0.0, 1.0) * se
            curves[d] = frontier_at_budgets(burden_draws[:, d], noisy, budgets)
        central = frontier_at_budgets(manual["burden_min"].to_numpy(), loss_values, budgets)
        for b, budget in enumerate(budgets):
            band_rows.append({"metric": metric, "budget_min": float(budget),
                              "central": float(central[b]),
                              "lo": float(np.nanquantile(curves[:, b], lo_q)),
                              "hi": float(np.nanquantile(curves[:, b], hi_q))})
    bands = pd.DataFrame(band_rows)

    # surrogate-assisted ILP on a designed sample, checked against enumeration
    tau = element_tau(cfg, res_share, modal, kappa)
    sample_idx = rng.choice(len(manual),
                            size=min(cfg.experiments.surrogate_sample, len(manual)),
                            replace=False)
    surrogate = fit_surrogate(x[sample_idx], manual["mare"].to_numpy()[sample_idx])
    base_burden = float(bm.mean_burden(frozenset(), "manual_transcription", res_share, modal,
                                       cfg.burden, kappa))
    ilp_rows = []
    # burden without rework, to match the linear constraint of the programme
    linear_burden = base_burden + x @ tau
    for extra in np.linspace(0.0, float(tau.sum()), cfg.experiments.ilp_budgets + 1)[1:]:
        sol = solve_surrogate_ilp(surrogate, tau, float(extra), cfg.experiments.mip_gap)
        direct = ev.losses(ev.evaluate(sol["elements"]))["mare"]
        feasible_mask = linear_burden <= base_burden + extra + 1e-9
        best = int(np.argmin(np.where(feasible_mask, manual["mare"].to_numpy(), np.inf)))
        ilp_rows.append({
            "budget_extra_min": float(extra), "status": sol["status"],
            "condition": sol["condition"], "primal_feasible": sol["primal_feasible"],
            "mip_gap_tolerance": sol["mip_gap"], "ilp_burden_extra_min": sol["burden"],
            "ilp_elements": ", ".join(sorted(sol["elements"])),
            "surrogate_loss": sol["surrogate_at_solution"], "simulated_loss": direct,
            "enumeration_optimum": float(manual["mare"].iloc[best]),
            "regret": direct - float(manual["mare"].iloc[best]),
            "surrogate_r2": surrogate.r2,
        })
    return {"specs": table, "bands": bands, "ilp": pd.DataFrame(ilp_rows),
            "calibration": pd.DataFrame([{"kappa": kappa, "base_burden_min": base_burden,
                                          "res_share": res_share,
                                          **{f"tau_{e}": t for e, t in
                                             zip(OPTIONAL_ELEMENTS, tau, strict=True)}}])}


INTERVAL_ELEMENTS = ("utility_interval", "inverter_interval")


def recommended_spec(specs: pd.DataFrame, tolerance: float, allow_interval: bool = False
                     ) -> pd.Series:
    """Lowest-burden specification within ``tolerance`` of the attainable loss reduction.

    With ``allow_interval`` false the search is restricted to specifications that use
    monthly records only (no interval data from the utility or the production meter).
    """
    manual = specs[specs["mode"] == "manual_transcription"]
    if not allow_interval:
        manual = manual[(manual[list(INTERVAL_ELEMENTS)].sum(axis=1) == 0)]
    front = manual.iloc[pareto_front(manual["burden_min"].to_numpy(),
                                     manual["mare"].to_numpy())]
    floor = front["mare"].min()
    base = manual[manual["n_elements"] == 0]["mare"].iloc[0]
    ok = front[front["mare"] <= floor + tolerance * (base - floor)]
    best: pd.Series = ok.sort_values("burden_min").iloc[0]
    return best


def size_distribution_sensitivity(cfg: Config, specs: dict[str, frozenset[str]]
                                  ) -> pd.DataFrame:
    """Headline accuracy under the empirical and the fitted lognormal size distributions."""
    rows = []
    for dist in ("empirical", "lognormal"):
        pop = cfg.population.model_copy(update={"size_distribution": dist})
        alt = cfg.model_copy(update={"population": pop})
        rec = simulate(alt, cfg.experiments.size_sensitivity_n, seed=cfg.seed + 901)
        ev = SpecEvaluator(rec, alt)
        for key, elements in specs.items():
            res = ev.evaluate(elements)
            loss = ev.losses(res)
            rows.append({"size_distribution": dist, "spec": key, "n": len(rec),
                         "mare": loss["mare"], "mare_se": loss["mare_se"],
                         "median_are_res": loss["median_are_res"],
                         "median_are_eei": loss["median_are_eei"],
                         "median_request": float(rec["amount_requested"].median())})
    return pd.DataFrame(rows)


def spec_elements(row: pd.Series) -> frozenset[str]:
    return frozenset(e for e in OPTIONAL_ELEMENTS if int(row[e]) == 1)


# --- E7 -------------------------------------------------------------------------------------


def e7_selection(records: pd.DataFrame, cfg: Config, extra: dict[str, frozenset[str]]
                 ) -> pd.DataFrame:
    ev = SpecEvaluator(records, cfg)
    sel = SelectionEvaluator(ev, np.random.default_rng(cfg.seed + 7))
    named = {k: v[1] for k, v in NAMED_SPECS.items()} | extra
    rows = []
    for ratio in cfg.competition.funding_ratio_sensitivity:
        true_sel = sel.true_selection(ratio)
        for key, elements in named.items():
            for condition, with_errors, apply_rules in CONDITIONS:
                p, se = sel.change_probability(
                    ev.evaluate(elements, with_errors=with_errors, apply_rules=apply_rules),
                    ratio)
                rows.append({"spec": key, "condition": condition, "funding_ratio": ratio,
                             "selection_change": p, "se": se,
                             "mean_selected": float(true_sel.sum(axis=1).mean())})
    return pd.DataFrame(rows)


def score_structure(records: pd.DataFrame, cfg: Config) -> dict[str, float]:
    """Descriptive statistics of true scores in the synthetic population."""
    from reapschema import competition as comp

    ev = SpecEvaluator(records, cfg)
    tables = comp.scoring_tables()
    r = ev.records
    pts = comp.energy_points(ev.target, r["amount_requested"].to_numpy(), tables)
    score = comp.energy_dependent_score(
        ev.is_res, ev.target, ev.true_pre, r["project_cost"].to_numpy(),
        r["amount_requested"].to_numpy(), r["energy_price"].to_numpy(), tables)
    ok = comp.eligible(ev.is_res, ev.target, ev.true_pre, r["project_cost"].to_numpy(),
                       r["energy_price"].to_numpy(), r["useful_life"].to_numpy(),
                       r["has_storage"].to_numpy(dtype=bool))
    return {"share_energy_points_at_cap": float((pts >= tables.energy_cap).mean()),
            "share_energy_points_at_cap_res": float((pts[ev.is_res] >= tables.energy_cap).mean()),
            "share_energy_points_at_cap_eei": float((pts[~ev.is_res]
                                                     >= tables.energy_cap).mean()),
            "distinct_energy_scores": float(np.unique(np.round(score, 2)).size),
            "share_eligible": float(ok.mean()),
            "share_eligible_res": float(ok[ev.is_res].mean()),
            "share_eligible_eei": float(ok[~ev.is_res].mean())}


# --- E8 -------------------------------------------------------------------------------------


def e8_modes(records: pd.DataFrame, cfg: Config, rng: np.random.Generator,
             hours_per_response: float, specs: dict[str, frozenset[str]]) -> pd.DataFrame:
    """Burden and accuracy by collection mode, and for mixtures with manual entry."""
    ev = SpecEvaluator(records, cfg)
    sel = SelectionEvaluator(ev, np.random.default_rng(cfg.seed + 7))
    res_share = _res_share(cfg)
    modal = bm.modal_times(cfg.burden)
    kappa = float(bm.calibration_factor(cfg.burden, modal, res_share, hours_per_response))
    draws = bm.sample_times(cfg.burden, rng, cfg.burden.monte_carlo_draws)
    kappa_d = bm.calibration_factor(cfg.burden, draws, res_share, hours_per_response)
    rows = []
    for key, elements in specs.items():
        per_mode: dict[str, dict[str, float]] = {}
        for mode in MODES:
            res = ev.evaluate(elements, mode)
            loss = ev.losses(res)
            b = float(bm.mean_burden(elements, mode, res_share, modal, cfg.burden, kappa,
                                     loss["flag_rate"]))
            bd = np.asarray(bm.mean_burden(elements, mode, res_share, draws, cfg.burden,
                                           kappa_d, loss["flag_rate"]))
            per_mode[mode] = {"burden": b, "mare": loss["mare"],
                              "median_are": loss["median_are"],
                              "selection_change": sel.change_probability(res)[0],
                              "burden_lo": float(np.quantile(bd, 0.05)),
                              "burden_hi": float(np.quantile(bd, 0.95))}
        for mode in MODES:
            for avail in (cfg.experiments.availability_grid if mode != "manual_transcription"
                          else [1.0]):
                mix = {k: avail * per_mode[mode][k]
                       + (1 - avail) * per_mode["manual_transcription"][k]
                       for k in ("burden", "mare", "selection_change", "burden_lo",
                                 "burden_hi")}
                rows.append({"spec": key, "mode": mode, "availability": avail, **mix})
    return pd.DataFrame(rows)


# --- sensitivity, convergence, interval coverage ----------------------------------------------


def burden_sobol(cfg: Config, hours_per_response: float, elements: frozenset[str],
                 res_share: float, flag_rates: tuple[float, float]) -> pd.DataFrame:
    """Sobol indices of the burden difference (recommended minus current specification)."""
    params = bm.time_parameters(cfg.burden)
    active = [p for p in params if p.high > p.low]
    problem = {"num_vars": len(active), "names": [p.name for p in active],
               "bounds": [[0.0, 1.0]] * len(active)}
    u = sobol_sample.sample(problem, cfg.burden.sobol_base_samples, calc_second_order=False,
                            seed=cfg.seed)
    times: dict[str, Any] = {p.name: np.full(u.shape[0], p.mode) for p in params}
    for j, p in enumerate(active):
        times[p.name] = p.sample(u[:, j])
    kappa = bm.calibration_factor(cfg.burden, times, res_share, hours_per_response)
    y = np.asarray(
        bm.mean_burden(elements, "manual_transcription", res_share, times, cfg.burden, kappa,
                       flag_rates[1])
        - bm.mean_burden(frozenset(), "manual_transcription", res_share, times, cfg.burden,
                         kappa, flag_rates[0]))
    si = sobol_analyze.analyze(problem, y, calc_second_order=False, num_resamples=200,
                               seed=cfg.seed)
    return pd.DataFrame({"parameter": problem["names"], "S1": si["S1"],
                         "S1_conf": si["S1_conf"], "ST": si["ST"], "ST_conf": si["ST_conf"],
                         "output_mean": float(y.mean()), "output_sd": float(y.std(ddof=1))})


def convergence(records: pd.DataFrame, cfg: Config, specs: dict[str, frozenset[str]]
                ) -> pd.DataFrame:
    """Running estimates and Monte Carlo standard errors of headline quantities."""
    ev = SpecEvaluator(records, cfg)
    rows = []
    sizes = np.unique(np.round(np.geomspace(
        min(cfg.experiments.convergence_min_n, ev.n), ev.n,
        cfg.experiments.convergence_points)).astype(int))
    for key, elements in specs.items():
        are = np.minimum(ev.evaluate(elements).are, cfg.experiments.are_cap)
        for n in sizes:
            sub = are[:n]
            rows.append({"spec": key, "n": int(n), "mare": float(sub.mean()),
                         "se": float(sub.std(ddof=1) / np.sqrt(n)),
                         "relative_se": float(sub.std(ddof=1) / np.sqrt(n) / sub.mean())})
    return pd.DataFrame(rows)


def interval_coverage(records: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Coverage of true avoided energy use by ASHRAE-14 and block-bootstrap intervals."""
    eei = records[(records["category"] == "EEI") & records["c_boot_lo"].notna()]
    truth = eei["true_savings_avoided"].to_numpy()
    est = eei["c_s_avoided"].to_numpy()
    half = np.abs(eei["c_fsu"].to_numpy() * est)
    half = np.where(np.isfinite(half), half, np.inf)
    cover_fsu = np.abs(truth - est) <= half
    cover_boot = (truth >= eei["c_boot_lo"].to_numpy()) & (truth <= eei["c_boot_hi"].to_numpy())
    width_boot = (eei["c_boot_hi"].to_numpy() - eei["c_boot_lo"].to_numpy()) / 2
    finite = np.isfinite(half)
    return pd.DataFrame([{
        "n": int(len(eei)), "nominal": cfg.mv.confidence,
        "coverage_fsu": float(cover_fsu.mean()),
        "coverage_bootstrap": float(cover_boot.mean()),
        "median_halfwidth_fsu_rel": float(np.median(half[finite] / np.abs(truth[finite]))),
        "median_halfwidth_bootstrap_rel": float(np.median(width_boot / np.abs(truth))),
        "share_fsu_unbounded": float((~finite).mean()),
    }])


def population_summary(records: pd.DataFrame, cfg: Config) -> dict[str, Any]:
    pop = load_population(tuple(cfg.population.size_fit_fiscal_years))
    r = records
    return {
        "n": int(len(r)), "res_share_awards": pop.res_share,
        "res_share_sample": float((r["category"] == "RES").mean()),
        "error_share": float((r["error_class"] != "none").mean()),
        "award_fit": pop.award_fit, "award_log_mean": pop.award_log_mean,
        "award_log_sd": pop.award_log_sd,
        "median_request": float(r["amount_requested"].median()),
        "median_capacity_kw": float(r.loc[r["category"] == "RES", "capacity_kw"].median()),
        "median_savings_fraction": float(
            r.loc[r["category"] == "EEI", "savings_fraction"].median()),
        "median_replaced_fraction": float(
            r.loc[r["category"] == "RES", "replaced_fraction"].median()),
        "median_station_distance_km": float(r["station_distance_km"].median()),
        "n_states": int(r["state"].nunique()),
        "plausibility_sigma": {},
    }


def write_json(path: Path, obj: Any) -> None:
    def default(o: Any) -> Any:
        if isinstance(o, np.generic):
            return o.item()
        if isinstance(o, frozenset | set):
            return sorted(o)
        raise TypeError(type(o))

    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=default) + "\n")


RULE_TABLE = [(r.key, r.description, ", ".join(sorted(r.requires)) or "none", r.applies_to,
               r.kind) for r in RULES]
