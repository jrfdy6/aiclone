from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.models import PersonaDelta
from app.services.workspace_registry_service import REPO_ROOT

ROOT = REPO_ROOT
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
        "display_name": "Easy Outfit App",
        "brief_heading": "Easy Outfit App",
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
    "easyoutfitapp": "Easy Outfit App focuses on reducing daily decision fatigue with context-aware, closet-first outfit recommendations and trustworthy product execution.",
    "ai-swag-store": "AI Swag Store owns differentiated AI merchandise discovery, offer testing, traffic learning, and disciplined catalog decisions inside its workspace.",
    "agc": "AGC is a government-contracting-first lane for AI consulting, capability positioning, inbound opportunity qualification, and traceable capture work.",
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
ROUTING_SCORE_DIMENSIONS = (
    "domain_match",
    "execution_relevance",
    "strategic_relevance",
    "identity_relevance",
    "urgency",
    "confidence",
)
AI_EXECUTIVE_HINTS = (
    "automation",
    "automations",
    "brain",
    "canonical memory",
    "control plane",
    "cross-workspace",
    "execution",
    "memory",
    "multiple active projects",
    "operating system",
    "portfolio",
    "pm",
    "routing",
    "second brain",
    "standup",
    "system",
    "teams operate",
    "workflow",
)
EXECUTION_RELEVANCE_HINTS = (
    "build",
    "customer",
    "execute",
    "execution",
    "handoff",
    "implementation",
    "operate",
    "operating",
    "process",
    "result",
    "ship",
    "workflow",
)
URGENCY_HINTS = (
    "blocked",
    "blocker",
    "critical",
    "immediately",
    "now",
    "priority",
    "urgent",
)
EXPLICIT_WORKSPACE_CANDIDATE_KEYS = (
    "brain_workspace_candidates",
    "brain_suggested_workspace_keys",
    "route_workspace_keys",
    "workspace_candidates",
)
WORKSPACE_DOMAIN_HINTS: dict[str, dict[str, tuple[str, ...]]] = {
    "fusion-os": {
        "strong": (
            "fusion academy",
            "education",
            "higher education",
            "admissions",
            "enrollment",
            "referral",
            "referrals",
            "market development",
            "twice exceptional",
            "2e",
            "neurodivergent",
        ),
        "weak": (
            "fusion",
            "academy",
            "college",
            "school",
            "schools",
            "family",
            "families",
            "student",
            "students",
        ),
    },
    "easyoutfitapp": {
        "strong": (
            "easy outfit",
            "easyoutfit",
            "outfit",
            "outfits",
            "fashion",
            "wardrobe",
            "closet",
            "digital closet",
            "digital organization",
            "personal style",
            "decision fatigue",
            "what to wear",
        ),
        "weak": (
            "style",
            "recommendation quality",
            "metadata quality",
            "styling",
        ),
    },
    "ai-swag-store": {
        "strong": (
            "ai swag",
            "swag",
            "swag store",
            "merch",
            "merchandise",
            "accessory",
            "accessories",
            "product drop",
            "product drops",
            "catalog",
            "fulfillment",
            "demand signal",
            "demand test",
            "website visit",
            "website visits",
        ),
        "weak": (
            "commerce",
            "shop",
            "shopify",
            "merch consumer",
        ),
    },
    "agc": {
        "strong": (
            "agc",
            "acorn global collective",
            "agc initiative",
            "agc initiatives",
            "agc work",
            "agc mission",
            "government contracting",
            "government contract",
            "prime contractor",
            "subcontractor",
            "public sector",
            "rfp",
            "rfq",
            "proposal",
            "capability statement",
            "procurement",
        ),
        "weak": (
            "ai consulting",
            "inbound email",
            "capture",
        ),
    },
}


