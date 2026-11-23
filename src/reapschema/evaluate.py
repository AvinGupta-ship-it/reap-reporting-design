"""Evaluation of synthetic applicants: estimator values and rule scores per submission.

For every applicant the estimators and rules are run on the evidence as reported
(possibly containing an injected error) and on the error-free evidence. The flat
records produced here are the inputs of every experiment.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from typing import Any

import numpy as np
import pandas as pd

from reapschema import mv, validate
from reapschema.config import Config
from reapschema.synth.evidence import Evidence
from reapschema.synth.generator import SyntheticApplicant, generate_applicant, spawn_seeds
from reapschema.synth.weather import site_weather


def _periods(bills: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return bills.start, bills.end, bills.printed


def path_values(ev: Evidence, cfg: Config, *, with_bootstrap: np.random.Generator | None = None
                ) -> dict[str, float]:
    """Verified-quantity candidates under each estimator path for one submission."""
    pre, post = ev.pre_bills, ev.post_bills
    out: dict[str, float] = {
        "cpre_undated": float(pre.printed.sum()),
        "cpre_dated": float(pre.printed.sum() / pre.days.sum() * 365.0),
        "cpre_interval": float(ev.interval_pre_daily.sum()),
    }
    if ev.category == "RES":
        out["p_claim"] = float(ev.claim_value)
        out["p_inverter"] = float(ev.inverter_kwh.sum())
        out["p_interval"] = float(ev.interval_inverter_total)
        return out
    weather = site_weather(ev.state)
    table = mv.station_table(ev.state, cfg.mv.balance_grid_f)
    out["s_undated"] = float(pre.printed.sum() - post.printed.sum())
    out["s_dated"] = float(365.0 * (pre.printed.sum() / pre.days.sum()
                                    - post.printed.sum() / post.days.sum()))
    est = mv.estimate_savings(_periods(pre), _periods(post), table, cfg.mv.confidence)
    out["s_norm"] = est.normalized
    out["s_avoided"] = est.avoided
    out["fsu"] = est.fsu
    out["cvrmse"] = est.baseline.cvrmse
    out["ndb"] = est.baseline.ndb
    out["adj_r2"] = est.baseline.adj_r2
    out["rho"] = est.autocorrelation
    out["cvrmse_post"] = est.reporting.cvrmse
    # normalization is used only when both models meet the fit criterion; otherwise the
    # day-annualized difference is retained
    limit = cfg.validation.cvrmse_max
    fits = est.baseline.cvrmse <= limit and est.reporting.cvrmse <= limit
    out["s_norm_guarded"] = est.normalized if fits else out["s_dated"]
    merged = mv.estimate_savings(
        mv.merge_estimated(pre.start, pre.end, pre.printed, pre.estimated),
        mv.merge_estimated(post.start, post.end, post.printed, post.estimated),
        table, cfg.mv.confidence)
    out["s_norm_merged"] = merged.normalized
    out["s_avoided_merged"] = merged.avoided
    fits_m = merged.baseline.cvrmse <= limit and merged.reporting.cvrmse <= limit
    out["s_norm_merged_guarded"] = merged.normalized if fits_m else out["s_dated"]
    weekend = weather.daytype.reshape(-1, 24)[:, 0]
    d0 = ev.in_service_day
    daily = mv.estimate_savings_daily(
        ev.interval_pre_daily, ev.interval_post_daily, d0 - 365, d0, weather.daily_temp_station,
        weekend, mv.station_table(ev.state, cfg.mv.daily_heating_grid_f),
        mv.station_table(ev.state, cfg.mv.daily_cooling_grid_f), cfg.mv.confidence)
    out["s_interval_norm"] = daily.normalized
    out["s_interval_avoided"] = daily.avoided
    out["fsu_interval"] = daily.fsu
    if with_bootstrap is not None:
        lo, hi = mv.bootstrap_avoided_interval(
            _periods(pre), _periods(post), table, est, with_bootstrap,
            cfg.mv.bootstrap_replicates, cfg.mv.bootstrap_block, cfg.mv.confidence)
        out["boot_lo"], out["boot_hi"] = lo, hi
    return out


def evaluate_applicant(app: SyntheticApplicant, cfg: Config,
                       seed: np.random.SeedSequence | None = None) -> dict[str, Any]:
    """Flat record of truth, estimator values and rule scores for one applicant."""
    ev = app.clean
    rec: dict[str, Any] = {
        "index": app.index, "state": app.state, "category": app.category,
        "facility_type": app.facility_type, "technology": ev.technology,
        "error_class": app.error.error_class, "error_variant": app.error.variant,
        "error_target": app.error.target, "error_magnitude": app.error.magnitude,
        "project_cost": ev.project_cost, "amount_requested": ev.amount_requested,
        "energy_price": ev.energy_price, "useful_life": ev.useful_life_years,
        "capacity_kw": ev.capacity_kw, "has_storage": ev.has_storage,
        "arrangement": ev.arrangement, "enduse_share": ev.enduse_share,
        "true_production": app.truth.production,
        "true_production_normal": app.truth.production_normal,
        "true_pre_consumption": app.truth.pre_consumption,
        "true_savings_avoided": app.truth.savings_avoided,
        "true_savings_normal": app.truth.savings_normal,
        **app.covariates,
    }
    model_declared = (app.truth.production / app.covariates["pv_factor"]
                      if app.category == "RES" else 0.0)
    rec["model_post_declared"] = model_declared
    if app.category == "RES":
        daily = mv.default_model(app.state, cfg.mv, cfg.population.res)
        d0 = ev.in_service_day
        years = daily.size / 365.0
        rec["model_post_default"] = ev.capacity_kw * float(daily[d0:d0 + 365].sum())
        rec["model_normal_default"] = ev.capacity_kw * float(daily.sum() / years)
        rec["model_normal_declared"] = (app.truth.production_normal
                                        / app.covariates["pv_factor"])
    boot = None
    if (seed is not None and app.category == "EEI"
            and app.index < cfg.mv.bootstrap_subsample * 5):
        boot = np.random.default_rng(seed.spawn(1)[0])
    clean_paths = path_values(ev, cfg, with_bootstrap=boot)
    clean_rules = validate.rule_scores(ev, cfg, model_post_declared=model_declared)
    if app.category == "EEI":
        clean_rules["model_fit"] = clean_paths["cvrmse"]
    if app.reported is app.clean:
        rep_paths, rep_rules = clean_paths, clean_rules
    else:
        rep_paths = path_values(app.reported, cfg)
        rep_rules = validate.rule_scores(app.reported, cfg, model_post_declared=model_declared)
        if app.category == "EEI":
            rep_rules["model_fit"] = rep_paths["cvrmse"]
    for name, value in clean_paths.items():
        rec[f"c_{name}"] = value
    for name, value in rep_paths.items():
        if not name.startswith("boot_"):
            rec[f"r_{name}"] = value
    for name, value in clean_rules.items():
        rec[f"c_rule_{name}"] = value
    for name, value in rep_rules.items():
        rec[f"r_rule_{name}"] = value
    return rec


def _work(args: tuple[int, np.random.SeedSequence, Config, dict[str, Any]]) -> dict[str, Any]:
    index, seed, cfg, kwargs = args
    app = generate_applicant(index, seed, cfg, **kwargs)
    return evaluate_applicant(app, cfg, seed)


def simulate(cfg: Config, n: int | None = None, *, seed: int | None = None,
             workers: int | None = None, **generator_kwargs: Any) -> pd.DataFrame:
    """Generate and evaluate ``n`` synthetic applicants.

    Each applicant uses its own child of ``SeedSequence(seed)``, so results are
    identical for any number of worker processes.
    """
    n = cfg.n_applicants if n is None else n
    seeds = spawn_seeds(cfg.seed if seed is None else seed, n)
    tasks = [(i, seeds[i], cfg, generator_kwargs) for i in range(n)]
    n_workers = cfg.n_workers if workers is None else workers
    if n_workers <= 1:
        records = [_work(t) for t in tasks]
    else:
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            records = list(pool.map(_work, tasks, chunksize=16))
    return pd.DataFrame.from_records(records)
