"""POST /sync/plan: the shared rules table, run by the server for the web client.

The rules table itself is tested row by row in test_sync.py; here: the HTTP layer around it
(the formats a browser sends, skipped files, login, isolation).
"""
import pytest

from common.sync_rules import Kind
from server.routers.sync import _KIND


def plan_for(client, headers, local=(), snapshot=()):
    r = client.post("/sync/plan", headers=headers, json={"local": list(local), "snapshot": list(snapshot)})
    assert r.status_code == 200, r.text
    return r.json()


def kinds(reply):
    return {a["name"]: a["kind"] for a in reply["actions"]}


def entry_after_sync(local_file, server_file):
    """What a client stores after syncing a file: the server's file as it came in the JSON reply."""
    return {"name": server_file["name"], "server_modified": server_file["modified_at"],
            "server_size": server_file["size"], "local_mtime": local_file["mtime"], "local_size": local_file["size"]}


@pytest.fixture
def ivanka(make_user):
    return make_user("ivanka")


def upload(client, headers, name, data=b"x"):
    r = client.post("/files", headers=headers, files={"file": (name, data)})
    assert r.status_code == 201, r.text
    return r.json()


def test_first_sync_uploads_downloads_and_compares(client, ivanka):
    upload(client, ivanka, "only-there.png")
    same = upload(client, ivanka, "Both.js")
    reply = plan_for(client, ivanka, local=[{"name": "only-here.c", "mtime": 1, "size": 1},
                                            {"name": "both.js", "mtime": 1, "size": 1}])
    assert kinds(reply) == {"only-here.c": "upload", "only-there.png": "download", "both.js": "compare"}
    downloads = [a for a in reply["actions"] if a["kind"] == "download"]
    assert downloads[0]["file"]["id"] > 0  # the client gets the current id with the action
    compare = next(a for a in reply["actions"] if a["kind"] == "compare")
    assert compare["key"] == "both.js" and compare["file"]["id"] == same["id"]  # matched ignoring case


def test_a_second_sync_right_after_changes_nothing(client, ivanka):
    """The snapshot round-trips through JSON ("...Z" times) and must still match the server's."""
    server_file = upload(client, ivanka, "a.js")
    local_file = {"name": "a.js", "mtime": 1_700_000_000_123, "size": 1}  # a browser's milliseconds
    reply = plan_for(client, ivanka, local=[local_file], snapshot=[entry_after_sync(local_file, server_file)])
    assert kinds(reply) == {"a.js": "nothing"}


def test_changes_on_each_side_follow_the_rules_table(client, ivanka):
    files = {n: upload(client, ivanka, n) for n in ("edited-here.js", "edited-there.js", "gone-here.js", "same.js")}
    local = {n: {"name": n, "mtime": 1, "size": 1} for n in files}
    snapshot = [entry_after_sync(local[n], files[n]) for n in files]
    client.put(f"/files/{files['edited-there.js']['id']}", headers=ivanka, files={"file": ("x", b"new")})
    local["edited-here.js"] = {"name": "edited-here.js", "mtime": 2, "size": 1}
    del local["gone-here.js"]

    reply = plan_for(client, ivanka, local=local.values(), snapshot=snapshot)
    assert kinds(reply) == {"edited-here.js": "replace", "edited-there.js": "download",
                            "gone-here.js": "delete_server", "same.js": "nothing"}


def test_edited_on_both_sides_is_compared_first_with_the_reason(client, ivanka):
    server_file = upload(client, ivanka, "a.js")
    old_local = {"name": "a.js", "mtime": 1, "size": 1}
    client.put(f"/files/{server_file['id']}", headers=ivanka, files={"file": ("a.js", b"y")})
    reply = plan_for(client, ivanka, local=[{"name": "a.js", "mtime": 2, "size": 1}],
                     snapshot=[entry_after_sync(old_local, server_file)])
    assert reply["actions"][0]["kind"] == "compare"
    assert reply["actions"][0]["reason"] == "changed here, changed on the server"


def test_files_the_server_would_refuse_are_skipped_and_left_alone(client, ivanka, monkeypatch):
    monkeypatch.setattr("server.routers.sync.MAX_UPLOAD_BYTES", 5)
    upload(client, ivanka, "big.js")  # same name on the server: must not be overwritten or downloaded
    reply = plan_for(client, ivanka, local=[{"name": "a:b.js", "mtime": 1, "size": 1},
                                            {"name": "big.js", "mtime": 1, "size": 6},
                                            {"name": "ok.js", "mtime": 1, "size": 1}])
    assert kinds(reply) == {"ok.js": "upload"}
    assert reply["skipped"] == ["a:b.js: File name contains characters that are not allowed: :",
                                "big.js: larger than 0 MB"]


def test_login_required_and_users_see_only_their_own_files(client, ivanka, make_user):
    upload(client, ivanka, "private.js")
    assert client.post("/sync/plan", json={"local": [], "snapshot": []}).status_code == 401
    bob = make_user("bob")
    assert plan_for(client, bob)["actions"] == []  # ivanka's file isn't on bob's drive


def test_every_kind_has_a_name_in_the_contract():
    assert set(_KIND) == set(Kind)
