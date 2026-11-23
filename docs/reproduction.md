# Reproduction

## Environment

```
uv sync --frozen --extra dev        # creates .venv from pyproject.toml and uv.lock
```

The optimization solver HiGHS is installed from the `highspy` wheel pinned by version
and hash in `uv.lock`. LaTeX (`latexmk`, `elsarticle`) and `pandoc` are needed for the
manuscript and comment; the `Dockerfile` provides them.

## Steps

| Step | Command | Output | Typical time (8 cores) |
|---|---|---|---|
| 1. Retrieve inputs | `python scripts/fetch_data.py` | `data/raw/`, `data/MANIFEST.yaml` | 1 h (about 2.8 GB; PVGIS requests dominate) |
| 2. Process inputs | `python -m reapschema.data.process` | `data/processed/` | 2 min |
| 3. Experiments | `python -m reapschema.pipeline run --config configs/paper.yaml` | `results/paper/`, `results/summaries/paper/`, `data/synthetic/` | see `results/paper/runtime.json` |
| 4. Values and tables | `python -m reapschema.report --config configs/paper.yaml` | `paper/generated/` | 10 s |
| 5. Figures | `make figures` | `paper/figures/` | 1 min |
| 6. Manuscript and SI | `make paper` | `paper/manuscript.pdf`, `paper/manuscript.docx`, `paper/si.pdf` | 1 min |
| 7. Comment | `make comment` | `comment/comment.pdf`, `comment/comment.docx`, `comment/attachment_technical.pdf` | 1 min |

`make all` runs steps 1–7. `make quick` runs steps 3–5 with `configs/quick.yaml`
(fewer applicants and replicates) and writes to `results/quick/`; it takes about two
minutes once inputs are present.

Steps 1 and 2 are idempotent: files whose checksum matches the manifest are not
downloaded again, and processed files are rebuilt only when absent. The small processed
tables needed by the tests (`load_profiles.parquet`, `load_response.json`,
`prices.csv`, `reap_awards.csv`) are committed; the hourly weather tables are rebuilt
from the downloads.

## Network hosts

`www.federalregister.gov`, `www.govinfo.gov`, `www.eia.gov`, `developer.nlr.gov`
(PVWatts reference run; the NREL developer network moved to this host),
`api.usaspending.gov`, `www.ncei.noaa.gov` (station history),
`noaa-isd-pds.s3.amazonaws.com` (ISD-Lite), `re.jrc.ec.europa.eu` (PVGIS 5.2),
`oedi-data-lake.s3.amazonaws.com` (ComStock), `web.archive.org` and `www.oig.usda.gov`
(OIG documents), and `api.crossref.org` / `api.datacite.org` (reference checker).

## Determinism

All random draws descend from the `seed` in the configuration through
`numpy.random.SeedSequence.spawn`, one child per synthetic applicant, so results do
not depend on the number of worker processes (`tests/test_pipeline.py`). Every output
has a `.meta.json` sidecar with the git commit, configuration hash, input checksums,
package versions and seed. `paper/generated/values.tex` records a hash of the result
summaries it was built from; `tests/test_generated.py` fails if a macro used in the
manuscript, the supporting information or the comment is undefined, or if the values
are stale relative to `results/summaries/paper/`.

## Checks

```
make test        # pytest
make lint        # ruff
make typecheck   # mypy --strict on src/
make refs        # DOI metadata against Crossref / DataCite
```
