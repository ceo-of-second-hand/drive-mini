"""Folder sync (SyncService): make a chosen local folder and the drive match.

How it decides (agreed rules, see specs/02-stage2-plan.md, decision 3):
- A *snapshot* remembers both sides as they were after the last sync. It lives in
  %APPDATA%\\DriveMini\\sync\\ (one JSON per user + server + folder), never in the synced folder.
- "Changed since last sync" = modified time or size differs from THAT side's snapshot value.
  Server times are only compared with server times, laptop times with laptop times, and only
  for equality (never "which is newer").
- Files are matched by name, ignoring case. Ids always come from the fresh server list fetched at
  the start of each sync, never from the snapshot (which stores no ids).
- Conflicts change nothing; the user resolves them with resolve(): keep mine / keep server's.
"""
import hashlib
import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse

from client.api import ApiError, RestApiClient
from common.rules import MAX_UPLOAD_BYTES, name_key, validate_file_name
from common.schemas import FileOut

IGNORED_NAMES = {"desktop.ini", "thumbs.db"}  # created by Windows itself in folders
TEMP_PREFIX = ".drivemini-"  # our own temporary files while downloading


# --- data ---

@dataclass
class LocalFile:
    name: str
    path: Path
    mtime_ns: int
    size: int


@dataclass
class Entry:
    """One file in the snapshot: both sides as they were after the last sync."""
    name: str
    server_modified: str  # ISO time from the server (compared only with server times)
    server_size: int
    local_mtime_ns: int  # from this PC's file system (compared only with this PC's times)
    local_size: int


class Kind(Enum):
    UPLOAD = "upload"
    DOWNLOAD = "download"
    COMPARE = "compare bytes"
    REPLACE = "replace on server"
    DELETE_SERVER = "delete on server"
    DELETE_LOCAL = "delete locally"
    FORGET = "forget"
    CONFLICT = "conflict"
    NOTHING = "nothing"


@dataclass
class Action:
    kind: Kind
    key: str
    local: LocalFile | None
    server: FileOut | None
    entry: Entry | None
    reason: str = ""  # for conflicts: what happened on each side


@dataclass
class Conflict:
    name: str
    key: str
    reason: str


@dataclass
class SyncResult:
    uploaded: list[str] = field(default_factory=list)
    downloaded: list[str] = field(default_factory=list)
    deleted_on_server: list[str] = field(default_factory=list)
    deleted_locally: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)

    @property
    def nothing_happened(self) -> bool:
        return not any(asdict(self).values())


# --- snapshot ---

def account_id(server_url: str, username: str) -> str:
    """'ivanka@127.0.0.1_8000': one drive = one user on one server."""
    host = (urlparse(str(server_url)).netloc or "server").replace(":", "_")
    return f"{username}@{host}"


def snapshot_path(server_url: str, username: str, folder: Path) -> Path:
    """One snapshot per account + folder, in %APPDATA%\\DriveMini\\sync\\."""
    folder_id = hashlib.sha1(str(Path(folder).resolve()).casefold().encode()).hexdigest()[:10]
    base = Path(os.environ.get("APPDATA") or Path.home())
    return base / "DriveMini" / "sync" / f"{account_id(server_url, username)}-{folder_id}.json"


def unlink_folder(server_url: str, username: str, folder: Path) -> None:
    """Stop syncing a folder: forget its snapshot. Its files stay as they are; if it is chosen
    again later, that sync is a first sync (compare by name and bytes, nothing is deleted)."""
    snapshot_path(server_url, username, folder).unlink(missing_ok=True)


