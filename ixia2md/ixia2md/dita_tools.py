"""DITA-side helpers: build a quality baseline from the source, and prepare the source for conversion.

Why prepare: DITA-OT's Markdown output drops the <title> of a <table>, so table captions would be
lost. `prepare_dita` moves each table title (and each figure title) into a visible caption paragraph
before conversion. The baseline is computed first, from the untouched source.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from lxml import etree

log = logging.getLogger("ixia2md.dita")

SYMBOLS = "™®©×–—≥≤±µΩ"


def _parser() -> etree.XMLParser:
    # No DTD loading and no network: DITA files name public DTDs we neither have nor want to fetch.
    return etree.XMLParser(load_dtd=False, no_network=True, resolve_entities=False, recover=True, huge_tree=True)


def dita_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".dita", ".xml"})


def map_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".ditamap", ".bookmap"})


def _text(el) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def build_baseline(dita_root: Path, doc_id: str = "", version: str = "", title_hint: str = "") -> dict:
    """Expected content of the Markdown, computed from the DITA source."""
    sections, tables, figures = [], [], []
    notes = related = image_count = table_count = 0
    sym = {c: 0 for c in SYMBOLS}
    seen_titles = set()

    def add_section(t: str):
        t = t.strip()
        if t and t.lower() not in seen_titles:
            seen_titles.add(t.lower())
            sections.append({"number": "", "title": t, "page": 0, "depth": 1})

    for m in map_files(dita_root):
        try:
            tree = etree.parse(str(m), _parser())
        except Exception:
            continue
        r = tree.getroot()
        if r is not None:
            t = r.find("title")
            if t is None:
                t = r.find(".//booktitle/mainbooktitle")
            if t is not None:
                add_section(_text(t))

    for f in dita_files(dita_root):
        try:
            tree = etree.parse(str(f), _parser())
        except Exception as e:
            log.warning("Could not parse %s: %s", f.name, e)
            continue
        root = tree.getroot()
        if root is None:
            continue
        for t in root.xpath("self::*/title | .//section/title | .//example/title | .//topic/title | .//concept/title | .//task/title | .//reference/title"):
            add_section(_text(t))
        for t in root.xpath(".//table | .//simpletable"):
            table_count += 1
            title = t.find("title")
            if title is not None and _text(title):
                tables.append({"number": len(tables) + 1, "title": _text(title)})
        for fig in root.xpath(".//fig"):
            title = fig.find("title")
            if title is not None and _text(title):
                figures.append({"number": len(figures) + 1, "title": _text(title)})
        image_count += len(root.xpath(".//image"))
        notes += len(root.xpath(".//note"))
        related += len(root.xpath(".//related-links"))
        body = "".join(root.itertext())
        for c in SYMBOLS:
            sym[c] += body.count(c)

    return {
        "source": "dita",
        "meta": {"publication_content_id": doc_id, "online_version": version, "date": "", "title": title_hint,
                 "has_taxonomy_section": False, "has_description_section": False, "has_keywords_section": False},
        "sections": sections,
        "tables": tables,
        "figures": figures,
        "counts": {"sections": len(sections), "tables": table_count, "figures": image_count,
                   "notes": notes, "related_information_blocks": related},
        "symbols": {c: n for c, n in sym.items() if n},
        "must_not_appear": [],
        "mojibake_in_reference": 0,
    }


def _caption(tag: str, text: str, parent_doc) -> etree._Element:
    p = etree.Element("p")
    b = etree.SubElement(p, tag)
    b.text = text
    return p


def prepare_dita(dita_root: Path) -> dict:
    """Make table and figure titles survive conversion. Returns counts of what was changed."""
    changed = {"tables": 0, "figures": 0, "files": 0}
    for f in dita_files(dita_root):
        try:
            tree = etree.parse(str(f), _parser())
        except Exception:
            continue
        root = tree.getroot()
        if root is None:
            continue
        touched = False
        for table in root.xpath(".//table"):
            title = table.find("title")
            if title is None or not _text(title):
                continue
            parent = table.getparent()
            cap = _caption("b", _text(title), tree)
            parent.insert(parent.index(table), cap)
            table.remove(title)
            changed["tables"] += 1
            touched = True
        for fig in root.xpath(".//fig"):
            title = fig.find("title")
            if title is None or not _text(title):
                continue
            parent = fig.getparent()
            cap = _caption("i", _text(title), tree)
            parent.insert(parent.index(fig) + 1, cap)
            changed["figures"] += 1
            touched = True
        if touched:
            doctype = tree.docinfo.doctype or None
            f.write_bytes(etree.tostring(tree, xml_declaration=True, encoding="UTF-8", doctype=doctype))
            changed["files"] += 1
    return changed
