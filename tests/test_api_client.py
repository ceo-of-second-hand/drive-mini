"""The desktop client's RestApiClient against the real server code (in-process)."""
from datetime import timezone

import pytest

from client.api import ApiError, RestApiClient
from common.schemas import FileOut
from tests.conftest import PASSWORD


@pytest.fixture
def api(client):
    return RestApiClient(http=client)  # FastAPI's TestClient is an httpx.Client


def test_register_login_and_me(api):
    api.register("Ivanka", "Ivanka", PASSWORD)
    user = api.login("ivanka", PASSWORD)
    assert api.logged_in
    assert (user.username, user.display_name) == ("ivanka", "Ivanka")
    api.logout()
    assert not api.logged_in


def test_list_is_parsed_into_shared_schema(api, client, make_user):
    headers = make_user("ivanka")
    client.post("/files", headers=headers, files={"file": ("app.js", b"console.log(1);")})
    api.login("ivanka", PASSWORD)
    files = api.list_files()
    assert len(files) == 1 and isinstance(files[0], FileOut)
    assert files[0].name == "app.js"
    assert files[0].created_at.tzinfo == timezone.utc  # real UTC datetimes, not strings


def test_server_errors_become_api_errors_with_the_detail_text(api):
    api.register("ivanka", "Ivanka", PASSWORD)
    with pytest.raises(ApiError) as duplicate:
        api.register("IVANKA", "Other", PASSWORD)
    assert duplicate.value.status == 409 and "already taken" in duplicate.value.detail

    with pytest.raises(ApiError) as wrong:
        api.login("ivanka", "nope")
    assert wrong.value.status == 401 and wrong.value.detail == "Wrong username or password."
    assert not api.logged_in


def test_file_list_needs_login(api):
    with pytest.raises(ApiError) as exc:
        api.list_files()
    assert exc.value.status == 401


def test_unreachable_server_is_a_readable_error():
    api = RestApiClient("http://127.0.0.1:9")  # nothing listens on port 9
    with pytest.raises(ApiError) as exc:
        api.login("ivanka", PASSWORD)
    assert exc.value.status == 0 and "Cannot reach the server" in exc.value.detail
