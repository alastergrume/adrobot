"""FastAPI application: Keitaro campaign creator and editor."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.keitaro import KeitaroError
from app.routers import api, pages
from app.services.editor import EditorError

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Adrobot Keitaro wrapper", version="1.0.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(api.router)
app.include_router(pages.router)


@app.exception_handler(EditorError)
def editor_error_handler(request: Request, error: EditorError):
    return JSONResponse(status_code=400, content={"detail": str(error)})


@app.exception_handler(KeitaroError)
def keitaro_error_handler(request: Request, error: KeitaroError):
    status = 404 if error.status_code == 404 else 502
    return JSONResponse(status_code=status, content={"detail": str(error)})
