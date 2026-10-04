from fastapi import APIRouter

from .. import config
from ..schemas import AskRequest, AskResponse, Conflict, Source
from ..services import answer, conflicts, vectorstore

router = APIRouter()


def to_source(passage: dict, highlight: str | None = None) -> Source:
    return Source(
        doc_name=passage.get("doc_name") or "Unknown document",
        page=passage.get("page"),
        snippet=passage.get("text") or "",
        highlight=highlight,
    )


@router.post("", response_model=AskResponse)
def ask(req: AskRequest):
    summary = answer.is_summary_question(req.question)
    if summary:
        passages = vectorstore.lead_passages(req.document_ids)
    else:
        passages = vectorstore.search(req.question, req.document_ids)

    too_far = not summary and bool(passages) and passages[0]["distance"] > config.MAX_DISTANCE
    if not passages or too_far:
        return AskResponse(
            answer="I couldn't find anything about this in the selected documents.",
            answer_mode="insufficient_evidence",
            confidence="low",
            confidence_reason="No passage was similar enough to the question.",
            insufficient_evidence=True,
        )

    result = answer.generate(req.question, passages)

    multiple_documents = len({p["doc_id"] for p in passages}) > 1
    if result.get("source_only") and multiple_documents:
        found, conflict_check_available = [], False
    else:
        found, conflict_check_available = conflicts.find_conflicts(req.question, passages)

    return AskResponse(
        answer=result["answer"],
        answer_mode="source_only" if result.get("source_only") else "generated",
        fallback_reason=result.get("fallback_reason"),
        confidence=result["confidence"],
        confidence_reason=result["confidence_reason"],
        conflict_check_available=conflict_check_available,
        sources=[to_source(p, h) for p, h in result["used"]],
        conflicts=[Conflict(summary=s, sources=[to_source(p) for p in group]) for s, group in found],
    )