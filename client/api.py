"""RestApiClient: the desktop client's only link to the server (httpx).

Every reply is parsed with the shared schemas (common/schemas.py), so a mismatch with the
server fails loudly here. Errors of any kind become ApiError with a readable message.
The login token is kept in memory only.
"""
from pathlib import Path

import httpx
from pydantic import ValidationError

from common import rules
from common.schemas import ErrorOut, FileOut, UserOut

DEFAULT_SERVER = "http://127.0.0.1:8000"


def upload_problem(path: Path) -> str | None:
    """Check a local file against the shared rules before sending it. None = OK.

    The server enforces the same rules; checking here gives an instant, clear message.
    """
    if not path.is_file():
        return f"'{path.name}' is not a file (folders can't be uploaded)."
    error = rules.validate_file_name(path.name)
    if error:
        return error
    if path.stat().st_size > rules.MAX_UPLOAD_BYTES:
        return f"'{path.name}' is larger than {rules.MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
    return None


class ApiError(Exception):
    """A failed request. status is the HTTP code, or 0 if the server couldn't be reached."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


class RestApiClient:
    def __init__(self, base_url: str = DEFAULT_SERVER, http: httpx.Client | None = None):
        # Tests pass FastAPI's TestClient (an httpx.Client) to talk to the app in-process.
        self._http = http or httpx.Client(base_url=base_url, timeout=15)
        self._token: str | None = None

    @property
    def base_url(self) -> str:
        return str(self._http.base_url)

    @property
    def logged_in(self) -> bool:
        return self._token is not None

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        try:
            response = self._http.request(method, url, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise ApiError(0, f"Cannot reach the server at {self.base_url} ({exc.__class__.__name__}).")
        if response.is_error:
            try:
                detail = ErrorOut.model_validate(response.json()).detail
            except (ValueError, ValidationError):
                detail = response.text or response.reason_phrase
            raise ApiError(response.status_code, detail)
        return response

    # --- accounts ---

    def register(self, username: str, display_name: str, password: str) -> UserOut:
        r = self._request("POST", "/auth/register", json={
            "username": username, "display_name": display_name, "password": password})
        return UserOut.model_validate(r.json())

    def login(self, username: str, password: str) -> UserOut:
        r = self._request("POST", "/auth/login", data={"username": username, "password": password})
        self._token = r.json()["access_token"]
        return self.me()

    def logout(self) -> None:
        self._token = None  # tokens are stateless: forgetting it is the logout

    def me(self) -> UserOut:
        return UserOut.model_validate(self._request("GET", "/auth/me").json())

    # --- files ---

    def list_files(self) -> list[FileOut]:
        return [FileOut.model_validate(item) for item in self._request("GET", "/files").json()]

    def upload(self, path: Path) -> FileOut:
        """New file. A taken name raises ApiError with status 409 (then offer replace)."""
        r = self._request("POST", "/files", files={"file": (path.name, path.read_bytes())})
        return FileOut.model_validate(r.json())

    def replace(self, file_id: int, path: Path) -> FileOut:
        """New content for an existing file; its name, created time and uploader stay."""
        r = self._request("PUT", f"/files/{file_id}", files={"file": (path.name, path.read_bytes())})
        return FileOut.model_validate(r.json())

    def download(self, file_id: int) -> bytes:
        return self._request("GET", f"/files/{file_id}/content").content

    def delete(self, file_id: int) -> None:
        self._request("DELETE", f"/files/{file_id}")
