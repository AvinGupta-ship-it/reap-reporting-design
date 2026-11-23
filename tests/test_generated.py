"""Generated values: every macro used in the documents is defined and none is stale."""

from __future__ import annotations

import re

import pytest

from reapschema.provenance import REPO_ROOT
from reapschema.report import summaries_hash

GENERATED = REPO_ROOT / "paper" / "generated"
DOCUMENTS = [REPO_ROOT / "paper" / "manuscript.tex", REPO_ROOT / "paper" / "si.tex",
             REPO_ROOT / "comment" / "comment.tex",
             REPO_ROOT / "comment" / "attachment_technical.tex"]
# commands of LaTeX and the loaded packages that begin with a capital letter
KNOWN = {"S", "L", "Big", "Delta", "Bigg", "LaTeX", "TeX", "P", "O", "H", "AA", "Large"}


def defined_macros() -> set[str]:
    text = (GENERATED / "values.tex").read_text()
    return set(re.findall(r"\\newcommand\{\\([A-Za-z]+)\}", text))


@pytest.mark.parametrize("document", DOCUMENTS, ids=lambda p: p.name)
def test_macros_used_are_defined(document):
    text = re.sub(r"(?<!\\)%.*", "", document.read_text())
    used = set(re.findall(r"\\([A-Z][A-Za-z]+)", text)) - KNOWN
    missing = sorted(used - defined_macros())
    assert not missing, missing


def test_values_are_not_stale():
    header = (GENERATED / "values.tex").read_text().splitlines()[:5]
    recorded = next(line.split(":", 1)[1].strip() for line in header if "results-hash" in line)
    assert recorded == summaries_hash(REPO_ROOT / "results" / "summaries" / "paper")


def test_no_macro_expands_to_a_missing_value():
    text = (GENERATED / "values.tex").read_text()
    assert "{n/a}" not in text and "{nan}" not in text


def test_generated_tables_exist_for_every_input():
    for document in DOCUMENTS:
        for name in re.findall(r"\\input\{(?:\.\./paper/)?generated/([a-z_0-9]+\.tex)\}",
                               document.read_text()):
            assert (GENERATED / name).exists(), name


def test_figures_exist_for_every_include():
    for document in DOCUMENTS:
        for name in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{figures/([a-z_0-9]+)\}",
                               document.read_text()):
            assert (REPO_ROOT / "paper" / "figures" / f"{name}.pdf").exists(), name
