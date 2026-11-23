"""Figure 2: pipeline of the synthetic applicant generator and evaluation."""

from __future__ import annotations

import matplotlib.pyplot as plt
from common import BLUE, FIG_WIDTH, GREEN, ORANGE, TEXT_PT, VERMILION, save, style
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

# four columns by three rows; all lengths in inches
W, H = 1.36, 0.92
GUT, VGAP = 0.33, 0.34
X = [0.02 + k * (W + GUT) for k in range(4)]
Y = [2 * (H + VGAP) + 0.40, (H + VGAP) + 0.40, 0.40]  # bottom of rows 0, 1, 2
BOXES = {
    "loads": (0, 0, "Load shapes", "ComStock by State;\nassumed farm types", BLUE),
    "weather": (0, 1, "Weather", "NSRDB, ERA5,\nISD station", BLUE),
    "awards": (0, 2, "Size and mix", "USAspending;\nEIA prices", BLUE),
    "facility": (1, 0, "Facility load", "scaling, noise,\nnon-routine change", GREEN),
    "project": (1, 1, "Project", "PVWatts PV or\nefficiency measure", GREEN),
    "truth": (1, 2, "Ground truth", "production, savings,\nprior use", ORANGE),
    "billing": (2, 0, "Billing", "read cycles,\nestimates, netting", GREEN),
    "errors": (2, 1, "Error injection", "six labeled\nclasses", VERMILION),
    "evidence": (2, 2, "Evidence", "schema instance,\nclean and reported", GREEN),
    "rules": (3, 0, "Validation rules", "active set depends\non elements", "0.4"),
    "mv": (3, 1, "M&V estimators", "bill difference to\ndegree-day models", "0.4"),
    "loss": (3, 2, "Outcomes", "error, selection\nchange, burden", ORANGE),
}
LINE = "0.3"


def main() -> None:
    style()
    plt.rcParams["axes.grid"] = False
    fig_h = Y[0] + H + 0.08
    fig = plt.figure(figsize=(FIG_WIDTH, fig_h))
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, FIG_WIDTH)
    ax.set_ylim(0, fig_h)
    ax.axis("off")
    pos = {}
    for key, (c, r, head, body, color) in BOXES.items():
        x, y = X[c], Y[r]
        pos[key] = (x, y)
        ax.add_patch(FancyBboxPatch((x, y), W, H, boxstyle="round,pad=0,rounding_size=0.06",
                                    fc="white", ec=color, lw=1.3))
        ax.text(x + W / 2, y + H - 0.19, head, ha="center", va="center", fontsize=TEXT_PT,
                weight="bold")
        ax.text(x + W / 2, y + 0.33, body, ha="center", va="center", fontsize=TEXT_PT,
                linespacing=1.15)

    def path(points: list[tuple[float, float]]) -> None:
        for a, b in zip(points[:-2], points[1:-1], strict=True):
            ax.plot([a[0], b[0]], [a[1], b[1]], color=LINE, lw=0.9, solid_capstyle="round")
        ax.add_patch(FancyArrowPatch(points[-2], points[-1], arrowstyle="-|>",
                                     mutation_scale=9, lw=0.9, color=LINE, shrinkA=0,
                                     shrinkB=0))

    def right(key: str, frac: float = 0.5) -> tuple[float, float]:
        return pos[key][0] + W, pos[key][1] + frac * H

    def left(key: str, frac: float = 0.5) -> tuple[float, float]:
        return pos[key][0], pos[key][1] + frac * H

    def top(key: str) -> tuple[float, float]:
        return pos[key][0] + W / 2, pos[key][1] + H

    def bottom(key: str) -> tuple[float, float]:
        return pos[key][0] + W / 2, pos[key][1]

    def elbow(src: tuple[float, float], dst: tuple[float, float], x_mid: float) -> None:
        path([src, (x_mid, src[1]), (x_mid, dst[1]), dst])

    g1 = X[0] + W  # gutters between columns
    g2 = X[1] + W
    g3 = X[2] + W
    path([right("loads", 0.6), left("facility", 0.6)])
    path([right("weather", 0.4), left("project", 0.4)])
    elbow(right("weather", 0.7), left("facility", 0.3), g1 + 0.10)
    elbow(right("awards"), left("project", 0.15), g1 + 0.20)
    path([right("facility", 0.6), left("billing", 0.6)])
    elbow(right("project", 0.6), left("billing", 0.3), g2 + 0.10)
    # ground truth from facility and project, entering from the left margin of the gutter
    path([bottom("project"), top("truth")])
    elbow(right("facility", 0.25), (pos["truth"][0] + W, pos["truth"][1] + 0.6 * H), g2 + 0.20)
    path([bottom("billing"), top("errors")])
    path([bottom("errors"), top("evidence")])
    elbow(right("evidence", 0.6), left("mv", 0.4), g3 + 0.10)
    elbow(right("evidence", 0.35), left("rules", 0.4), g3 + 0.20)
    path([bottom("rules"), top("mv")])
    path([bottom("mv"), top("loss")])
    # truth to outcomes beneath the bottom row
    bx, by = bottom("truth")
    lx, ly = bottom("loss")
    path([(bx, by), (bx, by - 0.20), (lx, by - 0.20), (lx, ly)])
    save(fig, "fig2_generator", [])


if __name__ == "__main__":
    main()
