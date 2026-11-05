"""Score a Markdown output folder against a baseline.

The baseline comes either from the DITA source (default, works for any document) or from a rendered
reference such as the sample PDF (see tools/build_pdf_baseline.py). Statuses: PASS, WARN, FAIL.
FAIL blocks delivery when FAIL_ON_QUALITY_FAIL is set; WARN ships with a review flag.
"""
from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[‐-―]", "-", s)
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"[*_`\\]", "", s)
    return re.sub(r"\s+", " ", s).strip().lower()


@dataclass
class Check:
    name: str
    status: str
    detail: str
    items: list[str] = field(default_factory=list)


@dataclass
class QualityReport:
    checks: list[Check]

    @property
    def tally(self) -> dict:
        return {k: sum(c.status == k for c in self.checks) for k in ("PASS", "WARN", "FAIL")}

    @property
    def failed(self) -> bool:
        return self.tally["FAIL"] > 0

    def to_markdown(self) -> str:
        t = self.tally
        order = {"FAIL": 0, "WARN": 1, "PASS": 2}
        lines = ["# Conversion quality report", "", f"**{t['PASS']} pass · {t['WARN']} warn · {t['FAIL']} fail**", "",
                 "| Status | Check | Detail |", "|---|---|---|"]
        for c in sorted(self.checks, key=lambda c: order[c.status]):
            lines.append(f"| {c.status} | {c.name} | {c.detail} |")
        for c in self.checks:
            if c.items and c.status != "PASS":
                lines += ["", f"### {c.name} (first {len(c.items)})"] + [f"- {i}" for i in c.items]
        return "\n".join(lines) + "\n"

    def to_dict(self) -> dict:
        return {"summary": self.tally, "checks": [c.__dict__ for c in self.checks]}


def _load(folder: str) -> dict[str, str]:
    files = {}
    for root, _, names in os.walk(folder):
        for n in names:
            if n.lower().endswith((".md", ".markdown")):
                p = os.path.join(root, n)
                raw = open(p, "rb").read()
                try:
                    files[p] = raw.decode("utf-8")
                except UnicodeDecodeError:
                    files[p] = raw.decode("utf-8", errors="replace") + "\n�"
    return files


_NOTE_WORDS = r"(note|important|attention|caution|warning|danger|tip|remember|restriction|fastpath|notice|trouble)"


