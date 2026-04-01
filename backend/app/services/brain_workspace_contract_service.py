from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.models import PersonaDelta

ROOT = Path(__file__).resolve().parents[3]
WORKSPACES_ROOT = ROOT / "workspaces"
INFERRED_BRIEF_PATH = ROOT / "docs" / "inferred_workspace_operating_brief_2026-03-31.md"
PACK_FILES = ("CHARTER.md", "IDENTITY.md", "SOUL.md", "USER.md", "AGENTS.md")
WORKSPACE_KEYS = ("shared_ops", "linkedin-os", "fusion-os", "easyoutfitapp", "ai-swag-store", "agc")
PROJECT_WORKSPACE_KEYS = ("fusion-os", "easyoutfitapp", "ai-swag-store", "agc")
WORKSPACE_CONFIG: dict[str, dict[str, str]] = {
    "shared_ops": {
        "display_name": "Executive",
        "brief_heading": "Executive Interpretation Rule",
        "root": "shared-ops",
    },
    "linkedin-os": {
        "display_name": "FEEZIE OS",
        "brief_heading": "FEEZIE OS",
        "root": "linkedin-content-os",
    },
    "fusion-os": {
        "display_name": "Fusion OS",
        "brief_heading": "Fusion OS",
        "root": "fusion-os",
    },
    "easyoutfitapp": {
        "display_name": "EasyOutfitApp",
        "brief_heading": "EasyOutfitApp",
        "root": "easyoutfitapp",
    },
    "ai-swag-store": {
        "display_name": "AI Swag Store",
        "brief_heading": "AI Swag Store",
        "root": "ai-swag-store",
    },
    "agc": {
        "display_name": "AGC",
        "brief_heading": "AGC",
        "root": "agc",
    },
}
FALLBACK_CONTRACT_TEXT: dict[str, str] = {
    "shared_ops": "Executive review interprets strong signals across Neo, Yoda, and Jean-Claude before broad downstream changes are made.",
    "linkedin-os": "FEEZIE OS is the public-facing operating system for visibility, personal brand, career signal, and thought leadership rooted in real work.",
    "fusion-os": "Fusion OS covers admissions, enrollment, school operations, referral systems, families, students, and leadership execution with trust and clarity.",
    "easyoutfitapp": "EasyOutfitApp focuses on fashion, outfit logic, closet organization, metadata quality, personal style, and recommendation quality grounded in context.",
    "ai-swag-store": "AI Swag Store owns merchandising, product drops, accessories, commerce validation, catalog decisions, and demand-testing for AI-branded physical goods.",
    "agc": "AGC is a protected operating lane for AGC initiatives with separate mission clarity, traceable goals, local memory, and distinct execution rules.",
}
AI_PORTFOLIO_HINTS = (
    "ai",
    "artificial intelligence",
    "ai clone",
    "second brain",
    "agent",
    "agents",
    "llm",
    "llms",
    "openai",
    "anthropic",
    "chatgpt",
    "claude",
    "prompt",
    "prompts",
)
WORKSPACE_DOMAIN_HINTS: dict[str, tuple[str, ...]] = {
    "fusion-os": (
        "fusion",
        "academy",
        "education",
        "higher education",
        "college",
        "admissions",
        "enrollment",
        "referral",
        "referrals",
        "school",
        "schools",
        "family",
        "families",
        "student",
        "students",
        "market development",
        "twice exceptional",
        "2e",
        "neurodivergent",
    ),
    "easyoutfitapp": (
        "easy outfit",
        "easyoutfit",
        "outfit",
        "outfits",
        "style",
        "fashion",
        "wardrobe",
        "closet",
        "digital closet",
        "digital organization",
        "personal style",
        "recommendation quality",
        "metadata quality",
    ),
    "ai-swag-store": (
        "swag",
        "merch",
        "merchandise",
        "accessory",
        "accessories",
        "commerce",
        "catalog",
        "fulfillment",
        "product drop",
        "product drops",
        "demand signal",
        "demand test",
        "shop",
        "store",
    ),
    "agc": (
        "agc",
        "agc initiative",
        "agc initiatives",
        "agc work",
        "agc mission",
    ),
}


