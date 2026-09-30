"""JSON shapes exchanged between the server and the clients (the API contract).

The server uses these as request/response models; the client parses every reply with the
same classes, so a renamed or missing field fails immediately on both sides.
"""
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

from common.rules import validate_password


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=64)
    password: str

    @field_validator("username")
    @classmethod
    def lower_username(cls, value: str) -> str:
        return value.lower()  # usernames are case-insensitive

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        error = validate_password(value)
        if error:
            raise ValueError(error)
        return value


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str


class FileOut(BaseModel):
    """One file in the user's virtual disk, with the attributes shown in the file table.

    Reply-only: clients never send these fields. Times are the server's, in UTC ("...Z").
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    extension: str
    size: int
    mime_type: str
    created_at: datetime
    modified_at: datetime
    uploader_name: str
    editor_name: str

    @field_validator("created_at", "modified_at")
    @classmethod
    def as_utc(cls, value: datetime) -> datetime:
        # SQLite returns naive datetimes; all times are stored in UTC.
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class ErrorOut(BaseModel):
    """Error body, FastAPI's standard format: {"detail": "..."}."""
    detail: str