def run_checks(folder: str, base: dict) -> QualityReport:
    res: list[Check] = []

    def add(name, status, detail, items=None):
        res.append(Check(name, status, detail, (items or [])[:25]))

    files = _load(folder)
    if not files:
        add("Output exists", "FAIL", "No Markdown files found in the output folder.")
        return QualityReport(res)
    add("Output exists", "PASS", f"{len(files)} Markdown files.")
    empty = [os.path.relpath(p, folder) for p, t in files.items() if len(t.strip()) < 20]
    add("No empty files", "PASS" if not empty else "FAIL", f"{len(empty)} empty or near-empty files.", empty)

    full = "\n".join(files.values())
    htext, prev_skips = [], 0
    for t in files.values():
        in_code, prev = False, 0
        for l in t.splitlines():
            if l.strip().startswith("```"):
                in_code = not in_code
            m = None if in_code else re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", l)
            if m:
                lvl = len(m.group(1))
                htext.append(norm(m.group(2)))
                if prev and lvl > prev + 1:
                    prev_skips += 1
                prev = lvl

    secs = base["sections"]
    missing = [(f'{s["number"]} ' if s.get("number") else "") + s["title"] for s in secs
               if not any(norm(s["title"]) == h or norm(s["title"]) in h or (h in norm(s["title"]) and len(h) > 12) for h in htext)]
    cov = 1 - len(missing) / max(1, len(secs))
    add("Section coverage", "PASS" if not missing else ("WARN" if cov >= 0.98 else "FAIL"),
        f"{len(secs) - len(missing)}/{len(secs)} source sections found as headings ({cov:.0%}).", missing)
    add("Heading levels", "PASS" if prev_skips == 0 else "WARN", f"{prev_skips} places where a heading skips a level.")

    exp = base["counts"]["tables"]
    pipe = len(re.findall(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", full, flags=re.M))
    html = len(re.findall(r"<table\b", full, flags=re.I))
    found = pipe + html
    add("Tables", "PASS" if found >= exp else ("WARN" if found >= 0.95 * exp else "FAIL"),
        f"{found} tables found ({pipe} pipe, {html} HTML); source has {exp}.")
    ntext = norm(full)
    miss_t = [f'{t["title"]}' for t in base["tables"] if norm(t["title"]) not in ntext]
    add("Table captions", "PASS" if not miss_t else ("WARN" if len(miss_t) <= 0.03 * max(1, len(base["tables"])) else "FAIL"),
        f'{len(base["tables"]) - len(miss_t)}/{len(base["tables"])} table titles present.', miss_t)

    imgs = []
    for p, t in files.items():
        for m in re.finditer(r"!\[([^\]]*)\]\(([^)\s]+)[^)]*\)", t):
            imgs.append((p, m.group(1), m.group(2)))
        for m in re.finditer(r"<img\b[^>]*>", t, flags=re.I):
            src = re.search(r'src="([^"]+)"', m.group(0))
            alt = re.search(r'alt="([^"]*)"', m.group(0))
            imgs.append((p, alt.group(1) if alt else "", src.group(1) if src else ""))
    fexp = base["counts"]["figures"]
    add("Figures (images present)", "PASS" if len(imgs) >= fexp else ("WARN" if len(imgs) >= 0.95 * fexp else "FAIL"),
        f"{len(imgs)} images referenced; source has {fexp}.")
    broken = [f"{os.path.relpath(p, folder)} -> {src}" for p, _, src in imgs
              if not re.match(r"^(https?:|data:)", src) and not os.path.exists(os.path.join(os.path.dirname(p), src.split("#")[0].replace("%20", " ")))]
    add("Image files exist", "PASS" if not broken else "FAIL", f"{len(broken)} image references point to missing files.", broken)
    noalt = [src for _, alt, src in imgs if not alt.strip()]
    add("Image alt text", "PASS" if not noalt else "WARN", f"{len(noalt)} images have no alt text.", noalt)
    miss_f = [f["title"] for f in base["figures"] if norm(f["title"]) not in ntext]
    add("Figure captions", "PASS" if not miss_f else ("WARN" if len(miss_f) <= 0.03 * max(1, len(base["figures"])) else "FAIL"),
        f'{len(base["figures"]) - len(miss_f)}/{len(base["figures"])} figure titles present.', miss_f)

    nexp = base["counts"]["notes"]
    notes = len(re.findall(rf"^\s*>?\s*\*{{0,2}}{_NOTE_WORDS}\b:?\*{{0,2}}", full, flags=re.I | re.M)) \
        + len(re.findall(rf"^\s*(?:!!!|:::)\s*{_NOTE_WORDS}", full, flags=re.I | re.M))
    add("Notes preserved", "PASS" if notes >= nexp else ("WARN" if notes >= 0.9 * nexp else "FAIL"),
        f"{notes} note blocks detected; source has {nexp}.")
    rexp = base["counts"]["related_information_blocks"]
    rel = len(re.findall(r"related information", full, flags=re.I))
    add("Related information", "PASS" if rel >= rexp else "WARN", f"{rel} blocks; source has {rexp}.")

    leaks = [b for b in base.get("must_not_appear", []) if b and b in full]
    rh = base.get("running_header_line")
    if rh and re.search(r"^\s*" + re.escape(rh) + r"\s*$", full, flags=re.M):
        leaks.append(rh)
    foot = len(re.findall(r"^\s*\d+\s*\|\s*\d{4}\.\d{2}\.\d{2}\s*$", full, flags=re.M))
    dots = len(re.findall(r"\.{6,}\s*\d+\s*$", full, flags=re.M))
    add("No page furniture", "PASS" if not (leaks or foot or dots) else "FAIL",
        f"{len(leaks)} boilerplate strings, {foot} page footers, {dots} dotted-leader lines leaked.", leaks)

    pats = {
        "raw DITA tags": r"</?(xref|conref|keyref|conkeyref|ph|codeph|uicontrol|menucascade|shortdesc|steps?|stepresult|cmd|prolog|topicref|data|simpletable|strow|stentry)\b",
        "unresolved key or variable": r"\{\{[^}]+\}\}|\$\{[^}]+\}",
        "conref or keyref attributes": r"\b(conref|keyref|conkeyref)=",
        "broken markdown links": r"\]\(\s*\)|\]\(#\)",
    }
    for name, pat in pats.items():
        hits = re.findall(pat, full)
        add(f"No {name}", "PASS" if not hits else "FAIL", f"{len(hits)} occurrences.", [str(h) for h in hits])

    bad = []
    for p, t in files.items():
        for m in re.finditer(r"(?<!!)\[[^\]]*\]\(([^)\s#]+\.md)(#[^)]*)?\)", t):
            if not os.path.exists(os.path.join(os.path.dirname(p), m.group(1))):
                bad.append(f"{os.path.relpath(p, folder)} -> {m.group(1)}")
    add("Internal links resolve", "PASS" if not bad else "FAIL", f"{len(bad)} links point to missing files.", bad)

    moj = len(re.findall(r"�|Ã.|â€", full))
    add("Encoding", "PASS" if moj <= base.get("mojibake_in_reference", 0) else "FAIL", f"{moj} garbled characters.")
    lost = {c: n for c, n in base.get("symbols", {}).items() if full.count(c) < n * 0.8}
    add("Special characters kept", "PASS" if not lost else "WARN",
        "Trademark, math and punctuation symbols present." if not lost else f"Fewer than expected: {lost}")

    cid = base.get("meta", {}).get("publication_content_id")
    has_fm = any(t.lstrip().startswith("---") for t in files.values())
    ok = has_fm and (not cid or any(cid in t for t in files.values()))
    add("Document metadata", "PASS" if ok else "WARN",
        "Front matter present." if ok else "No front matter carrying the document ID.")
    return QualityReport(res)
