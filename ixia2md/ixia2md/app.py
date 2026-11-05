"""The web app for seg.altera.com (standard library only).

Run:  python -m ixia2md.app --host 0.0.0.0 --port 8080
Put it behind your company SSO / reverse proxy. The app itself has no sign-in: it reads the user name
from the X-Forwarded-User or X-Auth-Request-Email header that the proxy sets, and logs it per run.
"""
from __future__ import annotations

import argparse
import html
import logging
import mimetypes
import secrets
import shutil
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from .config import FLAVORS, Config
from .pipeline import STEPS, run

log = logging.getLogger("ixia2md.app")
E = html.escape
RETENTION_HOURS = 24
MAX_PREVIEW = 60_000


# ---------------------------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------------------------
class Job:
    def __init__(self, job_id: str, user: str, doc_id: str, origin_id: str, version: str, flavor: str):
        self.id, self.user = job_id, user
        self.doc_id, self.origin_id, self.version, self.flavor = doc_id, origin_id, version, flavor
        self.steps = {k: ("pending", "") for k, _ in STEPS}
        self.state = "running"          # running | done | failed
        self.error = ""
        self.failed_step = ""
        self.output_dir: Path | None = None
        self.quality: dict = {}
        self.manifest: dict = {}
        self.created = time.time()


JOBS: dict[str, Job] = {}
LOCK = threading.Lock()
SLOTS = threading.BoundedSemaphore(2)       # at most two conversions at once


def start_job(cfg: Config, user: str, doc_id: str, origin_id: str, version: str, flavor: str) -> Job:
    job = Job(secrets.token_urlsafe(12), user, doc_id, origin_id, version, flavor)
    with LOCK:
        JOBS[job.id] = job

    def progress(step, state, detail):
        job.steps[step] = (state, detail)

    def work():
        with SLOTS:
            log.info("run start user=%s doc=%s origin=%s version=%s flavor=%s", user, doc_id, origin_id, version or "latest", flavor)
            res = run(cfg, doc_id, origin_id, version, flavor, run_dir=Path(cfg.output_root) / job.id, progress=progress)
            job.output_dir, job.quality, job.manifest = res.output_dir, res.quality, res.manifest
            job.error, job.failed_step = res.error, res.failed_step
            job.state = "done" if res.ok else "failed"
            log.info("run end user=%s doc=%s result=%s", user, doc_id, job.state)

    threading.Thread(target=work, daemon=True).start()
    return job


def sweep(cfg: Config) -> None:
    root = Path(cfg.output_root)
    if not root.exists():
        return
    cutoff = time.time() - RETENTION_HOURS * 3600
    for d in root.iterdir():
        try:
            if d.is_dir() and d.stat().st_mtime < cutoff:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass


