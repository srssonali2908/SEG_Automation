import json
import os
from pathlib import Path

import pytest

from ixia2md import mock_ccms
from ixia2md.ccms import CcmsAuthError, CcmsClient, SnapshotRef, encode_doc_path
from ixia2md.config import Config
from ixia2md.fetch import _local
from ixia2md.pipeline import run
from ixia2md.resolve import NoSnapshotError, pick_snapshot

ROOT = Path(__file__).resolve().parent.parent
DITA_HOME = os.environ.get("DITA_OT_HOME", "")
MAP = mock_ccms.MAP_PATH


@pytest.fixture(scope="module")
def server():
    srv, url = mock_ccms.start(ROOT / "sample_ccms", 0)
    yield url
    srv.shutdown()


def cfg_for(url, tmp_path, **kw):
    return Config(ccms_url=url, ccms_user="demo", ccms_password="demo", dita_ot_home=DITA_HOME,
                  output_root=str(tmp_path), **kw)


# ---- snapshot rules (pure) ------------------------------------------------------------------
S = lambda p, st, c, v="", o="": SnapshotRef(path=p, status=st, created=c, version=v, origin=o)


def test_no_version_takes_latest_published():
    cfg = Config()
    snaps = [S("a", "Published", "2026-01-01"), S("b", "Published", "2026-03-01"), S("c", "Draft", "2026-05-01")]
    snap, _ = pick_snapshot(snaps, cfg)
    assert snap.path == "b"          # newer draft is ignored


def test_no_published_snapshot_is_an_error():
    with pytest.raises(NoSnapshotError, match="no published snapshot"):
        pick_snapshot([S("a", "Draft", "2026-01-01")], Config())


def test_version_selects_that_snapshot_even_if_unpublished():
    snaps = [S("a", "Published", "2026-01-01", "1"), S("c", "Draft", "2026-05-01", "2")]
    snap, _ = pick_snapshot(snaps, Config(), version="2")
    assert snap.path == "c"


def test_version_not_found():
    with pytest.raises(NoSnapshotError, match="Version 9"):
        pick_snapshot([S("a", "Published", "2026-01-01", "1")], Config(), version="9")


def test_origin_filter_and_missing_origin_field():
    snaps = [S("a", "Published", "2026-01-01", o="X"), S("b", "Published", "2026-02-01", o="Y")]
    assert pick_snapshot(snaps, Config(), origin_id="X")[0].path == "a"
    with pytest.raises(NoSnapshotError):
        pick_snapshot(snaps, Config(), origin_id="Z")
    _, notes = pick_snapshot([S("a", "Published", "2026-01-01")], Config(), origin_id="X")
    assert notes                      # told the user the origin ID could not be used


def test_doc_path_encoding():
    assert encode_doc_path("/Content/Guide/guide.ditamap") == "%7CContent%7CGuide%7Cguide.ditamap"


def test_unsafe_path_is_refused(tmp_path):
    from ixia2md.ccms import CcmsError
    with pytest.raises(CcmsError):
        _local(tmp_path, "/Content/../../etc/passwd")


# ---- client ---------------------------------------------------------------------------------
def test_bad_credentials(server, tmp_path):
    c = cfg_for(server, tmp_path)
    c.ccms_password = "nope"
    with pytest.raises(CcmsAuthError):
        CcmsClient(c).login()


# ---- end to end (needs DITA-OT) -------------------------------------------------------------
needs_dita = pytest.mark.skipif(not DITA_HOME, reason="set DITA_OT_HOME to run the conversion tests")


@needs_dita
def test_end_to_end_latest_published(server, tmp_path):
    events = []
    res = run(cfg_for(server, tmp_path), MAP, origin_id="ORIG-1", progress=lambda *a: events.append(a))
    assert res.ok, res.error
    out = res.output_dir
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["version"] == "3"                       # v3 is the latest PUBLISHED; v2 is a newer draft
    assert (out / "index.md").read_text().startswith("---")
    assert (out / "images" / "flow.png").exists()
    assert "Key GTS Transceiver Features" in (out / "overview.md").read_text()   # table caption kept
    assert (out.parent / "output.zip").exists()
    assert res.quality["summary"]["FAIL"] == 0
    assert [e[0] for e in events if e[1] == "done"] == ["connect", "resolve", "fetch", "convert", "check", "package"]


@needs_dita
def test_specific_version(server, tmp_path):
    res = run(cfg_for(server, tmp_path), MAP, version="1")
    assert res.ok and res.manifest["version"] == "1"


def test_unknown_document(server, tmp_path):
    res = run(cfg_for(server, tmp_path), "/Content/Nope/missing.ditamap")
    assert not res.ok and res.failed_step == "resolve"


def test_bad_version_reports_resolve_step(server, tmp_path):
    res = run(cfg_for(server, tmp_path), MAP, version="42")
    assert not res.ok and res.failed_step == "resolve" and "42" in res.error
