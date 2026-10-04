import re

from . import llm

SYSTEM = """You answer questions using ONLY the numbered passages provided.
If the passages do not contain the answer, say so plainly. Never use outside knowledge.
Write like a thoughtful research assistant: answer the question directly in a few clear sentences,
use plain language, and avoid dumping or restating whole passages. If passages disagree, say that
they disagree and explain what each source says. Do not choose a winner or assume an amendment
overrides an earlier document unless the passages themselves establish that relationship.
Every factual statement must be supported by a passage listed in "used". If the evidence is weak,
incomplete, or contradictory, say that plainly and use low or medium confidence.
Reply with JSON only, in this shape:
{"answer": str,
 "confidence": "high" | "medium" | "low",
 "confidence_reason": str,
 "used": [{"n": int, "highlight": str}]}
"used" lists the passages that support the answer. "highlight" must be an exact phrase copied from that passage."""


def format_passages(passages: list[dict]) -> str:
    return "\n\n".join(
        f"[{i}] ({p['doc_name']}, page {p['page']})\n{p['text']}" for i, p in enumerate(passages, 1)
    )


def _is_summary_question(question: str) -> bool:
    q = question.casefold()
    return any(term in q for term in (
        "summarize", "summary", "main points", "key points", "overview",
        "what is this document about", "what are these documents about",
        "what is the document about", "what are the documents about",
    ))


def _excerpt(text: str, limit: int = 380) -> str:
    clean = " ".join(text.split())
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    excerpt = " ".join(sentences[:2]).strip()
    if len(excerpt) > limit:
        excerpt = excerpt[:limit].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
    return excerpt or clean[:limit]


def _source_only_summary(passages: list[dict]) -> tuple[str, list[tuple[dict, None]]]:
    """Build a clearly labeled extractive fallback from distinct cited pages."""
    chosen = []
    seen_pages = set()
    for passage in passages:
        key = (passage.get("doc_id"), passage.get("page"))
        if key in seen_pages:
            continue
        seen_pages.add(key)
        excerpt = _excerpt(passage["text"])
        if excerpt:
            chosen.append((passage, excerpt))
        if len(chosen) == 4:
            break

    bullets = [
        f"• {excerpt} ({passage['doc_name']}, p. {passage['page']})"
        for passage, excerpt in chosen
    ]
    answer = (
        "I can’t synthesize the full set of documents right now. Here are short excerpts "
        "from the closest matching pages; they are source text, not a generated summary:\n\n"
        + "\n\n".join(bullets)
    )
    return answer, [(passage, None) for passage, _ in chosen]


def generate(question: str, passages: list[dict]) -> dict:
    """Returns answer metadata and cited passages; source_only marks model fallback."""
    data, fallback_reason = llm.complete_json(SYSTEM, f"Passages:\n{format_passages(passages)}\n\nQuestion: {question}")

    if not data or not isinstance(data.get("answer"), str) or not data["answer"].strip():
        if _is_summary_question(question):
            summary, citations = _source_only_summary(passages)
            return {
                "answer": summary,
                "confidence": "low",
                "confidence_reason": "Source excerpts only; the model did not produce a summary.",
                "used": citations or [(passages[0], None)],
                "source_only": True,
                "fallback_reason": fallback_reason or "The model response did not include a usable answer.",
            }
        best = passages[0]
        return {
            "answer": "I couldn't write a grounded answer right now. Here is the closest matching passage from your documents.",
            "confidence": "low",
            "confidence_reason": "",
            "used": [(best, None)],
            "source_only": True,
            "fallback_reason": fallback_reason or "The model response did not include a usable answer.",
        }

    used = []
    cited = data.get("used", [])
    if isinstance(cited, list):
        for item in cited:
            if not isinstance(item, dict):
                continue
            n = item.get("n")
            if isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= len(passages):
                p, h = passages[n - 1], item.get("highlight")
                used.append((p, h if isinstance(h, str) and h and h in p["text"] else None))
    confidence_reason = data.get("confidence_reason", "")
    return {
        "answer": data.get("answer", ""),
        "confidence": data.get("confidence", "low") if isinstance(data.get("confidence"), str) and data.get("confidence") in {"high", "medium", "low"} else "low",
        "confidence_reason": confidence_reason if isinstance(confidence_reason, str) else "",
        "used": used or [(passages[0], None)],
        "source_only": False,
        "fallback_reason": None,
    }
