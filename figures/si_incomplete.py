"""SI figure: error growth with missing months and estimated reads (synthetic)."""

from __future__ import annotations

import matplotlib.pyplot as plt
from common import BLUE, GREEN, VERMILION, read, save, style


def main() -> None:
    style()
    e5 = read("e5_incomplete.csv")
    p0 = e5["estimated_read_prob"].min()
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.6))
    miss = e5[e5["estimated_read_prob"] == p0]
    for est, color, label in (("cpre_undated", VERMILION, "Sum of bills"),
                              ("cpre_dated", BLUE, "Day-annualized")):
        g = miss[miss["estimator"] == est].sort_values("missing_months")
        axes[0].plot(g["missing_months"], 100 * g["median_are"], color=color, marker="o",
                     label=label)
    axes[0].set_title("Pre-installation use")
    axes[0].set_xlabel("Missing months per period")
    axes[0].set_ylabel("Median absolute relative error (%)")
    for est, color, label in (("s_undated", VERMILION, "Undated difference"),
                              ("s_dated", GREEN, "Dated difference"),
                              ("s_norm", BLUE, "Normalized")):
        g = miss[miss["estimator"] == est].sort_values("missing_months")
        axes[1].plot(g["missing_months"], 100 * g["median_are"], color=color, marker="o",
                     label=label)
    axes[1].set_title("EEI savings")
    axes[1].set_xlabel("Missing months per period")
    full = e5[e5["missing_months"] == 0]
    for est, color, label in (("s_undated", VERMILION, "Undated difference"),
                              ("s_norm", BLUE, "Normalized"),
                              ("s_norm_merged", GREEN, "Normalized, estimates merged")):
        g = full[full["estimator"] == est].sort_values("estimated_read_prob")
        axes[2].plot(100 * g["estimated_read_prob"], 100 * g["median_are"], color=color,
                     marker="o", label=label)
    axes[2].set_title("EEI savings")
    axes[2].set_xlabel("Probability a read is estimated (%)")
    for ax in axes:
        ax.legend(fontsize=6)
        ax.set_ylim(bottom=0)
    fig.tight_layout()
    save(fig, "si_incomplete", ["e5_incomplete.csv"])


if __name__ == "__main__":
    main()