def load_snapshot(path: Path) -> dict[str, Entry]:
    """Missing or unreadable snapshot = first sync (every file is 'new')."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {key: Entry(**value) for key, value in data["files"].items()}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def save_snapshot(path: Path, entries: dict[str, Entry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"files": {key: asdict(entry) for key, entry in sorted(entries.items())}}
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def make_entry(server: FileOut, local: LocalFile) -> Entry:
    return Entry(name=server.name, server_modified=server.modified_at.isoformat(),
                 server_size=server.size, local_mtime_ns=local.mtime_ns, local_size=local.size)


# --- local folder ---

def stat_local(path: Path) -> LocalFile:
    st = path.stat()
    return LocalFile(path.name, path, st.st_mtime_ns, st.st_size)


def scan(folder: Path) -> tuple[dict[str, LocalFile], dict[str, str]]:
    """Top-level files only (the drive has no folders). Returns (files, skipped: key -> reason)."""
    files, skipped = {}, {}
    for item in sorted(Path(folder).iterdir()):
        name = item.name
        if name.casefold() in IGNORED_NAMES or name.startswith(("~$", TEMP_PREFIX)):
            continue  # Windows/Office clutter and our own temp files: silently ignored
        if item.is_dir():
            skipped[name_key(name)] = f"{name}: subfolders aren't synced"
            continue
        problem = validate_file_name(name)
        if problem is None and item.stat().st_size > MAX_UPLOAD_BYTES:
            problem = f"larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB"
        if problem:
            skipped[name_key(name)] = f"{name}: {problem}"
            continue
        files[name_key(name)] = stat_local(item)
    return files, skipped


def write_atomic(path: Path, data: bytes) -> None:
    """Write via a temp file in the same folder, so a crash never leaves half a file."""
    tmp = path.with_name(f"{TEMP_PREFIX}{uuid.uuid4().hex}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


# --- deciding ---

def plan(local: dict[str, LocalFile], server: dict[str, FileOut],
         snapshot: dict[str, Entry]) -> list[Action]:
    """One action per file name: the rules table, nothing else (no I/O)."""
    actions = []
    for key in sorted(set(local) | set(server) | set(snapshot)):
        l, s, e = local.get(key), server.get(key), snapshot.get(key)
        if e is None:  # not seen at the last sync (or first sync)
            kind = Kind.COMPARE if (l and s) else Kind.UPLOAD if l else Kind.DOWNLOAD
            actions.append(Action(kind, key, l, s, e))
            continue
        here = "deleted" if l is None else \
            "same" if (l.mtime_ns, l.size) == (e.local_mtime_ns, e.local_size) else "changed"
        there = "deleted" if s is None else \
            "same" if (s.modified_at.isoformat(), s.size) == (e.server_modified, e.server_size) else "changed"
        kind = {
            ("same", "same"): Kind.NOTHING,
            ("changed", "same"): Kind.REPLACE,
            ("same", "changed"): Kind.DOWNLOAD,
            ("deleted", "same"): Kind.DELETE_SERVER,
            ("same", "deleted"): Kind.DELETE_LOCAL,
            ("deleted", "deleted"): Kind.FORGET,
        }.get((here, there), Kind.CONFLICT)  # changed/changed, changed/deleted, deleted/changed
        reason = f"{here} here, {there} on the server" if kind is Kind.CONFLICT else ""
        actions.append(Action(kind, key, l, s, e, reason))
    return actions


# --- doing ---

class FolderSync:
    """Sync one local folder with the logged-in user's drive."""

    def __init__(self, api: RestApiClient, folder: Path, username: str):
        self.api = api
        self.folder = Path(folder)
        self.snapshot_file = snapshot_path(api.base_url, username, self.folder)

    def run(self) -> SyncResult:
        local, skipped = scan(self.folder)
        server = {name_key(f.name): f for f in self.api.list_files()}  # fresh list, fresh ids
        old = load_snapshot(self.snapshot_file)
        result = SyncResult(skipped=list(skipped.values()))
        new: dict[str, Entry] = {k: old[k] for k in skipped if k in old}  # skipped: leave as it was

        actions = plan({k: v for k, v in local.items() if k not in skipped},
                       {k: v for k, v in server.items() if k not in skipped},
                       {k: v for k, v in old.items() if k not in skipped})
        for action in actions:
            name = (action.local or action.server or action.entry).name
            try:
                entry = self._do(action, result)
            except (ApiError, OSError) as exc:
                result.errors.append(f"{name}: {getattr(exc, 'detail', exc)}")
                entry = action.entry  # keep the old state, so the next sync retries it
            if entry is not None:
                new[action.key] = entry
        save_snapshot(self.snapshot_file, new)
        return result

    def _do(self, a: Action, result: SyncResult) -> Entry | None:
        """Carry out one action; return the file's new snapshot entry (None = not tracked)."""
        if a.kind is Kind.NOTHING:
            return a.entry
        if a.kind is Kind.FORGET:
            return None
        if a.kind is Kind.CONFLICT:
            result.conflicts.append(Conflict((a.local or a.server or a.entry).name, a.key, a.reason))
            return a.entry  # unchanged until the user resolves it
        # Each result line is added only AFTER the action succeeded, so a failure is never
        # reported as done.
        if a.kind is Kind.UPLOAD:
            entry = make_entry(self.api.upload(a.local.path), a.local)
            result.uploaded.append(a.local.name)
            return entry
        if a.kind is Kind.REPLACE:
            entry = make_entry(self.api.replace(a.server.id, a.local.path), a.local)
            result.uploaded.append(f"{a.local.name} (updated)")
            return entry
        if a.kind is Kind.DOWNLOAD:
            target = a.local.path if a.local else self.folder / a.server.name
            write_atomic(target, self.api.download(a.server.id))
            result.downloaded.append(a.server.name + (" (updated)" if a.local else ""))
            return make_entry(a.server, stat_local(target))
        if a.kind is Kind.COMPARE:  # same name on both sides, never synced: same content?
            if self.api.download(a.server.id) == a.local.path.read_bytes():
                return make_entry(a.server, a.local)
            result.conflicts.append(Conflict(a.local.name, a.key, "different content on both sides"))
            return None
        if a.kind is Kind.DELETE_SERVER:
            self.api.delete(a.server.id)
            result.deleted_on_server.append(a.server.name)
            return None
        if a.kind is Kind.DELETE_LOCAL:
            a.local.path.unlink()
            result.deleted_locally.append(a.local.name)
            return None
        raise ValueError(a.kind)

    def resolve(self, conflict: Conflict, keep: str) -> str:
        """keep = "mine" or "server". Uses the current state of both sides, then updates the
        snapshot entry for this file. Returns a short description of what was done."""
        local = next((f for k, f in scan(self.folder)[0].items() if k == conflict.key), None)
        server = next((f for f in self.api.list_files() if name_key(f.name) == conflict.key), None)
        entries = load_snapshot(self.snapshot_file)
        entries.pop(conflict.key, None)
        if local is None and server is None:  # gone on both sides meanwhile: nothing to keep
            save_snapshot(self.snapshot_file, entries)
            return "it no longer exists on either side"
        if keep == "mine":
            if local and server:
                done, entry = "replaced the server's copy", make_entry(self.api.replace(server.id, local.path), local)
            elif local:
                done, entry = "uploaded yours", make_entry(self.api.upload(local.path), local)
            else:
                self.api.delete(server.id)
                done, entry = "deleted it on the server", None
        else:
            if server:
                target = local.path if local else self.folder / server.name
                write_atomic(target, self.api.download(server.id))
                done, entry = "downloaded the server's copy", make_entry(server, stat_local(target))
            else:
                local.path.unlink()
                done, entry = "deleted your copy", None
        if entry is not None:
            entries[conflict.key] = entry
        save_snapshot(self.snapshot_file, entries)
        return done
