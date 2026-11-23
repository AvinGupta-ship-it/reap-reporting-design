"""Synthetic applicant generator.

Each synthetic applicant combines a facility load model, actual-year weather at a
hypothetical site, a photovoltaic system or an efficiency measure, a billing
process and (with scenario probabilities) one injected reporting error. Ground
truth is retained for every applicant. All outputs are synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd
from scipy import stats

from reapschema.config import Config
from reapschema.data.process import PROCESSED
from reapschema.synth import billing, eei, errors, loads, pv
from reapschema.synth.evidence import Evidence
from reapschema.synth.weather import SiteWeather, available_states, site_weather

PRE_HISTORY_DAYS = 830
POST_HISTORY_DAYS = 420


@dataclass(frozen=True)
class Truth:
    production: float  # kWh in the 365 days from the in-service day (RES)
    production_normal: float  # mean annual kWh over the weather record (RES)
    pre_consumption: float  # kWh in the 365 days before the in-service day
    savings_avoided: float  # counterfactual minus actual, 365 days after (EEI)
    savings_normal: float  # mean annual savings over the weather record (EEI)
    affected_share: float


@dataclass(frozen=True)
class SyntheticApplicant:
    index: int
    state: str
    category: str
    facility_type: str
    truth: Truth
    clean: Evidence
    reported: Evidence  # equals ``clean`` when no error was injected
    error: errors.ErrorLabel
    covariates: dict[str, float]

    @property
    def target(self) -> float:
        """Quantity the evidence is meant to establish (annual kWh)."""
        return self.truth.production if self.category == "RES" else self.truth.savings_normal


@dataclass(frozen=True)
class Population:
    """Empirical inputs for sampling applicants (from USAspending and EIA)."""

    states: tuple[str, ...]
    state_probs: np.ndarray
    res_share: float
    award_log_mean: dict[str, float]
    award_log_sd: dict[str, float]
    award_fit: dict[str, dict[str, float]]
    award_samples: dict[str, np.ndarray]
    prices: dict[str, float]


@lru_cache(maxsize=4)
def load_population(fit_years: tuple[int, ...]) -> Population:
    awards = pd.read_csv(PROCESSED / "reap_awards.csv")
    states = tuple(sorted(available_states()))
    in_states = awards[awards["state"].isin(states)]
    counts = in_states["state"].value_counts().reindex(states).fillna(0.0) + 1.0
    res_share = float((awards["category"] == "RES").mean())
    log_mean: dict[str, float] = {}
    log_sd: dict[str, float] = {}
    fit: dict[str, dict[str, float]] = {}
    samples: dict[str, np.ndarray] = {}
    for cat in ("RES", "EEI"):
        sel = awards[(awards["category"] == cat) & awards["fiscal_year"].isin(fit_years)]
        samples[cat] = np.sort(sel["amount_usd"].to_numpy(dtype=float))
        logs = np.log(samples[cat])
        log_mean[cat] = float(logs.mean())
        log_sd[cat] = float(logs.std(ddof=1))
        ad = stats.anderson(logs, dist="norm")
        ks = stats.kstest((logs - logs.mean()) / logs.std(ddof=1), "norm")
        fit[cat] = {"n": float(logs.size), "anderson_darling": float(ad.statistic),
                    "ad_critical_5pct": float(ad.critical_values[2]),
                    "ks_statistic": float(ks.statistic)}
    prices_frame = pd.read_csv(PROCESSED / "prices.csv")
    prices = dict(zip(prices_frame["state"], prices_frame["commercial_usd_per_kwh"],
                      strict=True))
    return Population(states, (counts / counts.sum()).to_numpy(), res_share, log_mean, log_sd,
                      fit, samples, {str(k): float(v) for k, v in prices.items()})


def draw_award(rng: np.random.Generator, population: Population, category: str,
               distribution: str) -> float:
    """Historical award amount: resampled from observed awards or from the lognormal fit."""
    if distribution == "empirical":
        return float(rng.choice(population.award_samples[category]))
    return float(np.exp(rng.normal(population.award_log_mean[category],
                                   population.award_log_sd[category])))


def _daily(x: np.ndarray) -> np.ndarray:
    return x.reshape(-1, 24).sum(axis=1)


def _shifted_sets(all_bills: billing.Bills, in_service_day: int, shift: int
                  ) -> tuple[billing.Bills, billing.Bills]:
    """Pre and post sets displaced across the in-service date by ``shift`` bills."""
    pre_idx = np.flatnonzero(all_bills.end < in_service_day)[-12:]
    post_idx = np.flatnonzero(all_bills.start >= in_service_day)[:12]
    return all_bills.take(pre_idx + shift + 1), all_bills.take(post_idx - shift - 1)


def generate_applicant(index: int, seed: np.random.SeedSequence, cfg: Config, *,
                       estimated_prob: float | None = None,
                       error_class: str | None = None) -> SyntheticApplicant:
    """Generate one synthetic applicant from its own seed sequence."""
    rng = np.random.default_rng(seed)
    pop_cfg = cfg.population
    population = load_population(tuple(pop_cfg.size_fit_fiscal_years))
    state = str(rng.choice(population.states, p=population.state_probs))
    weather: SiteWeather = site_weather(state)
    category = "RES" if rng.random() < population.res_share else "EEI"
    types = list(pop_cfg.facility_types)
    facility_type = str(rng.choice(types, p=[pop_cfg.facility_types[t] for t in types]))
    model = loads.individualize(loads.facility_model(state, facility_type), rng, pop_cfg.load)
    price = population.prices[state]

    d_lo = max(weather.day_of(pop_cfg.install_date_range[0]), PRE_HISTORY_DAYS)
    d_hi = min(weather.day_of(pop_cfg.install_date_range[1]),
               weather.n_days - POST_HISTORY_DAYS - 1)
    day0 = int(rng.integers(d_lo, d_hi + 1))  # in-service day
    first_day = day0 - PRE_HISTORY_DAYS
    h0, h1 = first_day * 24, (day0 + POST_HISTORY_DAYS) * 24
    n_hours = h1 - h0
    rel = np.arange(n_hours) // 24 + first_day  # day index of each hour
    after = rel >= day0
    pre_year = (rel >= day0 - 365) & (rel < day0)
    post_year = (rel >= day0) & (rel < day0 + 365)

    end_uses = loads.end_use_loads(model, weather, h0, h1)
    noise = loads.noise_factors(rng, n_hours, pop_cfg.load)
    occupancy = np.ones(n_hours)
    if rng.random() < pop_cfg.load.occupancy_change_prob:
        when = int(rng.integers(day0 - 300, day0 + 300))
        occupancy[rel >= when] = max(1.0 + rng.normal(0.0, pop_cfg.load.occupancy_change_sd), 0.5)
    base_names = set(model.base)
    shape = np.zeros(n_hours)
    for name, arr in end_uses.items():
        shape += arr * (occupancy if name in base_names else 1.0)
    shape_noisy = shape * noise
    pre_total_rel = float(shape_noisy[pre_year].sum())
    shares = {name: float(arr[pre_year].sum() / max(shape[pre_year].sum(), 1e-12))
              for name, arr in end_uses.items()}

    # deterministic full-record series for normal-year truth
    full_hours = weather.n_days * 24
    years = weather.n_days / 365.0

    capacity = tilt = 0.0
    azimuth = 180.0
    has_storage = False
    arrangement = "none"
    pv_series = np.zeros(n_hours)
    savings_rel = np.zeros(n_hours)
    affected_share = 0.0
    production_normal = savings_normal = 0.0
    technology: str
    factor = 1.0

    if category == "RES":
        res = pop_cfg.res
        technology = "solar_electric"
        award = draw_award(rng, population, "RES", pop_cfg.size_distribution)
        cost = award / pop_cfg.historical_award_share_of_cost
        capacity = cost / (res.cost_per_watt_median * float(
            rng.lognormal(0.0, res.cost_per_watt_log_sd))) / 1000.0
        tilt = float(rng.uniform(*res.tilt_range_deg))
        azimuth = float(np.clip(rng.normal(res.azimuth_mean_deg, res.azimuth_sd_deg), 90, 270))
        factor = (float(rng.lognormal(0.0, res.derate_log_sd))
                  * (1.0 - float(rng.uniform(0.0, res.shading_loss_max)))
                  * (1.0 + float(rng.normal(0.0, res.irradiance_bias_sd))))
        kwargs = dict(capacity_kw=capacity, tilt=tilt, surface_azimuth=azimuth,
                      dc_ac_ratio=res.dc_ac_ratio, inverter_efficiency=res.inverter_efficiency,
                      system_losses=res.system_losses,
                      temperature_coefficient=res.temperature_coefficient)
        full = pv.simulate_site_pv(weather, 0, full_hours, **kwargs) * factor
        production_normal = float(full.sum() / years)
        pv_series = np.where(after, full[h0:h1], 0.0)
        production = float(pv_series[post_year].sum())
        replaced = float(rng.uniform(*res.replaced_fraction_range))
        scale = production / replaced / pre_total_rel
        has_storage = bool(rng.random() < res.storage_share)
        names = list(res.netting_arrangements)
        arrangement = str(rng.choice(names, p=[res.netting_arrangements[k] for k in names]))
        useful_life = res.useful_life_years
        max_request = pop_cfg.max_request_res
    else:
        e_cfg = pop_cfg.eei
        measure = eei.draw_measure(rng, shares, e_cfg)
        technology = measure.technology
        savings_rel = eei.savings_series(end_uses, measure)
        occ_sel = np.zeros(n_hours)
        for name in measure.end_uses:
            if name in end_uses:
                occ_sel += measure.reduction * end_uses[name] * (
                    occupancy if name in base_names else 1.0)
        savings_rel = occ_sel
        affected_share = float(sum(shares.get(e, 0.0) for e in measure.end_uses))
        fraction = float((savings_rel * noise)[pre_year].sum() / pre_total_rel)
        award = draw_award(rng, population, "EEI", pop_cfg.size_distribution)
        cost = award / pop_cfg.historical_award_share_of_cost
        payback = float(np.clip(rng.lognormal(np.log(e_cfg.payback_median_years),
                                              e_cfg.payback_log_sd),
                                0.5, e_cfg.useful_life_years))
        annual_savings = cost / (payback * price)
        scale = annual_savings / max(fraction, 1e-6) / pre_total_rel
        useful_life = e_cfg.useful_life_years
        max_request = pop_cfg.max_request_eei
        # normal-year savings with the facility in its final occupancy state
        full_eu = loads.end_use_loads(model, weather, 0, full_hours)
        occ_final = float(occupancy[-1])
        full_sav = np.zeros(full_hours)
        for name in measure.end_uses:
            if name in full_eu:
                full_sav += measure.reduction * full_eu[name] * (
                    occ_final if name in base_names else 1.0)
        savings_normal = float(full_sav.sum() / years) * scale

    load_cf = scale * shape_noisy
    load = load_cf - np.where(after, scale * savings_rel * noise, 0.0)
    load = np.maximum(load, 0.0)
    delivered_h = np.maximum(load - pv_series, 0.0)
    export_h = np.maximum(pv_series - load, 0.0)
    if arrangement == "none":
        export_register = np.zeros(n_hours)
    else:
        export_register = export_h
    basis = "net_of_exports" if arrangement == "conventional_net_metering" else "delivered_only"

    reads = billing.read_days(rng, first_day, day0 + POST_HISTORY_DAYS - 1,
                              cfg.billing.cycle_mean_days, cfg.billing.read_jitter_days)
    all_bills = billing.make_bills(
        rng, _daily(delivered_h), _daily(export_register),
        delivered_h.reshape(-1, 24).max(axis=1), first_day, reads, cfg.billing, price, basis,
        estimated_prob=estimated_prob,
    )
    pre_bills, post_bills, earlier = billing.select_periods(all_bills, day0)

    truth = Truth(
        production=float(pv_series[post_year].sum()),
        production_normal=production_normal,
        pre_consumption=float(load[pre_year].sum()),
        savings_avoided=float((load_cf - load)[post_year].sum()),
        savings_normal=savings_normal,
        affected_share=affected_share,
    )
    request = float(np.clip(pop_cfg.award_share_of_cost * cost, pop_cfg.min_request,
                            max_request))

    inv_start = inv_end = np.zeros(0, dtype=int)
    inv_kwh = np.zeros(0)
    inverter_total = 0.0
    if category == "RES":
        meter = 1.0 + float(rng.normal(0.0, pop_cfg.res.meter_error_sd))
        edges = day0 + np.round(np.arange(13) * 365.0 / 12.0).astype(int)
        daily_pv = _daily(pv_series)
        inv_start, inv_end = edges[:-1], edges[1:] - 1
        inv_kwh = np.array([daily_pv[a - first_day:b - first_day + 1].sum()
                            for a, b in zip(inv_start, inv_end, strict=True)]) * meter
        inverter_total = float(inv_kwh.sum())
        claim = inverter_total
        method = "metered_production"
    else:
        claim = float(pre_bills.printed.sum() - post_bills.printed.sum())
        method = "billing_difference"

    daily_delivered = _daily(delivered_h)
    daily_export = _daily(export_register)
    a_pre, a_post = day0 - 365 - first_day, day0 - first_day
    reported_share = float(np.clip(affected_share * (1.0 + rng.normal(0.0, 0.10)), 0.0, 1.0))
    clean = Evidence(
        applicant_id=f"{index:06d}", state=state, category=category, technology=technology,
        in_service_day=day0, project_cost=cost, amount_requested=request, energy_price=price,
        useful_life_years=useful_life, pre_bills=pre_bills, post_bills=post_bills,
        claim_value=claim, claim_pre_energy=float(pre_bills.printed.sum()),
        claim_method=method, capacity_kw=capacity, tilt=tilt, azimuth=azimuth,
        has_storage=has_storage, arrangement=arrangement, inverter_start=inv_start,
        inverter_end=inv_end, inverter_kwh=inv_kwh, enduse_share=reported_share,
        interval_pre_daily=daily_delivered[a_pre:a_post],
        interval_post_daily=daily_delivered[a_post:a_post + 365],
        interval_post_export_daily=daily_export[a_post:a_post + 365],
        interval_inverter_total=inverter_total,
    )

    chosen = error_class if error_class is not None else errors.draw_error_class(
        rng, category, cfg.errors)
    if category == "EEI" and chosen in errors.RES_ONLY:
        chosen = "none"
    shift = int(rng.integers(0, 3))
    ghi_daily_kwh = float(weather.ghi.sum() / weather.n_days / 1000.0)
    reported, label = errors.inject(
        clean, chosen, rng, cfg.errors, earlier_bills=earlier,
        straddling=_shifted_sets(all_bills, day0, shift), mean_daily_ghi_kwh=ghi_daily_kwh,
    )

    t_pre = weather.daily_temp_site[day0 - 365:day0]
    t_post = weather.daily_temp_site[day0:day0 + 365]
    ghi_post = float(weather.ghi[day0 * 24:(day0 + 365) * 24].sum())
    covariates = {
        "delta_hdd18": float(np.maximum(18.0 - t_post, 0).sum()
                             - np.maximum(18.0 - t_pre, 0).sum()),
        "delta_cdd18": float(np.maximum(t_post - 18.0, 0).sum()
                             - np.maximum(t_pre - 18.0, 0).sum()),
        "delta_mean_temp": float(t_post.mean() - t_pre.mean()),
        "ghi_anomaly": ghi_post / (float(weather.ghi.sum()) / years) - 1.0,
        "occupancy_changed": float(occupancy[0] != occupancy[-1]),
        "savings_fraction": (truth.savings_normal / truth.pre_consumption
                             if category == "EEI" else 0.0),
        "replaced_fraction": (truth.production / truth.pre_consumption
                              if category == "RES" else 0.0),
        "n_estimated_reads": float(pre_bills.estimated.sum() + post_bills.estimated.sum()),
        "install_day": float(day0),
        "pv_factor": factor if category == "RES" else 1.0,
        "station_distance_km": weather.station_distance_km,
    }
    return SyntheticApplicant(index, state, category, facility_type, truth, clean, reported,
                              label, covariates)


def spawn_seeds(seed: int, n: int) -> list[np.random.SeedSequence]:
    """Independent per-applicant seed sequences (results do not depend on worker count)."""
    return list(np.random.SeedSequence(seed).spawn(n))
