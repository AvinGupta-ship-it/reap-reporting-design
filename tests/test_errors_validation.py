"""Each injected error class is flagged by the rules designed to catch it."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from reapschema import validate
from reapschema.synth import errors
from reapschema.synth.generator import generate_applicant, spawn_seeds

ALL = frozenset(validate.OPTIONAL_ELEMENTS)


def make(cfg, error_class, category, start=0):
    seeds = spawn_seeds(cfg.seed + 17, 400)
    for i in range(start, 400):
        app = generate_applicant(i, seeds[i], cfg, error_class=error_class)
        if app.category == category and app.error.error_class == error_class:
            return app
    raise AssertionError("no applicant generated")


def scores(app, cfg, reported=True):
    ev = app.reported if reported else app.clean
    model = app.truth.production / app.covariates["pv_factor"] if app.category == "RES" else 0.0
    return validate.rule_scores(ev, cfg, model_post_declared=model)


EXPECTED = [
    ("unit", "RES", ["cf_range_claim", "cf_range_inverter", "payback_bounds"]),
    ("unit", "EEI", ["charge_consistency", "payback_bounds"]),
    ("wrong_period", "RES", ["period_alignment"]),
    ("wrong_period", "EEI", ["period_alignment"]),
    ("double_counting", "RES", ["account_consistency"]),
    ("double_counting", "EEI", ["account_consistency"]),
    ("gross_net", "RES", ["claim_recompute_inverter"]),
    ("nameplate_hours", "RES", ["claim_recompute_inverter"]),
]


@pytest.mark.parametrize("error_class, category, rules", EXPECTED)
def test_rule_flags_injected_error(cfg, error_class, category, rules):
    app = make(cfg, error_class, category)
    s = scores(app, cfg)
    assert any(s[r] > 0.5 for r in rules), {r: s[r] for r in rules}


@pytest.mark.parametrize("category", ["RES", "EEI"])
def test_transposed_digits_flagged_by_recomputation(cfg, category):
    for start in range(0, 200, 20):
        app = make(cfg, "transposed_digits", category, start)
        if abs(app.error.magnitude - 1.0) < 0.03:
            continue  # a swap of low-order digits is within the recomputation tolerance
        s = scores(app, cfg)
        keys = ["sum_check_pre", "claim_recompute", "claim_recompute_inverter"]
        assert any(s[k] > 0.5 for k in keys if not np.isnan(s[k])), app.error
        return
    raise AssertionError("no material transposition generated")


def test_deterministic_rules_pass_error_free_evidence(cfg, applicants):
    deterministic = [r.key for r in validate.RULES
                     if r.kind == "deterministic" and r.key != "payback_bounds"]
    for app in applicants:
        s = scores(app, cfg, reported=False)
        for key in deterministic:
            assert np.isnan(s[key]) or s[key] == 0.0, (key, app.category)


def test_rules_requiring_elements_are_inactive_under_current_specification():
    active = {r.key for r in validate.active_rules(frozenset(), "RES")}
    assert "period_alignment" not in active and "cf_range_claim" in active
    assert {r.key for r in validate.active_rules(ALL, "EEI")} >= {
        "period_alignment", "account_consistency", "enduse_bound"}
    assert all(r.applies_to != "RES" for r in validate.active_rules(ALL, "EEI"))


def test_error_labels_and_class_draws(cfg):
    rng = np.random.default_rng(0)
    draws = [errors.draw_error_class(rng, "RES", cfg.errors) for _ in range(20000)]
    for cls, rate in cfg.errors.rates.items():
        assert np.mean([d == cls for d in draws]) == pytest.approx(rate, abs=0.01)
    eei = {errors.draw_error_class(rng, "EEI", cfg.errors) for _ in range(5000)}
    assert not eei & set(errors.RES_ONLY)


@given(value=st.integers(10, 10**9), seed=st.integers(0, 1000))
def test_transposition_preserves_digits(value, seed):
    out = errors.transpose_digits(float(value), np.random.default_rng(seed))
    assert sorted(str(int(out)).zfill(len(str(value)))) == sorted(str(value))
    assert (int(out) - value) % 9 == 0