def recommend_brain_workspaces(delta: PersonaDelta) -> dict[str, Any]:
    scored: dict[str, dict[str, Any]] = {}

    def add_score(workspace_key: str, points: int, reason: str) -> None:
        entry = scored.setdefault(workspace_key, {"score": 0, "reasons": []})
        entry["score"] = int(entry.get("score") or 0) + points
        reasons = entry.setdefault("reasons", [])
        if reason not in reasons:
            reasons.append(reason)

    metadata = delta.metadata if isinstance(delta.metadata, dict) else {}
    primary_blob = _normalize_blob(
        [
            delta.persona_target,
            delta.trait,
            delta.notes,
            metadata.get("lane_hint"),
            metadata.get("evidence_source"),
            metadata.get("source_excerpt_clean"),
            metadata.get("source_context_excerpt"),
            metadata.get("belief_summary"),
            metadata.get("system_hypothesis"),
            " ".join(_metadata_string_array(metadata, "talking_points")),
        ]
    )
    secondary_blob = _normalize_blob(
        [
            metadata.get("experience_anchor"),
            metadata.get("experience_summary"),
            metadata.get("system_experience_hypothesis"),
        ]
    )

    add_score("linkedin-os", 5, "FEEZIE OS stays in the loop by default.")

    persona_target = _normalize_text(delta.persona_target)
    if "feeze" in persona_target or "linkedin" in persona_target:
        add_score("linkedin-os", 3, "The persona target is explicitly aligned to Feeze / LinkedIn.")

    metadata_workspace = _normalize_text(metadata.get("workspace_key"))
    if metadata_workspace in WORKSPACE_KEYS:
        add_score(metadata_workspace, 4, "The review item metadata already points at this workspace.")

    for prior_workspace in _metadata_string_array(metadata, "last_brain_route_workspace_keys"):
        if prior_workspace in WORKSPACE_KEYS:
            add_score(prior_workspace, 2, "This signal has already been routed here before.")

    has_ai_signal = _count_matches(primary_blob, AI_PORTFOLIO_HINTS) > 0
    if has_ai_signal:
        add_score("linkedin-os", 2, "AI is always relevant to FEEZIE OS.")
        for workspace_key in PROJECT_WORKSPACE_KEYS:
            add_score(workspace_key, 3, "AI is a portfolio-wide signal across the active project stack.")
        add_score("shared_ops", 3, "AI touches multiple workspaces, so executive review should stay in the loop.")

    for workspace_key, hints in WORKSPACE_DOMAIN_HINTS.items():
        contract_blob = _workspace_contract_blob(workspace_key)
        primary_match_count = _count_matches(primary_blob, hints)
        secondary_match_count = _count_matches(secondary_blob, hints)
        contract_match_count = _count_matches(contract_blob, hints)
        contract_excerpt = _workspace_contract_excerpt(workspace_key)

        if primary_match_count >= 2:
            add_score(
                workspace_key,
                5 if contract_match_count > 0 else 4,
                f"Multiple direct source cues align with {WORKSPACE_CONFIG[workspace_key]['display_name']}{' and its workspace contract' if contract_match_count > 0 else ''}. {contract_excerpt}",
            )
        elif primary_match_count == 1:
            add_score(
                workspace_key,
                3 if contract_match_count > 0 else 2,
                f"A direct source cue aligns with {WORKSPACE_CONFIG[workspace_key]['display_name']}{' and its workspace contract' if contract_match_count > 0 else ''}. {contract_excerpt}",
            )

        if secondary_match_count > 0:
            add_score(
                workspace_key,
                1,
                f"A weaker experience/context anchor also overlaps {WORKSPACE_CONFIG[workspace_key]['display_name']}.",
            )

    fusion_score = int(scored.get("fusion-os", {}).get("score") or 0)
    merch_score = int(scored.get("ai-swag-store", {}).get("score") or 0)
    if fusion_score >= 3 and merch_score >= 3:
        add_score("fusion-os", 2, "This looks like a Fusion + merchandise crossover.")
        add_score("ai-swag-store", 2, "This looks like a Fusion + merchandise crossover.")
        add_score("shared_ops", 2, "This signal spans multiple operating lanes and should stay visible to executive review.")

    selected_project_workspaces = [
        workspace_key
        for workspace_key in PROJECT_WORKSPACE_KEYS
        if int(scored.get(workspace_key, {}).get("score") or 0) >= 3
    ]
    if not selected_project_workspaces:
        add_score("shared_ops", 2, "No other workspace crossed the confirmation threshold, so this should stay in executive review.")
    elif len(selected_project_workspaces) > 1:
        add_score("shared_ops", 2, "This signal appears cross-workspace, so executive review should stay included.")

    selected_keys = [
        workspace_key
        for workspace_key in WORKSPACE_KEYS
        if workspace_key == "linkedin-os"
        or (workspace_key == "shared_ops" and workspace_key in scored)
        or int(scored.get(workspace_key, {}).get("score") or 0) >= 3
    ]

    suggestion_details = [
        {
            "workspace_key": workspace_key,
            "label": WORKSPACE_CONFIG[workspace_key]["display_name"],
            "score": int(scored.get(workspace_key, {}).get("score") or 0),
            "reasons": list(scored.get(workspace_key, {}).get("reasons") or []),
            "contract_excerpt": _workspace_contract_excerpt(workspace_key),
        }
        for workspace_key in selected_keys
    ]

    return {
        "workspace_keys": selected_keys,
        "suggestion_details": suggestion_details,
        "contract_version": "brain_workspace_contract_v1",
    }


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip().lower()