# ---------------------------------------------------------------------------------------------
# Pages (Altera documentation theme: navy #001e50, cyan #00c7fd, blue #0054ae, text #282832)
# ---------------------------------------------------------------------------------------------
CSS = """
:root{--navy:#001e50;--cyan:#00c7fd;--blue:#0054ae;--text:#282832;--panel:#f3f3f9;--line:#e0e0e8;--ok:#1e6b3f;--warn:#7a4a00;--bad:#a4262c}
*{box-sizing:border-box}
body{margin:0;font-family:'Myriad Pro','Source Sans 3','Segoe UI',system-ui,sans-serif;background:var(--panel);color:var(--text);line-height:1.5}
a{color:var(--blue)}a:hover{color:var(--navy)}
header{background:var(--navy);color:#fff;border-bottom:3px solid var(--cyan);padding:0 32px;display:flex;flex-wrap:wrap;align-items:center;gap:24px;min-height:64px}
.brand{display:flex;align-items:center;gap:10px;font-weight:600;font-size:16px}
.logo{width:34px;height:32px;border-radius:6px;background:var(--cyan);color:var(--navy);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px}
header nav{display:flex;gap:8px;flex:1}
header nav a{color:#e6ecf5;text-decoration:none;padding:10px 14px;border-radius:8px;font-size:14px;font-weight:500}
header nav a.on{background:rgba(255,255,255,.16);color:#fff;font-weight:600}
.who{font-size:13px;color:#e6ecf5}
main{max-width:1180px;margin:0 auto;padding:40px 32px 56px}
h1{font-size:28px;line-height:1.2;margin:0 0 8px}
.lead{margin:0 0 24px;color:#4a4a58}
.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:28px}
label,.lab{display:block;font-size:13px;font-weight:600;margin-bottom:6px}
input[type=text],select{width:100%;height:44px;border:1px solid #a9a9b8;border-radius:8px;padding:0 14px;font:inherit;font-size:15px;color:var(--text);background:#fff}
input:focus,select:focus,button:focus-visible,a:focus-visible{outline:3px solid var(--blue);outline-offset:2px}
.hint{font-size:12px;color:#55556a;margin-top:4px}
.row{display:flex;flex-wrap:wrap;gap:20px;margin-bottom:22px}.row>div{flex:1 1 240px}
.modes{display:flex;flex-wrap:wrap;gap:12px}
.mode{flex:1 1 240px;border:1px solid #a9a9b8;border-radius:10px;padding:12px 16px;cursor:pointer;display:block;margin:0}
.mode input{margin-right:8px}.mode b{font-size:14px}.mode small{display:block;font-size:12px;color:#55556a;margin-left:24px}
.vernum{display:none}form:has(input[value=specific]:checked) .vernum{display:block}
.mode:has(input:checked){border:2px solid var(--blue);background:#eaf1ff;padding:11px 15px}
.btn{display:inline-flex;align-items:center;justify-content:center;min-height:48px;padding:0 28px;border-radius:10px;background:var(--navy);color:#fff;font:inherit;font-size:15px;font-weight:600;border:0;text-decoration:none;cursor:pointer}
.btn:hover{background:var(--blue);color:#fff}
.btn.sec{background:#fff;color:var(--text);border:1px solid #a9a9b8}.btn.sec:hover{background:var(--panel);color:var(--text)}
.err{background:#fdf0f0;border:1px solid #e8b4b8;color:var(--bad);border-radius:10px;padding:12px 16px;margin-bottom:20px}
ol.steps{list-style:none;margin:0;padding:0}
ol.steps li{display:flex;gap:14px;padding:14px 0;border-bottom:1px solid #ececf2}ol.steps li:last-child{border:0}
.dot{flex:none;width:26px;height:26px;border-radius:50%;border:2px solid #a9a9b8;display:flex;align-items:center;justify-content:center;color:#fff;font-size:14px;font-weight:700}
.dot.done{background:var(--ok);border-color:var(--ok)}.dot.failed{background:var(--bad);border-color:var(--bad)}
.dot.running{border:3px solid var(--blue);border-right-color:#bfd3fa;animation:spin 1s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}@media (prefers-reduced-motion:reduce){.dot.running{animation:none}}
.sub{font-size:13px;color:#55556a}
.grid{display:flex;flex-wrap:wrap;gap:24px;align-items:flex-start}
.tree{flex:1 1 300px;min-width:0}.view{flex:999 1 520px;min-width:0;padding:0;overflow:hidden}
.tree ul{list-style:none;margin:0;padding:0;font-family:Consolas,'JetBrains Mono',monospace;font-size:13px}
.tree li a{display:block;padding:7px 10px;border-radius:6px;text-decoration:none;color:var(--text);word-break:break-all}
.tree li a.sel{background:#eaf1ff;color:var(--blue);font-weight:600}.tree li a:hover{background:var(--panel)}
.vh{padding:14px 20px;border-bottom:1px solid #ececf2;font-family:Consolas,monospace;font-size:13px;font-weight:600}
pre{margin:0;padding:20px;white-space:pre-wrap;word-break:break-word;font-family:Consolas,'JetBrains Mono',monospace;font-size:13px;line-height:1.7;min-height:260px}
.pill{display:inline-block;padding:4px 12px;border-radius:999px;font-size:13px;font-weight:600;margin-bottom:12px}
.pill.ok{background:#e3f4ea;color:var(--ok)}.pill.warn{background:#fff3d6;color:var(--warn)}.pill.bad{background:#fdecec;color:var(--bad)}
.banner{background:#fff7e6;border:1px solid #f2d49b;color:#5a3a00;border-radius:12px;padding:14px 20px;margin-top:24px}
.actions{display:flex;flex-wrap:wrap;gap:12px;margin:16px 0 24px}
"""


def page(title: str, body: str, user: str = "", nav: str = "convert", refresh: bool = False) -> bytes:
    meta = '<meta http-equiv="refresh" content="2">' if refresh else ""
    who = f'<div class="who">{E(user)}</div>' if user else ""
    on = lambda k: ' class="on"' if nav == k else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">{meta}
<title>{E(title)}</title><style>{CSS}</style></head><body>
<header><div class="brand"><div class="logo">SEG</div>Content Export</div>
<nav><a href="/"{on('convert')}>Convert</a></nav>{who}</header>
<main>{body}</main></body></html>""".encode("utf-8")


def form_page(user: str, error: str = "", values: dict | None = None) -> bytes:
    v = values or {}
    err = f'<div class="err" role="alert">{E(error)}</div>' if error else ""
    latest = v.get("mode", "latest") == "latest"
    flavors = "".join(f'<option value="{k}"{" selected" if k == v.get("flavor", "markdown_github") else ""}>{E(n)}</option>' for k, n in FLAVORS.items())
    body = f"""<h1>Convert published content to Markdown</h1>