def recommend_brain_workspaces(delta: PersonaDelta) -> dict[str, Any]:
    scored: dict[str, dict[str, Any]] = {}

    def add_score(workspace_key: str, points: int, reason: str, dimension: str = "strategic_relevance") -> None:
        entry = scored.setdefault(workspace_key, {"score": 0, "reasons": [], "dimensions": _blank_dimensions()})
        entry["score"] = int(entry.get("score") or 0) + points
        dimensions = entry.setdefault("dimensions", _blank_dimensions())
        if dimension in ROUTING_SCORE_DIMENSIONS:
            dimensions[dimension] = int(dimensions.get(dimension) or 0) + points
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

    add_score("linkedin-os", 5, "FEEZIE OS stays in the loop by default.", "identity_relevance")

    persona_target = _normalize_text(delta.persona_target)
    if "feeze" in persona_target or "linkedin" in persona_target:
        add_score("linkedin-os", 3, "The persona target is explicitly aligned to Feeze / LinkedIn.", "identity_relevance")

    metadata_workspace = _normalize_workspace_key(metadata.get("workspace_key"))
    if metadata_workspace in WORKSPACE_KEYS:
        add_score(metadata_workspace, 6, "The review item metadata already points at this workspace.", "confidence")

    for prior_workspace in _metadata_string_array(metadata, "last_brain_route_workspace_keys"):
        normalized_prior = _normalize_workspace_key(prior_workspace)
        if normalized_prior in WORKSPACE_KEYS:
            add_score(normalized_prior, 2, "This signal has already been routed here before.", "confidence")

    explicit_workspace_candidates = _metadata_workspace_candidates(metadata)
    has_explicit_interpretation = _has_explicit_executive_interpretation(metadata)
    if explicit_workspace_candidates and has_explicit_interpretation:
        add_score(
            "shared_ops",
            3,
            "Explicit executive interpretation is present, so the route stays visible to executive review.",
            "strategic_relevance",
        )
        for workspace_key in explicit_workspace_candidates:
            add_score(
                workspace_key,
                6,
                "Explicit executive interpretation selected this workspace.",
                "confidence",
            )

    has_ai_signal = _count_matches(primary_blob, AI_PORTFOLIO_HINTS) > 0
    has_cross_portfolio_ai_signal = has_ai_signal and _count_matches(primary_blob, AI_EXECUTIVE_HINTS) > 0
    if has_ai_signal:
        add_score("linkedin-os", 2, "AI is relevant to FEEZIE OS by default.", "identity_relevance")
        add_score(
            "shared_ops",
            3,
            "Generic AI signal defaults to executive review before any project-workspace fanout.",
            "strategic_relevance",
        )
        if has_cross_portfolio_ai_signal:
            add_score(
                "shared_ops",
                2,
                "The AI signal has cross-portfolio operating implications, so standup should decide any fanout.",
                "execution_relevance",
            )

    for workspace_key, hint_groups in WORKSPACE_DOMAIN_HINTS.items():
        contract_blob = _workspace_contract_blob(workspace_key)
        strong_hints = hint_groups.get("strong", ())
        weak_hints = hint_groups.get("weak", ())
        primary_strong_matches = _count_matches(primary_blob, strong_hints)
        primary_weak_matches = _count_matches(primary_blob, weak_hints)
        secondary_strong_matches = _count_matches(secondary_blob, strong_hints)
        secondary_weak_matches = _count_matches(secondary_blob, weak_hints)
        contract_match_count = _count_matches(contract_blob, strong_hints) + _count_matches(contract_blob, weak_hints)
        contract_excerpt = _workspace_contract_excerpt(workspace_key)

        if primary_strong_matches >= 2:
            add_score(
                workspace_key,
                6 if contract_match_count > 0 else 5,
                f"Multiple strong source cues align with {WORKSPACE_CONFIG[workspace_key]['display_name']}{' and its workspace contract' if contract_match_count > 0 else ''}. {contract_excerpt}",
                "domain_match",
            )
        elif primary_strong_matches == 1:
            add_score(
                workspace_key,
                4 if contract_match_count > 0 else 3,
                f"A strong source cue aligns with {WORKSPACE_CONFIG[workspace_key]['display_name']}{' and its workspace contract' if contract_match_count > 0 else ''}. {contract_excerpt}",
                "domain_match",
            )
        elif primary_weak_matches >= 2:
            add_score(
                workspace_key,
                3 if contract_match_count > 0 else 2,
                f"Multiple weaker source cues still align with {WORKSPACE_CONFIG[workspace_key]['display_name']}{' and its workspace contract' if contract_match_count > 0 else ''}. {contract_excerpt}",
                "domain_match",
            )

        if secondary_strong_matches > 0 or secondary_weak_matches >= 2:
            add_score(
                workspace_key,
                1,
                f"A weaker experience/context anchor also overlaps {WORKSPACE_CONFIG[workspace_key]['display_name']}.",
                "strategic_relevance",
            )

        if primary_strong_matches > 0 or primary_weak_matches >= 2:
            add_score(
                workspace_key,
                min(primary_strong_matches + primary_weak_matches, 2),
                "The route has enough textual evidence to increase confidence.",
                "confidence",
            )
            if _count_matches(primary_blob, EXECUTION_RELEVANCE_HINTS) > 0:
                add_score(
                    workspace_key,
                    1,
                    "The signal mentions execution or operating movement, not only abstract interest.",
                    "execution_relevance",
                )
            if _count_matches(primary_blob, URGENCY_HINTS) > 0:
                add_score(workspace_key, 1, "The signal carries urgency or blocker language.", "urgency")

    fusion_score = int(scored.get("fusion-os", {}).get("score") or 0)
    merch_score = int(scored.get("ai-swag-store", {}).get("score") or 0)
    if fusion_score >= 3 and merch_score >= 3:
        add_score("fusion-os", 2, "This looks like a Fusion + merchandise crossover.", "strategic_relevance")
        add_score("ai-swag-store", 2, "This looks like a Fusion + merchandise crossover.", "strategic_relevance")
        add_score(
            "shared_ops",
            2,
            "This signal spans multiple operating lanes and should stay visible to executive review.",
            "strategic_relevance",
        )

    selected_project_workspaces = [
        workspace_key
        for workspace_key in PROJECT_WORKSPACE_KEYS
        if _project_workspace_confirmed(scored.get(workspace_key), has_ai_signal=has_ai_signal)
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
            "scoring_dimensions": dict(scored.get(workspace_key, {}).get("dimensions") or _blank_dimensions()),
            "reasons": list(scored.get(workspace_key, {}).get("reasons") or []),
            "contract_excerpt": _workspace_contract_excerpt(workspace_key),
            "routing_posture": _routing_posture(scored.get(workspace_key), has_ai_signal=has_ai_signal),
        }
        for workspace_key in selected_keys
    ]

    return {
        "workspace_keys": selected_keys,
        "suggestion_details": suggestion_details,
        "contract_version": "brain_workspace_contract_v3",
        "routing_policy": "generic_ai_to_executive_and_feezie_domain_evidence_required_for_project_workspaces",
    }


