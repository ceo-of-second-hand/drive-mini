"""File bytes on disk: storage/<user id>/<stored name>.

Stored names are random ids, so user-given file names never reach the file system
(no clashes, no path tricks). The real names live only in the database.
"""
import os
import uuid
from pathlib import Path

from server.config import settings


def new_stored_name() -> str:
    return uuid.uuid4().hex


def path_of(user_id: int, stored_name: str) -> Path:
    return settings.storage_dir / str(user_id) / stored_name


def save(user_id: int, stored_name: str, data: bytes) -> None:
    """Write via a temporary file, so a crash never leaves a half-written file."""
    path = path_of(user_id, stored_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def delete(user_id: int, stored_name: str) -> None:
    path_of(user_id, stored_name).unlink(missing_ok=True)
