"""Limits and checks shared by the server (enforces) and the client (pre-checks)."""

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_PASSWORD_BYTES = 72  # bcrypt ignores anything longer
MAX_FILE_NAME_LENGTH = 255

FORBIDDEN_NAME_CHARS = set('/\\:*?"<>|')
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL",
                  *(f"COM{i}" for i in range(1, 10)),
                  *(f"LPT{i}" for i in range(1, 10))}


def validate_file_name(name: str) -> str | None:
    """Return an error message, or None if the name is allowed.

    The rules keep every stored name valid as a Windows file name, so any file on the
    server can be downloaded or synced into a local folder.
    """
    if not name or not name.strip():
        return "File name is empty."
    if len(name) > MAX_FILE_NAME_LENGTH:
        return f"File name is longer than {MAX_FILE_NAME_LENGTH} characters."
    bad = sorted({c for c in name if c in FORBIDDEN_NAME_CHARS or ord(c) < 32})
    if bad:
        shown = " ".join(c if ord(c) >= 32 else "\\x%02x" % ord(c) for c in bad)
        return f"File name contains characters that are not allowed: {shown}"
    if name[-1] in ". ":
        return "File name cannot end with a dot or a space."
    if name.split(".")[0].upper() in RESERVED_NAMES:
        return f"'{name}' is a reserved name on Windows."
    return None


def validate_password(password: str) -> str | None:
    """Return an error message, or None if the password is allowed."""
    if not password:
        return "Password is empty."
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return f"Password is longer than {MAX_PASSWORD_BYTES} bytes."
    return None


def name_key(name: str) -> str:
    """Case-insensitive form of a file name: 'A.js' and 'a.js' are the same file,
    because a Windows folder cannot hold both."""
    return name.casefold()


def file_extension(name: str) -> str:
    """Lower-case extension without the dot: 'photo.JPG' -> 'jpg', 'Makefile' -> ''."""
    stem, dot, ext = name.rpartition(".")
    return ext.lower() if dot and stem else ""
