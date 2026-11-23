"""Schema round trip: LinkML YAML -> JSON Schema -> validation of fixtures."""

from __future__ import annotations

import copy
import json

import pytest

from reapschema import validate
from reapschema.schema import build
from reapschema.synth.evidence import to_package
from reapschema.synth.weather import site_weather
from tests.conftest import first_of


def package(app):
    w = site_weather(app.state)
    return to_package(app.clean, w.first_date, latitude=w.site.latitude,
                      longitude=w.site.longitude, station_id=w.station_id,
                      climate_zone=w.climate_zone())


def test_generated_json_schema_is_current():
    committed = json.loads((build.GENERATED / "reap_evidence.schema.json").read_text())
    assert committed == build.json_schema()


def test_specified_classes_present():
    classes = set(build.schema_view().all_classes())
    assert {"Applicant", "Facility", "Project", "Meter", "BillingRecord", "IntervalSeries",
            "PerformanceClaim", "EquipmentItem"} <= classes


@pytest.mark.parametrize("category", ["RES", "EEI"])
def test_synthetic_packages_validate(applicants, category):
    assert validate.schema_errors(package(first_of(applicants, category))) == []


def test_pydantic_models_accept_fixture(applicants):
    from reapschema.schema.generated import models

    pkg = models.EvidencePackage.model_validate(package(first_of(applicants, "RES")))
    assert str(getattr(pkg.project.category, "value", pkg.project.category)) == "RES"
    assert len(pkg.billing_records) == 36


@pytest.mark.parametrize("mutate, fragment", [
    (lambda p: p["performance_claim"].pop("claimed_value"), "claimed_value"),
    (lambda p: p["project"].__setitem__("technology", "perpetual_motion"), "technology"),
    (lambda p: p["billing_records"][0].__setitem__("energy_unit", "kWh"), "energy_unit"),
    (lambda p: p["billing_records"][0].__setitem__("period_start", "2010-13-45"), "period_start"),
    (lambda p: p["facility"].__setitem__("latitude", 123.0), "latitude"),
    (lambda p: p["project"].pop("rated_capacity"), "rated_capacity"),
    (lambda p: p.__setitem__("undeclared_field", 1), "undeclared_field"),
])
def test_invalid_fixtures_are_rejected(applicants, mutate, fragment):
    pkg = copy.deepcopy(package(first_of(applicants, "RES")))
    mutate(pkg)
    errors = validate.schema_errors(pkg)
    assert errors and any(fragment in e for e in errors)


def test_csv_templates_match_class_slots():
    view = build.schema_view()
    for cls in build.TABULAR_CLASSES:
        header = (build.GENERATED / "templates" / f"{cls}.csv").read_text().strip().split(",")
        assert header == [s.name for s in view.class_induced_slots(cls)]
