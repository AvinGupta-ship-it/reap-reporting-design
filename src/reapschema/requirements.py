"""Extraction of data requirements from the Federal Register XML of the rule.

The parser reads the regulatory text of 7 CFR part 4280 subpart B as published in
FR Doc. 2026-20178 and produces (i) a table of paragraph-level requirements with
hierarchical CFR designators, (ii) the figures of the Paperwork Reduction Act
notice in the preamble and (iii) the scoring tables of section 4280.140. A
separate mapping file links each requirement to elements of the evidence schema.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from reapschema.provenance import REPO_ROOT

RULE_XML = REPO_ROOT / "data" / "raw" / "federal_register" / "2026-20178.xml"
TRACEABILITY = Path(__file__).resolve().parent / "schema" / "traceability.yaml"

REQUIREMENT_SECTIONS = ("4280.122", "4280.131", "4280.160")
DEFINITION_TERMS = (
    "Annual energy production",
    "Energy assessment",
    "Energy audit (EA)",
    "Kilowatt-hour (kWh)",
    "Megawatt-hour (MWh)",
    "Metering agreement",
    "Rated system size",
    "Renewable energy system (RES)",
    "Simple payback",
    "Useful life",
)

_ROMAN = re.compile(r"^(x{0,3})(ix|iv|v?i{0,3})$")
_LEVELS = ("lower", "digit", "roman", "upper", "idigit", "iroman")


@dataclass(frozen=True)
class Paragraph:
    section: str
    designator: str
    heading: str
    text: str
    page: int

    @property
    def requirement_id(self) -> str:
        return f"{self.section}{self.designator}"


def _is_roman(token: str) -> bool:
    return bool(token) and bool(_ROMAN.match(token))


def _roman_value(token: str) -> int:
    values = {"i": 1, "v": 5, "x": 10}
    total = 0
    prev = 0
    for ch in reversed(token):
        v = values[ch]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total


def _ordinal(level: str, token: str) -> int:
    if level in ("digit", "idigit"):
        return int(token)
    if level in ("roman", "iroman"):
        return _roman_value(token)
    return ord(token.lower()) - ord("a") + 1


def _candidate_levels(token: str, italic: bool) -> list[str]:
    if italic:
        out = []
        if token.isdigit():
            out.append("idigit")
        if _is_roman(token):
            out.append("iroman")
        return out
    if token.isdigit():
        return ["digit"]
    if token.isalpha() and token.isupper() and len(token) == 1:
        return ["upper"]
    out = []
    if _is_roman(token):
        out.append("roman")
    if token.isalpha() and token.islower() and len(token) == 1:
        out.append("lower")
    return out


def _resolve_level(token: str, italic: bool, stack: dict[str, str]) -> str | None:
    """Choose the paragraph level of a designator given the current position."""
    candidates = _candidate_levels(token, italic)
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    # "(i)", "(v)" or "(x)" may be a level-1 letter or a level-3 roman numeral:
    # it is a letter only when it continues the letter sequence at level 1 and
    # no digit-level paragraph is open that could contain a roman list.
    depth = max((_LEVELS.index(k) for k in stack), default=-1)
    if "lower" in candidates and "roman" in candidates:
        current = stack.get("lower")
        continues_letters = current is not None and _ordinal("lower", token) == _ordinal(
            "lower", current
        ) + 1
        continues_roman = "roman" in stack and _roman_value(token) == _roman_value(
            stack["roman"]
        ) + 1
        starts_roman = _roman_value(token) == 1 and depth >= _LEVELS.index("digit")
        if continues_roman or starts_roman:
            return "roman"
        if continues_letters:
            return "lower"
        return "roman" if depth >= _LEVELS.index("digit") else "lower"
    return candidates[0]


def _flatten(elem: ET.Element) -> str:
    text = "".join(elem.itertext())
    return re.sub(r"\s+", " ", text).strip()


_DESIGNATOR = re.compile(r"^\(\s*([A-Za-z0-9]+)\s*\)\s*")


def _leading_designators(p: ET.Element) -> tuple[list[tuple[str, bool]], str, str]:
    """Split a paragraph into its leading designators, heading and body text."""
    flat = _flatten(p)
    # italic designators appear as "(<E T="03">1</E>)" at the start of the element
    italic_tokens: set[int] = set()
    raw = ET.tostring(p, encoding="unicode")
    raw = re.sub(r"<PRTPAGE[^>]*/>", "", raw)
    body = re.sub(r"^<P[^>]*>\s*", "", raw)
    # a designator typeset inside the italic heading: <E>(3) Heading.</E>
    body = re.sub(r'^<E T="03">\s*\(\s*([A-Za-z0-9]+)\s*\)\s*', r'(<E T="03">\1</E>) <E T="03">',
                  body)
    pos = 0
    index = 0
    while True:
        m = re.match(r"\(\s*<E T=\"03\">\s*([A-Za-z0-9]+)\s*</E>\s*\)\s*", body[pos:])
        m2 = re.match(r"\(\s*([A-Za-z0-9]+)\s*\)\s*", body[pos:])
        if m:
            italic_tokens.add(index)
            pos += m.end()
        elif m2:
            pos += m2.end()
        else:
            break
        index += 1
    designators: list[tuple[str, bool]] = []
    rest = flat
    i = 0
    while i < index:
        m3 = _DESIGNATOR.match(rest)
        if not m3:
            break
        designators.append((m3.group(1), i in italic_tokens))
        rest = rest[m3.end():]
        i += 1
    heading = ""
    remainder = body[pos:]
    hm = re.match(r"\s*<E T=\"03\">([^<]+)</E>", remainder)
    if hm and designators:
        heading = re.sub(r"\s+", " ", hm.group(1)).strip().rstrip(".")
    return designators, heading, rest


def _iter_regtext_sections(root: ET.Element) -> list[tuple[str, str, ET.Element]]:
    out: list[tuple[str, str, ET.Element]] = []
    for regtext in root.iter("REGTEXT"):
        for section in regtext.iter("SECTION"):
            sectno = section.findtext("SECTNO") or ""
            m = re.search(r"(\d{4}\.\d+)", sectno)
            if not m:
                continue
            subject = re.sub(r"\s+", " ", section.findtext("SUBJECT") or "").strip()
            out.append((m.group(1), subject, section))
    return out


def _page_index(xml_text: str) -> list[tuple[int, int]]:
    return [(m.start(), int(m.group(1))) for m in re.finditer(r'<PRTPAGE P="(\d+)"/>', xml_text)]


def parse_paragraphs(xml_path: Path = RULE_XML,
                     sections: tuple[str, ...] = REQUIREMENT_SECTIONS) -> list[Paragraph]:
    """Return designated paragraphs of the requested sections of subpart B."""
    xml_text = xml_path.read_text(encoding="utf-8")
    root = ET.fromstring(xml_text)
    pages = _page_index(xml_text)
    first_page = 62600
    out: list[Paragraph] = []
    seen_sections: set[str] = set()
    for sectno, _subject, section in _iter_regtext_sections(root):
        if sectno not in sections or sectno in seen_sections:
            continue
        seen_sections.add(sectno)
        stack: dict[str, str] = {}
        sect_pos = xml_text.find(f"<SECTNO>§ {sectno}", xml_text.find("<REGTEXT"))
        page = max((pg for pos, pg in pages if pos <= sect_pos), default=first_page)
        for child in section:
            if child.tag != "P":
                continue
            for pr in child.iter("PRTPAGE"):
                page = int(pr.attrib["P"])
            designators, heading, body = _leading_designators(child)
            if not designators:
                continue
            for token, italic in designators:
                level = _resolve_level(token, italic, stack)
                if level is None:
                    continue
                stack[level] = token
                for deeper in _LEVELS[_LEVELS.index(level) + 1:]:
                    stack.pop(deeper, None)
            designator = "".join(f"({stack[lv]})" for lv in _LEVELS if lv in stack)
            out.append(Paragraph(sectno, designator, heading, body, page))
    return out


def parse_definitions(xml_path: Path = RULE_XML,
                      terms: tuple[str, ...] = DEFINITION_TERMS) -> list[Paragraph]:
    """Return the selected definitions of section 4280.104 (subpart B)."""
    xml_text = xml_path.read_text(encoding="utf-8")
    root = ET.fromstring(xml_text)
    out: list[Paragraph] = []
    for sectno, _subject, section in _iter_regtext_sections(root):
        if sectno != "4280.104":
            continue
        current: str | None = None
        buffer: list[str] = []
        for child in section:
            if child.tag != "P":
                continue
            flat = _flatten(child)
            first = child.find("E")
            starts_term = (
                first is not None
                and first.attrib.get("T") == "03"
                and flat.startswith(_flatten(first))
                and not flat.startswith("(")
            )
            if starts_term and first is not None:
                if current in terms:
                    out.append(Paragraph("4280.104", f":{current}", current or "",
                                         " ".join(buffer), 0))
                current = _flatten(first).rstrip(".")
                buffer = [flat]
            else:
                buffer.append(flat)
        if current in terms:
            out.append(Paragraph("4280.104", f":{current}", current or "", " ".join(buffer), 0))
        break
    return out


def requirements_table(xml_path: Path = RULE_XML) -> pd.DataFrame:
    """Paragraph-level requirement table for the evidence-relevant sections."""
    paragraphs = parse_definitions(xml_path) + parse_paragraphs(xml_path)
    return pd.DataFrame(
        {
            "requirement_id": [p.requirement_id for p in paragraphs],
            "section": [p.section for p in paragraphs],
            "heading": [p.heading for p in paragraphs],
            "text": [p.text for p in paragraphs],
        }
    )


def load_traceability(path: Path = TRACEABILITY) -> list[dict[str, Any]]:
    loaded = yaml.safe_load(path.read_text())
    return list(loaded["mappings"])


def _best_mapping(requirement_id: str, mappings: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Longest-prefix match: a mapping covers a paragraph and its sub-paragraphs."""
    best: dict[str, Any] | None = None
    for m in mappings:
        key = str(m["requirement"])
        if requirement_id == key or (
            requirement_id.startswith(key) and requirement_id[len(key):].startswith("(")
        ):
            if best is None or len(key) > len(str(best["requirement"])):
                best = m
    return best


