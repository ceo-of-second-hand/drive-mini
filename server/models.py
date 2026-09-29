"""Database tables: users and the metadata of their files (file bytes live on disk)."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.db import Base


def utcnow() -> datetime:
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
    __table_args__ = (UniqueConstraint("owner_id", "name_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    name_key: Mapped[str] = mapped_column(String(255))
    extension: Mapped[str] = mapped_column(String(32))
    size: Mapped[int]
    mime_type: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    uploader_name: Mapped[str] = mapped_column(String(64))
    editor_name: Mapped[str] = mapped_column(String(64))
    # Random id used as the file name on disk, so user-given names never touch the file system.
    stored_name: Mapped[str] = mapped_column(String(32), unique=True)

    owner: Mapped[User] = relationship(back_populates="files")
