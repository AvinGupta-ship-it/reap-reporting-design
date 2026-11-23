"""Shared helpers for figure scripts: style, result loading, deterministic saving."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from reapschema.provenance import REPO_ROOT, sha256_file, write_sidecar  # noqa: E402

HERE = Path(__file__).resolve().parent
RESULTS = REPO_ROOT / "results" / os.environ.get("REAP_CONFIG", "paper")
OUT = Path(os.environ.get("REAP_FIGURES", REPO_ROOT / "paper" / "figures"))

# Figures are drawn at the text width of the documents so that they are never scaled down.
# Minimum sizes: 8 pt tick labels; 9 pt axis labels, legends and annotations.
FIG_WIDTH = 6.5
TICK_PT, TEXT_PT = 8, 9

# Okabe-Ito palette
BLUE, VERMILION, GREEN, PURPLE, ORANGE, SKY, BLACK, YELLOW = (
    "#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#000000", "#F0E442")

SPEC_LABELS = {
    "current": "Current rule",
    "dates": "+ billing dates",
    "dates_norm": "+ dates, normalization",
    "dates_norm_read": "+ dates, normalization, read type",
    "production_meter": "+ monthly production readings",
    "netting": "+ post bills, export, netting basis",
    "metadata": "Monthly data with full metadata",
    "recommended": "Frontier specification",
    "interval": "Interval data",
}


def style() -> None:
    plt.style.use("default")
    matplotlib.rc_file(HERE / "matplotlibrc")


def legend_below(fig: plt.Figure, handles: list, labels: list, ncol: int, y: float = 0.0,
                 x: float = 0.5, **kwargs) -> None:
    """Place a legend outside the axes, below the panels (figure coordinates)."""
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(x, y), ncol=ncol,
               fontsize=TEXT_PT, handlelength=1.8, columnspacing=1.4, **kwargs)


def read(name: str) -> pd.DataFrame:
    path = RESULTS / name
    return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)


def save(fig: plt.Figure, name: str, inputs: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.pdf"
    fig.savefig(path, metadata={"CreationDate": datetime(2026, 1, 1), "ModDate": None,
                                "Producer": "matplotlib", "Creator": "reapschema"})
    fig.savefig(OUT / f"{name}.png", dpi=300)  # raster copy for the DOCX build
    plt.close(fig)
    checksums = {i: sha256_file(RESULTS / i) for i in inputs if (RESULTS / i).exists()}
    write_sidecar(path, config={"figure": name, "results": RESULTS.name}, seed=None,
                  inputs=checksums, extra={"data_basis": "synthetic"})
