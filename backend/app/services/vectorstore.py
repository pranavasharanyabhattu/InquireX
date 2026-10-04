import json
from threading import Lock
import chromadb

from .. import config

_client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
_col = _client.get_or_create_collection("chunks", metadata={"hnsw:space": "cosine"})
_registry_lock = Lock()


def add_chunks(doc_id: str, doc_name: str, chunks: list[tuple[int, str]]) -> None:
    if not chunks:
        return
    _col.add(
        ids=[f"{doc_id}-{i}" for i in range(len(chunks))],
        documents=[text for _, text in chunks],
        metadatas=[{"doc_id": doc_id, "doc_name": doc_name, "page": page} for page, _ in chunks],
    )


def search(question: str, doc_ids: list[str], k: int = config.TOP_K) -> list[dict]:
    if _col.count() == 0:
        return []
    where = {"doc_id": {"$in": doc_ids}} if doc_ids else None
    res = _col.query(query_texts=[question], n_results=k, where=where)
    if not res or not res.get("documents") or not res["documents"][0]:
        return []
    return [
        {**meta, "text": text, "distance": dist}
        for text, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
    ]


def lead_passages(doc_ids: list[str], per_doc: int = 2, max_docs: int = 6) -> list[dict]:
    ids = doc_ids or [d["id"] for d in _load()]
    passages = []
    for doc_id in ids[:max_docs]:
        res = _col.get(ids=[f"{doc_id}-{i}" for i in range(per_doc)], include=["documents", "metadatas"])
        for text, meta in zip(res.get("documents") or [], res.get("metadatas") or []):
            passages.append({**meta, "text": text, "distance": 0.0})
    return passages


def delete_chunks(doc_id: str) -> None:
    _col.delete(where={"doc_id": doc_id})


def _load() -> list[dict]:
    if not config.REGISTRY_FILE.exists():
        return []
    try:
        data = json.loads(config.REGISTRY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def list_docs() -> list[dict]:
    return _load()


def register_doc(doc: dict) -> None:
    with _registry_lock:
        docs = _load()
        docs.append(doc)
        _write_registry(docs)


def unregister_doc(doc_id: str) -> bool:
    with _registry_lock:
        docs = _load()
        kept = [d for d in docs if d["id"] != doc_id]
        if len(kept) == len(docs):
            return False
        _write_registry(kept)
        return True


def _write_registry(docs: list[dict]) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp = config.REGISTRY_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(docs, ensure_ascii=False), encoding="utf-8")
    temp.replace(config.REGISTRY_FILE)