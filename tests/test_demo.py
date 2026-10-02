"""Three tests for the presentation. Run:  .venv\\Scripts\\pytest tests\\test_demo.py -v

1. the variant 57 operation: sort by creation date, ascending and descending;
2. a file uploaded to the server comes back byte-for-byte, and only to its owner;
3. login with a wrong password is rejected.
"""
from datetime import datetime, timedelta, timezone

from client.sorting import SortOrder, sort_by_created
from common.schemas import FileOut
from tests.conftest import PASSWORD


def test_variant_sort_by_creation_date():
    t0 = datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc)

    def file(file_id, name, hours):
        t = t0 + timedelta(hours=hours)
        return FileOut(id=file_id, name=name, extension="", size=1, mime_type="x", created_at=t,
                       modified_at=t, uploader_name="Ivanka", editor_name="Ivanka")

    # ids, names and creation times in different orders: only a real sort by date passes
    files = [file(1, "b.js", 2), file(2, "c.png", 5), file(3, "a.c", 0), file(4, "d.jpg", 1)]

    oldest_first = [f.name for f in sort_by_created(files, SortOrder.ASC)]
    newest_first = [f.name for f in sort_by_created(files, SortOrder.DESC)]
    assert oldest_first == ["a.c", "d.jpg", "b.js", "c.png"]
    assert newest_first == ["c.png", "b.js", "d.jpg", "a.c"]


def test_uploaded_file_comes_back_only_to_its_owner(client, make_user):
    ivanka, bob = make_user("ivanka"), make_user("bob")
    data = b"console.log('Drive Mini');"
    file_id = client.post("/files", headers=ivanka, files={"file": ("app.js", data)}).json()["id"]

    assert client.get(f"/files/{file_id}/content", headers=ivanka).content == data
    assert client.get(f"/files/{file_id}/content", headers=bob).status_code == 404


def test_wrong_password_is_rejected(client, make_user):
    make_user("ivanka")
    right = client.post("/auth/login", data={"username": "ivanka", "password": PASSWORD})
    wrong = client.post("/auth/login", data={"username": "ivanka", "password": "wrong"})
    assert right.status_code == 200
    assert wrong.status_code == 401
