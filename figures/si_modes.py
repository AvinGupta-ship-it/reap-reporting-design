"""SI figure: burden by collection mode and availability of automated access (synthetic)."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from common import BLACK, BLUE, GREEN, ORANGE, VERMILION, read, save, style

MODES = [("manual_transcription", "Manual", BLACK), ("utility_file_upload", "File upload", BLUE),
         ("green_button_download", "Green Button", GREEN),
         ("automated_utility_access", "Automated access", ORANGE)]
SPECS = [("current", "Current rule"), ("recommended", "Selected frontier\nspecification"),
         ("metadata", "Monthly data,\nfull metadata"), ("interval", "Interval data")]


def main() -> None:
    style()
    e8 = read("e8_modes.csv")
    full = e8[e8["availability"] == 1.0]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.9))
    width = 0.2
    for k, (mode, label, color) in enumerate(MODES):
        g = full[full["mode"] == mode].set_index("spec").loc[[s for s, _ in SPECS]]
        x = np.arange(len(SPECS)) + (k - 1.5) * width
        axes[0].bar(x, g["burden"], width, color=color, label=label)
        axes[0].errorbar(x, g["burden"], yerr=[g["burden"] - g["burden_lo"],
                                               g["burden_hi"] - g["burden"]],
                         fmt="none", ecolor="0.3", lw=0.6, capsize=1.5)
    axes[0].set_xticks(np.arange(len(SPECS)))
    axes[0].set_xticklabels([label for _, label in SPECS], fontsize=6)
    axes[0].set_ylabel("Respondent time (minutes)")
    axes[0].legend(fontsize=6)
    axes[0].grid(axis="x", visible=False)
    base = full[(full["spec"] == "current") & (full["mode"] == "manual_transcription")][
        "burden"].iloc[0]
    axes[1].axhline(base, color=BLACK, lw=0.8, ls="--", label="Current rule, manual")
    for mode, label, color in MODES[1:]:
        g = e8[(e8["spec"] == "recommended") & (e8["mode"] == mode)].sort_values(
            "availability")
        axes[1].plot(100 * g["availability"], g["burden"], color=color, marker="o", label=label)
    axes[1].plot([], [], color=VERMILION)
    axes[1].set_xlabel("Respondents able to use the mode (%)")
    axes[1].set_ylabel("Mean time, selected frontier specification (minutes)")
    axes[1].legend(fontsize=6)
    fig.tight_layout()
    save(fig, "si_modes", ["e8_modes.csv"])


if __name__ == "__main__":
    main()
