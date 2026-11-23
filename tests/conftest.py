from __future__ import annotations

import warnings

import pytest

from reapschema.config import Config, load_config
from reapschema.provenance import REPO_ROOT
from reapschema.synth.generator import SyntheticApplicant, generate_applicant, spawn_seeds

warnings.filterwarnings("ignore")


@pytest.fixture(scope="session")
def cfg() -> Config:
    return load_config(REPO_ROOT / "configs" / "quick.yaml")


@pytest.fixture(scope="session")
def applicants(cfg: Config) -> list[SyntheticApplicant]:
    seeds = spawn_seeds(cfg.seed, 24)
    return [generate_applicant(i, seeds[i], cfg, error_class="none") for i in range(24)]


def first_of(apps: list[SyntheticApplicant], category: str) -> SyntheticApplicant:
    return next(a for a in apps if a.category == category)
