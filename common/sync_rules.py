"""The sync rules table, shared by the desktop client and the server.

The desktop client imports plan() directly (client/sync.py). The web client can't run Python, so
the server runs this same plan() for it (POST /sync/plan). Pure logic, no I/O: the caller lists
the local folder and the drive, and carries out the actions.

How it decides (agreed rules, see specs/02-stage2-plan.md, decision 3):
- The snapshot remembers both sides as they were after the last sync.
- "Changed since last sync" = modified time or size differs from THAT side's snapshot value.
  Server times are only compared with server times, local times with local times, and only for
  equality (never "which is newer").
- Files are matched by name, ignoring case (the keys are name_key(name)).
"""
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from common.schemas import FileOut


class LocalInfo(Protocol):
    """What plan() needs to know about a local file. The unit of mtime_ns is the client's own
    (nanoseconds on desktop, milliseconds in a browser): it's only ever compared with itself."""
    name: str
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
    local: LocalInfo | None
    server: FileOut | None
    entry: Entry | None
    reason: str = ""  # for conflicts: what happened on each side


# --- deciding ---

def plan(local: dict[str, LocalInfo], server: dict[str, FileOut],
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
            # Changed on both sides: maybe one edit that already reached both (e.g. the same folder
            # synced by another client). Identical bytes = no conflict.
            ("changed", "changed"): Kind.COMPARE,
        }.get((here, there), Kind.CONFLICT)  # changed/deleted, deleted/changed
        reason = f"{here} here, {there} on the server" if kind in (Kind.CONFLICT, Kind.COMPARE) else ""
        actions.append(Action(kind, key, l, s, e, reason))
    return actions
