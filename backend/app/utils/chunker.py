from typing import List


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
    """Split text into word-based chunks with optional overlap."""
    print(f"    [chunker] Starting chunking, text length: {len(text)}", flush=True)
    words = text.split()
    print(f"    [chunker] Split into {len(words)} words", flush=True)
    if not words:
        return []

    chunks: List[str] = []
    start = 0
    while start < len(words):
        end = min(len(words), start + chunk_size)
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        # Move forward by chunk_size - overlap, but ensure we always make progress
        new_start = end - overlap
        if new_start <= start:  # Prevent infinite loop - we must make progress
            new_start = end
        if new_start >= len(words):
            break
        start = new_start
    print(f"    [chunker] Created {len(chunks)} chunks", flush=True)
    return chunks
