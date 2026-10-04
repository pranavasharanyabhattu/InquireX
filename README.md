# InquireX

InquireX is a local document investigation workspace. Upload PDFs, text files, Markdown files, or images; search their passages; ask questions grounded in retrieved text; and inspect the cited passages and possible disagreements between documents.

## Features

- Local document extraction and indexing with page-level citations.
- OCR for scanned PDFs and images through Tesseract (installed separately).
- Semantic passage search using ChromaDB's built-in embedding function.
- Optional Gemini or Anthropic generated answers; without an API key, the app still supports search and source-only fallback responses.
- Multiple username-based investigation histories stored on the local backend.
- A static frontend served by FastAPI, so the standard local setup uses one server.

## Requirements

- Windows: Python 3.11 or newer and the `py` launcher. Other platforms can use Python 3.11+ and `python`.
- Tesseract OCR is optional for native-text PDFs and text files, but required for scanned PDFs and image uploads.
- A Gemini API key is optional and enables generated answers and model-assisted conflict checks. Anthropic is also supported when its SDK is installed.

## Quick start (Windows)

From the project folder, create the virtual environment and install dependencies:

```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edit `backend/.env` and set `GEMINI_API_KEY` to enable Gemini. Then return to the project folder and run:

```powershell
cd ..
run.bat
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). FastAPI serves the UI, API, and interactive API docs at `/docs`. The health endpoint is `/api/health`.

To start without the batch file, run from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### macOS and Linux

From the repository root:

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
test -f .env || cp .env.example .env
python -m uvicorn app.main:app --reload
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000). The Windows `run.bat` launcher is not used on these platforms.

## Configuration

Configuration is read from `backend/.env` (when starting from `backend/`) or the process environment:

| Variable | Default | Purpose |
| --- | --- | --- |
| `LLM_PROVIDER` | `gemini` | `gemini` or `anthropic` |
| `LLM_MODEL` | Provider-specific | Model identifier accepted by the selected provider |
| `GEMINI_API_KEY` | unset | Enables Gemini answer generation |
| `ANTHROPIC_API_KEY` | unset | Enables Anthropic when `LLM_PROVIDER=anthropic` |
| `MAX_DISTANCE` | `0.75` | Maximum cosine distance accepted by the answer evidence gate |
| `ALLOWED_ORIGINS` | Local development origins | Comma-separated CORS origins for a separately hosted frontend |
| `TESSERACT_CMD` | Tesseract on `PATH` | Optional full path to the Tesseract executable |
| `OCR_LANG` | `eng` | Tesseract language codes, e.g. `eng+hin` when matching language data is installed |

The checked-in `backend/.env.example` is a template; never put real keys in tracked files. For Anthropic, install the optional dependency with `python -m pip install anthropic`.

## How it works

1. The frontend uploads supported files to `POST /api/documents`.
2. The backend extracts text page by page. Image-only PDF pages and image files use local Tesseract OCR.
3. Text is split into overlapping chunks and stored in a persistent ChromaDB collection. A small JSON registry stores document names and page counts.
4. Search retrieves the closest passages. Questions use an evidence distance threshold before any answer is generated.
5. When a provider key is configured, the model returns an answer and passage references as JSON. The API validates references and returns citations; provider failures use a clearly labeled source-only fallback.
6. A second model call checks retrieved passages from multiple documents for material contradictions.

The browser app and API are served from the same origin by default. The API routes are:

| Route | Method | Purpose |
| --- | --- | --- |
| `/api/health` | `GET` | Service, model-key, and OCR status |
| `/api/documents` | `GET` | List documents in the local registry |
| `/api/documents` | `POST` | Upload one or more files (`multipart/form-data`, field `files`) |
| `/api/documents/{doc_id}` | `DELETE` | Delete an indexed document |
| `/api/accounts/login` | `POST` | Open or create a username-based local account |
| `/api/accounts/{username}` | `PUT` | Save an account's investigation history |
| `/api/search` | `POST` | Search passages, optionally filtered by document IDs |
| `/api/ask` | `POST` | Retrieve evidence and answer a question |

## Local data and privacy

Runtime data is stored under `backend/app/data/`: uploaded originals, the ChromaDB index, the document registry, and account histories. This folder is ignored by Git. Back it up separately if you need to preserve investigations, and stop the server before moving or replacing its data.

Username accounts are a convenience for a local/demo workspace, not authentication. The API has no login session or access-control layer; anyone who can reach the backend can call its routes. Do not expose it to an untrusted network or store sensitive documents without adding real authentication and authorization.

## Troubleshooting

- **The app does not start:** install dependencies from `backend/requirements.txt` using the same Python environment that launches Uvicorn.
- **Generated answers are unavailable:** confirm the provider and key in `backend/.env`, then restart the server. Search and source-only fallback remain available.
- **A model name is rejected:** set `LLM_MODEL` to a model currently available to your provider and API key.
- **Scanned PDFs or images fail:** install Tesseract and the required language data, ensure it is on `PATH`, or set `TESSERACT_CMD`; restart the server after changing OCR configuration.
- **The first upload is slow:** ChromaDB may need to download its embedding model the first time it indexes content.
- **A frontend hosted separately cannot call the API:** set `ALLOWED_ORIGINS` to the exact frontend origin and configure `window.INQUIREX_API_BASE` before `frontend/app.js` loads.

## Testing

Run unit tests from the `backend/` directory:

```powershell
python -m pytest tests/
```

## Project layout

```text
backend/
  app/
    routes/       FastAPI route handlers
    services/     Extraction, chunking, retrieval, answers, and accounts
    config.py     Environment and local data paths
  tests/          Unit test suite
  .env.example    Safe configuration template
  requirements.txt
frontend/
  index.html      Single-page interface
  app.js          UI state and API calls
  styles.css      Workspace styling
run.bat           Windows local launcher
```
