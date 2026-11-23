"""SI figure: error growth with missing months and estimated reads (synthetic)."""

from __future__ import annotations

import matplotlib.pyplot as plt
from common import BLACK, BLUE, FIG_WIDTH, GREEN, VERMILION, legend_below, read, save, style

SERIES = {"cpre_undated": (VERMILION, "o", "Sum of bills / undated difference"),
          "cpre_dated": (BLACK, "D", "Day-annualized / dated difference"),
          "s_undated": (VERMILION, "o", ""), "s_dated": (BLACK, "D", ""),
          "s_norm": (BLUE, "s", "Normalized"),
          "s_norm_merged": (GREEN, "^", "Normalized, estimated reads merged")}


def main() -> None:
    style()
    e5 = read("e5_incomplete.csv")
    p0 = e5["estimated_read_prob"].min()
    fig, axes = plt.subplots(1, 3, figsize=(FIG_WIDTH, 3.5))
    fig.subplots_adjust(left=0.09, right=0.99, top=0.91, bottom=0.36, wspace=0.34)
    miss = e5[e5["estimated_read_prob"] == p0]
    full = e5[e5["missing_months"] == 0]
    handles: dict[str, object] = {}

    def draw(ax: plt.Axes, frame, x: str, names: tuple[str, ...], scale: float) -> None:
        for name in names:
            color, marker, label = SERIES[name]
            g = frame[frame["estimator"] == name].sort_values(x)
            (line,) = ax.plot(scale * g[x], 100 * g["median_are"], color=color, marker=marker,
                              ms=4)
            if label:
                handles.setdefault(label, line)
        ax.set_ylim(bottom=0)

    draw(axes[0], miss, "missing_months", ("cpre_undated", "cpre_dated"), 1.0)
    axes[0].set_title("(a) Pre-installation use", loc="left")
    axes[0].set_xlabel("Missing months")
    axes[0].set_ylabel("Median absolute relative error (%)")
    draw(axes[1], miss, "missing_months", ("s_undated", "s_dated", "s_norm"), 1.0)
    axes[1].set_title("(b) EEI savings", loc="left")
    axes[1].set_xlabel("Missing months")
    draw(axes[2], full, "estimated_read_prob", ("s_undated", "s_norm", "s_norm_merged"), 100.0)
    axes[2].set_title("(c) EEI savings", loc="left")
    axes[2].set_xlabel("Estimated reads (%)")
    legend_below(fig, list(handles.values()), list(handles), ncol=2, y=0.005)
    save(fig, "si_incomplete", ["e5_incomplete.csv"])


if __name__ == "__main__":
    main()
