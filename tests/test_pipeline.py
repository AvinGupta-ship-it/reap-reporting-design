"""Reproducibility, configuration and unit handling."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from reapschema import units
from reapschema.config import Config, load_config
from reapschema.evaluate import simulate
from reapschema.optimize import SpecEvaluator
from reapschema.provenance import REPO_ROOT, config_hash


def test_results_do_not_depend_on_worker_count(cfg):
    a = simulate(cfg, 10, workers=1)
    b = simulate(cfg, 10, workers=3)
    pd.testing.assert_frame_equal(a, b)
    c = simulate(cfg, 10, workers=1, seed=cfg.seed + 1)
    assert not np.allclose(a["true_pre_consumption"], c["true_pre_consumption"])


def test_configurations_validate():
    for name in ("paper", "quick"):
        cfg = load_config(REPO_ROOT / "configs" / f"{name}.yaml")
        assert cfg.name == name
        assert sum(cfg.errors.rates.values()) < 1
    paper = load_config(REPO_ROOT / "configs" / "paper.yaml")
    quick = load_config(REPO_ROOT / "configs" / "quick.yaml")
    assert paper.population == quick.population
    assert config_hash(paper.model_dump()) != config_hash(quick.model_dump())


def test_invalid_configuration_is_rejected(cfg):
    raw = cfg.model_dump()
    raw["billing"]["estimated_read_prob"] = 1.5
    with pytest.raises(ValidationError):
        Config.model_validate(raw)
    raw = cfg.model_dump()
    raw["unknown_section"] = {}
    with pytest.raises(ValidationError):
        Config.model_validate(raw)


def test_unit_conversions_are_dimensionally_consistent():
    assert units.energy_to_kwh(1.0, "MW.h") == pytest.approx(1000.0)
    assert units.energy_to_kwh(units.BTU_PER_KWH, "[Btu_IT]") == pytest.approx(1.0)
    assert units.energy_to_kwh(1.0, "M[Btu_IT]") == pytest.approx(1e6 / units.BTU_PER_KWH)
    assert units.power_to_kw(2.0, "MW") == pytest.approx(2000.0)
    assert units.BTU_PER_KWH == pytest.approx(3412.14, abs=0.01)
    assert units.fahrenheit_to_celsius(32.0) == pytest.approx(0.0)
    with pytest.raises(ValueError):
        units.energy_to_kwh(1.0, "kW")
    assert (1 * units.ureg.kilowatt_hour).check("[energy]")
    assert not (1 * units.ureg.kilowatt).check("[energy]")


def test_richer_specifications_do_not_reduce_detection(cfg):
    records = simulate(cfg, 60, workers=1)
    ev = SpecEvaluator(records, cfg)
    base = ev.evaluate(frozenset())
    rich = ev.evaluate(frozenset({"billing_dates", "meter_ids", "inverter_monthly"}))
    assert rich.corrected.sum() >= base.corrected.sum()
    clean = ev.evaluate(frozenset(), with_errors=False)
    assert not clean.corrected.any()
