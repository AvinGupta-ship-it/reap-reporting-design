"""Figure 6: accuracy-burden Pareto frontier over data-element specifications (synthetic)."""

from __future__ import annotations

import json

import matplotlib.pyplot as plt
from common import BLACK, BLUE, RESULTS, VERMILION, read, save, style

from reapschema.validate import OPTIONAL_ELEMENTS


def main() -> None:
    style()
    specs = read("e6_specs.parquet")
    bands = read("e6_bands.csv")
    rec = json.loads((RESULTS / "recommended.json").read_text())
    manual = specs[specs["mode"] == "manual_transcription"]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0))
    for ax, metric, flag, ylabel in (
        (axes[0], "mare", "on_frontier_mare", "Mean absolute relative error (capped at 1)"),
        (axes[1], "selection_change", "on_frontier_selection",
         "Share of awards changed by verification error"),
    ):
        ax.scatter(manual["burden_min"], manual[metric], s=2, color="0.75", linewidths=0,
                   rasterized=True, label="Specifications")
        b = bands[bands["metric"] == metric]
        ax.fill_between(b["budget_min"], b["lo"], b["hi"], color=BLUE, alpha=0.2, lw=0,
                        label="Frontier, 90% Monte Carlo band")
        front = manual[manual[flag]].sort_values("burden_min")
        ax.step(front["burden_min"], front[metric], where="post", color=BLUE,
                label="Pareto frontier")
        ax.plot(front["burden_min"], front[metric], "o", color=BLUE, ms=3)
        base = manual[manual["n_elements"] == 0].iloc[0]
        ax.plot(base["burden_min"], base[metric], "s", color=BLACK, ms=5, label="Current rule")
        row = manual[(manual[list(OPTIONAL_ELEMENTS)].sum(axis=1) == len(rec["elements"]))
                     & (manual[rec["elements"]].sum(axis=1) == len(rec["elements"]))].iloc[0]
        ax.plot(row["burden_min"], row[metric], "D", color=VERMILION, ms=5,
                label="Selected frontier specification")
        ax.set_xlabel("Respondent time for energy evidence (minutes)")
        ax.set_ylabel(ylabel)
        ax.set_xlim(manual["burden_min"].min() - 8, manual["burden_min"].quantile(0.9))
    axes[0].legend(fontsize=6)
    fig.tight_layout()
    save(fig, "fig6_frontier", ["e6_specs.parquet", "e6_bands.csv", "recommended.json"])


if __name__ == "__main__":
    main()