<p class="lead">Pick a document and we pull its published snapshot from IXIA CCMS, convert the DITA to Markdown, and give you an output folder.</p>
<form class="card" method="post" action="/convert">{err}
<div class="row"><div><label for="doc">Document ID</label>
<input id="doc" name="doc_id" type="text" required maxlength="500" value="{E(v.get('doc_id', ''))}" placeholder="/Content/Guide/guide.ditamap">
<div class="hint">The repository path of the map in CCMS.</div></div>
<div><label for="origin">Origin ID</label>
<input id="origin" name="origin_id" type="text" maxlength="200" value="{E(v.get('origin_id', ''))}" placeholder="Optional">
<div class="hint">Used to pick the right snapshot when several share a map.</div></div></div>
<div class="row"><div><span class="lab">Version</span><div class="modes">
<label class="mode"><input type="radio" name="mode" value="latest"{" checked" if latest else ""}><b>Latest published snapshot</b><small>No version control. Uses the newest publish.</small></label>
<label class="mode"><input type="radio" name="mode" value="specific"{"" if latest else " checked"}><b>Specific version</b><small>Enter a version number.</small></label></div>
<div class="vernum" style="max-width:280px;margin-top:12px"><label for="ver">Version number</label>
<input id="ver" name="version" type="text" maxlength="40" value="{E(v.get('version', ''))}" placeholder="Only used for a specific version"></div></div></div>
<div class="row"><div style="max-width:360px"><label for="fl">Markdown flavor</label><select id="fl" name="flavor">{flavors}</select></div></div>
<button class="btn" type="submit">Convert to Markdown</button></form>"""
    return page("New conversion", body, user)


def progress_page(job: Job) -> bytes:
    items = ""
    for key, label in STEPS:
        st, detail = job.steps[key]
        mark = {"done": "✓", "failed": "!", "running": "", "pending": ""}[st]
        items += f'<li><span class="dot {st}" aria-hidden="true">{mark}</span><div><b>{E(label)}</b><div class="sub">{E(detail) if detail else ("Waiting." if st == "pending" else "")}</div></div></li>'
    err = ""
    actions = ""
    if job.state == "failed":
        err = f'<div class="err" role="alert"><b>The conversion stopped.</b> {E(job.error)}</div>'
        actions = '<div class="actions"><a class="btn" href="/">Try again</a></div>'
    ver = f"version {job.version}" if job.version else "latest published snapshot"
    head = "Could not convert" if job.state == "failed" else "Converting"
    body = f"""<h1>{head} {E(job.doc_id)}</h1>
<p class="lead">Origin {E(job.origin_id or "not set")} · {E(ver)}</p>
<div class="card">{err}<ol class="steps">{items}</ol>{actions}</div>"""
    return page("Conversion running", body, job.user, refresh=job.state == "running")


def _tree(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def results_page(job: Job, sel: str) -> bytes:
    out = job.output_dir
    files = _tree(out)
    if sel not in files:
        sel = "index.md" if "index.md" in files else (files[0] if files else "")
    lis = "".join(f'<li><a href="/jobs/{job.id}?path={quote(f)}"{" class=sel" if f == sel else ""}>{E(f)}</a></li>' for f in files)
    preview = ""
    if sel:
        p = out / sel
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".svg"}:
            preview = f'<div style="padding:20px"><img alt="{E(sel)}" style="max-width:100%" src="/jobs/{job.id}/file?path={quote(sel)}"></div>'
        else:
            text = p.read_bytes()[:MAX_PREVIEW].decode("utf-8", errors="replace")
            preview = f"<pre>{E(text)}</pre>"
    t = (job.quality or {}).get("summary", {"PASS": 0, "WARN": 0, "FAIL": 0})
    if t["FAIL"]:
        pill = f'<span class="pill bad">Conversion complete · {t["FAIL"]} checks failed</span>'
    elif t["WARN"]:
        pill = '<span class="pill warn">Conversion complete · review suggested</span>'
    else:
        pill = '<span class="pill ok">Conversion complete</span>'
    banner = ""
    if t["FAIL"] or t["WARN"]:
        banner = (f'<div class="banner"><b>{t["FAIL"] + t["WARN"]} items need review.</b> Some content could not be mapped cleanly to Markdown. '
                  f'<a href="/jobs/{job.id}?path=quality-report.md">Open the quality report</a>.</div>')
    m = job.manifest
    body = f"""{pill}<h1>{E(job.doc_id)}</h1>
