"""Variant 57 operations on the file list: sort by creation date and the .c/.jpg filter.

Pure Python (no Qt), so the required variant test checks exactly the code the table uses.
Mirrors SortController / FilterController from the detailed class diagram.
"""
from enum import Enum
from typing import Iterable, Protocol, TypeVar

from common.rules import file_extension


class SortOrder(Enum):
    ASC = "oldest first"
    DESC = "newest first"


class FileFilter(Enum):
    ALL = "All files"
    C_JPG = "Only .c and .jpg"


C_JPG_EXTENSIONS = {"c", "jpg"}  # exactly as the variant says (.jpeg, .cpp etc. don't count)


class HasNameAndCreated(Protocol):
    id: int
    name: str
    created_at: object


F = TypeVar("F", bound=HasNameAndCreated)


def sort_by_created(files: Iterable[F], order: SortOrder) -> list[F]:
    """Files by creation date. Equal dates fall back to id, so the order is always stable."""
    return sorted(files, key=lambda f: (f.created_at, f.id), reverse=order is SortOrder.DESC)


def filter_files(files: Iterable[F], file_filter: FileFilter) -> list[F]:
    """All files, or only .c and .jpg (extension case doesn't matter: photo.JPG counts)."""
    if file_filter is FileFilter.ALL:
        return list(files)
    return [f for f in files if file_extension(f.name) in C_JPG_EXTENSIONS]
