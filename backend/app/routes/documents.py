import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from .. import config
from ..schemas import DocInfo
from ..services import vectorstore
from ..services.chunking import chunk_pages
from ..services.extract import extract_pages

router = APIRouter()


@router.get("", response_model=list[DocInfo])
def list_documents():
    return vectorstore.list_docs()


def _remove_document_data(doc_id: str, name: str) -> None:
    """Best-effort rollback of one document's registry, index, and upload."""
    try:
        vectorstore.unregister_doc(doc_id)
    except Exception as e:
        print(f"[documents] failed to remove registry entry for {name}: {e}")
    try:
        vectorstore.delete_chunks(doc_id)
    except Exception as e:
        print(f"[documents] failed to remove index for {name}: {e}")
    (config.UPLOAD_DIR / f"{doc_id}_{name}").unlink(missing_ok=True)


def _upload_one(f: UploadFile) -> dict:
    name = Path(f.filename or "file").name
    if Path(name).suffix.lower() not in config.ALLOWED_EXT:
        raise HTTPException(400, f"{name}: unsupported file type.")

    doc_id = uuid.uuid4().hex[:12]
    path = config.UPLOAD_DIR / f"{doc_id}_{name}"
    total = 0
    try:
        with open(path, "wb") as out:
            while True:
                chunk = f.file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > config.MAX_UPLOAD_BYTES:
                    raise HTTPException(413, f"{name} is larger than the 50 MB upload limit.")
                out.write(chunk)
    except HTTPException:
        path.unlink(missing_ok=True)
        raise
    except Exception as e:
        path.unlink(missing_ok=True)
        raise HTTPException(500, f"Could not save {name}: {e}") from e

    try:
        page_count, pages = extract_pages(path)
    except (ValueError, OSError) as e:
        path.unlink(missing_ok=True)
        raise HTTPException(400, str(e) or f"Could not read {name}.") from e
    except Exception as e:
        path.unlink(missing_ok=True)
        raise HTTPException(400, f"Could not process {name}: {e}") from e

    try:
        chunks = chunk_pages(pages)
        if not chunks:
            raise ValueError(f"No readable text passages could be extracted from {name}.")
        vectorstore.add_chunks(doc_id, name, chunks)
        doc = {"id": doc_id, "name": name, "pages": page_count}
        vectorstore.register_doc(doc)
        return doc
    except Exception as e:
        _remove_document_data(doc_id, name)
        detail = str(e) if isinstance(e, ValueError) else f"Could not index {name}. Please try again."
        raise HTTPException(400 if isinstance(e, ValueError) else 500, detail) from e


@router.post("", response_model=list[DocInfo])
def upload_documents(files: list[UploadFile] = File(...)):
    added = []
    try:
        for uploaded_file in files:
            added.append(_upload_one(uploaded_file))
    except Exception:
        for doc in added:
            _remove_document_data(doc["id"], doc["name"])
        raise
    return added


@router.delete("/{doc_id}")
def delete_document(doc_id: str):
    clean_id = doc_id.strip()
    if not clean_id.isalnum():
        raise HTTPException(400, "Invalid document ID.")
    if not vectorstore.unregister_doc(clean_id):
        raise HTTPException(404, "Document not found.")
    vectorstore.delete_chunks(clean_id)
    for path in config.UPLOAD_DIR.glob(f"{clean_id}_*"):
        path.unlink(missing_ok=True)
    return {"ok": True}
