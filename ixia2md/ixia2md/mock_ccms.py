"""A small stand-in for IXIA CCMS, for tests and demos. It mimics the documented endpoints only.

The JSON bodies are our ASSUMPTION of the real shapes (the documentation pages we could read do not
show them). Start it with:  python -m ixia2md.mock_ccms --port 8099
User: demo / password: demo
"""
from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

MAP_PATH = "/Content/Guide/guide.ditamap"
SNAPSHOTS = [
    {"documentIdentifier": "/Snapshots/guide_v1", "objectIdentifier": "s1", "currentStatus": "Published",
     "creationTime": "2026-10-01T09:00:00Z", "version": "1", "originIdentifier": "ORIG-1"},
    {"documentIdentifier": "/Snapshots/guide_v3", "objectIdentifier": "s3", "currentStatus": "Published",
     "creationTime": "2026-10-10T09:00:00Z", "version": "3", "originIdentifier": "ORIG-1"},
    {"documentIdentifier": "/Snapshots/guide_v2", "objectIdentifier": "s2", "currentStatus": "Authoring:work",
     "creationTime": "2026-10-20T09:00:00Z", "version": "2", "originIdentifier": "ORIG-1"},
]


class Handler(BaseHTTPRequestHandler):
    root: Path = Path(".")
    users = {"demo": "demo"}

    def log_message(self, *a):  # quiet
        pass

    def _json(self, code, body, headers=None):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _authed(self) -> bool:
        return "IxiaAuth=mock-session" in (self.headers.get("Cookie") or "")

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        if u.path == "/rest/1.0/sessions/authorize":
            if self.users.get(body.get("userName")) == body.get("password"):
                return self._json(200, {"ok": True}, {"Set-Cookie": "IxiaAuth=mock-session; Path=/"})
            return self._json(401, {"error": "bad credentials"})
        if u.path == "/rest/1.0/sessions/releaseSession":
            return self._json(200, {"ok": True})
        self._json(404, {})

    def do_GET(self):
        u = urlparse(self.path)
        if not self._authed():
            return self._json(401, {"error": "no session"})
        p = u.path
        pre = "/rest/1.0/documents/"
        if p.startswith(pre) and p.endswith("/snapshotsOfMap"):
            doc = unquote(p[len(pre):-len("/snapshotsOfMap")]).replace("|", "/")
            if doc != MAP_PATH:
                return self._json(404, {})
            return self._json(200, {"result": SNAPSHOTS})
        if p.startswith(pre + "snapshots/"):
            snap = unquote(p[len(pre + "snapshots/"):]).replace("|", "/")
            if not any(s["documentIdentifier"] == snap for s in SNAPSHOTS):
                return self._json(404, {})
            objs = []
            for f in sorted((self.root / "Content").rglob("*")):
                if f.is_file():
                    rel = "/" + f.relative_to(self.root).as_posix()
                    kind = "map" if rel.endswith(".ditamap") else "image" if rel.endswith(".png") else "topic"
                    objs.append({"documentIdentifier": rel, "genericObjectType": kind})
            return self._json(200, {"result": {"documentIdentifier": snap, "objects": objs}})
        if p == "/rest/1.0/files":
            path = parse_qs(u.query).get("url", [""])[0]
            f = (self.root / path.lstrip("/")).resolve()
            if not str(f).startswith(str(self.root.resolve())) or not f.is_file():
                return self._json(404, {})
            data = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self._json(404, {})


def start(root: Path, port: int = 0) -> tuple[ThreadingHTTPServer, str]:
    Handler.root = Path(root)
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent / "sample_ccms"))
    a = ap.parse_args()
    srv, url = start(Path(a.root), a.port)
    print(f"Mock CCMS on {url}  (user demo / password demo, map {MAP_PATH})")
    threading.Event().wait()
