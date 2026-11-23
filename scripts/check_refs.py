"""Check every DOI in a BibTeX file against Crossref (or DataCite) metadata.

For each entry with a ``doi`` field the registered title, year and first author
family name are compared with the entry. Any mismatch, or a DOI that does not
resolve, makes the script exit with a non-zero status.

Usage: python scripts/check_refs.py paper/references.bib
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import unicodedata
from pathlib import Path

import requests

USER_AGENT = "reapschema-reference-checker/1.0"
ENTRY = re.compile(r"@(\w+)\s*\{\s*([^,]+),(.*?)\n\}", re.S)
FIELD = re.compile(r"(\w+)\s*=\s*(\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}|\"[^\"]*\"|\d+)", re.S)


def normalise(text: str) -> str:
    text = re.sub(r"\\[a-zA-Z]+\s*|[{}\\\"'`^~$]", "", text)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def parse_bib(text: str) -> list[dict[str, str]]:
    entries = []
    for kind, key, body in ENTRY.findall(text):
        fields = {"_type": kind.lower(), "_key": key.strip()}
        for name, value in FIELD.findall(body):
            fields[name.lower()] = value.strip().strip("{}\"").strip()
        entries.append(fields)
    return entries


def lookup(doi: str) -> dict[str, str] | None:
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(f"https://api.crossref.org/works/{doi}", headers=headers, timeout=60)
    if resp.status_code == 200:
        msg = resp.json()["message"]
        year = ""
        for field in ("published-print", "published", "issued", "published-online"):
            parts = msg.get(field, {}).get("date-parts", [[None]])
            if parts and parts[0] and parts[0][0]:
                year = str(parts[0][0])
                break
        authors = msg.get("author") or msg.get("editor") or []
        return {"title": (msg.get("title") or [""])[0], "year": year,
                "years": " ".join(str(msg.get(f, {}).get("date-parts", [[""]])[0][0])
                                  for f in ("published-print", "published-online", "issued",
                                            "published")),
                "family": authors[0].get("family", authors[0].get("name", "")) if authors
                else ""}
    resp = requests.get(f"https://api.datacite.org/dois/{doi}", headers=headers, timeout=60)
    if resp.status_code == 200:
        attr = resp.json()["data"]["attributes"]
        creators = attr.get("creators") or [{}]
        family = creators[0].get("familyName") or creators[0].get("name", "").split(",")[0]
        return {"title": (attr.get("titles") or [{"title": ""}])[0]["title"],
                "year": str(attr.get("publicationYear", "")),
                "years": str(attr.get("publicationYear", "")), "family": family}
    return None


def check(entry: dict[str, str]) -> list[str]:
    doi = entry["doi"]
    meta = lookup(doi)
    if meta is None:
        return [f"{entry['_key']}: DOI {doi} did not resolve"]
    problems = []
    ours, theirs = normalise(entry.get("title", "")), normalise(meta["title"])
    if not ours or not (ours in theirs or theirs in ours or ours[:40] == theirs[:40]):
        problems.append(f"{entry['_key']}: title mismatch: {entry.get('title')!r} vs "
                        f"{meta['title']!r}")
    if entry.get("year") and entry["year"] not in meta["years"].split():
        problems.append(f"{entry['_key']}: year {entry['year']} not among registered "
                        f"{meta['years']}")
    first = entry.get("author", entry.get("editor", "")).split(" and ")[0]
    family = first.split(",")[0] if "," in first else first.split()[-1] if first else ""
    if family and meta["family"] and normalise(family) not in normalise(meta["family"]) and (
            normalise(meta["family"]) not in normalise(first)):
        problems.append(f"{entry['_key']}: first author {family!r} vs {meta['family']!r}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bibfile", type=Path)
    args = parser.parse_args()
    entries = parse_bib(args.bibfile.read_text(encoding="utf-8"))
    with_doi = [e for e in entries if "doi" in e]
    problems: list[str] = []
    for entry in with_doi:
        problems += check(entry)
        time.sleep(0.2)
    for entry in entries:
        if "doi" not in entry and "url" not in entry:
            problems.append(f"{entry['_key']}: neither DOI nor URL")
    print(f"{len(entries)} entries, {len(with_doi)} with DOI, {len(problems)} problem(s)")
    for p in problems:
        print("  " + p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