def _normalize_blob(values: list[Any]) -> str:
    return " ".join(part for part in (_normalize_text(value) for value in values) if part)


def _metadata_string_array(metadata: dict[str, Any], key: str) -> list[str]:
    value = metadata.get(key)
    if not isinstance(value, list):
        return []
    return [entry.strip().lower() for entry in value if isinstance(entry, str) and entry.strip()]


def _count_matches(text: str, hints: tuple[str, ...]) -> int:
    return sum(1 for hint in hints if _text_includes_hint(text, hint))


def _text_includes_hint(text: str, hint: str) -> bool:
    normalized_hint = hint.strip().lower()
    if not text or not normalized_hint:
        return False
    if len(normalized_hint) <= 3 and " " not in normalized_hint:
        return bool(re.search(rf"(^|[^a-z0-9]){re.escape(normalized_hint)}([^a-z0-9]|$)", text))
    return normalized_hint in text


@lru_cache(maxsize=32)
def _workspace_contract_excerpt(workspace_key: str) -> str:
    config = WORKSPACE_CONFIG.get(workspace_key)
    if not config:
        return ""
    root = WORKSPACES_ROOT / config["root"]
    for filename in ("CHARTER.md", "IDENTITY.md", "SOUL.md", "USER.md", "AGENTS.md"):
        path = root / filename
        if path.exists():
            excerpt = _first_meaningful_line(path.read_text(encoding="utf-8"))
            if excerpt:
                return excerpt
    inferred = _inferred_workspace_brief_excerpt(config["brief_heading"])
    if inferred:
        return inferred
    return _first_meaningful_line(FALLBACK_CONTRACT_TEXT.get(workspace_key, ""))


@lru_cache(maxsize=32)
def _workspace_contract_blob(workspace_key: str) -> str:
    config = WORKSPACE_CONFIG.get(workspace_key)
    if not config:
        return ""
    root = WORKSPACES_ROOT / config["root"]
    parts: list[str] = []
    for filename in PACK_FILES:
        path = root / filename
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    inferred = _inferred_workspace_brief_excerpt(config["brief_heading"])
    if inferred:
        parts.append(inferred)
    if not parts:
        fallback = FALLBACK_CONTRACT_TEXT.get(workspace_key, "")
        if fallback:
            parts.append(fallback)
    return _normalize_blob(parts)


@lru_cache(maxsize=16)
def _inferred_workspace_brief_excerpt(heading: str) -> str:
    if not INFERRED_BRIEF_PATH.exists():
        return ""
    text = INFERRED_BRIEF_PATH.read_text(encoding="utf-8")
    section = _extract_markdown_section(text, heading)
    return _first_meaningful_line(section)


def _extract_markdown_section(markdown: str, heading: str) -> str:
    normalized_heading = heading.strip().lower()
    capture = False
    lines: list[str] = []
    target_level = None
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            title = line[level:].strip().lower()
            if title == normalized_heading:
                capture = True
                target_level = level
                continue
            if capture and target_level is not None and level <= target_level:
                break
        if capture:
            lines.append(line)
    return "\n".join(lines).strip()


def _first_meaningful_line(markdown: str) -> str:
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        if line.startswith("-"):
            line = line[1:].strip()
        return line[:220]
    return ""
