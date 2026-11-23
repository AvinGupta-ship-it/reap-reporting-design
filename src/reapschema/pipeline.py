"""Single entry point that regenerates every result from raw inputs.

Usage::

    python -m reapschema.pipeline run --config configs/paper.yaml
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from reapschema import experiments as ex
from reapschema import requirements, validate
from reapschema.config import Config, load_config
from reapschema.data import process
from reapschema.evaluate import simulate
from reapschema.provenance import REPO_ROOT, sha256_file, write_sidecar
from reapschema.schema import build as schema_build
from reapschema.synth.evidence import to_package
from reapschema.synth.generator import generate_applicant, spawn_seeds
from reapschema.synth.weather import site_weather

SUMMARY_FILES = (
    "e1_burden_audit.json", "e2_accuracy.csv", "e2_hypothesis_tests.csv", "e3_rule_matrix.csv",
    "e3_ensemble.csv", "e4_summary.csv", "e4_bins.csv", "e5_incomplete.csv",
    "e6_frontier.csv", "e6_bands.csv", "e6_ilp.csv", "e6_calibration.csv", "e7_selection.csv",
    "e8_modes.csv", "sobol_burden.csv", "convergence.csv", "interval_coverage.csv",
    "population.json", "score_structure.json", "traceability.csv", "recommended.json",
    "e2_by_savings_fraction.csv", "sensitivity_size_distribution.csv",
)


def results_dir(cfg: Config) -> Path:
    path = REPO_ROOT / "results" / cfg.name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _save(frame: pd.DataFrame, path: Path, cfg: Config, inputs: dict[str, str] | None = None
          ) -> None:
    if path.suffix == ".parquet":
        frame.to_parquet(path, index=False)
    else:
        frame.to_csv(path, index=False)
    write_sidecar(path, config=cfg.model_dump(), seed=cfg.seed, inputs=inputs,
                  extra={"data_basis": "synthetic"})


def input_checksums() -> dict[str, str]:
    files = [process.PROCESSED / "load_profiles.parquet", process.PROCESSED / "prices.csv",
             process.PROCESSED / "reap_awards.csv", requirements.RULE_XML,
             process.RAW / "isd" / "station_selection.json"]
    return {f.name: sha256_file(f) for f in files if f.exists()}


def write_synthetic_sample(cfg: Config, n: int) -> Path:
    """A few complete synthetic evidence packages, validated against the JSON Schema."""
    out_dir = REPO_ROOT / "data" / "synthetic"
    out_dir.mkdir(parents=True, exist_ok=True)
    seeds = spawn_seeds(cfg.seed, n)
    packages = []
    for i in range(n):
        app = generate_applicant(i, seeds[i], cfg)
        weather = site_weather(app.state)
        pkg = to_package(app.clean, weather.first_date, latitude=weather.site.latitude,
                         longitude=weather.site.longitude, station_id=weather.station_id,
                         climate_zone=weather.climate_zone())
        errors = validate.schema_errors(pkg)
        if errors:
            raise ValueError(f"synthetic package violates the schema: {errors[:3]}")
        packages.append(pkg)
    path = out_dir / f"synthetic_evidence_packages_{cfg.name}.json"
    path.write_text(json.dumps({"data_basis": "synthetic", "packages": packages}, indent=1)
                    + "\n")
    write_sidecar(path, config=cfg.model_dump(), seed=cfg.seed,
                  extra={"data_basis": "synthetic"})
    return path


def run(cfg: Config) -> Path:
    t0 = time.time()
    out = results_dir(cfg)
    rng = np.random.default_rng(np.random.SeedSequence(cfg.seed).spawn(3)[2])
    schema_build.build()
    process.build_all()
    inputs = input_checksums()

    audit = ex.e1_burden_audit()
    ex.write_json(out / "e1_burden_audit.json", audit)
    hours = float(audit["hours_per_response"])
    trace = requirements.traceability_table()
    _save(trace, out / "traceability.csv", cfg, inputs)

    records = simulate(cfg)
    _save(records, out / "records.parquet", cfg, inputs)
    synth_dir = REPO_ROOT / "data" / "synthetic"
    synth_dir.mkdir(parents=True, exist_ok=True)
    _save(records, synth_dir / f"synthetic_applicants_{cfg.name}.parquet", cfg, inputs)
    write_synthetic_sample(cfg, cfg.experiments.evidence_sample)

    accuracy, samples = ex.e2_accuracy(records, cfg, rng)
    _save(accuracy, out / "e2_accuracy.csv", cfg)
    _save(samples, out / "e2_are_samples.parquet", cfg)
    _save(ex.hypothesis_tests(records, cfg), out / "e2_hypothesis_tests.csv", cfg)

    by_class = ex.simulate_by_class(cfg, cfg.experiments.e3_per_class)
    _save(by_class, out / "records_by_class.parquet", cfg, inputs)
    matrix, roc, ensemble = ex.e3_validation(by_class, cfg)
    _save(matrix, out / "e3_rule_matrix.csv", cfg)
    _save(roc, out / "e3_roc.parquet", cfg)
    _save(ensemble, out / "e3_ensemble.csv", cfg)

    bins, summary = ex.e4_normalization(records, cfg)
    _save(bins, out / "e4_bins.csv", cfg)
    _save(summary, out / "e4_summary.csv", cfg)

    _save(ex.e5_incomplete(cfg), out / "e5_incomplete.csv", cfg)

    frontier = ex.e6_frontier(records, cfg, rng, hours)
    specs = frontier["specs"]
    _save(specs, out / "e6_specs.parquet", cfg)
    _save(specs[specs["on_frontier_mare"] | specs["on_frontier_selection"]
                | (specs["n_elements"] == 0)], out / "e6_frontier.csv", cfg)
    _save(frontier["bands"], out / "e6_bands.csv", cfg)
    _save(frontier["ilp"], out / "e6_ilp.csv", cfg)
    _save(frontier["calibration"], out / "e6_calibration.csv", cfg)
    rec_row = ex.recommended_spec(specs, cfg.experiments.recommended_tolerance)
    rec_elements = ex.spec_elements(rec_row)
    int_row = ex.recommended_spec(specs, cfg.experiments.recommended_tolerance,
                                  allow_interval=True)
    int_elements = ex.spec_elements(int_row)
    base_row = specs[(specs["mode"] == "manual_transcription")
                     & (specs["n_elements"] == 0)].iloc[0]
    ex.write_json(out / "recommended.json", {
        "elements": sorted(rec_elements),
        "burden_min": float(rec_row["burden_min"]), "mare": float(rec_row["mare"]),
        "selection_change": float(rec_row["selection_change"]),
        "flag_rate": float(rec_row["flag_rate"]),
        "baseline_burden_min": float(base_row["burden_min"]),
        "baseline_mare": float(base_row["mare"]),
        "baseline_selection_change": float(base_row["selection_change"]),
        "baseline_flag_rate": float(base_row["flag_rate"]),
        "tolerance": cfg.experiments.recommended_tolerance,
        "interval_elements": sorted(int_elements),
        "interval_burden_min": float(int_row["burden_min"]),
        "interval_mare": float(int_row["mare"]),
        "interval_selection_change": float(int_row["selection_change"]),
    })
    extra = {"recommended": rec_elements, "recommended_interval": int_elements}

    _save(ex.e7_selection(records, cfg, extra), out / "e7_selection.csv", cfg)
    ex.write_json(out / "score_structure.json", ex.score_structure(records, cfg))
    named = {"current": frozenset(), "recommended": rec_elements,
             "recommended_interval": int_elements,
             "metadata": ex.NAMED_SPECS["metadata"][1],
             "interval": ex.NAMED_SPECS["interval"][1]}
    _save(ex.accuracy_by_savings_fraction(records), out / "e2_by_savings_fraction.csv", cfg)
    _save(ex.size_distribution_sensitivity(
        cfg, {"current": frozenset(), "recommended": rec_elements}),
        out / "sensitivity_size_distribution.csv", cfg)
    _save(ex.e8_modes(records, cfg, rng, hours, named), out / "e8_modes.csv", cfg)
    _save(ex.burden_sobol(cfg, hours, rec_elements, float(frontier["calibration"][
        "res_share"].iloc[0]), (float(base_row["flag_rate"]), float(rec_row["flag_rate"]))),
        out / "sobol_burden.csv", cfg)
    _save(ex.convergence(records, cfg, {"current": frozenset(), "recommended": rec_elements}),
          out / "convergence.csv", cfg)
    _save(ex.interval_coverage(records, cfg), out / "interval_coverage.csv", cfg)
    ex.write_json(out / "population.json", ex.population_summary(records, cfg))
    (out / "config.yaml").write_text(yaml.safe_dump(cfg.model_dump(mode="json"),
                                                    sort_keys=False))

    summaries = REPO_ROOT / "results" / "summaries" / cfg.name
    summaries.mkdir(parents=True, exist_ok=True)
    for name in SUMMARY_FILES:
        if (out / name).exists():
            shutil.copy2(out / name, summaries / name)
    runtime: dict[str, Any] = {"seconds": round(time.time() - t0, 1)}
    ex.write_json(out / "runtime.json", runtime)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run", help="run all experiments for a configuration")
    run_p.add_argument("--config", required=True)
    args = parser.parse_args()
    cfg = load_config(args.config)
    out = run(cfg)
    print(f"results written to {out}")


if __name__ == "__main__":
    main()
