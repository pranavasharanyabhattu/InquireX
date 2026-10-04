from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from . import config
from .routes import accounts, ask, documents, search
from .services import extract, llm

app = FastAPI(title="Document Investigator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"])
app.include_router(ask.router, prefix="/api/ask", tags=["ask"])
app.include_router(search.router, prefix="/api/search", tags=["search"])

@app.get("/api/health")
def health():
    return {
        "ok": True,
        "llm_configured": llm.available(),
        "provider": config.LLM_PROVIDER,
        "model": config.LLM_MODEL,
        "ocr_available": extract.ocr_available(),
    }


FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
