"""Measurement and verification estimators.

Whole-facility degree-day regression in the form of the CalTRACK billing method
and ASHRAE Guideline 14, avoided energy use and normalized annual savings,
fractional savings uncertainty, a residual block bootstrap, and weather
normalization and plausibility statistics for photovoltaic production.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from scipy import stats

from reapschema.config import MvConfig, ResConfig
from reapschema.synth import pv
from reapschema.synth.weather import site_weather


def c_to_f(temp_c: np.ndarray) -> np.ndarray:
    return temp_c * 9.0 / 5.0 + 32.0


def grid(spec: tuple[float, float, float]) -> np.ndarray:
    lo, hi, step = spec
    return np.arange(lo, hi + 0.5 * step, step)


@dataclass(frozen=True)
class DegreeDayTable:
    """Cumulative degree days of a daily temperature record for a grid of balance points."""

    grid_f: np.ndarray
    cum_hdd: np.ndarray  # (n_days + 1, G), deg F day
    cum_cdd: np.ndarray
    normal_hdd: np.ndarray  # mean annual degree days over the record, (G,)
    normal_cdd: np.ndarray

    def hdd(self, start: np.ndarray, end: np.ndarray) -> np.ndarray:
        """Heating degree days of inclusive day ranges; shape (n, G)."""
        return np.asarray(self.cum_hdd[np.asarray(end) + 1] - self.cum_hdd[np.asarray(start)])

    def cdd(self, start: np.ndarray, end: np.ndarray) -> np.ndarray:
        return np.asarray(self.cum_cdd[np.asarray(end) + 1] - self.cum_cdd[np.asarray(start)])


def degree_day_table(daily_temp_c: np.ndarray, grid_f: np.ndarray) -> DegreeDayTable:
    t = c_to_f(np.asarray(daily_temp_c, dtype=float))[:, None]
    hdd = np.maximum(grid_f[None, :] - t, 0.0)
    cdd = np.maximum(t - grid_f[None, :], 0.0)
    zero = np.zeros((1, grid_f.size))
    years = t.shape[0] / 365.0
    return DegreeDayTable(
        grid_f=grid_f,
        cum_hdd=np.vstack([zero, np.cumsum(hdd, axis=0)]),
        cum_cdd=np.vstack([zero, np.cumsum(cdd, axis=0)]),
        normal_hdd=hdd.sum(axis=0) / years,
        normal_cdd=cdd.sum(axis=0) / years,
    )


@lru_cache(maxsize=128)
def station_table(state: str, grid_spec: tuple[float, float, float]) -> DegreeDayTable:
    """Degree-day table of the weather station assigned to a State's site."""
    return degree_day_table(site_weather(state).daily_temp_station, grid(grid_spec))


@dataclass(frozen=True)
class DegreeDayModel:
    """Fitted model ``E = b0*d + bH*HDD(T_H) + bC*CDD(T_C)`` (plus optional extra terms)."""

    beta0: float
    beta_h: float
    beta_c: float
    i_h: int  # index of the heating balance point in the grid, -1 if absent
    i_c: int
    t_h_f: float
    t_c_f: float
    extra: np.ndarray  # coefficients of additional per-day regressors
    adj_r2: float
    cvrmse: float
    ndb: float
    n: int
    p: int
    residuals: np.ndarray  # per-day residuals of the fitting periods
    weights: np.ndarray

    def predict(self, days: np.ndarray, hdd: np.ndarray, cdd: np.ndarray,
                extra: np.ndarray | None = None) -> np.ndarray:
        """Predicted period energy from days and (n, G) degree-day arrays."""
        out = self.beta0 * np.asarray(days, dtype=float)
        if self.i_h >= 0:
            out = out + self.beta_h * hdd[:, self.i_h]
        if self.i_c >= 0:
            out = out + self.beta_c * cdd[:, self.i_c]
        if extra is not None and self.extra.size:
            out = out + (extra @ self.extra) * days
        return out

    def predict_normal_year(self, table: DegreeDayTable, extra_mean: np.ndarray | None = None
                            ) -> float:
        out = self.beta0 * 365.0
        if self.i_h >= 0:
            out += self.beta_h * float(table.normal_hdd[self.i_h])
        if self.i_c >= 0:
            out += self.beta_c * float(table.normal_cdd[self.i_c])
        if extra_mean is not None and self.extra.size:
            out += float(extra_mean @ self.extra) * 365.0
        return float(out)


