"""Command line: python -m ixia2md.cli --doc-id <path> [--origin-id X] [--version N] [--flavor markdown_github]"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import FLAVORS, Config
from .pipeline import STEPS, run


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ixia2md", description="Convert a published IXIA CCMS snapshot from DITA to Markdown.")
    ap.add_argument("--doc-id", required=True, help="repository path of the map, e.g. /Content/Guide/guide.ditamap")
    ap.add_argument("--origin-id", default="", help="origin ID (filters snapshots when they carry one)")
    ap.add_argument("--version", default="", help="snapshot version; leave empty for the latest published snapshot")
    ap.add_argument("--flavor", default="", choices=["", *FLAVORS], help="Markdown flavor (default from MD_FLAVOR)")
    ap.add_argument("--out", default="", help="run folder to create (default under OUTPUT_ROOT)")
    a = ap.parse_args(argv)

    cfg = Config.from_env()
    labels = dict(STEPS)

    def progress(step, state, detail):
        mark = {"running": "..", "done": "ok", "failed": "!!"}[state]
        if state != "running" or not detail:
            print(f"[{mark}] {labels[step]}{': ' + detail if detail else ''}", flush=True)

    res = run(cfg, a.doc_id, a.origin_id, a.version, a.flavor, run_dir=Path(a.out) if a.out else None, progress=progress)
    if res.ok:
        print(f"\nOutput folder: {res.output_dir}")
        return 0
    print(f"\nFailed at '{labels.get(res.failed_step, res.failed_step)}': {res.error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
