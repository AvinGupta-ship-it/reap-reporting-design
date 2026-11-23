"""SI figure: burden by collection mode and availability of automated access (synthetic)."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from common import BLACK, BLUE, FIG_WIDTH, GREEN, ORANGE, legend_below, read, save, style
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

MODES = [("manual_transcription", "Manual entry", BLACK),
         ("utility_file_upload", "File upload", BLUE),
         ("green_button_download", "Green Button", GREEN),
         ("automated_utility_access", "Automated access", ORANGE)]
SPECS = [("current", "Current\nrule"), ("recommended", "Frontier,\nmonthly"),
         ("metadata", "Full\nmetadata"), ("interval", "Interval\ndata")]


def main() -> None:
    style()
    e8 = read("e8_modes.csv")
    full = e8[e8["availability"] == 1.0]
    fig, axes = plt.subplots(1, 2, figsize=(FIG_WIDTH, 3.8))
    fig.subplots_adjust(left=0.10, right=0.985, top=0.92, bottom=0.34, wspace=0.34)
    width = 0.2
    for k, (mode, _label, color) in enumerate(MODES):
        g = full[full["mode"] == mode].set_index("spec").loc[[s for s, _ in SPECS]]
        x = np.arange(len(SPECS)) + (k - 1.5) * width
        axes[0].bar(x, g["burden"], width, color=color)
        axes[0].errorbar(x, g["burden"], yerr=[g["burden"] - g["burden_lo"],
                                               g["burden_hi"] - g["burden"]],
                         fmt="none", ecolor="0.35", lw=0.7, capsize=1.5)
    axes[0].set_xticks(np.arange(len(SPECS)))
    axes[0].set_xticklabels([label for _, label in SPECS])
    axes[0].set_ylabel("Respondent time (min)")
    axes[0].set_title("(a) By specification and mode", loc="left")
    axes[0].grid(axis="x", visible=False)
    base = full[(full["spec"] == "current") & (full["mode"] == "manual_transcription")][
        "burden"].iloc[0]
    axes[1].axhline(base, color=BLACK, lw=1.0, ls="--")
    for mode, _label, color in MODES[1:]:
        g = e8[(e8["spec"] == "recommended") & (e8["mode"] == mode)].sort_values(
            "availability")
        axes[1].plot(100 * g["availability"], g["burden"], color=color, marker="o", ms=4)
    axes[1].set_xlabel("Respondents able to use the mode (%)")
    axes[1].set_ylabel("Mean time (min)")
    axes[1].set_title("(b) Frontier specification", loc="left")
    handles = [Patch(color=c) for _m, _l, c in MODES] + [Line2D([], [], color=BLACK, ls="--")]
    labels = [label for _m, label, _c in MODES] + ["Current rule, manual entry"]
    legend_below(fig, handles, labels, ncol=3, y=0.005)
    save(fig, "si_modes", ["e8_modes.csv"])


if __name__ == "__main__":
    main()
