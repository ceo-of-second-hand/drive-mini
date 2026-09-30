"""RestApiClient: the desktop client's only link to the server (httpx).

Every reply is parsed with the shared schemas (common/schemas.py), so a mismatch with the
server fails loudly here. Errors of any kind become ApiError with a readable message.
The login token is kept in memory only.
"""
import httpx
from pydantic import ValidationError

from common.schemas import ErrorOut, FileOut, UserOut

DEFAULT_SERVER = "http://127.0.0.1:8000"


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
