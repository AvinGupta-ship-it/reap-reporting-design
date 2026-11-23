"""Figure 5: bias of unnormalized and normalized estimates vs weather difference (synthetic)."""

from __future__ import annotations

import matplotlib.pyplot as plt
from common import BLUE, FIG_WIDTH, GREEN, VERMILION, legend_below, read, save, style

STYLES = {"unnormalized": (VERMILION, "o", "Unnormalized"),
          "normalized_annual": (BLUE, "s", "Normalized (monthly data)"),
          "interval_normalized": (GREEN, "^", "Normalized (interval data)")}


def main() -> None:
    style()
    bins = read("e4_bins.csv")
    fig, axes = plt.subplots(1, 2, figsize=(FIG_WIDTH, 3.5))
    fig.subplots_adjust(left=0.13, right=0.985, top=0.91, bottom=0.30, wspace=0.38)
    handles = {}
    for ax, cat, xlabel, ylabel in (
        (axes[0], "EEI", "Post- minus pre-period\nmean temperature (°C)",
         "Bias of savings estimate\n(% of pre-installation use)"),
        (axes[1], "RES", "Post-period irradiance anomaly\n(% of long-term mean)",
         "Bias vs long-term production (%)"),
    ):
        scale_x = 1.0 if cat == "EEI" else 100.0
        for name, (color, marker, label) in STYLES.items():
            g = bins[(bins["category"] == cat) & (bins["estimator"] == name)].sort_values("x_mid")
            if g.empty:
                continue
            handles[label] = ax.errorbar(g["x_mid"] * scale_x, 100 * g["bias"],
                                         yerr=196 * g["bias_se"], color=color, marker=marker,
                                         capsize=2, lw=1.2, ms=4)
        ax.axhline(0, color="0.3", lw=0.5)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title("(a) Efficiency improvements" if cat == "EEI"
                     else "(b) Photovoltaic systems", loc="left")
    legend_below(fig, list(handles.values()), list(handles), ncol=3, y=0.005)
    save(fig, "fig5_normalization", ["e4_bins.csv"])


if __name__ == "__main__":
    main()
