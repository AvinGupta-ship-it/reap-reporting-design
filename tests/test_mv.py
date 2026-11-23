"""M&V estimators against analytical cases and an independent implementation."""

from __future__ import annotations

import numpy as np
import pytest
import statsmodels.api as sm
from hypothesis import given, settings
from hypothesis import strategies as st
from scipy import stats

from reapschema import mv

GRID = mv.grid((30.0, 90.0, 3.0))


def synthetic_year(seed: int = 0, years: int = 3):
    rng = np.random.default_rng(seed)
    day = np.arange(365 * years)
    temp_f = 55 + 25 * np.sin(2 * np.pi * (day - 110) / 365) + rng.normal(0, 4, day.size)
    return (temp_f - 32) * 5 / 9


def bills(table, b0, bh, bc, th, tc, first=5, n=12, scale=1.0):
    edges = first + np.round(np.arange(n + 1) * 30.4375).astype(int)
    start, end = edges[:-1], edges[1:] - 1
    days = end - start + 1
    ih, ic = int(np.where(GRID == th)[0][0]), int(np.where(GRID == tc)[0][0])
    energy = b0 * days + bh * table.hdd(start, end)[:, ih] + bc * table.cdd(start, end)[:, ic]
    return start, end, energy * scale


def test_degree_days_match_direct_computation():
    temp_c = synthetic_year()
    table = mv.degree_day_table(temp_c, GRID)
    start, end = np.array([10, 200]), np.array([40, 229])
    temp_f = temp_c * 9 / 5 + 32
    for k, tb in enumerate(GRID):
        direct = [np.maximum(tb - temp_f[a:b + 1], 0).sum() for a, b in zip(start, end)]
        assert table.hdd(start, end)[:, k] == pytest.approx(direct)


def test_model_recovers_known_coefficients_without_noise():
    table = mv.degree_day_table(synthetic_year(), GRID)
    start, end, energy = bills(table, b0=120.0, bh=3.5, bc=6.0, th=57.0, tc=66.0)
    model = mv.fit_degree_day_model(energy, end - start + 1, table.hdd(start, end),
                                    table.cdd(start, end), GRID, GRID)
    assert (model.t_h_f, model.t_c_f) == (57.0, 66.0)
    assert model.beta0 == pytest.approx(120.0, rel=1e-8)
    assert model.beta_h == pytest.approx(3.5, rel=1e-8)
    assert model.beta_c == pytest.approx(6.0, rel=1e-8)
    assert model.cvrmse == pytest.approx(0.0, abs=1e-8)
    assert model.ndb == pytest.approx(0.0, abs=1e-10)


def test_fit_matches_independent_weighted_least_squares():
    rng = np.random.default_rng(3)
    table = mv.degree_day_table(synthetic_year(1), GRID)
    start, end, energy = bills(table, 80.0, 2.0, 4.0, 60.0, 69.0)
    energy = energy * (1 + rng.normal(0, 0.05, energy.size))
    days = end - start + 1
    model = mv.fit_degree_day_model(energy, days, table.hdd(start, end), table.cdd(start, end),
                                    GRID, GRID)
    cols = [np.ones(days.size)]
    if model.i_h >= 0:
        cols.append(table.hdd(start, end)[:, model.i_h] / days)
    if model.i_c >= 0:
        cols.append(table.cdd(start, end)[:, model.i_c] / days)
    ref = sm.WLS(energy / days, np.column_stack(cols), weights=days).fit()
    ours = [model.beta0] + ([model.beta_h] if model.i_h >= 0 else []) + (
        [model.beta_c] if model.i_c >= 0 else [])
    assert ours == pytest.approx(ref.params, rel=1e-8)
    assert model.adj_r2 == pytest.approx(ref.rsquared_adj, rel=1e-8)


def test_savings_recovered_for_noise_free_reduction():
    table = mv.degree_day_table(synthetic_year(2), GRID)
    pre = bills(table, 100.0, 3.0, 5.0, 57.0, 66.0, first=5)
    post = bills(table, 80.0, 2.4, 4.0, 57.0, 66.0, first=5 + 366)
    est = mv.estimate_savings(pre, post, table, 0.9)
    ps, pe, penergy = post
    days = pe - ps + 1
    ih, ic = int(np.where(GRID == 57.0)[0][0]), int(np.where(GRID == 66.0)[0][0])
    counterfactual = (100.0 * days + 3.0 * table.hdd(ps, pe)[:, ih]
                      + 5.0 * table.cdd(ps, pe)[:, ic])
    assert est.avoided == pytest.approx(counterfactual.sum() - penergy.sum(), rel=1e-8)
    normal = (20.0 * 365 + 0.6 * table.normal_hdd[ih] + 1.0 * table.normal_cdd[ic])
    assert est.normalized == pytest.approx(normal, rel=1e-8)


def test_no_change_gives_zero_savings():
    table = mv.degree_day_table(synthetic_year(4), GRID)
    pre = bills(table, 100.0, 3.0, 0.0, 57.0, 66.0, first=5)
    post = bills(table, 100.0, 3.0, 0.0, 57.0, 66.0, first=5 + 366)
    est = mv.estimate_savings(pre, post, table, 0.9)
    assert abs(est.avoided) < 1e-6 * post[2].sum()
    assert abs(est.normalized) < 1e-6 * post[2].sum()


def test_fractional_savings_uncertainty_formula():
    t = stats.t.ppf(0.95, 12 - 3)
    expected = t * 1.26 * 0.1 * np.sqrt((1 + 2 / 12) / 12) / 0.2
    assert mv.fractional_savings_uncertainty(0.1, 0.2, 12, 12, 3, 0.0, 0.9) == pytest.approx(
        expected)
    worse = mv.fractional_savings_uncertainty(0.1, 0.2, 12, 12, 3, 0.5, 0.9)
    assert worse > expected
    assert mv.fractional_savings_uncertainty(0.1, 0.0, 12, 12, 3, 0.0, 0.9) == float("inf")


def test_merge_estimated_conserves_energy_and_span():
    start = np.array([0, 30, 60, 90])
    end = np.array([29, 59, 89, 119])
    energy = np.array([10.0, 20.0, 30.0, 40.0])
    s, e, v = mv.merge_estimated(start, end, energy, np.array([False, True, False, False]))
    assert v.sum() == energy.sum()
    assert list(s) == [0, 30, 90] and list(e) == [29, 89, 119]
    assert list(v) == [10.0, 50.0, 40.0]


@settings(max_examples=25, deadline=None)
@given(scale=st.floats(0.01, 1000.0), b0=st.floats(10, 500), bh=st.floats(0.5, 10))
def test_coefficients_scale_with_energy(scale, b0, bh):
    table = mv.degree_day_table(synthetic_year(5), GRID)
    start, end, energy = bills(table, b0, bh, 0.0, 60.0, 66.0)
    days = end - start + 1
    args = (days, table.hdd(start, end), table.cdd(start, end), GRID, GRID)
    a = mv.fit_degree_day_model(energy, *args)
    b = mv.fit_degree_day_model(energy * scale, *args)
    assert b.beta0 == pytest.approx(a.beta0 * scale, rel=1e-6)
    assert b.beta_h == pytest.approx(a.beta_h * scale, rel=1e-6)
    assert b.beta_h >= 0 and b.beta_c >= 0


def test_normalized_production_and_plausibility():
    assert mv.normalized_production(100.0, 50.0, 55.0) == pytest.approx(110.0)
    assert mv.plausibility_z(100.0, 100.0, 0.1) == 0.0
    assert mv.plausibility_z(np.e * 100.0, 100.0, 0.5) == pytest.approx(2.0)
