"""Figure 1: class diagram of the evidence schema, drawn from the LinkML source."""

from __future__ import annotations

import matplotlib.pyplot as plt
from common import BLUE, FIG_WIDTH, save, style
from matplotlib.patches import FancyArrowPatch, Rectangle

from reapschema.schema.build import schema_view

# two-column layout; all lengths in inches
COLUMNS = (("EvidencePackage", "Applicant", "Facility", "Meter", "IntervalSeries"),
           ("Project", "BillingRecord", "PerformanceClaim", "EquipmentItem"))
MULTIPLICITY = {"Applicant": "1", "Facility": "1", "Project": "1", "Meter": "1..*",
                "BillingRecord": "0..*", "IntervalSeries": "0..*", "PerformanceClaim": "1",
                "EquipmentItem": "0..*"}
BOX_W, ROW, HEAD, GAP = 2.82, 0.142, 0.20, 0.17
LEFT, GUTTER = 0.30, 0.56
FONT = 7.0
LINE = "0.3"


def main() -> None:
    style()
    plt.rcParams["axes.grid"] = False
    view = schema_view()
    slots = {c: view.class_induced_slots(c) for col in COLUMNS for c in col}
    heights = {c: HEAD + ROW * len(s) + 0.05 for c, s in slots.items()}
    total = max(sum(heights[c] for c in col) + GAP * (len(col) - 1) for col in COLUMNS)
    fig_h = total + 0.70
    fig = plt.figure(figsize=(FIG_WIDTH, fig_h))
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, FIG_WIDTH)
    ax.set_ylim(0, fig_h)
    ax.axis("off")
    boxes: dict[str, tuple[float, float, float]] = {}  # class -> (x, top, height)
    rows: dict[tuple[str, str], float] = {}  # (class, slot) -> y of the slot row
    for k, col in enumerate(COLUMNS):
        x = LEFT + k * (BOX_W + GUTTER)
        top = fig_h - 0.12
        for cls in col:
            h = heights[cls]
            ax.add_patch(Rectangle((x, top - h), BOX_W, h, fill=False, lw=0.8, ec="0.15"))
            ax.add_patch(Rectangle((x, top - HEAD), BOX_W, HEAD, color=BLUE, alpha=0.18, lw=0))
            ax.text(x + 0.06, top - HEAD / 2, cls, ha="left", va="center", weight="bold",
                    fontsize=FONT + 1)
            if cls in MULTIPLICITY:
                ax.text(x + BOX_W - 0.06, top - HEAD / 2, f"[{MULTIPLICITY[cls]}]", ha="right",
                        va="center", fontsize=FONT, color="0.25")
            for i, slot in enumerate(slots[cls]):
                unit = f" [{slot.unit.ucum_code}]" if slot.unit is not None else ""
                text = (f"{slot.name}{'' if slot.required else '?'}: {slot.range}"
                        f"{'[]' if slot.multivalued else ''}{unit}")
                y = top - HEAD - ROW * (i + 0.62)
                rows[(cls, slot.name)] = y
                ax.text(x + 0.06, y, text, fontsize=FONT, va="center",
                        family="DejaVu Sans Mono")
            boxes[cls] = (x, top, h)
            top -= h + GAP

    def arrow(points: list[tuple[float, float]], style_: str = "-|>") -> None:
        for a, b in zip(points[:-2], points[1:-1], strict=True):
            ax.plot([a[0], b[0]], [a[1], b[1]], color=LINE, lw=0.8, solid_capstyle="round")
        ax.add_patch(FancyArrowPatch(points[-2], points[-1], arrowstyle=style_,
                                     mutation_scale=8, lw=0.8, color=LINE, shrinkA=0,
                                     shrinkB=0))

    ex, etop, eh = boxes["EvidencePackage"]
    # composition: trunk in the left margin to the classes of the left column
    trunk_l = LEFT - 0.17
    start_y = etop - eh + 0.12
    ax.plot([ex, trunk_l], [start_y, start_y], color=LINE, lw=0.8)
    lows = []
    for cls in COLUMNS[0][1:]:
        x, top, _h = boxes[cls]
        y = top - HEAD / 2
        lows.append(y)
        arrow([(trunk_l, y), (x, y)])
    ax.plot([trunk_l, trunk_l], [start_y, min(lows)], color=LINE, lw=0.8)
    # composition: trunk in the gutter to the classes of the right column
    trunk_r = LEFT + BOX_W + 0.16
    src_y = etop - HEAD / 2
    ax.plot([ex + BOX_W, trunk_r], [src_y, src_y], color=LINE, lw=0.8)
    ys = []
    for cls in COLUMNS[1]:
        x, top, _h = boxes[cls]
        y = top - HEAD / 2
        ys.append(y)
        arrow([(trunk_r, y), (x, y)])
    ax.plot([trunk_r, trunk_r], [min(ys), max([*ys, src_y])], color=LINE, lw=0.8)
    # references to Meter: second trunk in the gutter, dashed
    ref_x = LEFT + BOX_W + 0.38
    mx, mtop, _mh = boxes["Meter"]
    # enter Meter at the slot row farthest from the composition arrows
    meter_rows = [rows[("Meter", s.name)] for s in slots["Meter"]]
    target_y = max(meter_rows, key=lambda y: min(abs(y - c) for c in [*ys, *lows]))
    for cls in ("BillingRecord", "IntervalSeries"):
        x, _top, _h = boxes[cls]
        y = rows[(cls, "meter")]
        edge = x if cls == "BillingRecord" else x + BOX_W
        ax.plot([edge, ref_x, ref_x], [y, y, target_y], color=LINE, lw=0.8, ls=(0, (3, 2)))
    ax.plot([ref_x, mx + BOX_W + 0.12], [target_y, target_y], color=LINE, lw=0.8,
            ls=(0, (3, 2)))
    arrow([(mx + BOX_W + 0.12, target_y), (mx + BOX_W, target_y)])
    ax.plot([0.30, 0.62], [0.2, 0.2], color=LINE, lw=0.8)
    ax.text(0.68, 0.2, "contains (multiplicity in brackets)", fontsize=FONT, va="center")
    ax.plot([3.25, 3.57], [0.2, 0.2], color=LINE, lw=0.8, ls=(0, (3, 2)))
    ax.text(3.63, 0.2, "refers to (slot meter)", fontsize=FONT, va="center")
    save(fig, "fig1_schema", [])


if __name__ == "__main__":
    main()
