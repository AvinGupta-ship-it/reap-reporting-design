"""Generate schema artefacts from the LinkML source.

Outputs, written to ``src/reapschema/schema/generated/``:

* ``reap_evidence.schema.json`` - JSON Schema used for submission validation;
* ``models.py`` - pydantic models;
* ``templates/<Class>.csv`` - header-only tabular templates, one per class;
* ``reap_evidence.md`` - element documentation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from linkml.generators.jsonschemagen import JsonSchemaGenerator
from linkml.generators.pydanticgen import PydanticGenerator
from linkml_runtime.utils.schemaview import SchemaView

SCHEMA_DIR = Path(__file__).resolve().parent
SOURCE = SCHEMA_DIR / "reap_evidence.yaml"
GENERATED = SCHEMA_DIR / "generated"

TABULAR_CLASSES = (
    "Applicant", "Facility", "Project", "Meter", "BillingRecord", "IntervalSeries",
    "PerformanceClaim", "EquipmentItem",
)


def schema_view() -> SchemaView:
    return SchemaView(str(SOURCE))


def json_schema() -> dict[str, Any]:
    text = JsonSchemaGenerator(str(SOURCE), top_class="EvidencePackage").serialize()
    result: dict[str, Any] = json.loads(text)
    return result


def schema_elements() -> set[str]:
    """All ``Class`` and ``Class.slot`` names defined by the schema."""
    view = schema_view()
    names: set[str] = set()
    for cls in view.all_classes():
        names.add(str(cls))
        for slot in view.class_induced_slots(cls):
            names.add(f"{cls}.{slot.name}")
    return names


def _documentation(view: SchemaView) -> str:
    schema = view.schema
    lines = [f"# {schema.title}", "", str(schema.description).strip(), "",
             f"Schema version {schema.version}.", ""]
    for cls_name in view.all_classes():
        cls = view.get_class(cls_name)
        lines += [f"## {cls_name}", "", str(cls.description or "").strip(), "",
                  "| Element | Range | Required | Multivalued | Unit | Description |",
                  "|---|---|---|---|---|---|"]
        for slot in view.class_induced_slots(cls_name):
            unit = slot.unit.ucum_code if slot.unit is not None else ""
            desc = " ".join(str(slot.description or "").split())
            lines.append(
                f"| `{slot.name}` | {slot.range} | {'yes' if slot.required else 'no'} | "
                f"{'yes' if slot.multivalued else 'no'} | {unit or ''} | {desc} |"
            )
        lines.append("")
    lines += ["## Enumerations", ""]
    for enum_name in view.all_enums():
        enum = view.get_enum(enum_name)
        lines += [f"### {enum_name}", "", " ".join(str(enum.description or "").split()), ""]
        for value, pv in enum.permissible_values.items():
            desc = " ".join(str(pv.description or "").split())
            lines.append(f"- `{value}`" + (f": {desc}" if desc else ""))
        lines.append("")
    return "\n".join(lines)


def build() -> None:
    GENERATED.mkdir(exist_ok=True)
    (GENERATED / "__init__.py").write_text('"""Artefacts generated from reap_evidence.yaml."""\n')
    (GENERATED / "reap_evidence.schema.json").write_text(
        json.dumps(json_schema(), indent=2, sort_keys=True) + "\n"
    )
    (GENERATED / "models.py").write_text(PydanticGenerator(str(SOURCE)).serialize())
    view = schema_view()
    templates = GENERATED / "templates"
    templates.mkdir(exist_ok=True)
    for cls in TABULAR_CLASSES:
        slots = [s.name for s in view.class_induced_slots(cls)]
        (templates / f"{cls}.csv").write_text(",".join(slots) + "\n")
    (GENERATED / "reap_evidence.md").write_text(_documentation(view))


if __name__ == "__main__":
    build()
