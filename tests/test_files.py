"""The virtual disk: upload, replace, download, delete, and who may see what."""
import time

from server.config import settings


def upload(client, headers, name, data=b"console.log('hi');"):
    return client.post("/files", headers=headers, files={"file": (name, data)})


def stored_files(user_id=1):
    folder = settings.storage_dir / str(user_id)
    return sorted(p.name for p in folder.iterdir()) if folder.exists() else []


def test_upload_stores_all_attributes(client, make_user):
    headers = make_user("ivanka", "Ivanka")
    f = upload(client, headers, "app.js", b"12345").json()
    assert (f["name"], f["extension"], f["size"], f["mime_type"]) == \
        ("app.js", "js", 5, "text/javascript")
    assert f["created_at"] == f["modified_at"]
    assert f["uploader_name"] == f["editor_name"] == "Ivanka"
    assert len(stored_files()) == 1


def test_upload_existing_name_in_any_case_is_conflict(client, make_user):
    headers = make_user("ivanka")
    upload(client, headers, "app.js")
    r = upload(client, headers, "APP.JS")
    assert r.status_code == 409
    assert len(client.get("/files", headers=headers).json()) == 1


def test_upload_bad_name_is_rejected(client, make_user):
    headers = make_user("ivanka")
    r = upload(client, headers, "a:b.js")
    assert r.status_code == 422
    assert "not allowed" in r.json()["detail"]


def test_upload_over_size_limit_is_rejected(client, make_user, monkeypatch):
    monkeypatch.setattr("server.routers.files.MAX_UPLOAD_BYTES", 10)  # no need for a 50 MB file
    headers = make_user("ivanka")
    assert upload(client, headers, "small.c", b"x" * 10).status_code == 201
    assert upload(client, headers, "big.c", b"x" * 11).status_code == 413


def test_replace_keeps_identity_and_changes_content(client, make_user):
    headers = make_user("ivanka")
    before = upload(client, headers, "app.js", b"v1").json()
    old_disk = stored_files()
    time.sleep(0.01)
    after = client.put(f"/files/{before['id']}", headers=headers,
                       files={"file": ("other-name.txt", b"version 2")}).json()
    for kept in ["id", "name", "created_at", "uploader_name"]:
        assert after[kept] == before[kept]
    assert after["size"] == 9
    assert after["modified_at"] > before["modified_at"]
    assert stored_files() != old_disk and len(stored_files()) == 1  # old bytes removed
    content = client.get(f"/files/{before['id']}/content", headers=headers)
    assert content.content == b"version 2"


def test_download_returns_exact_bytes_and_name(client, make_user):
    headers = make_user("ivanka")
    data = bytes(range(256))  # every byte value, to catch any text conversion
    file_id = upload(client, headers, "logo.png", data).json()["id"]
    r = client.get(f"/files/{file_id}/content", headers=headers)
    assert r.content == data
    assert 'filename="logo.png"' in r.headers["content-disposition"]


def test_delete_removes_row_and_bytes(client, make_user):
    headers = make_user("ivanka")
    file_id = upload(client, headers, "main.c").json()["id"]
    assert client.delete(f"/files/{file_id}", headers=headers).status_code == 204
    assert client.get("/files", headers=headers).json() == []
    assert stored_files() == []
    assert client.get(f"/files/{file_id}/content", headers=headers).status_code == 404


def test_other_users_files_are_invisible_and_login_is_required(client, make_user):
    ivanka, bob = make_user("ivanka"), make_user("bob")
    file_id = upload(client, ivanka, "main.c").json()["id"]

    assert client.get("/files", headers=bob).json() == []
    assert client.get(f"/files/{file_id}/content", headers=bob).status_code == 404
    assert client.put(f"/files/{file_id}", headers=bob,
                      files={"file": ("x.c", b"x")}).status_code == 404
    assert client.delete(f"/files/{file_id}", headers=bob).status_code == 404
    assert client.get(f"/files/{file_id}/content", headers=ivanka).status_code == 200  # untouched

    for method, url in [("get", "/files"), ("post", "/files"), ("put", f"/files/{file_id}"),
                        ("get", f"/files/{file_id}/content"), ("delete", f"/files/{file_id}")]:
        assert client.request(method, url).status_code == 401
