"""Folder sync for clients that can't run Python (the web client).

The client sends what's in its folder and its snapshot; the server adds its fresh file list and
answers with the actions from the shared rules table, common/sync_rules.py (the same plan() the
desktop client imports). Carrying them out (uploads, downloads, local deletes) stays on the
client: only it can touch the folder.
"""
from datetime import timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from common.rules import MAX_UPLOAD_BYTES, name_key, validate_file_name
from common.schemas import ErrorOut, FileOut, SyncAction, SyncPlanIn, SyncPlanOut
from common.sync_rules import Entry, Kind, plan
from server.db import get_db
from server.models import FileMetadata, User
from server.security import get_current_user

router = APIRouter(prefix="/sync", tags=["sync"], responses={401: {"model": ErrorOut}})


class _Local:
    """A local file as plan() sees it (LocalInfo)."""

    def __init__(self, name: str, mtime: int, size: int):
        self.name, self.mtime_ns, self.size = name, mtime, size


@router.post("/plan", response_model=SyncPlanOut)
def sync_plan(body: SyncPlanIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """What a sync should do, file by file. Nothing is changed here."""
    records = db.scalars(select(FileMetadata).where(FileMetadata.owner_id == user.id)).all()
    server = {name_key(r.name): FileOut.model_validate(r) for r in records}  # fresh list, fresh ids

    # Local files the server would refuse are skipped: they stay as they are on both sides.
    local, skipped = {}, {}
    for f in body.local:
        problem = validate_file_name(f.name)
        if problem is None and f.size > MAX_UPLOAD_BYTES:
            problem = f"larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB"
        if problem:
            skipped[name_key(f.name)] = f"{f.name}: {problem}"
        else:
            local[name_key(f.name)] = _Local(f.name, f.mtime, f.size)

    # The client stores server times as the JSON it got ("...Z"); plan() compares them with
    # FileOut.modified_at.isoformat() ("...+00:00"), so both are brought to the same form here.
    snapshot = {name_key(e.name): Entry(e.name, e.server_modified.astimezone(timezone.utc).isoformat(),
                                        e.server_size, e.local_mtime, e.local_size)
                for e in body.snapshot}

    actions = plan({k: v for k, v in local.items() if k not in skipped},
                   {k: v for k, v in server.items() if k not in skipped},
                   {k: v for k, v in snapshot.items() if k not in skipped})
    return SyncPlanOut(
        actions=[SyncAction(kind=_KIND[a.kind], key=a.key, name=(a.local or a.server or a.entry).name,
                            file=a.server, reason=a.reason) for a in actions],
        skipped=list(skipped.values()),
    )


_KIND = {Kind.UPLOAD: "upload", Kind.DOWNLOAD: "download", Kind.COMPARE: "compare",
         Kind.REPLACE: "replace", Kind.DELETE_SERVER: "delete_server", Kind.DELETE_LOCAL: "delete_local",
         Kind.FORGET: "forget", Kind.CONFLICT: "conflict", Kind.NOTHING: "nothing"}
