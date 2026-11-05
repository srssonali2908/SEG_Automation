"""Download every object of a snapshot into a work folder, keeping the repository layout."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .ccms import CcmsClient, CcmsError, SnapshotObject, SnapshotRef


@dataclass
class Fetched:
    root: Path                    # folder containing the downloaded tree
    root_map: Path                # the map DITA-OT is run on
    files: list[str]              # repository paths, in download order
    counts: dict


def _local(root: Path, repo_path: str) -> Path:
    # Normalize and refuse anything that would escape the work folder.
    parts = [p for p in PurePosixPath(repo_path.replace("\\", "/")).parts if p not in ("/", "", ".")]
    if any(p == ".." for p in parts):
        raise CcmsError(f"Refusing unsafe path from CCMS: {repo_path}")
    return root.joinpath(*parts)


def pick_root_map(objects: list[SnapshotObject], snapshot: SnapshotRef, requested_map: str) -> SnapshotObject:
    maps = [o for o in objects if o.kind == "map" or o.path.lower().endswith((".ditamap", ".bookmap"))]
    if not maps:
        raise CcmsError("The snapshot contains no DITA map to convert.")
    # Prefer the map that was asked for, else the one flagged as root, else the first map.
    want = PurePosixPath(requested_map).name
    for o in maps:
        if PurePosixPath(o.path).name == want:
            return o
    for o in maps:
        if o.raw.get("isRoot") or o.raw.get("rootMap"):
            return o
    return maps[0]


def fetch_snapshot(client: CcmsClient, snapshot: SnapshotRef, requested_map: str, workdir: Path, progress=lambda msg: None) -> Fetched:
    objects = client.get_snapshot_objects(snapshot.path)
    if not objects:
        raise CcmsError("The snapshot lists no objects.")
    root = workdir / "dita"
    root.mkdir(parents=True, exist_ok=True)
    counts = {"maps": 0, "topics": 0, "images": 0, "other": 0}
    files: list[str] = []
    for i, o in enumerate(objects, 1):
        data = client.download(o.path)
        dest = _local(root, o.path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        files.append(o.path)
        low = o.path.lower()
        if o.kind == "map" or low.endswith((".ditamap", ".bookmap")):
            counts["maps"] += 1
        elif o.kind == "image" or low.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".bmp")):
            counts["images"] += 1
        elif low.endswith((".dita", ".xml")) or o.kind == "topic":
            counts["topics"] += 1
        else:
            counts["other"] += 1
        if i % 25 == 0:
            progress(f"Downloaded {i} of {len(objects)} files")
    root_obj = pick_root_map(objects, snapshot, requested_map)
    return Fetched(root=root, root_map=_local(root, root_obj.path), files=files, counts=counts)
