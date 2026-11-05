"""Choose the snapshot to convert.

Rules (proposed, see the plan doc; confirm with IXIASOFT):
  * version given      -> the snapshot of the map with that version, else error "version not found".
  * version empty      -> the most recent snapshot whose currentStatus counts as published,
                          else error "no published snapshot".
  * origin ID given    -> snapshots are filtered by it when the snapshot data carries an origin field.
"""
from __future__ import annotations

from .ccms import CcmsClient, SnapshotRef
from .config import Config


class NoSnapshotError(Exception):
    """No snapshot matches. The message is safe to show to a user."""


def _sort_key(s: SnapshotRef):
    # ISO-8601 UTC strings sort chronologically; an empty value sorts first.
    return (s.created or "", s.path)


def pick_snapshot(snaps: list[SnapshotRef], cfg: Config, origin_id: str = "", version: str = "") -> tuple[SnapshotRef, list[str]]:
    """Return (snapshot, notes). Pure function so the rules are easy to test."""
    notes: list[str] = []
    candidates = list(snaps)
    if not candidates:
        raise NoSnapshotError("The document has no snapshots.")

    origin_id = (origin_id or "").strip()
    version = (version or "").strip()

    if origin_id:
        if any(s.origin for s in candidates):
            filtered = [s for s in candidates if s.origin == origin_id]
            if not filtered:
                raise NoSnapshotError(f"No snapshot of this document has origin ID {origin_id}.")
            candidates = filtered
        else:
            notes.append("Snapshots carry no origin field, so the origin ID was not used to filter them.")

    if version:
        matches = [s for s in candidates if s.version == version]
        if not matches:
            raise NoSnapshotError(f"Version {version} was not found among this document's snapshots.")
        return max(matches, key=_sort_key), notes

    published = [s for s in candidates if s.status.strip().lower() in cfg.published_statuses]
    if not published:
        raise NoSnapshotError("This document has no published snapshot.")
    return max(published, key=_sort_key), notes


def resolve_snapshot(client: CcmsClient, doc_id: str, origin_id: str = "", version: str = "") -> tuple[SnapshotRef, list[str]]:
    snaps = client.list_snapshots(doc_id)
    return pick_snapshot(snaps, client.cfg, origin_id=origin_id, version=version)
