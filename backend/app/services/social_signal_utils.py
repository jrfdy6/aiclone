from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from app.services.social_belief_engine import social_belief_engine
from app.services.social_evaluation_engine import social_evaluation_engine
from app.services.social_expression_engine import social_expression_engine
from app.services.social_technique_engine import social_technique_engine

LENS_IDS: list[str] = [
    "admissions",
    "entrepreneurship",
    "current-role",
    "program-leadership",
    "enrollment-management",
    "ai",
    "ops-pm",
    "therapy",
    "referral",
    "personal-story",
]

LENS_LABELS = {
    "admissions": "Admissions",
    "entrepreneurship": "Entrepreneurship",
    "current-role": "Current Job",
    "program-leadership": "Program Leadership",
    "enrollment-management": "Enrollment",
    "ai": "AI",
    "ops-pm": "Ops / PM",
    "therapy": "Therapy",
    "referral": "Referral",
    "personal-story": "Personal Story",
}

FORBIDDEN_PHRASES = [
    "agreed.",
    "completely agree.",
    "what stands out",
    "this is directly relevant",
    "this is directly useful",
    "from an admissions lens",
    "from an entrepreneurship lens",
    "from a leadership lens",
    "from an ai and ops lens",
]

GENERIC_SOURCE_PHRASES = [
    "this is important",
    "in today's world",
    "leverage",
    "game changer",
    "synergy",
    "more than ever",
]

PREFERRED_REPLACEMENTS = {
    "agreed.": "That part matters.",
    "completely agree.": "This is the part a lot of teams miss.",
}

LANE_ALIASES = {
    "admissions": "admissions",
    "entrepreneurship": "entrepreneurship",
    "current job": "current-role",
    "current role": "current-role",
    "job": "current-role",
    "job / current role": "current-role",
    "personal story": "personal-story",
    "job / program leadership": "program-leadership",
    "program leadership": "program-leadership",
    "leadership": "program-leadership",
    "enrollment": "enrollment-management",
    "enrollment mgmt": "enrollment-management",
    "ai": "ai",
    "ai + ops": "ai",
    "ai entrepreneurship": "ai",
    "ai-entrepreneurship": "ai",
    "ops": "ops-pm",
    "ops / pm": "ops-pm",
    "ops + pm": "ops-pm",
    "ops / project management": "ops-pm",
    "ops/project management": "ops-pm",
    "project management": "ops-pm",
    "pm": "ops-pm",
    "therapy": "therapy",
    "therapy / referral": "therapy",
    "therapist / referral": "therapy",
    "therapist-referral": "therapy",
    "referral": "referral",
    "custom": "current-role",
}

DEFAULT_ENGAGEMENT = {"likes": 0, "comments": 0, "shares": 0}
SOURCE_CLASS_IDS = {"short_form", "article", "long_form_media", "manual"}
UNIT_KIND_IDS = {"full_post", "paragraph", "section", "segment", "quote_cluster", "claim_block"}
RESPONSE_MODE_IDS = ("comment", "repost", "post_seed", "belief_evidence")


def normalize_inline_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def normalize_multiline_text(value: str | None) -> str:
    if not value:
        return ""
    lines = [normalize_inline_text(line) for line in str(value).replace("\r", "\n").split("\n")]
    return "\n\n".join(line for line in lines if line)


def clean_sentence(value: str | None) -> str:
    if not value:
        return ""
    text = normalize_inline_text(value)
    if not text:
        return ""
    return text[:-1] if text.endswith(".") else text


def list_strings(value: Any, limit: int = 8) -> list[str]:
    if isinstance(value, list):
        items = value
    elif value:
        items = [value]
    else:
        items = []

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = normalize_inline_text(str(item))
        lowered = text.lower()
        if not text or lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def join_parts(parts: list[str]) -> str:
    return " ".join(part.strip() for part in parts if part and part.strip())


