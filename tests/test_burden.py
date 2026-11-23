"""Burden audit reproduces the published figures and their discrepancies."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from reapschema import burden as bm
from reapschema.validate import OPTIONAL_ELEMENTS


def test_audit_reproduces_published_figures_and_discrepancies():
    a = bm.run_audit()
    assert (a["respondents"], a["responses"], a["total_hours"]) == (2977, 112073, 150883)
    assert a["product_responses"] == pytest.approx(112054.28, abs=1e-6)
    assert a["responses_discrepancy"] == pytest.approx(18.72, abs=1e-6)
    assert a["product_hours"] == pytest.approx(150177.82, abs=1e-6)
    assert a["hours_discrepancy"] == pytest.approx(705.18, abs=1e-6)
    assert a["implied_responses_per_respondent"] == pytest.approx(112073 / 2977)
    assert a["implied_hours_per_response"] == pytest.approx(150883 / 112073)


def test_published_ratios_are_truncated_not_rounded():
    a = bm.run_audit()
    assert not a["responses_consistent_with_rounding"]
    assert a["responses_consistent_with_truncation"]
    assert not a["hours_consistent_with_rounding"]
    assert a["hours_consistent_with_truncation"]
    assert a["rounded_implied_responses_per_respondent"] == 37.65
    assert a["rounded_implied_hours_per_response"] == 1.35


def test_inventory_comparison():
    a = bm.run_audit()
    assert a["inventory_hours_per_response"] == pytest.approx(257879 / 81765)
    assert a["change_responses_percent"] > 0 > a["change_hours_percent"]


def test_calibration_matches_notice_anchor(cfg):
    times = bm.modal_times(cfg.burden)
    kappa = bm.calibration_factor(cfg.burden, times, 0.8, 1.34)
    base = bm.mean_burden(frozenset(), "manual_transcription", 0.8, times, cfg.burden, kappa)
    assert base == pytest.approx(cfg.burden.anchor_responses * 1.34 * 60)


@settings(max_examples=60, deadline=None)
@given(bits=st.lists(st.booleans(), min_size=len(OPTIONAL_ELEMENTS),
                     max_size=len(OPTIONAL_ELEMENTS)),
       extra=st.sampled_from(OPTIONAL_ELEMENTS), category=st.sampled_from(["RES", "EEI"]),
       mode=st.sampled_from(["manual_transcription", "utility_file_upload",
                             "green_button_download", "automated_utility_access"]))
def test_burden_is_monotone_in_elements(bits, extra, category, mode):
    from reapschema.config import load_config
    from reapschema.provenance import REPO_ROOT

    cfg = load_config(REPO_ROOT / "configs" / "quick.yaml").burden
    times = bm.modal_times(cfg)
    elements = {e for e, b in zip(OPTIONAL_ELEMENTS, bits, strict=True) if b}
    lower = bm.burden_minutes(frozenset(elements), mode, category, times, cfg)
    upper = bm.burden_minutes(frozenset(elements | {extra}), mode, category, times, cfg)
    assert upper >= lower >= 0


def test_triangular_sampler_respects_bounds():
    p = bm.TimeParameter("x", 1.0, 2.0, 5.0)
    draws = p.sample(np.random.default_rng(0).random(20000))
    assert draws.min() >= 1.0 and draws.max() <= 5.0
    assert draws.mean() == pytest.approx((1 + 2 + 5) / 3, rel=0.02)
