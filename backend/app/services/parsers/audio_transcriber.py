from pathlib import Path


def transcribe_audio(_path: Path) -> str:
    """Legacy stub kept to prevent silent fallback to an invalid whisper module."""
    raise NotImplementedError(
        "Generic audio transcription is not implemented here. Use the caption-first YouTube watchlist pipeline or a "
        "compatible local Whisper backend that exposes load_model."
    )
