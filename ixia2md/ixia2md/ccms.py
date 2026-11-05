"""Read-only client for the IXIA CCMS REST API (documented for 7.5).

Endpoints used, all under <ccms_url>/rest/1.0:
  /sessions/authorize                       sign in, returns the IxiaAuth cookie
  /documents/{docPath}/snapshotsOfMap       list the snapshots of a map
  /documents/snapshots/{docPath}            a snapshot and the objects it contains
  /files?url=<path>                         download a document's content
  /sessions/releaseSession                  sign out

Collection separators in {docPath} are encoded as %7C, as the documentation requires.

Response bodies for the snapshot calls are not documented in the pages we could read
(DocumentIdentifierResult, SnapshotInformationResult). The parsing below is therefore tolerant and
isolated in the `parse_*` functions: adjust them in ONE place once real responses are known.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import requests

from .config import Config

log = logging.getLogger("ixia2md.ccms")


class CcmsError(Exception):
    """Any failure talking to CCMS. The message is safe to show to a user."""


class CcmsAuthError(CcmsError):
    pass


class CcmsNotFound(CcmsError):
    pass


@dataclass
class SnapshotRef:
    path: str                     # documentIdentifier of the snapshot
    object_id: str = ""
    status: str = ""              # currentStatus
    created: str = ""             # creationTime (UTC ISO string) or modifiedTime
    version: str = ""
    origin: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class SnapshotObject:
    path: str
    kind: str = ""                # genericObjectType: map, topic, image, ditaval ...
    raw: dict = field(default_factory=dict)


def encode_doc_path(path: str) -> str:
    """Encode a repository path for use as {docPath}: '/' becomes %7C."""
    return quote(path.replace("/", "|"), safe="")


# --------------------------------------------------------------------------------------------
# Tolerant parsing of response bodies (single place to adjust once real payloads are known)
# --------------------------------------------------------------------------------------------
_LIST_KEYS = ("result", "results", "items", "documents", "snapshots", "objects", "members", "children")


def _as_list(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for k in _LIST_KEYS:
            if k in payload:
                v = payload[k]
                if isinstance(v, list):
                    return [x for x in v if isinstance(x, dict)]
                if isinstance(v, dict):
                    inner = _as_list(v)
                    if inner:
                        return inner
    return []


def parse_snapshot_list(payload: Any, cfg: Config) -> list[SnapshotRef]:
    out = []
    for item in _as_list(payload):
        path = item.get("documentIdentifier") or item.get("path") or ""
        if not path:
            continue
        out.append(SnapshotRef(
            path=path,
            object_id=str(item.get("objectIdentifier", "")),
            status=str(item.get("currentStatus", "")),
            created=str(item.get("creationTime") or item.get("modifiedTime") or ""),
            version=str(item.get(cfg.version_field, "")),
            origin=str(item.get(cfg.origin_field, "")),
            raw=item,
        ))
    return out


def parse_snapshot_objects(payload: Any) -> list[SnapshotObject]:
    body = payload.get("result", payload) if isinstance(payload, dict) else payload
    items: list[dict] = []
    if isinstance(body, dict):
        for k in ("objects", "documents", "members", "items", "children"):
            if isinstance(body.get(k), list):
                items = [x for x in body[k] if isinstance(x, dict)]
                break
    else:
        items = _as_list(body)
    out = []
    for it in items:
        path = it.get("documentIdentifier") or it.get("path") or ""
        if path:
            out.append(SnapshotObject(path=path, kind=str(it.get("genericObjectType", "")).lower(), raw=it))
    return out


# --------------------------------------------------------------------------------------------
class CcmsClient:
    def __init__(self, cfg: Config):
        if not cfg.ccms_url:
            raise CcmsError("CCMS_URL is not set.")
        self.cfg = cfg
        self.base = cfg.ccms_url.rstrip("/") + "/rest/1.0"
        self.s = requests.Session()
        self.s.verify = cfg.verify_tls
        self.s.headers["Accept"] = "application/json"
        self._signed_in = False

    # -- session -----------------------------------------------------------------------------
    def login(self) -> None:
        cfg = self.cfg
        if cfg.ccms_auth_cookie:
            self.s.cookies.set("IxiaAuth", cfg.ccms_auth_cookie)
            self._signed_in = True
            return
        if not (cfg.ccms_user and cfg.ccms_password):
            raise CcmsAuthError("No CCMS credentials configured (CCMS_USER and CCMS_PASSWORD, or CCMS_AUTH_COOKIE).")
        try:
            r = self.s.request(cfg.login_method, self.base + "/sessions/authorize",
                               json={cfg.login_user_field: cfg.ccms_user, cfg.login_password_field: cfg.ccms_password},
                               timeout=cfg.timeout)
        except requests.RequestException as e:
            raise CcmsError(f"Cannot reach CCMS at {cfg.ccms_url}: {type(e).__name__}") from None
        if r.status_code in (401, 403):
            raise CcmsAuthError("CCMS rejected the service account sign-in.")
        if r.status_code >= 400:
            raise CcmsError(f"CCMS sign-in failed with HTTP {r.status_code}.")
        if "IxiaAuth" not in self.s.cookies:
            raise CcmsAuthError("CCMS sign-in succeeded but returned no IxiaAuth session cookie.")
        self._signed_in = True

    def logout(self) -> None:
        if not self._signed_in:
            return
        try:
            self.s.request(self.cfg.login_method, self.base + "/sessions/releaseSession", timeout=self.cfg.timeout)
        except requests.RequestException:
            pass
        self._signed_in = False

    def __enter__(self):
        self.login()
        return self

    def __exit__(self, *exc):
        self.logout()

    # -- low level ---------------------------------------------------------------------------
    def _get(self, path: str, **params) -> requests.Response:
        try:
            r = self.s.get(self.base + path, params=params or None, timeout=self.cfg.timeout)
        except requests.RequestException as e:
            raise CcmsError(f"CCMS unreachable while calling {path.split('?')[0]}: {type(e).__name__}") from None
        if r.status_code == 401:
            raise CcmsAuthError("The CCMS session is no longer valid (HTTP 401).")
        if r.status_code == 404:
            raise CcmsNotFound(f"Not found in CCMS: {path.split('?')[0]}")
        if r.status_code >= 400:
            raise CcmsError(f"CCMS returned HTTP {r.status_code} for {path.split('?')[0]}.")
        return r

    # -- documented calls --------------------------------------------------------------------
    def list_snapshots(self, map_path: str) -> list[SnapshotRef]:
        r = self._get(f"/documents/{encode_doc_path(map_path)}/snapshotsOfMap")
        return parse_snapshot_list(r.json(), self.cfg)

    def get_snapshot_objects(self, snapshot_path: str) -> list[SnapshotObject]:
        r = self._get(f"/documents/snapshots/{encode_doc_path(snapshot_path)}")
        return parse_snapshot_objects(r.json())

    def download(self, doc_path: str) -> bytes:
        return self._get("/files", url=doc_path).content
