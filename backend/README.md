# InquireX

## First-time setup

From PowerShell in this folder, run:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

To run unit tests:

```powershell
python -m pytest tests/
```

Then start the app from the project folder with `run.bat` (double-click it or run `cmd /c run.bat`). Open **http://127.0.0.1:8000/**. FastAPI serves the frontend and API from the same origin, so the local app needs no separate frontend server. The health endpoint is at `/api/health`; interactive API docs are at `/docs`.

For model generated answers, set `GEMINI_API_KEY` in `backend/.env`. Without a key, passage search still works and the app clearly shows source-only results; model-based conflict detection is unavailable.

Scanned PDFs and image uploads use local OCR. Install the Python dependencies from `requirements.txt`, then install the Tesseract OCR engine separately using the [official installation guide](https://tesseract-ocr.github.io/tessdoc/Installation.html). On Windows, the guide points to the UB Mannheim installer. Make sure `tesseract.exe` is on PATH; if installed elsewhere, set `TESSERACT_CMD` in `backend/.env` to its full path. Restart InquireX after installing it. Native-text PDFs do not need OCR. Set `OCR_LANG=eng+hin` if you install both English and Hindi language data.

The first upload downloads Chroma's embedding model and may take a little longer. Uploaded originals and the Chroma database are stored under `backend/app/data/`.

## Username accounts

The login screen asks for a unique username. Entering a new username creates it; entering an existing username restores that account's saved investigations. Accounts and investigation histories are stored in `backend/app/data/accounts.json`, so the backend data directory must persist between restarts. This demo uses username-only access and does not authenticate account ownership; use real authentication before exposing it to other people or the public internet.
