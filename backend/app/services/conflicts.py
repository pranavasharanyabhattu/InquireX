from . import llm
from .answer import format_passages

SYSTEM = """You compare passages from DIFFERENT documents. Given a question, find cases where two or more
documents give contradictory information that matters for answering it (different numbers, dates, names, terms).
Ignore differences in wording that don't change the meaning.
Reply with JSON only: {"conflicts": [{"summary": str, "passages": [int, ...]}]}
Use an empty list if there are no real contradictions. Each conflict must cite passages from at least two documents."""


def find_conflicts(question: str, passages: list[dict]) -> tuple[list[tuple[str, list[dict]]], bool]:
    """Returns ([(summary, [passage, ...]), ...], check_succeeded)."""
    if len({p["doc_id"] for p in passages}) < 2:
        return [], True
    data, error = llm.complete_json(SYSTEM, f"Passages:\n{format_passages(passages)}\n\nQuestion: {question}")
    found = []
    conflicts = (data or {}).get("conflicts", [])
    if not isinstance(conflicts, list):
        conflicts = []
    for c in conflicts:
        if not isinstance(c, dict):
            continue
        cited = c.get("passages", [])
        if not isinstance(cited, list):
            continue
        group = [
            passages[n - 1] for n in cited
            if isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= len(passages)
        ]
        if len({p["doc_id"] for p in group}) >= 2:
            summary = c.get("summary")
            found.append((summary if isinstance(summary, str) and summary.strip() else "These documents disagree.", group))
    return found, error is None and data is not None