def _blank_dimensions() -> dict[str, int]:
    return {dimension: 0 for dimension in ROUTING_SCORE_DIMENSIONS}


def _normalize_workspace_key(value: Any) -> str:
    normalized = _normalize_text(value)
    aliases = {
        "feezie": "linkedin-os",
        "feezie os": "linkedin-os",
        "feezie-os": "linkedin-os",
        "linkedin": "linkedin-os",
        "linkedin content os": "linkedin-os",
        "linkedin-content-os": "linkedin-os",
        "shared-ops": "shared_ops",
        "shared ops": "shared_ops",
    }
    return aliases.get(normalized, normalized)


def _metadata_workspace_candidates(metadata: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    for key in EXPLICIT_WORKSPACE_CANDIDATE_KEYS:
        for value in _metadata_string_array(metadata, key):
            workspace_key = _normalize_workspace_key(value)
            if workspace_key in WORKSPACE_KEYS and workspace_key not in candidates:
                candidates.append(workspace_key)

    route_decision = metadata.get("route_decision")
    if isinstance(route_decision, dict):
        for key in ("workspace_key", "target_workspace", "target_workspace_key"):
            workspace_key = _normalize_workspace_key(route_decision.get(key))
            if workspace_key in WORKSPACE_KEYS and workspace_key not in candidates:
                candidates.append(workspace_key)
        for key in ("workspace_candidates", "target_workspace_keys", "workspace_keys"):
            values = route_decision.get(key)
            if isinstance(values, list):
                for value in values:
                    workspace_key = _normalize_workspace_key(value)
                    if workspace_key in WORKSPACE_KEYS and workspace_key not in candidates:
                        candidates.append(workspace_key)
    return candidates


def _has_explicit_executive_interpretation(metadata: dict[str, Any]) -> bool:
    executive_interpretation = metadata.get("executive_interpretation")
    if isinstance(executive_interpretation, dict) and any(_normalize_text(value) for value in executive_interpretation.values()):
        return True
    route_decision = metadata.get("route_decision")
    return isinstance(route_decision, dict) and any(_normalize_text(value) for value in route_decision.values())


def _project_workspace_confirmed(entry: dict[str, Any] | None, *, has_ai_signal: bool) -> bool:
    if not entry:
        return False
    dimensions = entry.get("dimensions") if isinstance(entry.get("dimensions"), dict) else {}
    domain_match = int(dimensions.get("domain_match") or 0)
    confidence = int(dimensions.get("confidence") or 0)
    total_score = int(entry.get("score") or 0)
    if confidence >= 6:
        return True
    if domain_match >= 4:
        return True
    if has_ai_signal:
        return False
    return total_score >= 3 and domain_match > 0


def _routing_posture(entry: dict[str, Any] | None, *, has_ai_signal: bool) -> str:
    if not entry:
        return "not_selected"
    dimensions = entry.get("dimensions") if isinstance(entry.get("dimensions"), dict) else {}
    if int(dimensions.get("confidence") or 0) >= 6:
        return "explicit"
    if int(dimensions.get("domain_match") or 0) >= 4:
        return "domain_confirmed"
    if has_ai_signal:
        return "executive_default"
    return "fallback_review"


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