<p class="lead">Origin {E(job.origin_id or "not set")} · version {E(str(m.get('version', '')))} · {len(files)} files</p>
<div class="actions"><a class="btn" href="/jobs/{job.id}/download.zip">Download ZIP</a><a class="btn sec" href="/">Convert another</a></div>
<div class="grid"><section class="card tree"><b>Output folder</b><ul>{lis}</ul></section>
<section class="card view"><div class="vh">{E(sel)}</div>{preview}</section></div>{banner}"""
    return page("Output folder", body, job.user)


# ---------------------------------------------------------------------------------------------
class App(BaseHTTPRequestHandler):
    cfg: Config = Config()

    def log_message(self, fmt, *a):
        log.debug(fmt, *a)

    def _user(self) -> str:
        return (self.headers.get("X-Forwarded-User") or self.headers.get("X-Auth-Request-Email") or "")[:120]

    def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8", extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; img-src 'self' data:")
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, to: str):
        self.send_response(303)
        self.send_header("Location", to)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _job(self, job_id: str) -> Job | None:
        return JOBS.get(job_id)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        user = self._user()
        if u.path == "/healthz":
            return self._send(200, b"ok", "text/plain")
        if u.path == "/":
            return self._send(200, form_page(user))
        parts = [p for p in u.path.split("/") if p]
        if len(parts) >= 2 and parts[0] == "jobs":
            job = self._job(parts[1])
            if not job:
                return self._send(404, page("Not found", '<h1>That run was not found</h1><p class="lead">It may have expired. <a href="/">Start a new conversion</a>.</p>', user), )
            if len(parts) == 2:
                if job.state == "done":
                    return self._send(200, results_page(job, (q.get("path") or [""])[0]))
                return self._send(200, progress_page(job))
            if job.state != "done" or not job.output_dir:
                return self._send(409, b"Run not finished", "text/plain")
            if parts[2] == "download.zip":
                z = job.output_dir.parent / "output.zip"
                if not z.exists():
                    return self._send(404, b"missing", "text/plain")
                name = "".join(c if c.isalnum() or c in "._-" else "_" for c in Path(job.doc_id).stem) or "output"
                return self._send(200, z.read_bytes(), "application/zip", {"Content-Disposition": f'attachment; filename="{name}-markdown.zip"'})
            if parts[2] == "file":
                rel = (q.get("path") or [""])[0]
                target = (job.output_dir / rel).resolve()
                if not str(target).startswith(str(job.output_dir.resolve()) + "/") or not target.is_file():
                    return self._send(404, b"not found", "text/plain")
                ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                if ctype == "image/svg+xml":
                    ctype = "text/plain"     # never serve scripts from user content
                return self._send(200, target.read_bytes(), ctype)
        self._send(404, page("Not found", '<h1>Page not found</h1><p><a href="/">Back to the converter</a></p>', user))

    def do_POST(self):
        if urlparse(self.path).path != "/convert":
            return self._send(404, b"not found", "text/plain")
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).netloc != self.headers.get("Host"):
            return self._send(403, b"Cross-site form posts are not accepted.", "text/plain")   # basic CSRF guard
        n = min(int(self.headers.get("Content-Length") or 0), 20_000)
        data = {k: v[0].strip() for k, v in parse_qs(self.rfile.read(n).decode("utf-8", "replace")).items()}
        user = self._user()
        doc_id = data.get("doc_id", "")
        mode = data.get("mode", "latest")
        version = data.get("version", "") if mode == "specific" else ""
        flavor = data.get("flavor", self.cfg.default_flavor)
        values = {**data, "mode": mode}
        if not doc_id:
            return self._send(400, form_page(user, "Enter a document ID.", values))
        if mode == "specific" and not version:
            return self._send(400, form_page(user, "Enter a version number, or choose the latest published snapshot.", values))
        if flavor not in FLAVORS:
            return self._send(400, form_page(user, "Choose a Markdown flavor from the list.", values))
        job = start_job(self.cfg, user, doc_id, data.get("origin_id", ""), version, flavor)
        self._redirect(f"/jobs/{job.id}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    App.cfg = Config.from_env()
    Path(App.cfg.output_root).mkdir(parents=True, exist_ok=True)
    sweep(App.cfg)
    srv = ThreadingHTTPServer((a.host, a.port), App)
    log.info("Serving on http://%s:%s (runs kept %s h)", a.host, a.port, RETENTION_HOURS)
    srv.serve_forever()


if __name__ == "__main__":
    main()