def _candidates(n_grid_h: int, n_grid_c: int, grid_h: np.ndarray, grid_c: np.ndarray
                ) -> tuple[np.ndarray, np.ndarray]:
    ih = [-1]
    ic = [-1]
    for i in range(n_grid_h):
        ih.append(i)
        ic.append(-1)
    for j in range(n_grid_c):
        ih.append(-1)
        ic.append(j)
    for i in range(n_grid_h):
        for j in range(n_grid_c):
            if grid_c[j] >= grid_h[i]:
                ih.append(i)
                ic.append(j)
    return np.asarray(ih), np.asarray(ic)


def fit_degree_day_model(
    energy: np.ndarray, days: np.ndarray, hdd: np.ndarray, cdd: np.ndarray,
    grid_h: np.ndarray, grid_c: np.ndarray, extra: np.ndarray | None = None,
    min_nonzero_periods: int = 3,
) -> DegreeDayModel:
    """Weighted least-squares fit with a grid search over balance points.

    The model is fitted to average daily use with weights equal to the number of
    days in each period, which is the per-day form of
    ``E_m = b0*d_m + bH*HDD_m + bC*CDD_m``. Candidates with a negative degree-day
    coefficient, or with fewer than ``min_nonzero_periods`` periods of non-zero degree
    days, are rejected;
    the candidate with the highest adjusted R-squared is selected.
    """
    energy = np.asarray(energy, dtype=float)
    days = np.asarray(days, dtype=float)
    n = energy.size
    y = energy / days
    w = days / days.sum()
    q = 0 if extra is None else extra.shape[1]
    ih, ic = _candidates(hdd.shape[1], cdd.shape[1], grid_h, grid_c)
    k = ih.size
    p_max = 3 + q
    x = np.zeros((k, n, p_max))
    x[:, :, 0] = 1.0
    xh = (hdd / days[:, None]).T  # (G, n)
    xc = (cdd / days[:, None]).T
    has_h = ih >= 0
    has_c = ic >= 0
    x[has_h, :, 1] = xh[ih[has_h]]
    x[has_c, :, 2] = xc[ic[has_c]]
    if extra is not None:
        x[:, :, 3:] = extra[None, :, :]
    xtw = x.transpose(0, 2, 1) * w[None, None, :]
    beta = np.einsum("kij,kj->ki", np.linalg.pinv(xtw @ x), xtw @ y)
    fitted = np.einsum("knp,kp->kn", x, beta)
    resid = y[None, :] - fitted
    sse = (w[None, :] * resid**2).sum(axis=1)
    ybar = float((w * y).sum())
    sst = float((w * (y - ybar) ** 2).sum())
    p = 1 + q + has_h.astype(int) + has_c.astype(int)
    dof = np.maximum(n - p, 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        r2 = 1.0 - sse / sst if sst > 0 else np.zeros(k)
        adj = 1.0 - (1.0 - r2) * (n - 1) / dof
    nonzero_h = (x[:, :, 1] > 0).sum(axis=1)
    nonzero_c = (x[:, :, 2] > 0).sum(axis=1)
    valid = (n - p) >= 1
    valid &= ~has_h | ((beta[:, 1] > 0) & (nonzero_h >= min_nonzero_periods))
    valid &= ~has_c | ((beta[:, 2] > 0) & (nonzero_c >= min_nonzero_periods))
    valid[0] = True
    score = np.where(valid, np.nan_to_num(adj, nan=-np.inf), -np.inf)
    score[0] = max(score[0], 0.0) if np.isfinite(score[0]) else 0.0
    best = int(np.argmax(score))
    b = beta[best]
    res = resid[best]
    pb = int(p[best])
    rmse = float(np.sqrt(sse[best] * n / max(n - pb, 1)))
    pred_total = fitted[best] * days
    return DegreeDayModel(
        beta0=float(b[0]),
        beta_h=float(b[1]) if has_h[best] else 0.0,
        beta_c=float(b[2]) if has_c[best] else 0.0,
        i_h=int(ih[best]), i_c=int(ic[best]),
        t_h_f=float(grid_h[ih[best]]) if has_h[best] else float("nan"),
        t_c_f=float(grid_c[ic[best]]) if has_c[best] else float("nan"),
        extra=b[3:].copy(),
        adj_r2=float(adj[best]) if np.isfinite(adj[best]) else 0.0,
        cvrmse=rmse / ybar if ybar > 0 else float("inf"),
        ndb=float((energy - pred_total).sum() / energy.sum()) if energy.sum() != 0 else 0.0,
        n=n, p=pb, residuals=res.copy(), weights=days.copy(),
    )


def merge_estimated(start: np.ndarray, end: np.ndarray, energy: np.ndarray,
                    estimated: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Combine each estimated read with the following period (CalTRACK 2.2.3 practice)."""
    s: list[int] = []
    e: list[int] = []
    v: list[float] = []
    carry_start: int | None = None
    carry = 0.0
    for i in range(len(energy)):
        if estimated[i] and i < len(energy) - 1:
            if carry_start is None:
                carry_start = int(start[i])
            carry += float(energy[i])
            continue
        s.append(int(start[i]) if carry_start is None else carry_start)
        e.append(int(end[i]))
        v.append(float(energy[i]) + carry)
        carry_start, carry = None, 0.0
    return np.asarray(s), np.asarray(e), np.asarray(v)


@dataclass(frozen=True)
class SavingsEstimate:
    avoided: float  # baseline adjusted to post-period weather minus post-period use
    normalized: float  # normal-year baseline minus normal-year post model
    baseline: DegreeDayModel
    reporting: DegreeDayModel
    post_days: int
    fsu: float  # fractional savings uncertainty of the avoided energy use
    autocorrelation: float


def lag1_autocorrelation(residuals: np.ndarray) -> float:
    r = np.asarray(residuals, dtype=float)
    r = r - r.mean()
    denom = float((r * r).sum())
    if denom <= 0 or r.size < 3:
        return 0.0
    return float((r[1:] * r[:-1]).sum() / denom)


def fractional_savings_uncertainty(cvrmse: float, savings_fraction: float, n: int, m: int,
                                   p: int, rho: float, confidence: float) -> float:
    """ASHRAE Guideline 14 fractional savings uncertainty with autocorrelation.

    ``U = t * 1.26 * CV * sqrt((n/n') * (1 + 2/n') / m) / F`` with effective sample
    size ``n' = n (1 - rho) / (1 + rho)``, ``n`` baseline periods, ``m`` reporting
    periods, ``F`` the savings fraction and ``t`` the two-sided Student quantile
    with ``n - p`` degrees of freedom.
    """
    if savings_fraction <= 0 or n - p < 1:
        return float("inf")
    rho_c = float(np.clip(rho, 0.0, 0.9))
    n_eff = n * (1.0 - rho_c) / (1.0 + rho_c)
    t = float(stats.t.ppf(0.5 + confidence / 2.0, n - p))
    return float(t * 1.26 * cvrmse * np.sqrt((n / n_eff) * (1.0 + 2.0 / n_eff) / m)
                 / savings_fraction)


def estimate_savings(
    pre: tuple[np.ndarray, np.ndarray, np.ndarray], post: tuple[np.ndarray, np.ndarray, np.ndarray],
    table: DegreeDayTable, confidence: float, min_nonzero_periods: int = 3,
) -> SavingsEstimate:
    """Savings from (start, end, energy) period arrays before and after installation."""
    g = table.grid_f

    def fit(periods: tuple[np.ndarray, np.ndarray, np.ndarray]) -> DegreeDayModel:
        start, end, energy = periods
        return fit_degree_day_model(energy, end - start + 1, table.hdd(start, end),
                                    table.cdd(start, end), g, g,
                                    min_nonzero_periods=min_nonzero_periods)

    base = fit(pre)
    report = fit(post)
    ps, pe, penergy = post
    pdays = pe - ps + 1
    predicted = base.predict(pdays, table.hdd(ps, pe), table.cdd(ps, pe))
    avoided = float(predicted.sum() - penergy.sum())
    normalized = base.predict_normal_year(table) - report.predict_normal_year(table)
    rho = lag1_autocorrelation(base.residuals)
    frac = avoided / float(predicted.sum()) if predicted.sum() > 0 else 0.0
    fsu = fractional_savings_uncertainty(base.cvrmse, frac, base.n, len(penergy), base.p, rho,
                                         confidence)
    return SavingsEstimate(avoided, normalized, base, report, int(pdays.sum()), fsu, rho)


def estimate_savings_daily(pre_daily: np.ndarray, post_daily: np.ndarray, pre_start: int,
                           post_start: int, daily_temp_c: np.ndarray, weekend: np.ndarray,
                           normal_table_h: DegreeDayTable, normal_table_c: DegreeDayTable,
                           confidence: float, min_nonzero_periods: int = 3
                           ) -> SavingsEstimate:
    """Savings from daily energy (aggregated interval data) with a weekday/weekend term."""
    gh, gc = normal_table_h.grid_f, normal_table_c.grid_f

    def design(start: int, n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        t = c_to_f(daily_temp_c[start:start + n])[:, None]
        return (np.maximum(gh[None, :] - t, 0.0), np.maximum(t - gc[None, :], 0.0),
                weekend[start:start + n].astype(float)[:, None])

    ones_pre = np.ones(pre_daily.size)
    ones_post = np.ones(post_daily.size)
    h_pre, c_pre, x_pre = design(pre_start, pre_daily.size)
    h_post, c_post, x_post = design(post_start, post_daily.size)
    base = fit_degree_day_model(pre_daily, ones_pre, h_pre, c_pre, gh, gc, extra=x_pre,
                                min_nonzero_periods=min_nonzero_periods)
    report = fit_degree_day_model(post_daily, ones_post, h_post, c_post, gh, gc, extra=x_post,
                                  min_nonzero_periods=min_nonzero_periods)
    predicted = base.predict(ones_post, h_post, c_post, extra=x_post)
    avoided = float(predicted.sum() - post_daily.sum())
    wk = np.array([2.0 / 7.0])

    def normal(model: DegreeDayModel) -> float:
        out = model.beta0 * 365.0 + float(wk @ model.extra) * 365.0
        if model.i_h >= 0:
            out += model.beta_h * float(normal_table_h.normal_hdd[model.i_h])
        if model.i_c >= 0:
            out += model.beta_c * float(normal_table_c.normal_cdd[model.i_c])
        return float(out)

    rho = lag1_autocorrelation(base.residuals)
    frac = avoided / float(predicted.sum()) if predicted.sum() > 0 else 0.0
    fsu = fractional_savings_uncertainty(base.cvrmse, frac, base.n, post_daily.size, base.p,
                                         rho, confidence)
    return SavingsEstimate(avoided, normal(base) - normal(report), base, report,
                           int(post_daily.size), fsu, rho)


def bootstrap_avoided_interval(
    pre: tuple[np.ndarray, np.ndarray, np.ndarray], post: tuple[np.ndarray, np.ndarray, np.ndarray],
    table: DegreeDayTable, estimate: SavingsEstimate, rng: np.random.Generator,
    replicates: int, block: int, confidence: float,
) -> tuple[float, float]:
    """Residual moving-block bootstrap interval for avoided energy use.

    Baseline residuals are resampled in blocks, the baseline is refitted at the
    selected balance points, and resampled residuals are added to the post-period
    prediction to represent period-level scatter.
    """
    start, end, energy = pre
    days = (end - start + 1).astype(float)
    base = estimate.baseline
    n = energy.size
    hdd = table.hdd(start, end)
    cdd = table.cdd(start, end)
    cols = [np.ones(n)]
    if base.i_h >= 0:
        cols.append(hdd[:, base.i_h] / days)
    if base.i_c >= 0:
        cols.append(cdd[:, base.i_c] / days)
    x = np.column_stack(cols)
    w = days / days.sum()
    fitted = base.predict(days, hdd, cdd) / days
    ps, pe, penergy = post
    pdays = (pe - ps + 1).astype(float)
    phdd, pcdd = table.hdd(ps, pe), table.cdd(ps, pe)
    pcols = [np.ones(penergy.size)]
    if base.i_h >= 0:
        pcols.append(phdd[:, base.i_h] / pdays)
    if base.i_c >= 0:
        pcols.append(pcdd[:, base.i_c] / pdays)
    xp = np.column_stack(pcols)
    # residuals inflated for the degrees of freedom used by the fit
    resid = base.residuals * np.sqrt(n / max(n - base.p, 1))
    n_blocks = int(np.ceil(n / block))
    m = penergy.size
    m_blocks = int(np.ceil(m / block))
    xtw = x.T * w
    solver = np.linalg.pinv(xtw @ x) @ xtw
    out = np.empty(replicates)
    for b in range(replicates):
        starts = rng.integers(0, n - block + 1, n_blocks)
        idx = (starts[:, None] + np.arange(block)[None, :]).ravel()[:n]
        beta = solver @ (fitted + resid[idx])
        pstarts = rng.integers(0, n - block + 1, m_blocks)
        pidx = (pstarts[:, None] + np.arange(block)[None, :]).ravel()[:m]
        # the estimate's sampling error: refitted baseline plus period scatter
        out[b] = float((((xp @ beta) - resid[pidx]) * pdays).sum() - penergy.sum())
    lo, hi = np.quantile(out, [0.5 - confidence / 2.0, 0.5 + confidence / 2.0])
    centre = estimate.avoided
    return float(2 * centre - hi), float(2 * centre - lo)


# --- photovoltaic production -------------------------------------------------------------


@lru_cache(maxsize=128)
def default_pv_daily(state: str, tilt: float, azimuth: float, dc_ac_ratio: float,
                     inverter_efficiency: float, system_losses: float,
                     temperature_coefficient: float, albedo: float,
                     sapm_cell: tuple[float, float, float]) -> np.ndarray:
    """Modelled daily production per kW (kWh/kW) at a State's site for a default geometry."""
    weather = site_weather(state)
    hourly = pv.simulate_site_pv(
        weather, 0, weather.n_days * 24, capacity_kw=1.0, tilt=tilt, surface_azimuth=azimuth,
        dc_ac_ratio=dc_ac_ratio, inverter_efficiency=inverter_efficiency,
        system_losses=system_losses, temperature_coefficient=temperature_coefficient,
        albedo=albedo, sapm_cell=sapm_cell,
    )
    return hourly.reshape(-1, 24).sum(axis=1)


def default_model(state: str, mv_cfg: MvConfig, res_cfg: ResConfig) -> np.ndarray:
    return default_pv_daily(state, mv_cfg.default_tilt_deg, mv_cfg.default_azimuth_deg,
                            res_cfg.dc_ac_ratio, res_cfg.inverter_efficiency,
                            res_cfg.system_losses, res_cfg.temperature_coefficient,
                            res_cfg.albedo, res_cfg.sapm_cell)


def normalized_production(measured: float, modelled_actual: float, modelled_normal: float
                          ) -> float:
    """Weather-normalized production ``P * Y_normal / Y_actual``."""
    if modelled_actual <= 0:
        return float("nan")
    return measured * modelled_normal / modelled_actual


def plausibility_z(measured: float, modelled: float, sigma_log: float) -> float:
    """Standardised log ratio of measured to modelled production."""
    if measured <= 0 or modelled <= 0 or sigma_log <= 0:
        return float("inf") if measured <= 0 else 0.0
    return float(np.log(measured / modelled) / sigma_log)
