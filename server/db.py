"""Database connection and sessions (SQLAlchemy)."""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from server.config import settings

# SQLite objects are used from FastAPI's worker threads, so allow cross-thread use.
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, closed afterwards."""
    with SessionLocal() as db:
        yield db


def init_db() -> None:
    """Create missing tables. No migrations: if models change, delete the dev database."""
    import server.models  # noqa: F401  (registers the tables on Base)
    Base.metadata.create_all(engine)
