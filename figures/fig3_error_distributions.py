"""Figure 3: distribution of verification error by evidence specification (synthetic)."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from common import BLUE, FIG_WIDTH, SPEC_LABELS, TEXT_PT, VERMILION, legend_below, read, save, style
from matplotlib.lines import Line2D

ORDER = {"RES": ["current", "netting", "production_meter", "metadata", "interval"],
         "EEI": ["current", "dates", "dates_norm", "dates_norm_read", "interval"]}
TITLES = {"RES": "RES: annual production", "EEI": "EEI: annual savings"}
# (condition, color, vertical offset of the bar, x of the annotation column)
CONDITIONS = (("error_free", BLUE, 0.18, 1.03),
              ("with_errors_validated", VERMILION, -0.18, 1.215))


def main() -> None:
    style()
    samples = read("e2_are_samples.parquet")
    fig, axes = plt.subplots(2, 1, figsize=(FIG_WIDTH, 4.5))
    fig.subplots_adjust(left=0.37, right=0.775, top=0.935, bottom=0.19, hspace=0.62)
    for ax, cat in zip(axes, ("RES", "EEI"), strict=True):
        specs = ORDER[cat]
        for k, spec in enumerate(specs):
            for cond, color, dy, x_text in CONDITIONS:
                are = samples[(samples["spec"] == spec) & (samples["condition"] == cond)
                              & (samples["category"] == cat)]["are"].to_numpy()
                share = 100 * (are > 0.10).mean()
                are = np.clip(are, 1e-4, 10)
                q05, q25, q50, q75, q95 = np.quantile(are, [0.05, 0.25, 0.5, 0.75, 0.95])
                y = len(specs) - 1 - k + dy
                ax.plot([q05, q95], [y, y], color=color, lw=1.0)
                ax.plot([q25, q75], [y, y], color=color, lw=4.0, solid_capstyle="butt")
                ax.plot(q50, y, "o", color="white", mec=color, mew=1.0, ms=4.5)
                ax.text(x_text, len(specs) - 1 - k, f"{share:.1f}%", color=color,
                        fontsize=TEXT_PT, va="center", transform=ax.get_yaxis_transform())
        ax.set_yticks(range(len(specs)))
        ax.set_yticklabels([SPEC_LABELS[s] for s in specs][::-1], fontsize=TEXT_PT)
        ax.set_ylim(-0.6, len(specs) - 0.4)
        ax.set_xscale("log")
        ax.set_xlabel("Absolute relative error of verified quantity")
        ax.set_title(TITLES[cat], loc="left", weight="bold")
        ax.axvline(0.10, color="0.5", lw=0.6, ls=":")
        ax.grid(axis="y", visible=False)
        ax.text(1.03, 1.03, "error >10%", fontsize=TEXT_PT, va="bottom", weight="bold",
                transform=ax.transAxes)
    handles = [Line2D([], [], color=BLUE, lw=4), Line2D([], [], color=VERMILION, lw=4)]
    legend_below(fig, handles, ["Error-free evidence",
                                "With injected errors, after validation"], ncol=2, y=0.01)
    save(fig, "fig3_error_distributions", ["e2_are_samples.parquet"])


if __name__ == "__main__":
    main()
