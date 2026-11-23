"""Figure 5: bias of unnormalized and normalized estimates vs weather difference (synthetic)."""

from __future__ import annotations

import matplotlib.pyplot as plt
from common import BLUE, GREEN, VERMILION, read, save, style

STYLES = {"unnormalized": (VERMILION, "o", "Unnormalized"),
          "normalized_annual": (BLUE, "s", "Normalized (monthly bills)"),
          "interval_normalized": (GREEN, "^", "Normalized (interval data)")}


def main() -> None:
    style()
    bins = read("e4_bins.csv")
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.9))
    for ax, cat, xlabel, ylabel in (
        (axes[0], "EEI", "Post- minus pre-period mean temperature (°C)",
         "Bias of savings estimate\n(% of pre-installation use)"),
        (axes[1], "RES", "Post-period irradiance anomaly (% of long-term mean)",
         "Bias vs long-term production (%)"),
    ):
        scale_x = 1.0 if cat == "EEI" else 100.0
        for name, (color, marker, label) in STYLES.items():
            g = bins[(bins["category"] == cat) & (bins["estimator"] == name)].sort_values("x_mid")
            if g.empty:
                continue
            ax.errorbar(g["x_mid"] * scale_x, 100 * g["bias"], yerr=196 * g["bias_se"],
                        color=color, marker=marker, capsize=2, lw=1.0, label=label)
        ax.axhline(0, color="0.3", lw=0.5)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title("Efficiency improvements" if cat == "EEI" else "Photovoltaic systems")
        ax.legend(fontsize=6)
    fig.tight_layout()
    save(fig, "fig5_normalization", ["e4_bins.csv"])


if __name__ == "__main__":
    main()
