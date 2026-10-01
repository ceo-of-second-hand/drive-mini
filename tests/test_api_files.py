"""The desktop client's file operations (RestApiClient) against the real server, in-process."""
import pytest

from client.api import ApiError, RestApiClient, upload_problem
from tests.conftest import PASSWORD


@pytest.fixture
def api(client, make_user):
    make_user("ivanka")
    api = RestApiClient(http=client)
    api.login("ivanka", PASSWORD)
    return api


@pytest.fixture
def local_file(tmp_path):
    def _make(name: str, data: bytes = b"console.log(1);"):
        path = tmp_path / name
        path.write_bytes(data)
        return path
    return _make


def test_upload_download_delete_round_trip(api, local_file):
    uploaded = api.upload(local_file("app.js", b"hello"))
    assert [f.name for f in api.list_files()] == ["app.js"]
    assert api.download(uploaded.id) == b"hello"
    api.delete(uploaded.id)
    assert api.list_files() == []


def test_taken_name_is_409_then_replace_keeps_identity(api, local_file):
    first = api.upload(local_file("app.js", b"v1"))
    with pytest.raises(ApiError) as exc:
        api.upload(local_file("APP.JS", b"v2"))  # same name in another case
    assert exc.value.status == 409

    replaced = api.replace(first.id, local_file("APP.JS", b"version 2"))
    assert (replaced.id, replaced.name, replaced.created_at) == (first.id, "app.js", first.created_at)
    assert api.download(first.id) == b"version 2"


def test_upload_problem_uses_the_shared_rules(local_file, tmp_path, monkeypatch):
    assert upload_problem(local_file("notes.js")) is None
    assert "not a file" in upload_problem(tmp_path)
    monkeypatch.setattr("common.rules.MAX_UPLOAD_BYTES", 3)
    assert "larger than" in upload_problem(local_file("big.c", b"1234"))
    # Windows won't even create names like "a:b.js", so check that the shared name rule is applied:
    monkeypatch.setattr("common.rules.validate_file_name", lambda name: f"bad name {name}")
    assert upload_problem(local_file("x.js")) == "bad name x.js"
