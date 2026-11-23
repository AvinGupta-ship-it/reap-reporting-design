"""Billing aggregation conserves energy, including across estimated reads."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from reapschema.config import load_config
from reapschema.provenance import REPO_ROOT
from reapschema.synth import billing

CFG = load_config(REPO_ROOT / "configs" / "quick.yaml").billing


@settings(max_examples=60, deadline=None)
@given(seed=st.integers(0, 10_000), p_est=st.floats(0.0, 0.9), n_days=st.integers(200, 900),
       first=st.integers(0, 500))
def test_bills_conserve_energy(seed, p_est, n_days, first):
    rng = np.random.default_rng(seed)
    delivered = rng.gamma(2.0, 50.0, n_days)
    export = rng.gamma(1.0, 10.0, n_days)
    peak = delivered / 10
    reads = billing.read_days(rng, first, first + n_days - 1, CFG.cycle_mean_days,
                              CFG.read_jitter_days)
    bills = billing.make_bills(rng, delivered, export, peak, first, reads, CFG, 0.1,
                               "net_of_exports", estimated_prob=p_est)
    a, b = reads[0] - first, reads[-1] - first
    assert bills.delivered.sum() == pytest.approx(delivered[a:b].sum(), rel=1e-9)
    assert bills.export.sum() == pytest.approx(export[a:b].sum(), rel=1e-9)
    assert bills.printed.sum() == pytest.approx((delivered - export)[a:b].sum(), rel=1e-9)
    assert np.all(bills.start[1:] == bills.end[:-1] + 1)
    assert np.all(bills.days >= 1)
    assert np.all(bills.delivered >= -1e-9)
    assert not np.any(bills.estimated[1:] & bills.estimated[:-1])


def test_actual_reads_reproduce_period_sums():
    rng = np.random.default_rng(1)
    delivered = np.arange(400, dtype=float)
    reads = billing.read_days(rng, 0, 399, CFG.cycle_mean_days, CFG.read_jitter_days)
    bills = billing.make_bills(rng, delivered, np.zeros(400), delivered, 0, reads, CFG, 0.1,
                               "delivered_only", estimated_prob=0.0)
    for i in range(len(bills)):
        assert bills.delivered[i] == pytest.approx(
            delivered[bills.start[i]:bills.end[i] + 1].sum())
    assert not bills.estimated.any()


def test_twelve_bills_span_about_a_year(applicants):
    for app in applicants:
        for b in (app.clean.pre_bills, app.clean.post_bills):
            assert len(b) == 12
            assert 355 <= b.days.sum() <= 375
        assert app.clean.pre_bills.end.max() < app.clean.in_service_day
        assert app.clean.post_bills.start.min() >= app.clean.in_service_day


def test_generator_truth_is_consistent_with_evidence(applicants):
    for app in applicants:
        t, ev = app.truth, app.clean
        assert t.pre_consumption > 0
        # pre-installation bills cover nearly the same days as the truth window
        assert ev.pre_bills.printed.sum() == pytest.approx(t.pre_consumption, rel=0.15)
        assert ev.interval_pre_daily.sum() == pytest.approx(t.pre_consumption, rel=1e-9)
        if app.category == "RES":
            assert ev.claim_value == pytest.approx(t.production, rel=0.03)
            assert ev.interval_inverter_total == pytest.approx(ev.inverter_kwh.sum())
            assert np.all(ev.post_bills.export >= 0)
        else:
            assert t.savings_avoided > 0 and t.savings_normal > 0
            assert 0 < t.affected_share <= 1
