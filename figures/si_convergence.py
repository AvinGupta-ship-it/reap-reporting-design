"""SI figure: Monte Carlo convergence of headline loss estimates (synthetic)."""

from __future__ import annotations

import matplotlib.pyplot as plt
from common import BLACK, VERMILION, read, save, style


def main() -> None:
    style()
    conv = read("convergence.csv")
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8))
    for spec, color, label in (("current", BLACK, "Current rule"),
                               ("recommended", VERMILION, "Selected frontier specification")):
        g = conv[conv["spec"] == spec].sort_values("n")
        axes[0].errorbar(g["n"], 100 * g["mare"], yerr=196 * g["se"], color=color, marker="o",
                         capsize=2, label=label)
        axes[1].plot(g["n"], 100 * g["relative_se"], color=color, marker="o", label=label)
    axes[0].set_ylabel("Mean absolute relative error, capped (%)")
    axes[1].set_ylabel("Monte Carlo standard error (% of estimate)")
    axes[1].axhline(2.0, color="0.4", lw=0.6, ls="--")
    for ax in axes:
        ax.set_xscale("log")
        ax.set_xlabel("Number of synthetic applicants")
    axes[1].set_yscale("log")
    axes[0].legend()
    fig.tight_layout()
    save(fig, "si_convergence", ["convergence.csv"])


if __name__ == "__main__":
    main()
