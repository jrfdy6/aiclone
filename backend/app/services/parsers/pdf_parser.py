from pathlib import Path

from pdfminer.high_level import extract_text


def extract_text_from_pdf(path: Path) -> str:
    return extract_text(str(path))
