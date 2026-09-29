# Drive Mini

A lite Google Drive: a desktop client for a personal folder on a remote server.
Course project (System Type 2, variant 57).

Features: login, per-user virtual disk, file list with attributes (name, created, modified,
uploader, editor), upload / download / delete, show/hide columns, folder sync with conflict
detection, preview (`.js` as text, `.png` as image), sort by creation date, filter
(all / `.c` + `.jpg`), drag-and-drop upload.

## Stack
Python 3.12 · FastAPI · SQLAlchemy + SQLite · JWT (PyJWT) · bcrypt · PySide6 · httpx · pytest

## Setup
```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env      # then set JWT_SECRET to a random string
```

## Run
```
.venv\Scripts\uvicorn server.main:app --reload     # server, API docs at http://127.0.0.1:8000/docs
.venv\Scripts\python -m client                      # desktop client
.venv\Scripts\pytest -v                             # tests
```

## Settings (`.env`)
| Name           | Meaning                        | Default                  |
|----------------|--------------------------------|--------------------------|
| `JWT_SECRET`   | key used to sign login tokens  | none, must be set        |
| `DATABASE_URL` | SQLAlchemy database URL        | `sqlite:///drivemini.db` |
| `STORAGE_DIR`  | folder for uploaded file bytes | `storage`                |
