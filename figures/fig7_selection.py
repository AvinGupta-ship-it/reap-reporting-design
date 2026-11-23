"""Figure 7: probability that verification error changes selection, by specification."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from common import BLUE, SPEC_LABELS, VERMILION, YELLOW, read, save, style

ORDER = ["current", "dates", "dates_norm", "production_meter", "netting", "metadata",
         "recommended", "interval"]
CONDITIONS = [("with_errors_unvalidated", "0.55", "Injected errors, no validation"),
              ("with_errors_validated", VERMILION, "Injected errors, after validation"),
              ("error_free", BLUE, "Error-free evidence")]


def main() -> None:
    style()
    sel = read("e7_selection.csv")
    ratios = sorted(sel["funding_ratio"].unique())
    main_ratio = ratios[len(ratios) // 2]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.2), gridspec_kw={"width_ratios": [1.6, 1]})
    ax = axes[0]
    y = np.arange(len(ORDER))[::-1]
    for k, (cond, color, label) in enumerate(CONDITIONS):
        g = sel[(sel["condition"] == cond) & (sel["funding_ratio"] == main_ratio)].set_index(
            "spec").loc[ORDER]
        ax.errorbar(100 * g["selection_change"], y + 0.22 * (1 - k), xerr=196 * g["se"],
                    fmt="o", color=color, capsize=2, label=label)
    ax.set_yticks(y)
    ax.set_yticklabels([SPEC_LABELS[s] for s in ORDER], fontsize=6.3)
    ax.set_xlabel("Awards that differ from selection on true values (%)")
    ax.set_title(f"Funds equal to {100 * main_ratio:.0f}% of requests")
    ax.legend(fontsize=6, loc="lower right")
    ax.grid(axis="y", visible=False)
    ax = axes[1]
    for spec, color, marker in (("current", "black", "s"), ("recommended", VERMILION, "D"),
                                ("interval", YELLOW, "^")):
        g = sel[(sel["spec"] == spec) & (sel["condition"] == "with_errors_validated")
                ].sort_values("funding_ratio")
        ax.errorbar(100 * g["funding_ratio"], 100 * g["selection_change"], yerr=196 * g["se"],
                    color=color, marker=marker, capsize=2, mec="0.2", mew=0.4,
                    label=SPEC_LABELS[spec].replace("\n", " "))
    ax.set_xlabel("Funds as share of requests (%)")
    ax.set_ylabel("Awards that differ (%)")
    ax.set_title("Sensitivity to available funds")
    ax.legend(fontsize=6)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    save(fig, "fig7_selection", ["e7_selection.csv"])


if __name__ == "__main__":
    main()
