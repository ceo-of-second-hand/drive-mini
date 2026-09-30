"""Test setup: the server runs in-process against a temporary database and storage folder.

The environment is set before any server module is imported, because server.config reads it
at import time. Each test starts with empty tables and an empty storage folder.
"""
import os
import shutil
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="drivemini-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_tmp / 'test.db').as_posix()}"
os.environ["STORAGE_DIR"] = str(_tmp / "storage")
os.environ["JWT_SECRET"] = "test-secret-" + "x" * 32

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from server.config import settings  # noqa: E402
from server.db import Base, engine  # noqa: E402
from server.main import app  # noqa: E402

PASSWORD = "test123"


@pytest.fixture(autouse=True)
def clean_state():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    shutil.rmtree(settings.storage_dir, ignore_errors=True)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_user(client):
    """Register + log in a user; returns the Authorization header for their requests."""
    def _make(username: str, display_name: str | None = None) -> dict:
        r = client.post("/auth/register", json={
            "username": username, "display_name": display_name or username.title(),
            "password": PASSWORD})
        assert r.status_code == 201, r.text
        token = client.post("/auth/login", data={"username": username, "password": PASSWORD})
        return {"Authorization": f"Bearer {token.json()['access_token']}"}
    return _make


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()  # release the SQLite file so Windows can delete the folder
    shutil.rmtree(_tmp, ignore_errors=True)
