from ..config import CHUNK_OVERLAP, CHUNK_WORDS


def chunk_pages(pages: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Split each page into overlapping word windows. Keeps the page number with every chunk."""
    chunks = []
    step = CHUNK_WORDS - CHUNK_OVERLAP
    for page, text in pages:
        words = text.split()
        for start in range(0, len(words), step):
            piece = " ".join(words[start:start + CHUNK_WORDS])
            if piece:
                chunks.append((page, piece))
            if start + CHUNK_WORDS >= len(words):
                break
    return chunks
