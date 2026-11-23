"""Scoring tables and award selection invariants."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from reapschema import competition as comp
from reapschema.config import load_config
from reapschema.provenance import REPO_ROOT
from reapschema.units import BTU_PER_KWH

CFG = load_config(REPO_ROOT / "configs" / "quick.yaml").competition
T = comp.scoring_tables()


def test_percent_bands():
    pct = np.array([0.0, 9.44, 9.45, 19.5, 34.5, 49.5, 300.0])
    assert list(comp.percent_points(pct, T.pct_eei_bounds, T.pct_eei_points)) == [
        0, 0, 5, 10, 15, 20, 20]
    pct = np.array([9.4, 9.5, 24.5, 49.5, 74.5, 109.4, 109.5])
    assert list(comp.percent_points(pct, T.pct_res_bounds, T.pct_res_points)) == [
        0, 5, 10, 15, 20, 20, 0]


def test_payback_bands():
    assert list(comp.payback_points(np.array([3.9, 4, 7.9, 8, 12, 12.1]),
                                    T.payback_eei_bounds, T.payback_eei_points)) == [
        15, 10, 10, 5, 5, 0]
    assert list(comp.payback_points(np.array([9.9, 10, 14.9, 15, 25, 25.1, np.inf]),
                                    T.payback_res_bounds, T.payback_res_points)) == [
        15, 10, 10, 5, 5, 0, 0]


def test_energy_points_equation_and_cap():
    # 1,000 BTU per dollar -> 10 points; large ratios are capped at 25
    kwh = np.array([1000.0 * 5000 / BTU_PER_KWH, 1e7])
    pts = comp.energy_points(kwh, np.array([5000.0, 5000.0]), T)
    assert pts[0] == pytest.approx(10.0, abs=0.01) and pts[1] == 25.0


def test_eligibility_conditions():
    ok = comp.eligible(np.array([True, True, False]), np.array([130.0, 100.0, 10.0]),
                       np.array([100.0, 100.0, 100.0]), np.array([100.0, 100.0, 1000.0]),
                       np.array([0.1, 0.1, 0.1]), np.array([25.0, 25.0, 15.0]),
                       np.array([True, True, False]))
    assert list(ok) == [False, True, False]


@settings(max_examples=80, deadline=None)
@given(seed=st.integers(0, 10_000), n=st.integers(5, 300), ratio=st.floats(0.05, 1.5))
def test_selection_invariants(seed, n, ratio):
    rng = np.random.default_rng(seed)
    score = rng.choice([30, 40, 45, 50, 60, 75], n).astype(float)
    ok = rng.random(n) < 0.9
    state = rng.integers(0, 8, n)
    request = rng.uniform(1500, 200000, n)
    tie = rng.random(n)
    funds = ratio * request.sum()
    sel = comp.select(score, ok, state, request, tie, funds=funds, cfg=CFG)
    assert request[sel].sum() <= funds + 1e-6
    assert np.all(ok[sel]) and np.all(score[sel] >= CFG.minimum_score)
    more = comp.select(score, ok, state, request, tie, funds=funds * 1000, cfg=CFG)
    assert more.sum() == (ok & (score >= CFG.minimum_score)).sum()
    again = comp.select(score, ok, state, request, tie, funds=funds, cfg=CFG)
    assert np.array_equal(sel, again)


def test_top_per_state_is_funded_before_rank_order():
    score = np.array([90.0, 85.0, 80.0, 50.0])
    state = np.array([0, 0, 0, 1])
    request = np.full(4, 100000.0)
    sel = comp.select(score, np.ones(4, bool), state, request, np.arange(4.0),
                      funds=375000.0, cfg=CFG.model_copy(update={"top_per_state": 2}))
    # reserve is 20 percent; general funds cover three awards: two from state 0, one from 1
    assert list(sel) == [True, True, False, True]


def test_identical_values_give_no_selection_change():
    rng = np.random.default_rng(0)
    n = 400
    states = rng.choice(np.array(["IA", "NE", "TX", "VT"]), n)
    is_res = rng.random(n) < 0.8
    design = comp.design_competitions(rng, states, is_res, CFG)
    score = rng.choice([20.0, 30.0, 45.0, 60.0], n)
    request = rng.uniform(2000, 100000, n)
    a = comp.selections(design, score, np.ones(n, bool), request, CFG)
    b = comp.selections(design, score, np.ones(n, bool), request, CFG)
    assert comp.selection_change(a, b).max() == 0.0
