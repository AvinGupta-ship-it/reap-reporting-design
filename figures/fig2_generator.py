"""Figure 2: pipeline of the synthetic applicant generator and evaluation."""

from __future__ import annotations

import matplotlib.pyplot as plt
from common import BLUE, GREEN, ORANGE, VERMILION, save, style
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

BOXES = {
    "loads": (0.0, 4.0, "End-use load shapes\nComStock by State;\nhypothetical farm types",
              BLUE),
    "weather": (0.0, 2.6, "Actual-year weather\nNSRDB irradiance, ERA5 site\ntemperature, "
                          "ISD station", BLUE),
    "awards": (0.0, 1.2, "Project size and mix\nUSAspending 10.868;\nEIA prices", BLUE),
    "facility": (3.1, 4.0, "Facility hourly load\nscaling, noise,\noccupancy change", GREEN),
    "project": (3.1, 2.6, "Project\nPV (pvlib PVWatts) or\nefficiency measure", GREEN),
    "truth": (3.1, 1.2, "Ground truth\nproduction, normalized\nsavings, pre-period use", ORANGE),
    "billing": (6.2, 4.0, "Metering and billing\nread cycles, estimated\nreads, netting", GREEN),
    "errors": (6.2, 2.6, "Error injection\nsix labelled classes at\nscenario rates", VERMILION),
    "evidence": (6.2, 1.2, "Evidence package\nschema instance,\nclean and as reported", GREEN),
    "rules": (9.3, 4.0, "Validation rules\nactive set depends on\nelements collected", "0.4"),
    "mv": (9.3, 2.6, "M&V estimators\nbilling difference to\ndegree-day models", "0.4"),
    "loss": (9.3, 1.2, "Outcomes\nverification error,\nselection change, burden", ORANGE),
}
ARROWS = [("loads", "facility"), ("weather", "facility"), ("weather", "project"),
          ("awards", "project"), ("facility", "billing"), ("project", "billing"),
          ("facility", "truth"), ("project", "truth"), ("billing", "errors"),
          ("errors", "evidence"), ("evidence", "rules"), ("evidence", "mv"),
          ("rules", "mv"), ("mv", "loss"), ("truth", "loss")]
W, H = 2.6, 1.0


def main() -> None:
    style()
    plt.rcParams["axes.grid"] = False
    fig, ax = plt.subplots(figsize=(7.2, 3.3))
    for x, y, text, color in BOXES.values():
        ax.add_patch(FancyBboxPatch((x, y), W, H, boxstyle="round,pad=0.02,rounding_size=0.08",
                                    fc="white", ec=color, lw=1.1))
        head, _, rest = text.partition("\n")
        ax.text(x + W / 2, y + H - 0.2, head, ha="center", va="center", fontsize=6.8,
                weight="bold")
        ax.text(x + W / 2, y + 0.36, rest, ha="center", va="center", fontsize=5.8)
    for a, b in ARROWS:
        xa, ya = BOXES[a][0], BOXES[a][1]
        xb, yb = BOXES[b][0], BOXES[b][1]
        if xb > xa:
            p, q = (xa + W, ya + H / 2), (xb, yb + H / 2)
        elif yb < ya:
            p, q = (xa + W / 2, ya), (xb + W / 2, yb + H)
        else:
            p, q = (xa + W / 2, ya + H), (xb + W / 2, yb)
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=7, lw=0.6,
                                     color="0.3", shrinkA=1, shrinkB=1))
    ax.set_xlim(-0.1, 12.0)
    ax.set_ylim(1.0, 5.2)
    ax.axis("off")
    save(fig, "fig2_generator", [])


if __name__ == "__main__":
    main()
