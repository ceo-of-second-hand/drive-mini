"""Database tables: users and the metadata of their files (file bytes live on disk)."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.db import Base


def utcnow() -> datetime:
    """The single clock for all file and token times: the server's, in UTC.

    Clients never send times, so every device sees the same values, and the time zone of
    any PC doesn't matter. created_at = upload to the drive (not the file's date on the PC);
    modified_at = last upload/replace. Clients convert to local time only for display.
    """
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True)
    display_name: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(60))  # bcrypt, never the password
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    files: Mapped[list["FileMetadata"]] = relationship(back_populates="owner")


class FileMetadata(Base):
    """One file on a user's virtual disk."""
    __tablename__ = "files"
    # One name per disk, ignoring case (name_key = casefolded name).
    # sqlite_autoincrement: ids are never reused, even after the highest-id file is deleted,
    # so an old id can't silently point at a different file, and a higher id = added later.
    # (Applies when the table is created: an existing dev database must be deleted once.)
    __table_args__ = (UniqueConstraint("owner_id", "name_key"), {"sqlite_autoincrement": True})

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    name_key: Mapped[str] = mapped_column(String(255))
    extension: Mapped[str] = mapped_column(String(32))
    size: Mapped[int]
    mime_type: Mapped[str] = mapped_column(String(100))
    # default=utcnow (the function, no parentheses) runs on INSERT for each new row;
    # updates never use it, so replace sets modified_at explicitly.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    uploader_name: Mapped[str] = mapped_column(String(64))
    editor_name: Mapped[str] = mapped_column(String(64))
    # Random id used as the file name on disk, so user-given names never touch the file system.
    stored_name: Mapped[str] = mapped_column(String(32), unique=True)

    owner: Mapped[User] = relationship(back_populates="files")
