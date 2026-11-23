# Reproduction entry points. `make all` regenerates every number, table and figure of
# the manuscript and comment from raw inputs; `make quick` runs a reduced configuration.
PY ?= .venv/bin/python
CONFIG ?= configs/paper.yaml

.PHONY: all quick env data schema results report figures paper comment test lint typecheck refs clean

all: data results report figures paper comment

env:
	uv sync --frozen --extra dev

data:
	$(PY) scripts/fetch_data.py
	$(PY) -m reapschema.data.process

schema:
	$(PY) -m reapschema.schema.build

results:
	$(PY) -W ignore -m reapschema.pipeline run --config $(CONFIG)

report:
	$(PY) -W ignore -m reapschema.report --config $(CONFIG)

figures:
	for f in figures/fig*.py figures/si_*.py; do $(PY) -W ignore $$f || exit 1; done

paper:
	cd paper && latexmk -pdf -interaction=nonstopmode -halt-on-error manuscript.tex si.tex
	cd paper && sed -E 's/\\label\{eq:[a-z]+\}//' manuscript.tex | pandoc --from=latex --to=docx -M author="Avin Gupta" \
		-M author="iamavingupta@gmail.com" \
		--citeproc --bibliography=references.bib --resource-path=.:figures \
		--default-image-extension=png -o manuscript.docx

comment:
	$(MAKE) -C comment

quick:
	$(PY) -W ignore -m reapschema.pipeline run --config configs/quick.yaml
	$(PY) -W ignore -m reapschema.report --config configs/quick.yaml
	for f in figures/fig*.py figures/si_*.py; do \
		REAP_CONFIG=quick REAP_FIGURES=results/quick/figures $(PY) -W ignore $$f || exit 1; done

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check src scripts figures tests

typecheck:
	$(PY) -m mypy src

refs:
	$(PY) scripts/check_refs.py paper/references.bib

clean:
	rm -rf results/quick results/paper
	cd paper && latexmk -C
