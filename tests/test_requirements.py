"""Traceability from the rule text to the schema, and transcription checks."""

from __future__ import annotations

from reapschema import requirements
from reapschema.burden import load_transcribed
from reapschema.schema.build import schema_elements


def test_every_requirement_is_mapped():
    table = requirements.traceability_table()
    assert len(table) > 200
    assert (table["scope"] != "unmapped").all()
    assert set(table["scope"]) == {"evidence", "out_of_scope"}


def test_evidence_requirements_map_to_existing_schema_elements():
    table = requirements.traceability_table()
    elements = schema_elements()
    evidence = table[table["scope"] == "evidence"]
    assert (evidence["schema_elements"] != "").all()
    for cell in evidence["schema_elements"]:
        for name in cell.split("; "):
            assert name in elements, name


def test_mapping_keys_refer_to_parsed_paragraphs():
    ids = set(requirements.requirements_table()["requirement_id"])
    for mapping in requirements.load_traceability():
        assert mapping["requirement"] in ids, mapping["requirement"]


def test_key_paragraphs_are_parsed():
    table = requirements.requirements_table().set_index("requirement_id")
    assert "12 consecutive months pre-installation" in table.loc["4280.131(b)(17)(i)", "text"]
    assert table.loc["4280.131(b)(13)", "heading"] == "Size of RES"
    assert table.loc["4280.160(c)", "heading"] == "Equipment report"
    assert "common point of electrical coupling" in table.loc[
        "4280.104:Annual energy production", "text"]
    assert "4280.122(a)(8)(i)(F)(3)" in table.index


def test_pra_notice_matches_double_entry():
    parsed = requirements.parse_pra_notice()
    entry = load_transcribed("pra_notice_91FR62610.yaml")["entry_a"]
    for key, value in entry.items():
        assert parsed[key] == value, key
    assert parsed["describes_as_extension"]
    assert parsed["comment_document_title"].startswith("Notice of Extension")


def test_scoring_tables_match_double_entry():
    parsed = requirements.parse_scoring_tables()
    entry = load_transcribed("scoring_4280_140.yaml")["entry_a"]
    assert set(parsed) == set(entry)
    for key, rows in entry.items():
        assert [(label, float(points)) for label, points in rows] == parsed[key]


def test_double_entries_agree():
    for name in ("pra_notice_91FR62610.yaml", "omb_inventory_0570-0067.yaml",
                 "scoring_4280_140.yaml"):
        loaded = load_transcribed(name)
        assert loaded["entry_a"] == loaded["entry_b"]
