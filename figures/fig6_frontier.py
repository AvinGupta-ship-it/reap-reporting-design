"""Figure 6: accuracy-burden Pareto frontier over data-element specifications (synthetic)."""

from __future__ import annotations

import json

import matplotlib.pyplot as plt
from common import BLACK, BLUE, FIG_WIDTH, RESULTS, VERMILION, legend_below, read, save, style

from reapschema.validate import OPTIONAL_ELEMENTS


def main() -> None:
    style()
    specs = read("e6_specs.parquet")
    bands = read("e6_bands.csv")
    rec = json.loads((RESULTS / "recommended.json").read_text())
    manual = specs[specs["mode"] == "manual_transcription"]
    fig, axes = plt.subplots(1, 2, figsize=(FIG_WIDTH, 3.6))
    fig.subplots_adjust(left=0.13, right=0.985, top=0.915, bottom=0.385, wspace=0.42)
    handles: list = []
    for ax, metric, flag, title, ylabel in (
        (axes[0], "mare", "on_frontier_mare", "(a) Accuracy loss",
         "Mean absolute relative error\n(capped at 1)"),
        (axes[1], "selection_change", "on_frontier_selection", "(b) Selection loss",
         "Share of awards changed\nby verification error"),
    ):
        h_all = ax.scatter(manual["burden_min"], manual[metric], s=3, color="0.72",
                           linewidths=0, rasterized=True)
        b = bands[bands["metric"] == metric]
        h_band = ax.fill_between(b["budget_min"], b["lo"], b["hi"], color=BLUE, alpha=0.2, lw=0)
        front = manual[manual[flag]].sort_values("burden_min")
        (h_front,) = ax.step(front["burden_min"], front[metric], where="post", color=BLUE,
                             marker="o", ms=3.5)
        base = manual[manual["n_elements"] == 0].iloc[0]
        (h_base,) = ax.plot(base["burden_min"], base[metric], "s", color=BLACK, ms=6)
        row = manual[(manual[list(OPTIONAL_ELEMENTS)].sum(axis=1) == len(rec["elements"]))
                     & (manual[rec["elements"]].sum(axis=1) == len(rec["elements"]))].iloc[0]
        (h_rec,) = ax.plot(row["burden_min"], row[metric], "D", color=VERMILION, ms=6)
        ax.set_xlabel("Respondent time, energy evidence (min)")
        ax.set_ylabel(ylabel)
        ax.set_title(title, loc="left")
        ax.set_xlim(manual["burden_min"].min() - 8, manual["burden_min"].quantile(0.9))
        handles = [h_all, h_front, h_band, h_base, h_rec]
    legend_below(fig, handles, ["Specifications", "Pareto frontier",
                                "Frontier, 90% Monte Carlo band", "Current rule",
                                "Monthly-data frontier specification"], ncol=2, y=0.005)
    save(fig, "fig6_frontier", ["e6_specs.parquet", "e6_bands.csv", "recommended.json"])


if __name__ == "__main__":
    main()
