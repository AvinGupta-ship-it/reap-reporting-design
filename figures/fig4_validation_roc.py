"""Figure 4: ROC curves of the statistical validation rules by error class (synthetic)."""

from __future__ import annotations

import matplotlib.pyplot as plt
from common import (
    BLACK,
    BLUE,
    FIG_WIDTH,
    GREEN,
    ORANGE,
    PURPLE,
    SKY,
    VERMILION,
    legend_below,
    read,
    save,
    style,
)
from matplotlib.lines import Line2D

PANELS = [("plausibility_z", "RES", "(a) Production vs model,\ndefault geometry"),
          ("plausibility_z_geometry", "RES", "(b) Production vs model,\ndeclared geometry"),
          ("bill_difference", "RES", "(c) Production vs bills,\nbasis known"),
          ("bill_difference_unlabeled", "RES", "(d) Production vs bills,\nbasis unknown"),
          ("monthly_shape", "RES", "(e) Monthly production\nshape"),
          ("bill_outlier_dated", "EEI", "(f) Bill outlier,\ndaily use (EEI)")]
COLORS = {"unit": BLUE, "transposed_digits": VERMILION, "wrong_period": GREEN,
          "double_counting": PURPLE, "gross_net": ORANGE, "nameplate_hours": SKY}
NAMES = {"unit": "Unit", "transposed_digits": "Transposed digits",
         "wrong_period": "Wrong period", "double_counting": "Double counting",
         "gross_net": "Gross/net", "nameplate_hours": "Nameplate x hours"}


def main() -> None:
    style()
    roc = read("e3_roc.parquet")
    fig, axes = plt.subplots(2, 3, figsize=(FIG_WIDTH, 5.0), sharex=True, sharey=True)
    fig.subplots_adjust(left=0.09, right=0.985, top=0.92, bottom=0.215, wspace=0.12,
                        hspace=0.40)
    for ax, (rule, cat, title) in zip(axes.ravel(), PANELS, strict=True):
        sel = roc[(roc["rule"] == rule) & (roc["category"] == cat)]
        for cls, grp in sel.groupby("error_class"):
            g = grp.sort_values(["fpr", "tpr"])
            ax.plot([0, *g["fpr"], 1], [0, *g["tpr"], 1], color=COLORS[str(cls)])
        ax.plot([0, 1], [0, 1], color=BLACK, lw=0.5, ls=":")
        ax.set_title(title, fontsize=9, loc="left")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1.01)
        ax.set_aspect("equal")
    for ax in axes[1]:
        ax.set_xlabel("False-positive rate")
    for ax in axes[:, 0]:
        ax.set_ylabel("Detection rate")
    handles = [Line2D([], [], color=c, lw=1.6) for c in COLORS.values()]
    legend_below(fig, handles, [NAMES[k] for k in COLORS], ncol=3, y=0.005)
    save(fig, "fig4_validation_roc", ["e3_roc.parquet"])


if __name__ == "__main__":
    main()
