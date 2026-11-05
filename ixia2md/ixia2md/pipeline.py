"""The end-to-end run: sign in, resolve snapshot, download, prepare, convert, check, package."""
from __future__ import annotations

import json
import logging
import re
import shutil
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import dita_tools, quality
from .ccms import CcmsClient, CcmsError
from .config import FLAVORS, Config
from .convert import ConvertError, run_dita_ot
from .fetch import fetch_snapshot
from .resolve import NoSnapshotError, resolve_snapshot

log = logging.getLogger("ixia2md.pipeline")

STEPS = [
    ("connect", "Connect to CCMS"),
    ("resolve", "Find the snapshot"),
    ("fetch", "Download DITA"),
    ("convert", "Convert to Markdown"),
    ("check", "Check quality"),
    ("package", "Package output folder"),
]


@dataclass
class RunResult:
    ok: bool
    output_dir: Path | None = None
    error: str = ""
    failed_step: str = ""
    manifest: dict = field(default_factory=dict)
    quality: dict = field(default_factory=dict)


Progress = Callable[[str, str, str], None]   # (step_key, state: running|done|failed, detail)


def _safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")[:60] or "doc"


def new_run_dir(cfg: Config, doc_id: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    d = Path(cfg.output_root) / f"{stamp}_{_safe_name(Path(doc_id).stem or doc_id)}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _front_matter(meta: dict) -> str:
    def q(v):
        return json.dumps(v, ensure_ascii=False)
    return "---\n" + "\n".join(f"{k}: {q(v)}" for k, v in meta.items() if v not in ("", None)) + "\n---\n\n"


def run(cfg: Config, doc_id: str, origin_id: str = "", version: str = "", flavor: str = "",
        run_dir: Path | None = None, progress: Progress | None = None, client: CcmsClient | None = None) -> RunResult:
    progress = progress or (lambda *a: None)
    flavor = flavor or cfg.default_flavor
    if flavor not in FLAVORS:
        return RunResult(False, error=f"Unknown Markdown flavor '{flavor}'.", failed_step="connect")
    doc_id = (doc_id or "").strip()
    if not doc_id:
        return RunResult(False, error="Document ID is required.", failed_step="connect")

    run_dir = run_dir or new_run_dir(cfg, doc_id)
    work = run_dir / "work"
    out = run_dir / "output"
    step = "connect"
    t0 = time.time()
    own_client = client is None
    try:
        progress("connect", "running", "")
        client = client or CcmsClient(cfg)
        client.login()
        progress("connect", "done", "Signed in.")

        step = "resolve"
        progress("resolve", "running", "")
        snap, notes = resolve_snapshot(client, doc_id, origin_id, version)
        which = f"version {version}" if version else "latest published snapshot"
        progress("resolve", "done", f"Using the {which}." + ("".join(" " + n for n in notes)))

        step = "fetch"
        progress("fetch", "running", "")
        fetched = fetch_snapshot(client, snap, doc_id, work, lambda m: progress("fetch", "running", m))
        c = fetched.counts
        progress("fetch", "done", f"{c['topics']} topics, {c['images']} images, {c['maps']} maps.")
        if own_client:
            client.logout()

        step = "convert"
        progress("convert", "running", "")
        baseline = dita_tools.build_baseline(fetched.root, doc_id=doc_id, version=version or snap.version)
        if cfg.qa_baseline and Path(cfg.qa_baseline).is_file():
            baseline = json.loads(Path(cfg.qa_baseline).read_text(encoding="utf-8"))   # reference baseline overrides the source-derived one
        prep = dita_tools.prepare_dita(fetched.root)
        out.mkdir(parents=True, exist_ok=True)
        run_dita_ot(cfg, fetched.root_map, out, flavor, out / "conversion.log")
        progress("convert", "done", f"Converted with {FLAVORS[flavor]}; {prep['tables']} table and {prep['figures']} figure captions kept.")

        meta = {
            "document_id": doc_id, "origin_id": origin_id, "version": version or snap.version,
            "snapshot": snap.path, "snapshot_status": snap.status, "snapshot_created": snap.created,
            "flavor": flavor, "converted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": "IXIA CCMS",
        }
        index = out / "index.md"
        if index.exists():
            index.write_text(_front_matter(meta) + index.read_text(encoding="utf-8"), encoding="utf-8")

        step = "check"
        progress("check", "running", "")
        report = quality.run_checks(str(out), baseline)
        (out / "quality-report.md").write_text(report.to_markdown(), encoding="utf-8")
        t = report.tally
        progress("check", "done", f"{t['PASS']} pass, {t['WARN']} warn, {t['FAIL']} fail.")
        if report.failed and cfg.fail_on_quality_fail:
            raise ConvertError("The quality checks failed. See quality-report.md.")

        step = "package"
        progress("package", "running", "")
        manifest = {**meta, "files_downloaded": len(fetched.files), "counts": fetched.counts,
                    "quality": report.tally, "seconds": round(time.time() - t0, 1)}
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        if cfg.keep_dita_source:
            shutil.copytree(fetched.root, out / "dita-source", dirs_exist_ok=True)
        zip_path = run_dir / "output.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(out.rglob("*")):
                if p.is_file():
                    z.write(p, p.relative_to(out).as_posix())
        shutil.rmtree(work, ignore_errors=True)   # the downloaded DITA is not kept unless asked
        progress("package", "done", f"{sum(1 for _ in out.rglob('*') if _.is_file())} files.")
        return RunResult(True, output_dir=out, manifest=manifest, quality=report.to_dict())

    except (CcmsError, NoSnapshotError, ConvertError, RuntimeError) as e:
        progress(step, "failed", str(e))
        return RunResult(False, error=str(e), failed_step=step, output_dir=out if out.exists() else None)
    except Exception as e:                      # unexpected: keep the detail in the log, not in the UI
        log.exception("Unexpected failure in step %s", step)
        progress(step, "failed", f"Unexpected error ({type(e).__name__}). See the server log.")
        return RunResult(False, error=f"Unexpected error ({type(e).__name__}).", failed_step=step)
    finally:
        if own_client and client is not None:
            try:
                client.logout()
            except Exception:
                pass
