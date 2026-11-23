"""Figure 7: probability that verification error changes selection, by specification."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from common import BLUE, FIG_WIDTH, GREEN, SPEC_LABELS, TEXT_PT, VERMILION, read, save, style

ORDER = ["current", "dates", "dates_norm", "production_meter", "netting", "metadata",
         "recommended", "interval"]
CONDITIONS = [("with_errors_unvalidated", "0.55", "Errors, no validation"),
              ("with_errors_validated", VERMILION, "Errors, after validation"),
              ("error_free", BLUE, "Error-free evidence")]


def main() -> None:
    style()
    sel = read("e7_selection.csv")
    ratios = sorted(sel["funding_ratio"].unique())
    main_ratio = ratios[len(ratios) // 2]
    fig = plt.figure(figsize=(FIG_WIDTH, 6.4))
    top = fig.add_axes((0.40, 0.555, 0.575, 0.395))
    bottom = fig.add_axes((0.40, 0.165, 0.575, 0.24))
    y = np.arange(len(ORDER))[::-1]
    handles = []
    for k, (cond, color, label) in enumerate(CONDITIONS):
        g = sel[(sel["condition"] == cond) & (sel["funding_ratio"] == main_ratio)].set_index(
            "spec").loc[ORDER]
        handles.append(top.errorbar(100 * g["selection_change"], y + 0.24 * (1 - k),
                                    xerr=196 * g["se"], fmt="o", color=color, capsize=2,
                                    ms=4.5, label=label))
    top.set_yticks(y)
    top.set_yticklabels([SPEC_LABELS[s] for s in ORDER], fontsize=TEXT_PT)
    top.set_xlabel("Awards that differ from selection on true values (%)")
    top.set_title(f"(a) Funds equal to {100 * main_ratio:.0f}% of requests", loc="left")
    top.grid(axis="y", visible=False)
    top.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.2, -0.17), ncol=3,
               fontsize=TEXT_PT, columnspacing=1.0, handletextpad=0.3)
    lines = []
    for spec, color, marker in (("current", "black", "s"), ("recommended", VERMILION, "D"),
                                ("interval", GREEN, "^")):
        g = sel[(sel["spec"] == spec) & (sel["condition"] == "with_errors_validated")
                ].sort_values("funding_ratio")
        lines.append(bottom.errorbar(100 * g["funding_ratio"], 100 * g["selection_change"],
                                     yerr=196 * g["se"], color=color, marker=marker, capsize=2,
                                     mec="0.2", mew=0.5, ms=5, label=SPEC_LABELS[spec]))
    bottom.set_xlabel("Funds as share of requests (%)")
    bottom.set_ylabel("Awards that differ (%)")
    bottom.set_title("(b) Sensitivity to available funds (errors, after validation)",
                     loc="left")
    bottom.set_ylim(bottom=0)
    bottom.legend(handles=lines, loc="upper center", bbox_to_anchor=(0.2, -0.33), ncol=3,
                  fontsize=TEXT_PT, columnspacing=1.0, handletextpad=0.3)
    save(fig, "fig7_selection", ["e7_selection.csv"])


if __name__ == "__main__":
    main()
