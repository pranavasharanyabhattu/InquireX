from fastapi import APIRouter

from ..schemas import SearchRequest
from ..services import vectorstore

router = APIRouter()


@router.post("")
def search_documents(req: SearchRequest):
    passages = vectorstore.search(req.query, req.document_ids, k=12)
    return {
        "query": req.query,
        "results": [
            {
                "doc_name": p["doc_name"],
                "document_id": p["doc_id"],
                "page": p["page"],
                "snippet": p["text"],
                "distance": round(p["distance"], 4),
            }
            for p in passages
        ],
    }
