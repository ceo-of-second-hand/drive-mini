"""Server settings, read from environment variables or the git-ignored .env file."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # real environment variables win over .env

TOKEN_LIFETIME_HOURS = 12


@dataclass(frozen=True)
class Settings:
    jwt_secret: str
    database_url: str
    storage_dir: Path


def load_settings() -> Settings:
    jwt_secret = os.getenv("JWT_SECRET", "")
    if not jwt_secret or jwt_secret == "change-me":
        raise RuntimeError("JWT_SECRET is not set. Copy .env.example to .env and set a random value.")
    return Settings(
        jwt_secret=jwt_secret,
        database_url=os.getenv("DATABASE_URL", "sqlite:///drivemini.db"),
        storage_dir=Path(os.getenv("STORAGE_DIR", "storage")),
    )


settings = load_settings()
