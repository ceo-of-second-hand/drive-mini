"""Folder sync (client/sync.py).

Part 1: plan() for every row of the rules table (no I/O).
Part 2: real syncs of a temp folder against the in-process server.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from client.api import ApiError, RestApiClient
from client.sync import Entry, FolderSync, Kind, LocalFile, plan, snapshot_path, unlink_folder
from common.schemas import FileOut
from tests.conftest import PASSWORD

# --- Part 1: the rules table -------------------------------------------------------------

T = datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc)


def server_file(modified=T, size=10):
    return FileOut(id=1, name="a.js", extension="js", size=size, mime_type="x", created_at=T,
                   modified_at=modified, uploader_name="I", editor_name="I")


def local_file(mtime_ns=1000, size=10):
    return LocalFile("a.js", Path("a.js"), mtime_ns, size)


ENTRY = Entry("a.js", T.isoformat(), 10, 1000, 10)  # state after the last sync
SAME_L, CHANGED_L = local_file(), local_file(mtime_ns=2000)
SAME_S, CHANGED_S = server_file(), server_file(modified=T + timedelta(seconds=1))


@pytest.mark.parametrize("local, server, entry, expected", [
    (SAME_L, None, None, Kind.UPLOAD),               # new here, absent there
    (None, SAME_S, None, Kind.DOWNLOAD),             # absent here, new there
    (SAME_L, SAME_S, None, Kind.COMPARE),            # new on both sides: compare bytes
    (CHANGED_L, SAME_S, ENTRY, Kind.REPLACE),
    (SAME_L, CHANGED_S, ENTRY, Kind.DOWNLOAD),
    (CHANGED_L, CHANGED_S, ENTRY, Kind.CONFLICT),
    (None, SAME_S, ENTRY, Kind.DELETE_SERVER),
    (SAME_L, None, ENTRY, Kind.DELETE_LOCAL),
    (CHANGED_L, None, ENTRY, Kind.CONFLICT),
    (None, CHANGED_S, ENTRY, Kind.CONFLICT),
    (None, None, ENTRY, Kind.FORGET),
    (SAME_L, SAME_S, ENTRY, Kind.NOTHING),
])
def test_rules_table(local, server, entry, expected):
    actions = plan({"a.js": local} if local else {}, {"a.js": server} if server else {},
                   {"a.js": entry} if entry else {})
    assert [a.kind for a in actions] == [expected]


def test_size_alone_counts_as_a_change_on_each_side():
    assert plan({"a.js": local_file(size=11)}, {"a.js": SAME_S}, {"a.js": ENTRY})[0].kind is Kind.REPLACE
    assert plan({"a.js": SAME_L}, {"a.js": server_file(size=11)}, {"a.js": ENTRY})[0].kind is Kind.DOWNLOAD


def test_an_older_time_is_a_change_too():
    # equality only, never "newer": a file restored from a backup has an OLDER time
    assert plan({"a.js": local_file(mtime_ns=500)}, {"a.js": SAME_S}, {"a.js": ENTRY})[0].kind is Kind.REPLACE


# --- Part 2: real syncs -------------------------------------------------------------------

@pytest.fixture
def api(client, make_user):
    make_user("ivanka")
    api = RestApiClient(http=client)
    api.login("ivanka", PASSWORD)
    return api


@pytest.fixture
def folder(tmp_path):
    path = tmp_path / "my-drive"
    path.mkdir()
    return path


@pytest.fixture
def outside(tmp_path):
    """Files used to change the server 'from another computer'."""
    def _make(name, data):
        path = tmp_path / "elsewhere" / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
        return path
    return _make


def sync(api, folder):
    return FolderSync(api, folder, "ivanka").run()


def server_content(api, name):
    f = next(f for f in api.list_files() if f.name.casefold() == name.casefold())
    return api.download(f.id)


def edit(path: Path, data: bytes):
    path.write_bytes(data)
    os.utime(path, ns=(path.stat().st_atime_ns, path.stat().st_mtime_ns + 1_000_000))  # surely a new time


def test_first_sync_uploads_downloads_and_compares(api, folder, outside):
    (folder / "only-here.js").write_bytes(b"local")
    api.upload(outside("only-there.c", b"server"))
    (folder / "same.png").write_bytes(b"identical")
    api.upload(outside("same.png", b"identical"))
    (folder / "differs.js").write_bytes(b"mine")
    api.upload(outside("differs.js", b"theirs"))

    result = sync(api, folder)
    assert result.uploaded == ["only-here.js"]
    assert result.downloaded == ["only-there.c"]
    assert (folder / "only-there.c").read_bytes() == b"server"
    assert [c.name for c in result.conflicts] == ["differs.js"]  # identical same.png: no conflict
    assert (folder / "differs.js").read_bytes() == b"mine" and server_content(api, "differs.js") == b"theirs"


def test_second_sync_right_after_changes_nothing(api, folder):
    (folder / "a.js").write_bytes(b"1")
    sync(api, folder)
    assert sync(api, folder).nothing_happened


def test_local_edit_replaces_the_server_copy(api, folder):
    (folder / "a.js").write_bytes(b"v1")
    sync(api, folder)
    edit(folder / "a.js", b"version 2")
    assert sync(api, folder).uploaded == ["a.js (updated)"]
    assert server_content(api, "a.js") == b"version 2"
    assert len(api.list_files()) == 1  # replaced, not a second file


def test_server_edit_is_downloaded(api, folder, outside):
    (folder / "a.js").write_bytes(b"v1")
    sync(api, folder)
    file_id = api.list_files()[0].id
    api.replace(file_id, outside("a.js", b"edited elsewhere"))
    assert sync(api, folder).downloaded == ["a.js (updated)"]
    assert (folder / "a.js").read_bytes() == b"edited elsewhere"


def test_edits_on_both_sides_are_a_conflict_and_change_nothing(api, folder, outside):
    (folder / "a.js").write_bytes(b"v1")
    sync(api, folder)
    edit(folder / "a.js", b"mine")
    api.replace(api.list_files()[0].id, outside("a.js", b"theirs"))
    result = sync(api, folder)
    assert [(c.name, c.reason) for c in result.conflicts] == [("a.js", "changed here, changed on the server")]
    assert (folder / "a.js").read_bytes() == b"mine" and server_content(api, "a.js") == b"theirs"
    assert [c.name for c in sync(api, folder).conflicts] == ["a.js"]  # still there until resolved


def test_deletions_propagate_both_ways(api, folder):
    for name in ("gone-here.js", "gone-there.c"):
        (folder / name).write_bytes(b"x")
    sync(api, folder)
    (folder / "gone-here.js").unlink()
    api.delete(next(f.id for f in api.list_files() if f.name == "gone-there.c"))
    result = sync(api, folder)
    assert result.deleted_on_server == ["gone-here.js"] and result.deleted_locally == ["gone-there.c"]
    assert api.list_files() == [] and list(folder.iterdir()) == []


def test_changed_on_one_side_deleted_on_the_other_is_a_conflict(api, folder, outside):
    for name in ("edited-here.js", "edited-there.c"):
        (folder / name).write_bytes(b"x")
    sync(api, folder)
    ids = {f.name: f.id for f in api.list_files()}
    edit(folder / "edited-here.js", b"new")
    api.delete(ids["edited-here.js"])
    (folder / "edited-there.c").unlink()
    api.replace(ids["edited-there.c"], outside("edited-there.c", b"newer"))
    reasons = {c.name: c.reason for c in sync(api, folder).conflicts}
    assert reasons == {"edited-here.js": "changed here, deleted on the server",
                       "edited-there.c": "deleted here, changed on the server"}


def test_resolve_keep_mine_and_keep_servers(api, folder, outside):
    for name in ("mine.js", "theirs.js"):
        (folder / name).write_bytes(b"v1")
    syncer = FolderSync(api, folder, "ivanka")
    syncer.run()
    for f in api.list_files():
        edit(folder / f.name, b"local edit")
        api.replace(f.id, outside(f.name, b"server edit"))
    conflicts = {c.name: c for c in syncer.run().conflicts}

    syncer.resolve(conflicts["mine.js"], "mine")
    syncer.resolve(conflicts["theirs.js"], "server")
    assert server_content(api, "mine.js") == b"local edit"
    assert (folder / "theirs.js").read_bytes() == b"server edit"
    assert syncer.run().nothing_happened  # resolved for good


def test_skipped_and_ignored_files(api, folder, outside, monkeypatch):
    monkeypatch.setattr("client.sync.MAX_UPLOAD_BYTES", 5)
    (folder / "sub").mkdir()
    (folder / "big.js").write_bytes(b"123456")  # over the (lowered) limit
    api.upload(outside("big.js", b"small"))     # same name on the server must not overwrite it
    for clutter in ("desktop.ini", "Thumbs.db", "~$report.docx"):
        (folder / clutter).write_bytes(b"x")
    result = sync(api, folder)
    assert sorted(s.split(":")[0] for s in result.skipped) == ["big.js", "sub"]
    assert "subfolders aren't synced" in " ".join(result.skipped)
    assert (folder / "big.js").read_bytes() == b"123456"
    assert [f.name for f in api.list_files()] == ["big.js"]  # clutter not uploaded


def test_one_failing_file_does_not_stop_the_others(api, folder, monkeypatch):
    (folder / "bad.js").write_bytes(b"x")
    (folder / "good.js").write_bytes(b"y")
    real_upload = api.upload

    def flaky(path):
        if path.name == "bad.js":
            raise ApiError(500, "server hiccup")
        return real_upload(path)

    monkeypatch.setattr(api, "upload", flaky)
    result = sync(api, folder)
    assert result.uploaded == ["good.js"] and result.errors == ["bad.js: server hiccup"]
    monkeypatch.setattr(api, "upload", real_upload)
    assert sync(api, folder).uploaded == ["bad.js"]  # retried next time


def test_coming_back_to_an_unlinked_folder_is_a_first_sync(api, folder):
    (folder / "a.js").write_bytes(b"1")
    sync(api, folder)
    unlink_folder(api.base_url, "ivanka", folder)  # user switched to another folder
    (folder / "a.js").unlink()                      # ...and later this file is gone from the old one
    result = sync(api, folder)                      # coming back: nothing is deleted on the drive
    assert result.deleted_on_server == [] and result.downloaded == ["a.js"]
    assert [f.name for f in api.list_files()] == ["a.js"]


def test_snapshot_lives_in_appdata_without_ids(api, folder):
    (folder / "a.js").write_bytes(b"1")
    syncer = FolderSync(api, folder, "ivanka")
    syncer.run()
    assert syncer.snapshot_file == snapshot_path(api.base_url, "ivanka", folder)
    assert syncer.snapshot_file.is_relative_to(Path(os.environ["APPDATA"]))
    assert [p.name for p in folder.iterdir()] == ["a.js"]  # nothing extra in the synced folder
    entry = json.loads(syncer.snapshot_file.read_text())["files"]["a.js"]
    assert set(entry) == {"name", "server_modified", "server_size", "local_mtime_ns", "local_size"}
