"""Figure 3: distribution of verification error by evidence specification (synthetic)."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from common import BLUE, SPEC_LABELS, VERMILION, read, save, style

ORDER = {"RES": ["current", "netting", "production_meter", "metadata", "interval"],
         "EEI": ["current", "dates", "dates_norm", "dates_norm_read", "interval"]}
TITLES = {"RES": "Renewable energy systems: annual production",
          "EEI": "Efficiency improvements: annual savings"}


def main() -> None:
    style()
    samples = read("e2_are_samples.parquet")
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.1))
    for ax, cat in zip(axes, ("RES", "EEI"), strict=True):
        specs = ORDER[cat]
        for k, spec in enumerate(specs):
            for cond, color, dy in (("error_free", BLUE, 0.17),
                                    ("with_errors_validated", VERMILION, -0.17)):
                are = samples[(samples["spec"] == spec) & (samples["condition"] == cond)
                              & (samples["category"] == cat)]["are"].to_numpy()
                are = np.clip(are, 1e-4, 10)
                q05, q25, q50, q75, q95 = np.quantile(are, [0.05, 0.25, 0.5, 0.75, 0.95])
                y = len(specs) - 1 - k + dy
                ax.plot([q05, q95], [y, y], color=color, lw=0.8)
                ax.plot([q25, q75], [y, y], color=color, lw=3.2, solid_capstyle="butt")
                ax.plot(q50, y, "o", color="white", mec=color, mew=0.9, ms=4)
                ax.text(1.02, y, f"{100 * (are > 0.10).mean():.1f}%", color=color, fontsize=5.5,
                        va="center", transform=ax.get_yaxis_transform())
        ax.set_yticks(range(len(specs)))
        ax.set_yticklabels([SPEC_LABELS[s] for s in specs][::-1], fontsize=6.5)
        ax.set_xscale("log")
        ax.set_xlabel("Absolute relative error of verified quantity")
        ax.set_title(TITLES[cat])
        ax.axvline(0.10, color="0.5", lw=0.5, ls=":")
        ax.grid(axis="y", visible=False)
        ax.text(1.02, len(specs) - 0.45, ">10%", fontsize=5.5, va="center",
                transform=ax.get_yaxis_transform())
    axes[0].plot([], [], color=BLUE, lw=3, label="Error-free evidence")
    axes[0].plot([], [], color=VERMILION, lw=3, label="With injected errors, after validation")
    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=2, fontsize=6.5)
    fig.tight_layout(rect=(0, 0.06, 1, 1), w_pad=3.0)
    save(fig, "fig3_error_distributions", ["e2_are_samples.parquet"])


if __name__ == "__main__":
    main()