def traceability_table(xml_path: Path = RULE_XML, mapping_path: Path = TRACEABILITY
                       ) -> pd.DataFrame:
    """Requirement-to-schema traceability table (one row per regulatory paragraph)."""
    reqs = requirements_table(xml_path)
    mappings = load_traceability(mapping_path)
    rows = []
    for rec in reqs.itertuples(index=False):
        m = _best_mapping(str(rec.requirement_id), mappings)
        rows.append(
            {
                "requirement_id": rec.requirement_id,
                "heading": rec.heading,
                "scope": m["scope"] if m else "unmapped",
                "schema_elements": "; ".join(m.get("elements", [])) if m else "",
                "mapped_by": m["requirement"] if m else "",
                "note": m.get("note", "") if m else "",
            }
        )
    return pd.DataFrame(rows)


def parse_pra_notice(xml_path: Path = RULE_XML) -> dict[str, Any]:
    """Figures of the Paperwork Reduction Act notice in the preamble."""
    xml_text = xml_path.read_text(encoding="utf-8")
    start = xml_text.find("<HD SOURCE=\"HD1\">Paperwork Reduction Act")
    if start < 0:
        start = xml_text.find("Paperwork Reduction Act</HD>")
    end = xml_text.find("Regulatory Flexibility Act", start)
    flat = re.sub(r"<[^>]+>", " ", xml_text[start:end])
    flat = re.sub(r"\s+", " ", flat)

    def number(pattern: str) -> float:
        m = re.search(pattern, flat)
        if not m:
            raise ValueError(f"PRA notice field not found: {pattern}")
        return float(m.group(1).replace(",", ""))

    def text(pattern: str) -> str:
        m = re.search(pattern, flat)
        if not m:
            raise ValueError(f"PRA notice field not found: {pattern}")
        return m.group(1).strip()

    return {
        "omb_control_number": text(r"OMB Control Number:\s*([0-9-]+)"),
        "type_of_request": text(r"Type of Request:\s*(.+?)\s*Abstract:").rstrip("."),
        "hours_per_response": number(r"average\s+([0-9.]+)\s+hours per response"),
        "respondent_description": text(r"Respondents:\s*(.+?)\s*Estimated Number of Respondents")
        .rstrip("."),
        "respondents": number(r"Estimated Number of Respondents:\s*([0-9,]+)"),
        "responses_per_respondent": number(
            r"Estimated Number of Responses per Respondent:\s*([0-9.,]+?)\.?\s+Estimated"
        ),
        "responses": number(r"Estimated Number of Responses:\s*([0-9,]+)"),
        "total_hours": number(r"Estimated Total Annual Burden on Respondents:\s*([0-9,]+)"),
        "comment_deadline": text(r"must be received by\s+(.+?)\s+to be assured"),
        "describes_as_extension": "submitting to OMB for extension" in flat,
        "comment_document_title": text(r"locate the document title:\s*[“\"](.+?)[”\"]"),
    }


def parse_scoring_tables(xml_path: Path = RULE_XML) -> dict[str, list[tuple[str, float]]]:
    """Point tables of section 4280.140(d) keyed by their paragraph reference."""
    xml_text = xml_path.read_text(encoding="utf-8")
    root = ET.fromstring(xml_text)
    out: dict[str, list[tuple[str, float]]] = {}
    for sectno, _subject, section in _iter_regtext_sections(root):
        if sectno != "4280.140":
            continue
        for table in section.iter("GPOTABLE"):
            ttitle = table.find("TTITLE")
            title = _flatten(ttitle) if ttitle is not None else ""
            m = re.search(r"Paragraph\s*(.*)$", title)
            key = re.sub(r"\s+", "", m.group(1)) if m else title
            rows: list[tuple[str, float]] = []
            for row in table.iter("ROW"):
                cells = [_flatten(e) for e in row.iter("ENT")]
                if len(cells) == 2:
                    rows.append((cells[0], float(cells[1])))
            out[key] = rows
        break
    return out
