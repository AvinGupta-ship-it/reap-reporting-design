"""Figure 4: ROC curves of the statistical validation rules by error class (synthetic)."""

from __future__ import annotations

import matplotlib.pyplot as plt
from common import BLACK, BLUE, GREEN, ORANGE, PURPLE, SKY, VERMILION, read, save, style

PANELS = [("plausibility_z", "RES", "Production vs model\n(default geometry)"),
          ("plausibility_z_geometry", "RES", "Production vs model\n(declared geometry)"),
          ("bill_difference", "RES", "Production vs utility bills\n(export and basis known)"),
          ("bill_difference_unlabelled", "RES", "Production vs utility bills\n(basis unknown)"),
          ("monthly_shape", "RES", "Monthly production shape"),
          ("bill_outlier_dated", "EEI", "Bill outlier\n(average daily use)")]
COLORS = {"unit": BLUE, "transposed_digits": VERMILION, "wrong_period": GREEN,
          "double_counting": PURPLE, "gross_net": ORANGE, "nameplate_hours": SKY}
NAMES = {"unit": "Unit", "transposed_digits": "Transposed digits",
         "wrong_period": "Wrong period", "double_counting": "Double counting",
         "gross_net": "Gross/net", "nameplate_hours": "Nameplate x hours"}


def main() -> None:
    style()
    roc = read("e3_roc.parquet")
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 4.9), sharex=True, sharey=True)
    for ax, (rule, cat, title) in zip(axes.ravel(), PANELS, strict=True):
        sel = roc[(roc["rule"] == rule) & (roc["category"] == cat)]
        for cls, grp in sel.groupby("error_class"):
            g = grp.sort_values(["fpr", "tpr"])
            ax.plot([0, *g["fpr"], 1], [0, *g["tpr"], 1], color=COLORS[cls],
                    label=f"{NAMES[cls]} ({g['auc'].iloc[0]:.2f})")
        ax.plot([0, 1], [0, 1], color=BLACK, lw=0.4, ls=":")
        ax.set_title(f"{title} [{cat}]", fontsize=7)
        ax.legend(fontsize=5.2, loc="lower right", title="Error class (AUC)",
                  title_fontsize=5.2)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1.01)
    for ax in axes[1]:
        ax.set_xlabel("False-positive rate")
    for ax in axes[:, 0]:
        ax.set_ylabel("Detection rate")
    fig.tight_layout()
    save(fig, "fig4_validation_roc", ["e3_roc.parquet"])


if __name__ == "__main__":
    main()
