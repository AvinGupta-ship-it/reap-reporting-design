"""SI figure: Monte Carlo convergence of headline loss estimates (synthetic)."""

from __future__ import annotations

import matplotlib.pyplot as plt
from common import BLACK, FIG_WIDTH, VERMILION, legend_below, read, save, style


def main() -> None:
    style()
    conv = read("convergence.csv")
    fig, axes = plt.subplots(1, 2, figsize=(FIG_WIDTH, 3.4))
    fig.subplots_adjust(left=0.11, right=0.985, top=0.92, bottom=0.30, wspace=0.36)
    handles = []
    for spec, color, _label in (("current", BLACK, ""), ("recommended", VERMILION, "")):
        g = conv[conv["spec"] == spec].sort_values("n")
        handles.append(axes[0].errorbar(g["n"], 100 * g["mare"], yerr=196 * g["se"],
                                        color=color, marker="o", capsize=2, ms=4))
        axes[1].plot(g["n"], 100 * g["relative_se"], color=color, marker="o", ms=4)
    axes[0].set_ylabel("Accuracy loss (%)")
    axes[0].set_title("(a) Running estimate", loc="left")
    axes[1].set_ylabel("Standard error (% of estimate)")
    axes[1].set_title("(b) Monte Carlo standard error", loc="left")
    axes[1].axhline(2.0, color="0.4", lw=0.7, ls="--")
    for ax in axes:
        ax.set_xscale("log")
        ax.set_xlabel("Number of synthetic applicants")
    axes[1].set_yscale("log")
    legend_below(fig, handles, ["Current rule", "Monthly-data frontier specification"], ncol=2,
                 y=0.005)
    save(fig, "si_convergence", ["convergence.csv"])


if __name__ == "__main__":
    main()
