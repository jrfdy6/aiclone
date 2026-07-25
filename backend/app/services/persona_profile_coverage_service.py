from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.persona_bundle_writer import resolve_persona_bundle_read_path


VOICE_PATH = "identity/VOICE_PATTERNS.md"
COMMUNICATION_PATH = "identity/audience_communication.md"
CONTENT_EXAMPLES_PATH = "prompts/content_examples.md"
TASTE_EXAMPLES_PATH = "prompts/taste_examples.md"
STORY_PATH = "history/story_bank.md"


def _read(bundle_root: Path | None, relative_path: str) -> str:
    path = (
        bundle_root / relative_path
        if bundle_root is not None
        else resolve_persona_bundle_read_path(relative_path)
    )
    if not path.exists() or not path.is_file():
        return ""
    if path.is_symlink():
        raise ValueError("Persona profile files must be regular non-symlink files.")
    return path.read_text(encoding="utf-8", errors="ignore")


def _section_lines(text: str, heading: str) -> list[str]:
    target = f"## {heading}".strip().lower()
    active = False
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.lower() == target:
            active = True
            continue
        if active and line.startswith("## "):
            break
        if active and line and not line.startswith("<!--"):
            lines.append(line)
    return lines


def _bullet_count(lines: list[str]) -> int:
    return sum(1 for line in lines if line.startswith(("- ", "* ")))


def _level_two_heading_count(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip().startswith("## "))


def build_persona_profile_coverage(*, bundle_root: Path | None = None) -> dict[str, Any]:
    """Return content-free coverage facts for the private persona bundle."""

    voice = _read(bundle_root, VOICE_PATH)
    communication = _read(bundle_root, COMMUNICATION_PATH)
    examples = _read(bundle_root, CONTENT_EXAMPLES_PATH)
    taste = _read(bundle_root, TASTE_EXAMPLES_PATH)
    stories = _read(bundle_root, STORY_PATH)

    coverage = {
        "voice_sections": _level_two_heading_count(voice),
        "reusable_phrase_patterns": _bullet_count(_section_lines(voice, "Reusable Phrases")),
        "sentence_rhythm_rules": _bullet_count(_section_lines(voice, "Sentence Rhythm")),
        "communication_patterns": _bullet_count(_section_lines(communication, "Patterns")),
        "content_examples": _bullet_count(_section_lines(examples, "Good Examples")),
        "taste_anchors": _bullet_count(_section_lines(taste, "Taste Anchors")),
        "personal_stories": _level_two_heading_count(stories),
    }
    dimensions = {
        "favorite_language": coverage["reusable_phrase_patterns"] > 0,
        "sentence_structure": coverage["sentence_rhythm_rules"] > 0,
        "audience_communication": coverage["communication_patterns"] > 0,
        "content_examples": coverage["content_examples"] > 0,
        "taste": coverage["taste_anchors"] > 0,
        "personal_stories": coverage["personal_stories"] > 0,
    }
    return {
        "schema_version": "persona_profile_coverage/v1",
        "private_content_included": False,
        "ready": all(dimensions.values()),
        "dimensions": dimensions,
        "coverage": coverage,
        "supported_intake_lanes": [
            "phrase_candidate",
            "anecdote",
            "talking_point",
            "framework",
            "claim",
        ],
    }
