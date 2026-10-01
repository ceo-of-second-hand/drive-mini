"""Variant 57: sort by creation date (asc/desc) and the .c/.jpg filter (client/sorting.py).

These are the exact functions the file table uses.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from client.sorting import FileFilter, SortOrder, filter_files, sort_by_created

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)


@dataclass
class F:  # stands in for FileOut: only the fields sorting and filtering use
    id: int
    name: str
    created_at: datetime


# Ids, names and creation times are deliberately in three different orders, so a test can only
# pass if the sort really uses the creation time.
FILES = [
    F(1, "b-middle.js", T0 + timedelta(hours=2)),
    F(2, "c-newest.png", T0 + timedelta(hours=5)),
    F(3, "a-oldest.c", T0),
    F(4, "d-second.jpg", T0 + timedelta(hours=1)),
]


def names(files):
    return [f.name for f in files]


def test_sort_by_creation_date_ascending():
    assert names(sort_by_created(FILES, SortOrder.ASC)) == \
        ["a-oldest.c", "d-second.jpg", "b-middle.js", "c-newest.png"]


def test_sort_by_creation_date_descending():
    assert names(sort_by_created(FILES, SortOrder.DESC)) == \
        ["c-newest.png", "b-middle.js", "d-second.jpg", "a-oldest.c"]


def test_sort_is_stable_for_equal_creation_times():
    twins = [F(7, "x.js", T0), F(5, "y.js", T0), F(6, "z.js", T0)]
    assert [f.id for f in sort_by_created(twins, SortOrder.ASC)] == [5, 6, 7]
    assert [f.id for f in sort_by_created(twins, SortOrder.DESC)] == [7, 6, 5]


def test_sort_does_not_change_the_input_list():
    original = list(FILES)
    sort_by_created(FILES, SortOrder.ASC)
    assert FILES == original


def test_filter_all_keeps_everything():
    assert names(filter_files(FILES, FileFilter.ALL)) == names(FILES)


def test_filter_only_c_and_jpg_ignores_case_and_lookalikes():
    files = [F(i, n, T0) for i, n in enumerate([
        "main.c", "MAIN.C", "photo.jpg", "Photo.JPG",          # kept
        "app.js", "logo.png", "photo.jpeg", "main.cpp",       # not .c / .jpg
        "notes.c.txt", "c", "jpg", "archive.jpg.zip",
    ])]
    assert names(filter_files(files, FileFilter.C_JPG)) == ["main.c", "MAIN.C", "photo.jpg", "Photo.JPG"]


def test_filter_then_sort_together():
    assert names(sort_by_created(filter_files(FILES, FileFilter.C_JPG), SortOrder.DESC)) == \
        ["d-second.jpg", "a-oldest.c"]
