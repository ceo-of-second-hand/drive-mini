"""Accounts, login and tokens."""
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import select

from server.config import settings
from server.db import SessionLocal
from server.models import User
from tests.conftest import PASSWORD


def register(client, username="Ivanka", password=PASSWORD):
    return client.post("/auth/register",
                       json={"username": username, "display_name": "Ivanka", "password": password})


def token_header(sub="1", secret=None, expires_in=timedelta(hours=1)):
    payload = {"sub": sub, "exp": datetime.now(timezone.utc) + expires_in}
    return {"Authorization": "Bearer " + jwt.encode(payload, secret or settings.jwt_secret,
                                                    algorithm="HS256")}


def test_register_returns_account_with_lowercase_username(client):
    r = register(client, "Ivanka")
    assert r.status_code == 201
    assert r.json() == {"id": 1, "username": "ivanka", "display_name": "Ivanka"}


def test_register_same_username_in_any_case_is_conflict(client):
    register(client, "ivanka")
    r = register(client, "IVANKA")
    assert r.status_code == 409


def test_bad_register_input_gives_one_readable_line(client):
    r = register(client, "iv", password="x" * 80)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert isinstance(detail, str)
    assert "username" in detail and "password" in detail


def test_only_a_bcrypt_hash_is_stored(client):
    register(client)
    with SessionLocal() as db:
        stored = db.scalar(select(User.password_hash))
    assert stored != PASSWORD
    assert stored.startswith("$2b$")


def test_login_gives_a_working_token(client):
    register(client)
    r = client.post("/auth/login", data={"username": "IvAnKa", "password": PASSWORD})
    assert r.status_code == 200
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/auth/me", headers=headers).json()["username"] == "ivanka"


def test_wrong_password_and_unknown_user_look_the_same(client):
    register(client)
    wrong = client.post("/auth/login", data={"username": "ivanka", "password": "nope"})
    unknown = client.post("/auth/login", data={"username": "ghost", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_bad_tokens_are_rejected(client):
    register(client)
    good = token_header()
    tampered = {"Authorization": good["Authorization"][:-3] + "abc"}
    expired = token_header(expires_in=timedelta(minutes=-1))
    foreign = token_header(secret="someone-elses-key-" + "y" * 32)
    for headers in [{}, tampered, expired, foreign]:
        assert client.get("/auth/me", headers=headers).status_code == 401
    assert client.get("/auth/me", headers=good).status_code == 200
