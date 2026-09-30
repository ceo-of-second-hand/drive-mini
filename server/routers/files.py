"""The user's virtual disk: list, upload, replace, download, delete.

Textbook REST: POST only creates (an existing name -> 409), PUT replaces the content.
Sorting and filtering are done by the client.
"""
import mimetypes

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from common.rules import MAX_UPLOAD_BYTES, file_extension, name_key, validate_file_name
from common.schemas import ErrorOut, FileOut
from server import storage
from server.db import get_db
from server.models import FileMetadata, User, utcnow
from server.security import get_current_user

router = APIRouter(prefix="/files", tags=["files"], responses={401: {"model": ErrorOut}})


def _read_upload(file: UploadFile) -> bytes:
    """Read the uploaded bytes, refusing anything over the size limit."""
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    return data


def _own_file(file_id: int, user: User, db: Session) -> FileMetadata:
    """The user's file, or 404 (also for other users' files: their ids stay invisible)."""
    record = db.get(FileMetadata, file_id)
    if record is None or record.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found.")
    return record


@router.get("", response_model=list[FileOut])
def list_files(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(FileMetadata).where(FileMetadata.owner_id == user.id)
                      .order_by(FileMetadata.id)).all()


@router.post("", response_model=FileOut, status_code=status.HTTP_201_CREATED,
             responses={409: {"model": ErrorOut}, 413: {"model": ErrorOut}, 422: {"model": ErrorOut}})
def upload_file(file: UploadFile, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    name = file.filename or ""
    error = validate_file_name(name)
    if error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, error)
    conflict = HTTPException(status.HTTP_409_CONFLICT,
                             f"A file named '{name}' already exists. Replace it instead.")
    exists = db.scalar(select(FileMetadata.id).where(FileMetadata.owner_id == user.id,
                                                     FileMetadata.name_key == name_key(name)))
    if exists:
        raise conflict
    data = _read_upload(file)

    record = FileMetadata(
        owner_id=user.id, name=name, name_key=name_key(name), extension=file_extension(name),
        size=len(data),
        mime_type=mimetypes.guess_type(name)[0] or file.content_type or "application/octet-stream",
        uploader_name=user.display_name, editor_name=user.display_name,
        stored_name=storage.new_stored_name(),
    )
    storage.save(user.id, record.stored_name, data)
    db.add(record)
    try:
        db.commit()
    except IntegrityError:  # same name uploaded at the same moment
        db.rollback()
        storage.delete(user.id, record.stored_name)
        raise conflict
    return record


@router.put("/{file_id}", response_model=FileOut,
            responses={404: {"model": ErrorOut}, 413: {"model": ErrorOut}})
def replace_file(file_id: int, file: UploadFile, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """New content for an existing file. Keeps name, created date and uploader;
    updates size, modified date and editor. The uploaded file's own name is ignored."""
    record = _own_file(file_id, user, db)
    data = _read_upload(file)

    old_stored_name = record.stored_name
    record.stored_name = storage.new_stored_name()
    storage.save(user.id, record.stored_name, data)  # new bytes first, old ones removed after
    record.size = len(data)
    # Always a new server time, so sync on other devices sees "changed on server"
    # (it compares modified_at + size with its snapshot of the last sync).
    record.modified_at = utcnow()
    record.editor_name = user.display_name
    db.commit()
    storage.delete(user.id, old_stored_name)
    return record


@router.get("/{file_id}/content", response_class=FileResponse,
            responses={200: {"content": {"application/octet-stream": {}}}, 404: {"model": ErrorOut}})
def download_file(file_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """The file's bytes, for download or preview."""
    record = _own_file(file_id, user, db)
    return FileResponse(storage.path_of(user.id, record.stored_name),
                        media_type=record.mime_type, filename=record.name)


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT,
               responses={404: {"model": ErrorOut}})
def delete_file(file_id: int, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    record = _own_file(file_id, user, db)
    db.delete(record)
    db.commit()
    storage.delete(user.id, record.stored_name)
