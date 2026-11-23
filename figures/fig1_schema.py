"""Figure 1: class diagram of the evidence schema, drawn from the LinkML source."""

from __future__ import annotations

import matplotlib.pyplot as plt
from common import BLUE, save, style
from matplotlib.patches import FancyArrowPatch, Rectangle

from reapschema.schema.build import schema_view

LAYOUT = {  # class -> (x, y of top-left corner)
    "EvidencePackage": (4.3, 10.0),
    "Applicant": (0.0, 10.0), "Facility": (0.0, 7.9), "Meter": (0.0, 5.1),
    "IntervalSeries": (0.0, 2.3),
    "BillingRecord": (4.3, 5.6),
    "Project": (8.6, 10.0), "PerformanceClaim": (8.6, 4.6), "EquipmentItem": (8.6, 1.4),
}
WIDTH, ROW = 3.5, 0.27
EDGES = [("EvidencePackage", "Applicant", "1"), ("EvidencePackage", "Facility", "1"),
         ("EvidencePackage", "Meter", "1..*"), ("EvidencePackage", "IntervalSeries", "0..*"),
         ("EvidencePackage", "BillingRecord", "0..*"), ("EvidencePackage", "Project", "1"),
         ("EvidencePackage", "PerformanceClaim", "1"),
         ("EvidencePackage", "EquipmentItem", "0..*"),
         ("BillingRecord", "Meter", "meter"), ("IntervalSeries", "Meter", "meter")]


def main() -> None:
    style()
    plt.rcParams["axes.grid"] = False
    view = schema_view()
    fig, ax = plt.subplots(figsize=(7.2, 7.4))
    boxes = {}
    for cls, (x, y) in LAYOUT.items():
        slots = view.class_induced_slots(cls)
        height = ROW * (len(slots) + 1.3)
        ax.add_patch(Rectangle((x, y - height), WIDTH, height, fill=False, lw=0.7))
        ax.add_patch(Rectangle((x, y - ROW * 1.2), WIDTH, ROW * 1.2, color=BLUE, alpha=0.18,
                               lw=0))
        ax.text(x + WIDTH / 2, y - ROW * 0.6, cls, ha="center", va="center", weight="bold",
                fontsize=7.5)
        for k, slot in enumerate(slots):
            unit = f" [{slot.unit.ucum_code}]" if slot.unit is not None else ""
            mark = "" if slot.required else "?"
            star = "[]" if slot.multivalued else ""
            ax.text(x + 0.06, y - ROW * (1.75 + k),
                    f"{slot.name}{mark}: {slot.range}{star}{unit}", fontsize=5.3, va="center",
                    family="DejaVu Sans Mono")
        boxes[cls] = (x, y, height)
    for src, dst, label in EDGES:
        sx, sy, sh = boxes[src]
        dx, dy, dh = boxes[dst]
        if dx + WIDTH <= sx:  # target in the column to the left
            a = (sx, min(max(dy - 0.3, sy - sh + 0.15), sy - 0.15))
            b = (dx + WIDTH, dy - min(0.3, dh / 2))
        elif dx >= sx + WIDTH:  # target in the column to the right
            a = (sx + WIDTH, min(max(dy - 0.3, sy - sh + 0.15), sy - 0.15))
            b = (dx, dy - min(0.3, dh / 2))
        elif dy < sy:  # target below in the same column
            a, b = (sx + WIDTH / 2, sy - sh), (dx + WIDTH / 2, dy)
        else:  # target above in the same column
            a, b = (sx + WIDTH / 2, sy), (dx + WIDTH / 2, dy - dh)
        ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=7, lw=0.6,
                                     color="0.25", shrinkA=0, shrinkB=0))
        ax.text(a[0] + 0.75 * (b[0] - a[0]), a[1] + 0.75 * (b[1] - a[1]) + 0.09, label,
                fontsize=5.5, ha="center", color="0.25")
    ax.set_xlim(-0.2, 12.3)
    ax.set_ylim(-1.0, 10.3)
    ax.set_aspect("equal")
    ax.axis("off")
    save(fig, "fig1_schema", [])


if __name__ == "__main__":
    main()
