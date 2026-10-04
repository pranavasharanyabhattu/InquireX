import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
_backend_env = Path(__file__).resolve().parent.parent / ".env"
if _backend_env.is_file():
    load_dotenv(dotenv_path=_backend_env)

DATA_DIR = Path(__file__).parent / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
CHROMA_DIR = DATA_DIR / "chroma"
REGISTRY_FILE = DATA_DIR / "docs.json"

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")          # "gemini" (free tier) or "anthropic"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL") or ("gemini-3.8-flash" if LLM_PROVIDER == "gemini" else "claude-sonnet-5-5")

TOP_K = 6                 # passages retrieved per question
try:
    MAX_DISTANCE = float(os.getenv("MAX_DISTANCE", "0.75"))  # uncertainty gate
except ValueError:
    MAX_DISTANCE = 0.75
CHUNK_WORDS, CHUNK_OVERLAP = 200, 40
ALLOWED_EXT = {".pdf", ".txt", ".md", ".png", ".jpg", ".jpeg"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5500,http://127.0.0.1:5500,http://localhost:8080,http://localhost:3000",
    ).split(",") if o.strip()
]

for d in (UPLOAD_DIR, CHROMA_DIR):
    d.mkdir(parents=True, exist_ok=True)
