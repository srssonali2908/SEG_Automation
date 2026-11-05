#!/usr/bin/env python3
"""Build a conversion-quality baseline (baseline.json) from a rendered reference document (PDF text export).

Usage: build_baseline.py <reference.txt> <baseline.json>
The baseline records what a correct Markdown conversion must contain: section titles,
table/figure captions, note and "Related Information" counts, special characters,
and boilerplate that must NOT leak into the output.
"""
import json, re, sys, unicodedata

def norm(s):
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[‐-―]", "-", s)
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip().lower()

def main(src, dst):
    lines = open(src, encoding="utf-8", errors="replace").read().splitlines()

    # --- Table of contents -------------------------------------------------
    start = next(i for i, l in enumerate(lines) if l.strip() == "Contents")
    NUM = r"(?:\d+|[A-Z])(?:\.\d+)*"
    toc_re = re.compile(rf"^({NUM})\.?\s+(.+?)\s*\.{{3,}}\s*(\d+)\s*$")
    start_re = re.compile(rf"^({NUM})\.?\s+(\S.*)$")
    toc, pending, body_start = [], None, None
    for i in range(start + 1, len(lines)):
        l = lines[i].strip()
        m = toc_re.match(l)
        if m:
            toc.append({"number": m.group(1), "title": m.group(2).strip(), "page": int(m.group(3))})
            pending = None
            continue
        if pending and re.search(r"\.{3,}\s*\d+\s*$", l):  # wrapped entry tail
            title = pending[1] + " " + re.sub(r"\s*\.{3,}\s*\d+\s*$", "", l)
            page = int(re.search(r"(\d+)\s*$", l).group(1))
            toc.append({"number": pending[0], "title": title.strip(), "page": page})
            pending = None
            continue
        sm = start_re.match(l)
        if sm and "...." not in l and toc:
            pending = (sm.group(1), sm.group(2).strip())
            continue
        if toc and l and not toc_re.match(l) and not pending and not re.match(
                r"^(Contents|GTS Transceiver PHY User Guide.*|\d+|Draft Copy.*)$", l):
            body_start = i
            break
    for t in toc:
        t["depth"] = t["number"].count(".") + 1

    body = lines[body_start:] if body_start else lines

    # --- Captions ----------------------------------------------------------
    def captions(kind):
        out, seen = [], set()
        for l in body:
            m = re.match(rf"^{kind} (\d+)\. (.+)$", l.strip())
            if m and m.group(1) not in seen:
                seen.add(m.group(1))
                out.append({"number": int(m.group(1)), "title": m.group(2).strip()})
        return out
    tables, figures = captions("Table"), captions("Figure")

    text = "\n".join(body)
    notes = len(re.findall(r"^Note:", text, flags=re.M))
    related = len(re.findall(r"^Related Information\s*$", text, flags=re.M))
    steps = len(re.findall(r"^\d+\. [A-Z]", text, flags=re.M))

    # Boilerplate that must never leak into Markdown output
    boiler = [
        "Draft Copy—Do Not Distribute",
        "© Altera Corporation. Altera, the Altera logo",
        "*Other names and brands may be claimed as the property of others.",
        "GTS Transceiver PHY User Guide: Agilex 3 FPGAs and SoCs",
    ]
    boiler_counts = {b: text.count(b) for b in boiler}

    symbols = {c: text.count(c) for c in "™®©×–—≥≤±µΩ" if text.count(c)}
    mojibake = len(re.findall(r"�|Ã.|â€", text))

    header = "\n".join(lines[:60])
    meta = {
        "publication_content_id": (re.search(r"Publication Content ID:\s*(\S+)", header) or [None, None])[1],
        "online_version": (re.search(r"Online Version\s*(\S+)", header) or [None, None])[1],
        "date": (re.search(r"^(\d{4}\.\d{2}\.\d{2})$", header, flags=re.M) or [None, None])[1],
        "title": lines[2].strip(),
        "has_taxonomy_section": "Taxonomy Information" in header,
        "has_description_section": "Document Description Information" in "\n".join(lines[:120]),
        "has_keywords_section": "Keywords Information" in "\n".join(lines[:120]),
    }

    baseline = {
        "source": src,
        "meta": meta,
        "sections": toc,
        "tables": tables,
        "figures": figures,
        "counts": {"sections": len(toc), "tables": len(tables), "figures": len(figures),
                   "notes": notes, "related_information_blocks": related, "numbered_step_lines": steps},
        "symbols": symbols,
        "must_not_appear": [b for b in boiler],
        "reference_boilerplate_occurrences": boiler_counts,
        "mojibake_in_reference": mojibake,
    }
    json.dump(baseline, open(dst, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(json.dumps({"meta": meta, "counts": baseline["counts"], "symbols": symbols}, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
