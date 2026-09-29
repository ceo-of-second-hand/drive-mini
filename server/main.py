"""Drive Mini backend (FastAPI)."""
from fastapi import FastAPI

app = FastAPI(title="Drive Mini")


@app.get("/health")
def health():
    return {"status": "ok"}
