"""Shared rules (common/rules.py): the checks both the server and the client rely on."""
import pytest

from common.rules import file_extension, name_key, validate_file_name, validate_password


@pytest.mark.parametrize("name", ["notes.js", "photo.JPG", "my report v2.c", "звіт.js", "Makefile"])
def test_normal_file_names_are_accepted(name):
    assert validate_file_name(name) is None


@pytest.mark.parametrize("name", [
    "", "   ", "a:b.js", "what?.png", "../x.js", "a\\b.js", "CON", "con.txt", "x.", "x ", "a" * 256,
])
def test_bad_file_names_are_rejected(name):
    assert validate_file_name(name) is not None


def test_password_limit_is_counted_in_bytes():
    assert validate_password("x" * 72) is None
    assert validate_password("x" * 73) is not None
    assert validate_password("ї" * 37) is not None  # 37 letters, but 74 bytes in UTF-8
    assert validate_password("") is not None


def test_names_are_case_insensitive_and_extensions_lower_case():
    assert name_key("A.JS") == name_key("a.js")
    assert file_extension("photo.JPG") == "jpg"
    assert file_extension("main.c") == "c"
    assert file_extension("Makefile") == ""
    assert file_extension(".gitignore") == ""
