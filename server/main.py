"""Drive Mini backend (FastAPI)."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from server.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Drive Mini", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    """Turn FastAPI's list of input errors into one readable line, so every error
    body matches ErrorOut: {"detail": "..."}."""
    parts = []
    for err in exc.errors():
        field = ".".join(str(p) for p in err["loc"] if p not in ("body", "query", "path", "form"))
        message = err["msg"].removeprefix("Value error, ")
        parts.append(f"{field}: {message}" if field else message)
    return JSONResponse(status_code=422, content={"detail": "; ".join(parts)})


@app.get("/health")
def health():
    return {"status": "ok"}
