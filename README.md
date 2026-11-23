# reap-reporting-design

Evidence schema, synthetic applicants, measurement-and-verification estimators,
validation rules and accuracy–burden optimization for the pre- and post-installation
energy evidence collected by USDA's Rural Energy for America Program (REAP) under
7 CFR part 4280 subpart B, as amended by the final rule with comment period at
91 FR 62600 (October 1, 2026; FR Doc. 2026-20178; docket RBS-26-Business-0529).

The repository contains

- `src/reapschema/` — the importable package `reapschema`:
  - `schema/` — LinkML schema of performance evidence and the artifacts generated from
    it (JSON Schema, pydantic models, CSV templates, element documentation), and the
    requirement-to-schema traceability mapping;
  - `requirements` — parser of the rule's Federal Register XML;
  - `synth/` — synthetic applicant generator (loads, weather, photovoltaic production,
    efficiency measures, billing, error injection);
  - `mv` — degree-day regression, savings and uncertainty, production normalization;
  - `validate` — schema validation and the rule layer;
  - `burden` — audit of the published burden estimate and the element time model;
  - `competition` — scoring under §4280.140 and selection under §4280.150;
  - `optimize` — exhaustive and surrogate integer-programming frontier;
  - `experiments`, `pipeline`, `report` — experiments E1–E8, the single entry point,
    and generation of every number and table used in the manuscript and comment;
- `paper/` — manuscript and supporting information (LaTeX, PDF, DOCX);
- `comment/` — Paperwork Reduction Act comment on OMB Control Number 0570-0067 and its
  technical attachment;
- `data/` — provenance manifest, small raw inputs, transcribed values and synthetic
  outputs; `docs/` — model, data and reproduction notes.

**All applicant data in this repository are synthetic.** They are produced by code from
public load shapes, weather records and stated assumptions; they are not REAP
application data and say nothing about any real applicant, facility or award.
Scenario parameters that are not taken from a cited source are hypothetical and are
marked as such in `configs/`.

## Installation

Python 3.11 or later and [uv](https://docs.astral.sh/uv/) are required.

```
uv sync --frozen --extra dev
```

`Dockerfile` builds the same environment together with the LaTeX toolchain.

## Reproduction

```
make all      # fetch inputs, run configs/paper.yaml, build values, figures, paper, comment
make quick    # reduced configuration (configs/quick.yaml); a few minutes on a laptop
make test     # unit, property, verification and regression tests
```

The equivalent single command for the experiments is

```
python -m reapschema.pipeline run --config configs/paper.yaml
```

`docs/reproduction.md` gives the steps, expected run times and the network hosts
contacted by `scripts/fetch_data.py`.

## Citation

See `CITATION.cff`. The repository is archived on Zenodo at
https://doi.org/10.5281/zenodo.24460622 (concept DOI, resolving to the latest version).

## License

Code: BSD 3-Clause. Text, figures and derived data: CC BY 4.0. See `LICENSE`.