def ensure_period(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    return text if text.endswith((".", "!", "?")) else f"{text}."


def normalize_voice(text: str) -> str:
    normalized = " ".join(text.split()).strip()
    for source, replacement in PREFERRED_REPLACEMENTS.items():
        if normalized.lower().startswith(source):
            normalized = replacement + normalized[len(source) :]
    replacements = {
        "What stands out to me here is": "The deeper issue here is",
        "From an enrollment perspective,": "",
        "From an admissions perspective,": "",
        "From a leadership lens,": "",
        "From an AI and ops lens,": "",
    }
    for source, replacement in replacements.items():
        normalized = normalized.replace(source, replacement)
    for phrase in FORBIDDEN_PHRASES:
        normalized = normalized.replace(phrase, "")
        normalized = normalized.replace(phrase.title(), "")
    normalized = " ".join(normalized.split())
    return ensure_period(normalized) if normalized else ""


def normalize_lane(value: str | None) -> str:
    if not value:
        return "current-role"
    lowered = normalize_inline_text(value).lower()
    normalized = LANE_ALIASES.get(lowered, lowered.replace("_", "-").replace(" ", "-"))
    return normalized if normalized in LENS_IDS else "current-role"


def normalize_source_class(value: str | None) -> str:
    normalized = normalize_inline_text(value).lower().replace("-", "_").replace(" ", "_")
    return normalized if normalized in SOURCE_CLASS_IDS else ""


def normalize_unit_kind(value: str | None) -> str:
    normalized = normalize_inline_text(value).lower().replace("-", "_").replace(" ", "_")
    return normalized if normalized in UNIT_KIND_IDS else ""


def normalize_response_modes(value: Any) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for item in list_strings(value, 8):
        mode = item.lower().replace("-", "_").replace(" ", "_")
        if mode not in RESPONSE_MODE_IDS or mode in seen:
            continue
        seen.add(mode)
        normalized.append(mode)
    return normalized


def contains_generic_phrase(text: str | None) -> bool:
    lowered = normalize_inline_text(text).lower()
    if not lowered:
        return False
    return any(phrase in lowered for phrase in GENERIC_SOURCE_PHRASES)


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", " ".join(text.split())) if part.strip()]


def summarize_text(text: str, sentences: int = 3) -> str:
    return " ".join(split_sentences(text)[:sentences]).strip()


def standout_lines_from_text(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) >= 2:
        return lines[:2]
    return split_sentences(text)[:2]


def first_meaningful_line(text: str) -> str:
    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned
    return text.strip()


def infer_source_channel(*, source_url: str | None = None, source_platform: str | None = None) -> str:
    platform = normalize_inline_text(source_platform).lower()
    if platform:
        return platform
    if not source_url:
        return "manual"
    parsed = urlparse(source_url)
    host = parsed.netloc.replace("www.", "").lower()
    if "linkedin" in host:
        return "linkedin"
    if "reddit" in host:
        return "reddit"
    if "substack" in host:
        return "substack"
    if not host:
        return "manual"
    return host.split(".")[0]


def infer_source_class(*, source_channel: str, source_type: str, capture_method: str, extraction_method: str) -> str:
    normalized_channel = normalize_inline_text(source_channel).lower()
    normalized_type = normalize_inline_text(source_type).lower()
    normalized_capture = normalize_inline_text(capture_method).lower()
    normalized_extraction = normalize_inline_text(extraction_method).lower()

    if normalized_channel == "manual" or normalized_capture == "manual" or normalized_extraction.startswith("manual"):
        return "manual"
    if normalized_type in {"video", "episode", "transcript", "audio", "podcast"} or normalized_channel in {"youtube", "podcast"}:
        return "long_form_media"
    if normalized_type in {"article", "essay", "newsletter"} or normalized_channel in {"rss", "substack", "web"}:
        return "article"
    return "short_form"


def infer_unit_kind(*, source_class: str, source_type: str, capture_method: str, raw_text: str) -> str:
    normalized_class = normalize_source_class(source_class) or "short_form"
    normalized_type = normalize_inline_text(source_type).lower()
    normalized_capture = normalize_inline_text(capture_method).lower()
    sentence_count = len(split_sentences(raw_text))

    if normalized_class == "long_form_media":
        if normalized_type in {"segment", "clip"}:
            return "segment"
        if normalized_type == "quote_cluster":
            return "quote_cluster"
        return "section"
    if normalized_class == "article":
        return "paragraph"
    if normalized_class == "manual" and (normalized_type in {"quote", "note"} or normalized_capture == "manual" and sentence_count <= 2):
        return "claim_block"
    return "full_post"


def infer_response_modes(*, source_class: str, unit_kind: str) -> list[str]:
    normalized_class = normalize_source_class(source_class) or "short_form"
    normalized_unit = normalize_unit_kind(unit_kind) or "full_post"

    if normalized_class == "long_form_media":
        if normalized_unit in {"segment", "quote_cluster", "claim_block"}:
            return ["comment", "repost", "post_seed", "belief_evidence"]
        return ["post_seed", "belief_evidence"]
    return ["comment", "repost", "post_seed", "belief_evidence"]


def _timestamp_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def infer_default_lane(signal: dict[str, Any], raw_text: str) -> str:
    joined = " ".join(
        [
            normalize_inline_text(signal.get("title")),
            normalize_inline_text(signal.get("summary")),
            normalize_inline_text(signal.get("why_it_matters")),
            " ".join(list_strings(signal.get("topics") or signal.get("topic_tags"), 8)),
            raw_text,
        ]
    ).lower()
    role_alignment = normalize_inline_text(signal.get("role_alignment")).lower()

    if any(term in joined for term in ["admissions", "prospect", "student journey", "higher ed content"]):
        return "admissions"
    if any(term in joined for term in ["enrollment", "conversion", "follow-up", "drop-off"]):
        return "enrollment-management"
    if any(term in joined for term in ["referral", "partner", "family trust", "handoff"]):
        return "referral"
    if any(term in joined for term in ["therapy", "therapist", "mental health", "healing"]):
        return "therapy"
    if role_alignment == "ai_intrapreneur" or any(term in joined for term in ["ai", "agent", "model", "context"]):
        return "ai"
    if any(term in joined for term in ["workflow", "ownership", "handoff", "operations", "project", "pm", "execution"]):
        return "ops-pm"
    if role_alignment == "operator_authority" or any(term in joined for term in ["leadership", "leader", "accountability", "team"]):
        return "program-leadership"
    return "current-role"


def normalize_saved_signal(
    signal: dict[str, Any],
    *,
    signal_id: str | None = None,
    source_path: str | None = None,
    raw_text: str | None = None,
) -> dict[str, Any]:
    raw_text_value = normalize_multiline_text(
        raw_text
        or signal.get("raw_text")
        or signal.get("body_text")
        or signal.get("full_text")
        or signal.get("summary")
        or ""
    )
    standout_lines = list_strings(signal.get("headline_candidates"), 4)
    if not standout_lines and raw_text_value:
        standout_lines = standout_lines_from_text(raw_text_value)

    title = (
        normalize_inline_text(signal.get("title"))
        or (standout_lines[0][:120] if standout_lines else "")
        or first_meaningful_line(raw_text_value)[:120]
        or "Untitled"
    )
    summary = normalize_inline_text(signal.get("summary")) or summarize_text(raw_text_value)
    source_url = normalize_inline_text(signal.get("source_url"))
    source_channel = infer_source_channel(source_url=source_url, source_platform=signal.get("source_platform"))
    source_type = normalize_inline_text(signal.get("source_type")) or "post"
    capture_method = normalize_inline_text(signal.get("capture_method")) or "saved_signal"
    captured_at = normalize_inline_text(signal.get("captured_at") or signal.get("created_at")) or _timestamp_now()
    published_at = normalize_inline_text(signal.get("published_at") or signal.get("created_at")) or captured_at
    engagement = dict(DEFAULT_ENGAGEMENT)
    engagement.update(signal.get("engagement") or {})

    core_claim = (
        clean_sentence(signal.get("core_claim"))
        or clean_sentence(standout_lines[0] if standout_lines else "")
        or clean_sentence(summary)
        or clean_sentence(title)
    )
    supporting_claims = list_strings(signal.get("supporting_claims"), 3)
    if not supporting_claims:
        for candidate in standout_lines[1:]:
            cleaned = clean_sentence(candidate)
            if cleaned and cleaned.lower() != core_claim.lower():
                supporting_claims.append(cleaned)
        summary_claim = clean_sentence(summary)
        if summary_claim and summary_claim.lower() != core_claim.lower() and summary_claim not in supporting_claims:
            supporting_claims.append(summary_claim)

    source_metadata = dict(signal.get("source_metadata") or {})
    extraction_method = (
        normalize_inline_text(source_metadata.get("extraction_method"))
        or normalize_inline_text(signal.get("extraction_method"))
        or "saved_signal"
    )
    source_metadata.setdefault("extraction_method", extraction_method)
    source_class = normalize_source_class(signal.get("source_class")) or infer_source_class(
        source_channel=source_channel,
        source_type=source_type,
        capture_method=capture_method,
        extraction_method=extraction_method,
    )
    unit_kind = normalize_unit_kind(signal.get("unit_kind")) or infer_unit_kind(
        source_class=source_class,
        source_type=source_type,
        capture_method=capture_method,
        raw_text=raw_text_value,
    )
    response_modes = normalize_response_modes(signal.get("response_modes")) or infer_response_modes(
        source_class=source_class,
        unit_kind=unit_kind,
    )
    source_metadata.setdefault("source_class", source_class)
    source_metadata.setdefault("unit_kind", unit_kind)
    source_metadata.setdefault("response_modes", response_modes)

    trust_notes = list_strings(signal.get("trust_notes"), 4)
    if extraction_method and extraction_method not in trust_notes:
        trust_notes.append(extraction_method)

    normalized_lane = normalize_lane(signal.get("priority_lane"))
    if normalized_lane == "current-role" and normalize_inline_text(signal.get("priority_lane")):
        normalized_lane = infer_default_lane(signal, raw_text_value)

    return {
        "signal_id": signal_id or normalize_inline_text(signal.get("id")) or "",
        "ingest_mode": normalize_inline_text(signal.get("ingest_mode")) or ("manual" if signal.get("capture_method") == "manual" else "harvested"),
        "source_channel": source_channel,
        "source_type": source_type,
        "source_class": source_class,
        "unit_kind": unit_kind,
        "response_modes": response_modes,
        "source_url": source_url,
        "source_path": source_path or normalize_inline_text(signal.get("source_path")),
        "source_lane": normalize_inline_text(signal.get("source_kind")) or "market_signal",
        "capture_method": capture_method,
        "title": title,
        "author": normalize_inline_text(signal.get("author")) or "Unknown",
        "published_at": published_at,
        "captured_at": captured_at,
        "raw_text": raw_text_value,
        "summary": summary,
        "standout_lines": standout_lines[:2],
        "core_claim": ensure_period(core_claim) if core_claim else "",
        "supporting_claims": [ensure_period(item) for item in supporting_claims[:2]],
        "topic_tags": list_strings(signal.get("topics") or signal.get("topic_tags"), 8),
        "trust_notes": trust_notes,
        "source_metadata": source_metadata,
        "priority_lane": normalized_lane,
        "role_alignment": normalize_inline_text(signal.get("role_alignment")),
        "risk_level": normalize_inline_text(signal.get("risk_level")),
        "publish_posture": normalize_inline_text(signal.get("publish_posture")),
        "why_it_matters": normalize_inline_text(signal.get("why_it_matters")),
        "language_patterns": list_strings(signal.get("language_patterns"), 8),
        "engagement": engagement,
    }


def normalize_manual_signal(
    *,
    raw_text: str,
    title: str | None = None,
    url: str | None = None,
    author: str | None = None,
    priority_lane: str = "custom",
    source_type: str = "post",
    extraction_method: str = "manual_text",
) -> dict[str, Any]:
    source_channel = infer_source_channel(source_url=url)
    signal = {
        "id": "",
        "ingest_mode": "manual",
        "capture_method": "manual",
        "source_platform": source_channel,
        "source_type": source_type,
        "source_class": "manual",
        "source_url": url or "",
        "author": author or "manual preview",
        "title": title or first_meaningful_line(raw_text)[:120],
        "summary": summarize_text(raw_text),
        "headline_candidates": standout_lines_from_text(raw_text),
        "unit_kind": "claim_block" if len(split_sentences(raw_text)) <= 2 else "full_post",
        "response_modes": ["comment", "repost", "post_seed", "belief_evidence"],
        "priority_lane": normalize_lane(priority_lane),
        "raw_text": raw_text,
        "source_metadata": {"extraction_method": extraction_method},
        "trust_notes": [extraction_method],
    }
    return normalize_saved_signal(signal, raw_text=raw_text)


def build_generation_context(signal: dict[str, Any], lane_id: str) -> dict[str, Any]:
    standout = signal.get("standout_lines") or []
    core_line = clean_sentence(standout[0] if standout else signal.get("summary"))
    supporting_line = ""
    for candidate in standout:
        cleaned = clean_sentence(candidate)
        if cleaned and cleaned.lower() != core_line.lower() and not contains_generic_phrase(cleaned):
            supporting_line = cleaned
            break
    if not supporting_line:
        supporting = signal.get("supporting_claims") or []
        for candidate in supporting:
            cleaned = clean_sentence(candidate)
            if cleaned and cleaned.lower() != core_line.lower() and not contains_generic_phrase(cleaned):
                supporting_line = cleaned
                break
    if not supporting_line:
        summary = clean_sentence(signal.get("summary"))
        if summary and summary.lower() != core_line.lower() and not contains_generic_phrase(summary):
            supporting_line = summary
    belief_context = social_belief_engine.assess_signal(signal, lane_id)
    expression_context = select_source_takeaway(
        candidates=[supporting_line, core_line, clean_sentence(signal.get("summary"))],
        lane_id=lane_id,
    )
    return {
        "title": clean_sentence(signal.get("title")),
        "core_line": ensure_period(core_line or clean_sentence(signal.get("title")) or "this post"),
        "supporting_line": ensure_period(supporting_line) if supporting_line else "",
        "summary": ensure_period(clean_sentence(signal.get("summary"))),
        "source_takeaway": expression_context["output_text"],
        "source_takeaway_origin": expression_context["source_text"],
        "source_takeaway_strategy": expression_context["strategy"],
        "expression_assessment": expression_context,
        "priority_lane": lane_id,
        "belief_used": belief_context["belief_used"],
        "belief_summary": belief_context["belief_summary"],
        "experience_anchor": belief_context["experience_anchor"],
        "experience_summary": belief_context["experience_summary"],
        "stance": belief_context["stance"],
        "agreement_level": belief_context["agreement_level"],
        "role_safety": belief_context["role_safety"],
        "stance_comment_open": belief_context["stance_comment_open"],
        "stance_repost_open": belief_context["stance_repost_open"],
        "bridge_line": belief_context["bridge_line"],
    }


def preserve_source_structure(text: str | None, lane_id: str) -> str:
    cleaned = clean_sentence(text)
    if not cleaned:
        return ""

    not_because_match = re.search(r"not because (?P<a>.+?) but because (?P<b>.+)$", cleaned, flags=re.IGNORECASE)
    if not_because_match:
        a = clean_sentence(not_because_match.group("a"))
        b = clean_sentence(not_because_match.group("b"))
        return ensure_period(f"The issue is not that {a}. It is that {b}")

    isnt_match = re.search(r"isn[’']t (?P<a>.+?), it[’']s (?P<b>.+)$", cleaned, flags=re.IGNORECASE)
    if isnt_match:
        a = clean_sentence(isnt_match.group("a"))
        b = clean_sentence(isnt_match.group("b"))
        return ensure_period(f"The challenge is not {a}. It is {b}")

    substitute_match = re.search(r"not a substitute for (?P<a>.+)$", cleaned, flags=re.IGNORECASE)
    if substitute_match:
        replacement = clean_sentence(substitute_match.group("a"))
        return ensure_period(f"The tool can help, but it cannot replace {replacement}")

    augment_match = re.search(r"can augment (?P<a>.+?), but humans still need to (?P<b>.+)$", cleaned, flags=re.IGNORECASE)
    if augment_match:
        a = clean_sentence(augment_match.group("a"))
        b = clean_sentence(augment_match.group("b"))
        return ensure_period(f"AI can support {a}, but people still need to {b}")

    start_with_match = re.search(r"if you want better (?P<a>.+?), start with (?P<b>.+)$", cleaned, flags=re.IGNORECASE)
    if start_with_match:
        a = clean_sentence(start_with_match.group("a"))
        b = clean_sentence(start_with_match.group("b"))
        return ensure_period(f"If you want better {a}, you have to start closer to {b}")

    return ""


def rewrite_source_claim(text: str | None, lane_id: str) -> str:
    cleaned = clean_sentence(text)
    if not cleaned:
        return ""

    lowered = cleaned.lower()

    not_because_match = re.search(r"not because (?P<a>.+?) but because (?P<b>.+)$", cleaned, flags=re.IGNORECASE)
    if not_because_match:
        a = clean_sentence(not_because_match.group("a"))
        b = clean_sentence(not_because_match.group("b"))
        return ensure_period(f"The constraint is usually {b}, not {a}")

    isnt_match = re.search(r"isn[’']t (?P<a>.+?), it[’']s (?P<b>.+)$", cleaned, flags=re.IGNORECASE)
    if isnt_match:
        a = clean_sentence(isnt_match.group("a"))
        b = clean_sentence(isnt_match.group("b"))
        return ensure_period(f"The bigger challenge is less {a} and more {b}")

    substitute_match = re.search(r"not a substitute for (?P<a>.+)$", cleaned, flags=re.IGNORECASE)
    if substitute_match:
        replacement = clean_sentence(substitute_match.group("a"))
        return ensure_period(f"The tool can assist, but it cannot replace {replacement}")

    augment_match = re.search(r"can augment (?P<a>.+?), but humans still need to (?P<b>.+)$", cleaned, flags=re.IGNORECASE)
    if augment_match:
        a = clean_sentence(augment_match.group("a"))
        b = clean_sentence(augment_match.group("b"))
        return ensure_period(f"The win is augmentation around {a}, while the human layer still has to {b}")

    start_with_match = re.search(r"if you want better (?P<a>.+?), start with (?P<b>.+)$", cleaned, flags=re.IGNORECASE)
    if start_with_match:
        b = clean_sentence(start_with_match.group("b"))
        return ensure_period(f"The strongest signal usually sits closer to {b} than the headline team realizes")

    if "they hear the real questions" in lowered or "questions prospects ask" in lowered:
        return "The frontline usually hears the real questions before the rest of the system does."

    if "human connection" in lowered and "make meaning" in lowered:
        return "The point is not removing the human layer. It is creating more room for judgment, connection, and meaning."

    if "more than ever" in lowered or contains_generic_phrase(cleaned):
        return ""

    if lane_id == "ai" and contains_any(lowered, ["ai", "model", "tool", "prompt", "judgment"]):
        return "The real gap is usually not access by itself. It is whether people know how to use the system with judgment."
    if lane_id == "ops-pm" and contains_any(lowered, ["workflow", "handoff", "ownership", "process", "execution"]):
        return "The issue usually shows up in ownership, handoffs, and how the work actually moves."
    if lane_id == "current-role" and contains_any(lowered, ["student", "family", "staff", "classroom", "education"]):
        return "The useful question is what this changes in the lived experience of the work right now."
    if lane_id == "program-leadership" and contains_any(lowered, ["team", "leadership", "manager", "organization"]):
        return "The leadership move is turning the pattern into shared standards and follow-through."
    if lane_id == "therapy" and contains_any(lowered, ["therapy", "human", "support", "emotion", "trust"]):
        return "The deeper issue is whether the experience still feels clear, containing, and human."
    if lane_id == "referral" and contains_any(lowered, ["partner", "referral", "trust", "family"]):
        return "The referral question is whether someone would feel confident sending the next person into this experience."
    if lane_id == "admissions" and contains_any(lowered, ["admissions", "prospect", "student journey", "enrollment"]):
        return "The frontline signal usually shows up first in the questions people keep asking."

    return ""


def source_takeaway(ctx: dict[str, Any]) -> str:
    return normalize_inline_text(ctx.get("source_takeaway"))


def repost_seed(ctx: dict[str, Any]) -> str:
    seed = source_takeaway(ctx)
    if seed:
        return seed
    fallback_by_lane = {
        "current-role": "The practical value here only shows up once it changes the work.",
        "program-leadership": "The pattern only matters once leadership turns it into process.",
        "ai": "The AI question usually starts at the judgment layer.",
        "ops-pm": "The delivery layer is usually where the real constraint shows up.",
        "therapy": "The human experience underneath the process is usually the real signal.",
        "referral": "The trust question usually shows up after the handoff, not before it.",
        "admissions": "The frontline usually hears the clearest signal first.",
        "enrollment-management": "The journey friction usually appears before the conversion problem does.",
        "entrepreneurship": "The edge usually comes from what gets operationalized, not what gets noticed.",
        "personal-story": "Some lessons only make sense once you have lived them yourself.",
    }
    return fallback_by_lane.get(ctx.get("priority_lane", ""), "The underlying signal here is more practical than it first appears.")


def select_source_takeaway(*, candidates: list[str], lane_id: str) -> dict[str, Any]:
    for candidate in candidates:
        cleaned = clean_sentence(candidate)
        if not cleaned:
            continue

        rewrite_candidates: list[dict[str, str]] = []
        structure_preserving = preserve_source_structure(cleaned, lane_id)
        if structure_preserving:
            rewrite_candidates.append({"text": structure_preserving, "strategy": "structure-preserving"})

        pattern_rewrite = rewrite_source_claim(cleaned, lane_id)
        if pattern_rewrite and normalize_inline_text(pattern_rewrite).lower() not in {
            normalize_inline_text(item["text"]).lower() for item in rewrite_candidates
        }:
            rewrite_candidates.append({"text": pattern_rewrite, "strategy": "pattern-rewrite"})

        if not rewrite_candidates:
            continue

        return social_expression_engine.choose_candidate(cleaned, rewrite_candidates)

    return {
        "source_text": "",
        "output_text": "",
        "strategy": "none",
        "source_structure": "none",
        "output_structure": "none",
        "structure_preserved": True,
        "source_expression_quality": 0.0,
        "output_expression_quality": 0.0,
        "expression_delta": 0.0,
        "overlap_ratio": 0.0,
        "adjusted_output_quality": 0.0,
        "warnings": [],
    }


def comment_open(ctx: dict[str, Any], fallback: str) -> str:
    stance = ctx.get("stance", "")
    stance_open = normalize_inline_text(ctx.get("stance_comment_open"))
    lane_open = normalize_inline_text(fallback)
    if stance in {"counter", "personal-anchor"}:
        return stance_open or lane_open
    return lane_open or stance_open


def repost_open(ctx: dict[str, Any], fallback: str) -> str:
    stance = ctx.get("stance", "")
    stance_open = normalize_inline_text(ctx.get("stance_repost_open"))
    lane_open = normalize_inline_text(fallback)
    if stance in {"counter", "personal-anchor"}:
        return stance_open or lane_open
    return lane_open or stance_open


def bridge_line(ctx: dict[str, Any]) -> str:
    return ctx.get("bridge_line", "")


def contains_any(text: str, needles: list[str]) -> bool:
    lowered = text.lower()
    for needle in needles:
        token = needle.lower()
        if token.isalpha() and len(token) <= 3:
            if re.search(rf"\b{re.escape(token)}\b", lowered):
                return True
            continue
        if token in lowered:
            return True
    return False


def infer_signal_profile(ctx: dict[str, str]) -> dict[str, bool]:
    text = " ".join(
        [
            ctx.get("title", ""),
            ctx.get("core_line", ""),
            ctx.get("supporting_line", ""),
            ctx.get("summary", ""),
            ctx.get("priority_lane", ""),
        ]
    ).lower()
    return {
        "is_ai": contains_any(text, ["ai", "agent", "model", "workflow", "context"]),
        "is_education": contains_any(text, ["education", "higher ed", "student", "admissions", "enrollment"]),
        "is_admissions": contains_any(text, ["admissions", "prospect", "student journey", "enrollment"]),
        "is_trust": contains_any(text, ["trust", "referral", "family", "human connection", "relationship"]),
        "is_role": contains_any(text, ["current role", "current job", "institution", "staff", "student success", "team", "organization"]),
        "is_ops": contains_any(text, ["workflow", "ownership", "handoff", "project", "pm", "process", "operations", "execution"]),
        "is_therapy": contains_any(text, ["therapy", "therapist", "mental health", "healing", "emotion", "nervous system"]),
        "is_referral": contains_any(text, ["referral", "partner", "consultant", "counselor", "handoff", "trusted source"]),
    }


def build_admissions_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    profile = infer_signal_profile(ctx)
    if profile["is_admissions"]:
        return (
            join_parts(
                [
                    comment_open(ctx, "That part matters."),
                    source_takeaway(ctx),
                    bridge_line(ctx),
                    "That is usually where the real market signal shows up before the website, campaign, or pitch deck catches up.",
                    "When teams feed that back into messaging and follow-up, trust and enrollment both get stronger.",
                ]
            ),
            "The frontline questions are usually the strategy.",
            join_parts(
                [
                    repost_open(ctx, repost_seed(ctx)),
                    "Admissions teams usually hear the market before the rest of the institution does.",
                    "The repeated questions are often the clearest signal about where message clarity, follow-up, or the student journey still needs work.",
                ]
            ),
        )

    return (
        join_parts(
            [
                comment_open(ctx, "This is what teams miss."),
                source_takeaway(ctx),
                bridge_line(ctx),
                "In admissions work, this same issue usually shows up when teams lose context between inquiry, follow-up, and handoff.",
                "When that context is tighter, the experience feels more human and the pipeline gets stronger.",
            ]
        ),
        "Context gaps show up fast in admissions.",
        join_parts(
            [
                repost_open(ctx, repost_seed(ctx)),
                "This same issue shows up when context breaks between the first conversation, the next follow-up, and what the student or family actually needs.",
                "That is usually where experience, trust, and conversion all start moving in the wrong direction.",
            ]
        ),
    )


def build_entrepreneurship_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    return (
        join_parts(
            [
                comment_open(ctx, "There is a real builder lesson in this."),
                source_takeaway(ctx),
                bridge_line(ctx),
                "The edge is usually not the headline idea by itself. It is what you do with that signal operationally.",
                "The builders who turn repeated insight into process usually compound faster.",
            ]
        ),
        "The edge is usually in the system.",
        join_parts(
            [
                repost_open(ctx, repost_seed(ctx)),
                "This feels more like an execution lesson than a content lesson.",
                "The people closest to the work usually see the friction, demand, and language patterns first, which is where better systems tend to come from.",
            ]
        ),
    )


def build_current_role_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    return (
        join_parts(
            [
                comment_open(ctx, "This lands for me in the day-to-day work."),
                source_takeaway(ctx),
                bridge_line(ctx),
                "In the current role, the real test is whether students, families, staff, or the next owner of the work actually feel the difference.",
                "If it does not change follow-through, clarity, or support this week, it is still just a smart observation.",
            ]
        ),
        "If it does not change the next step, it is still theory.",
        join_parts(
            [
                repost_open(ctx, repost_seed(ctx)),
                "I keep reading this through the current-job lens.",
                "The real question is what changes for students, families, staff, or execution this week because of it.",
            ]
        ),
    )


def build_personal_story_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    return (
        join_parts(
            [
                comment_open(ctx, "This hits a nerve for me."),
                source_takeaway(ctx),
                bridge_line(ctx),
                "A lot of these lessons only become obvious once you are the one carrying the follow-through instead of talking about it from a distance.",
                "That is usually where the insight stops being abstract and starts changing how you work.",
            ]
        ),
        "This one feels lived-in.",
        join_parts(
            [
                repost_open(ctx, repost_seed(ctx)),
                "I have learned some version of this the hard way.",
                "The part that sticks is usually not the idea itself. It is what becomes clear once you are the person holding the responsibility on the other side of it.",
            ]
        ),
    )


def build_program_leadership_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    return (
        join_parts(
            [
                comment_open(ctx, "This is where leadership either compounds the signal or wastes it."),
                source_takeaway(ctx),
                bridge_line(ctx),
                "The teams closest to the work usually hear the signal first, but leadership shows up in whether that becomes shared standards, coaching, and decision-making.",
                "If it never gets translated into something the broader team can repeat, it stays as an anecdote instead of becoming execution.",
            ]
        ),
        "Leaders have to turn the pattern into something repeatable.",
        join_parts(
            [
                repost_open(ctx, repost_seed(ctx)),
                "This is a leadership signal as much as a content or systems signal.",
                "The job is not just spotting the pattern early. It is building the shared process and coaching around it before the drift gets expensive.",
            ]
        ),
    )


def build_therapy_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    profile = infer_signal_profile(ctx)
    if profile["is_therapy"] or profile["is_trust"]:
        return (
            join_parts(
                [
                    comment_open(ctx, "This lands for me as an attunement and regulation issue, not just a systems issue."),
                    source_takeaway(ctx),
                    bridge_line(ctx),
                    "People can usually feel the difference between support that is merely efficient and support that is actually containing, clear, and attuned.",
                    "That is where the therapeutic layer shows up for me because the quality of the container changes what people can do inside it.",
                ]
            ),
            "People feel the quality of the container fast.",
            join_parts(
                [
                    repost_open(ctx, repost_seed(ctx)),
                    "The part I keep coming back to is the emotional experience underneath the process.",
                    "Even a strong workflow can miss the mark if people do not feel accurately held, regulated, and understood inside it.",
                ]
            ),
        )

    return (
        join_parts(
            [
                comment_open(ctx, "Even when a post sounds practical, I still hear the attunement question underneath it."),
                source_takeaway(ctx),
                bridge_line(ctx),
                "A lot of people can tolerate friction if they still feel seen, but they usually disengage once the experience feels cold, dysregulating, or misattuned.",
                "That is what makes this feel like a therapy lens to me rather than only an ops lens.",
            ]
        ),
        "People know when the support stops feeling attuned.",
        join_parts(
            [
                repost_open(ctx, repost_seed(ctx)),
                "I keep hearing the human side of the experience in this.",
                "A lot of process questions are also emotional-safety questions once a real person is living inside the system.",
            ]
        ),
    )


def build_referral_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    profile = infer_signal_profile(ctx)
    if profile["is_referral"] or profile["is_trust"] or profile["is_admissions"]:
        return (
            join_parts(
                [
                    comment_open(ctx, "This feels like a referral-confidence issue to me."),
                    source_takeaway(ctx),
                    bridge_line(ctx),
                    "Strong referral ecosystems usually grow when partners trust what happens after the handoff, not just the pitch before it.",
                    "That confidence gets built through clarity, responsiveness, and a receiving experience someone would feel good putting their name behind again.",
                ]
            ),
            "Referral trust usually lives after the handoff.",
            join_parts(
            [
                repost_open(ctx, repost_seed(ctx)),
                "I read this through the referral lens.",
                "The real question is whether a partner, parent, or trusted source would feel confident sending the next person into this experience again.",
            ]
        ),
    )

    return (
        join_parts(
            [
                comment_open(ctx, "This still sounds like a referral-system question to me."),
                source_takeaway(ctx),
                bridge_line(ctx),
                "Partnerships usually get stronger when expectations are clear and the receiving experience is easy to trust.",
                "That is what makes people send the next person with confidence instead of hesitation because their own reputation is on the line too.",
            ]
        ),
        "Partners repeat what they can trust.",
        join_parts(
            [
                repost_open(ctx, repost_seed(ctx)),
                "The referral lens here is about confidence in the receiving system.",
                "If the experience is not clear and dependable after the handoff, the partnership eventually weakens no matter how good the relationship sounded up front.",
            ]
        ),
    )


def build_enrollment_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    profile = infer_signal_profile(ctx)
    if profile["is_admissions"] or profile["is_education"]:
        return (
            join_parts(
                [
                    comment_open(ctx, "This is an enrollment signal to me."),
                    source_takeaway(ctx),
                    bridge_line(ctx),
                    "Repeated confusion is usually a journey problem before it becomes a conversion problem.",
                    "The more clearly teams can hear and resolve that friction, the better the downstream fit and follow-through tend to be.",
                ]
            ),
            "Repeated confusion is usually a journey problem.",
            join_parts(
            [
                repost_open(ctx, repost_seed(ctx)),
                "I read this as an enrollment operations signal.",
                "Small clarity gaps tend to show up later as weaker follow-up, lower conversion, or avoidable friction in the student journey.",
            ]
        ),
        )

    return (
        join_parts(
            [
                comment_open(ctx, "I still read this as an enrollment operations issue."),
                source_takeaway(ctx),
                bridge_line(ctx),
                "This is what happens when teams do not have enough context to guide the next step well.",
                "That usually shows up later as weaker follow-through and more avoidable friction.",
            ]
        ),
        "Bad context usually becomes enrollment friction.",
        join_parts(
            [
                repost_open(ctx, repost_seed(ctx)),
                "This still reads like an enrollment operations issue to me.",
                "When context is weak, the next step gets weaker too, and that tends to show up later as drop-off, confusion, or slow follow-through.",
            ]
        ),
    )


def build_ai_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    profile = infer_signal_profile(ctx)
    if profile["is_ai"]:
        return (
            join_parts(
                [
                    comment_open(ctx, "The AI point here is stronger than people think."),
                    source_takeaway(ctx),
                    bridge_line(ctx),
                    "AI literacy is not just tool familiarity. It is knowing how to ask better questions, pressure-test outputs, and keep human judgment in the loop.",
                    "That is usually the real divide once the technology is already in the room because access alone does not teach discernment.",
                ]
            ),
            "AI literacy is judgment, not just access.",
            join_parts(
            [
                repost_open(ctx, repost_seed(ctx)),
                "I read this first through an AI lens.",
                "The practical gap is rarely raw access anymore. It is whether people know how to direct the system well and challenge weak outputs when they show up.",
            ]
        ),
        )

    return (
        join_parts(
            [
                comment_open(ctx, "Even when a post is not explicitly about AI, it still points to an AI-judgment question."),
                source_takeaway(ctx),
                bridge_line(ctx),
                "The difference usually comes down to whether people can evaluate, translate, and apply the output with discernment.",
                "That is what makes the AI lens different from a general operations lens because the judgment layer has to stay visible.",
            ]
        ),
        "The AI layer is usually a judgment layer.",
        join_parts(
            [
                repost_open(ctx, repost_seed(ctx)),
                "I still see an AI question sitting underneath this.",
                "Once teams know how to direct, evaluate, and challenge the system well, the downstream quality changes a lot.",
            ]
        ),
    )


def build_ops_pm_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    profile = infer_signal_profile(ctx)
    if profile["is_ops"] or profile["is_ai"]:
        return (
            join_parts(
                [
                    comment_open(ctx, "This reads like a delivery design problem before anything else."),
                    source_takeaway(ctx),
                    bridge_line(ctx),
                    "Most teams do not break at the strategy layer. They break at the handoff, ownership, cadence, and follow-through layer.",
                    "That is why this feels more like workflow design and project control than thought leadership to me.",
                ]
            ),
            "Weak ownership usually kills the good idea.",
            join_parts(
                [
                repost_open(ctx, repost_seed(ctx)),
                    "I read this through an ops and PM lens.",
                    "The real question is who owns the next step, how the work moves, and where the process is currently leaking before the delay becomes normal.",
                ]
            ),
        )

    return (
        join_parts(
            [
                comment_open(ctx, "Even if the post sounds strategic, I still hear a delivery problem inside it."),
                source_takeaway(ctx),
                bridge_line(ctx),
                "Operations and project management usually show up in how work gets translated into repeatable action.",
                "That is where clarity, cadence, accountability, and clean handoffs start mattering more than the original idea.",
            ]
        ),
        "The delivery layer usually decides the outcome.",
        join_parts(
            [
                repost_open(ctx, repost_seed(ctx)),
                "This sounds like an ops and PM question to me.",
                "If the ownership model and workflow are weak, the idea usually stalls no matter how strong it sounded up front.",
            ]
        ),
    )


COMMENT_BUILDERS = {
    "admissions": build_admissions_comment,
    "entrepreneurship": build_entrepreneurship_comment,
    "current-role": build_current_role_comment,
    "personal-story": build_personal_story_comment,
    "program-leadership": build_program_leadership_comment,
    "enrollment-management": build_enrollment_comment,
    "ai": build_ai_comment,
    "ops-pm": build_ops_pm_comment,
    "therapy": build_therapy_comment,
    "referral": build_referral_comment,
}


def build_variants(signal: dict[str, Any]) -> dict[str, dict[str, Any]]:
    variants: dict[str, dict[str, Any]] = {}
    for lens_id in LENS_IDS:
        context = build_generation_context(signal, lens_id)
        comment, short_comment, repost = COMMENT_BUILDERS[lens_id](context)
        normalized_comment = " ".join(normalize_voice(comment).split())
        normalized_short_comment = " ".join(normalize_voice(short_comment).split())
        normalized_repost = " ".join(normalize_voice(repost).split())
        belief_assessment = {
            "stance": context["stance"],
            "agreement_level": context["agreement_level"],
            "belief_used": context["belief_used"],
            "belief_summary": context["belief_summary"],
            "experience_anchor": context["experience_anchor"],
            "experience_summary": context["experience_summary"],
            "role_safety": context["role_safety"],
        }
        expression_assessment = context["expression_assessment"]
        technique_assessment = social_technique_engine.select_for_variant(signal, lens_id, belief_assessment)
        evaluation = social_evaluation_engine.evaluate_variant(
            lane_id=lens_id,
            signal=signal,
            belief=belief_assessment,
            technique=technique_assessment,
            expression=expression_assessment,
            comment=normalized_comment,
            repost=normalized_repost,
            short_comment=normalized_short_comment,
        )
        variants[lens_id] = {
            "label": LENS_LABELS[lens_id],
            "comment": normalized_comment,
            "short_comment": normalized_short_comment,
            "repost": normalized_repost,
            "why_this_angle": f"Use a {LENS_LABELS[lens_id].lower()} framing for this signal. {technique_assessment['reason']}.",
            "stance": context["stance"],
            "agreement_level": context["agreement_level"],
            "belief_used": context["belief_used"],
            "belief_summary": context["belief_summary"],
            "experience_anchor": context["experience_anchor"],
            "experience_summary": context["experience_summary"],
            "role_safety": context["role_safety"],
            "techniques": technique_assessment["techniques"],
            "emotional_profile": technique_assessment["emotional_profile"],
            "technique_reason": technique_assessment["reason"],
            "expression_assessment": expression_assessment,
            "evaluation": evaluation,
        }
    return variants
