from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from app.services.social_article_understanding_service import social_article_understanding_service
from app.services.social_belief_engine import social_belief_engine
from app.services.social_evaluation_engine import social_evaluation_engine
from app.services.social_expression_engine import social_expression_engine
from app.services.social_johnnie_perspective_service import social_johnnie_perspective_service
from app.services.social_persona_retrieval_service import social_persona_retrieval_service
from app.services.social_reaction_brief_service import social_reaction_brief_service
from app.services.social_response_type_service import social_response_type_service
from app.services.social_stage_evaluation_service import social_stage_evaluation_service
from app.services.social_template_composition_service import social_template_composition_service
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
    cleaned: list[str] = []
    seen: set[str] = set()
    for part in parts:
        normalized = normalize_inline_text(part)
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(normalized)
    return " ".join(cleaned)


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


ABSTRACT_BRIDGE_PHRASES = [
    "abstract commentary",
    "community-facing execution",
    "live operating role",
]

STANCE_OPEN_OPTIONS = {
    "reinforce": {
        "comment": [
            "That part matters.",
            "This tracks for me.",
            "That lands.",
        ],
        "repost": [
            "This is directionally right.",
            "This points at the right issue.",
            "This is closer to the real issue than most takes.",
        ],
    },
    "nuance": {
        "comment": [
            "Look, people get this wrong all the time. The signal is real, but the frame is incomplete.",
            "I understand where they're coming from, but here's where I can't rock with it.",
            "They're not wrong, but that's incomplete.",
            "Can I be honest? The direction is fine, but the frame gets too clean for real life.",
            "That's an interesting perspective. The issue usually shows up one layer lower in the work.",
        ],
        "repost": [
            "The signal is there, but the conversation usually stops too early.",
            "I understand the core point, but here's where it loses me.",
            "Directionally yes, but here's where I can't rock with the framing.",
            "The signal is there. The story around it gets too clean.",
        ],
    },
    "counter": {
        "comment": [
            "Look, that's not really the issue.",
            "Look, here's where I can't rock with it.",
            "Can I be honest? That dog will not hunt once this hits real life.",
            "That's an interesting perspective, but the work usually breaks underneath that headline.",
        ],
        "repost": [
            "They're not wrong, but that's incomplete.",
            "Look, I would frame this a little differently.",
            "Here's where the frame loses me.",
            "The headline sounds clean. Real life is messier than that.",
        ],
    },
    "translate": {
        "comment": [
            "Real talk: this gets more useful once you bring it down into the day-to-day work.",
            "I keep translating this into the real work on the ground.",
            "Read that again. It changes once the work is actually yours to carry.",
        ],
        "repost": [
            "This changes once it touches the real work.",
            "Real talk: this reads differently once it hits the day-to-day work.",
            "This gets clearer once it reaches the real operating environment.",
        ],
    },
    "personal-anchor": {
        "comment": [
            "I have seen some version of this up close.",
            "This feels familiar for a reason.",
            "I know this pattern a little too well.",
        ],
        "repost": [
            "This feels familiar for a reason.",
            "I have seen this pattern up close before.",
            "This one sounds different when you have lived some version of it.",
        ],
    },
    "systemize": {
        "comment": [
            "Show me the artifact. The idea is only useful once it becomes a system.",
            "The pattern only matters once it becomes a system.",
            "If it cannot survive the workflow, it is just another tab.",
        ],
        "repost": [
            "The idea is only useful once it becomes process.",
            "Show me the artifact. The pattern only counts once the system changes around it.",
            "If it never becomes repeatable, it is just another tab.",
        ],
    },
}

STANCE_CONTRAST_OPTIONS = {
    "reinforce": {
        "comment": [
            "The part worth repeating is what this changes in practice.",
            "The useful part is what this changes once it leaves the headline.",
            "The real value shows up in what this changes downstream.",
        ],
        "repost": [
            "The part worth keeping is what this changes in practice.",
            "The useful version is what survives contact with the work.",
            "The downstream change is the part that actually matters.",
        ],
    },
    "nuance": {
        "comment": [
            "That's incomplete. The real shift usually shows up in execution.",
            "I see why people say this, but the real break usually shows up in the handoff.",
            "I understand the story. Show me the artifact.",
            "The headline is fine. The process underneath it is where it gets real.",
        ],
        "repost": [
            "That's not really the issue. The practical shift usually shows up later.",
            "Directionally yes, but the practical issue usually sits one layer lower.",
            "The headline is fine. The operational problem is usually underneath it.",
            "I agree with the signal, but the real friction usually shows up later.",
        ],
    },
    "counter": {
        "comment": [
            "That frame is too clean. The real shift usually shows up once the work starts moving.",
            "That sounds good, but that's not how it works in real life.",
            "The story sounds clean. Show me the artifact.",
            "This is not really a system if it falls apart in the workflow.",
        ],
        "repost": [
            "Partial functionality can hide a real system failure.",
            "That is a story. Where is the artifact?",
            "The headline is not wrong. The real constraint usually sits underneath the workflow.",
            "That dog will not hunt once the process gets real.",
        ],
    },
    "translate": {
        "comment": [
            "The useful version is what survives contact with the actual work.",
            "This only gets sharper once it meets the day-to-day work.",
            "The real test is what this sounds like on the ground.",
        ],
        "repost": [
            "This only gets useful once it reaches the real work.",
            "The practical version is what survives contact with the work.",
            "The real test is what this changes on the ground.",
        ],
    },
    "personal-anchor": {
        "comment": [
            "This sounds cleaner on paper than it does when you are the one carrying it.",
            "It reads one way from a distance and another way from inside the work.",
            "This lands differently once you have had to carry the follow-through.",
        ],
        "repost": [
            "This reads differently once you have had to carry it.",
            "It sounds one way from a distance and another way from inside the work.",
            "This lands differently once the follow-through is yours.",
        ],
    },
    "systemize": {
        "comment": [
            "The idea is not the finish line. The repeatable system is.",
            "Noticing the pattern is one thing. Making it repeatable is the real move.",
            "Show me the artifact. The system built around the pattern is what matters.",
        ],
        "repost": [
            "The idea is not enough. The repeatable system is the real story.",
            "If it is not useful, it is just another tab.",
            "Seeing the signal is one thing. Turning it into process is the real move.",
        ],
    },
}


def normalize_lane(value: str | None) -> str:
    if not value:
        return "current-role"
    lowered = normalize_inline_text(value).lower()
    normalized = LANE_ALIASES.get(lowered, lowered.replace("_", "-").replace(" ", "-"))
    return normalized if normalized in LENS_IDS else "current-role"


def _variation_seed(ctx: dict[str, Any], slot: str) -> int:
    payload = "|".join(
        [
            normalize_inline_text(ctx.get("title")),
            normalize_inline_text(ctx.get("priority_lane")),
            normalize_inline_text(ctx.get("stance")),
            normalize_inline_text(((ctx.get("response_type_packet") or {}).get("response_type"))),
            normalize_inline_text(ctx.get("source_takeaway_origin")),
            slot,
        ]
    )
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def pick_option(ctx: dict[str, Any], slot: str, options: list[str], fallback: str = "") -> str:
    cleaned: list[str] = []
    seen: set[str] = set()
    for option in options:
        normalized = normalize_inline_text(option)
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(normalized)
    if not cleaned:
        return normalize_inline_text(fallback)
    index = _variation_seed(ctx, slot) % len(cleaned)
    selected = cleaned[index]
    social_template_composition_service.record_option(
        ctx,
        slot=slot,
        options=cleaned,
        selected=selected,
        selected_index=index,
    )
    return selected


def pick_template(ctx: dict[str, Any], slot: str, templates: list[list[str]]) -> list[str]:
    if not templates:
        return []
    selected = templates[_variation_seed(ctx, slot) % len(templates)]
    social_template_composition_service.record_template(
        ctx,
        slot=slot,
        templates=templates,
        selected=selected,
    )
    return selected


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
    article_understanding = social_article_understanding_service.analyze(signal, lane_id)
    persona_retrieval = social_persona_retrieval_service.retrieve(signal, lane_id, article_understanding)
    belief_context = social_belief_engine.assess_signal(
        signal,
        lane_id,
        article_understanding=article_understanding,
        persona_retrieval=persona_retrieval,
    )

    selected_belief = persona_retrieval.get("selected_belief") or {}
    selected_experience = persona_retrieval.get("selected_experience") or {}
    selected_belief_text = clean_sentence(selected_belief.get("summary_text") or selected_belief.get("text"))
    selected_experience_text = clean_sentence(selected_experience.get("summary_text") or selected_experience.get("text"))
    if selected_belief_text:
        belief_context["belief_used"] = selected_belief.get("title") or belief_context.get("belief_used", "")
        belief_context["belief_summary"] = selected_belief_text
    if selected_experience_text:
        belief_context["experience_anchor"] = selected_experience.get("title") or belief_context.get("experience_anchor", "")
        belief_context["experience_summary"] = selected_experience_text

    johnnie_perspective = social_johnnie_perspective_service.build(
        signal=signal,
        lane_id=lane_id,
        article_understanding=article_understanding,
        persona_retrieval=persona_retrieval,
        belief_assessment=belief_context,
    )

    expression_context = select_source_takeaway(
        candidates=[supporting_line, core_line, clean_sentence(signal.get("summary"))],
        lane_id=lane_id,
        article_understanding=article_understanding,
    )
    if not normalize_inline_text(expression_context.get("output_text")) and normalize_inline_text(article_understanding.get("thesis")):
        expression_context = {
            **expression_context,
            "source_text": article_understanding.get("thesis", ""),
            "output_text": ensure_period(article_understanding.get("thesis", "")),
            "strategy": "article-understanding-fallback",
            "source_structure": article_understanding.get("source_expression", "plain"),
            "output_structure": article_understanding.get("source_expression", "plain"),
            "structure_preserved": True,
            "source_expression_quality": 7.0,
            "output_expression_quality": 7.2,
            "expression_delta": 0.2,
            "overlap_ratio": 0.0,
            "adjusted_output_quality": 7.2,
            "warnings": [],
        }

    reaction_brief = social_reaction_brief_service.build(
        lane_id=lane_id,
        article_understanding=article_understanding,
        persona_retrieval=persona_retrieval,
        johnnie_perspective=johnnie_perspective,
    )
    response_type_packet = social_response_type_service.select(
        signal=signal,
        lane_id=lane_id,
        article_understanding=article_understanding,
        johnnie_perspective=johnnie_perspective,
        reaction_brief=reaction_brief,
    )

    rendered_stance = belief_context["stance"]
    response_type = normalize_inline_text(response_type_packet.get("response_type")).lower()
    if response_type == "personal_story":
        rendered_stance = "personal-anchor"
    elif response_type == "contrarian" and rendered_stance not in {"counter", "nuance"}:
        rendered_stance = "counter"

    return {
        "title": clean_sentence(signal.get("title")),
        "core_line": ensure_period(core_line or clean_sentence(signal.get("title")) or "this post"),
        "supporting_line": ensure_period(supporting_line) if supporting_line else "",
        "summary": ensure_period(clean_sentence(signal.get("summary"))),
        "source_takeaway": expression_context["output_text"] or ensure_period(article_understanding.get("thesis")),
        "source_takeaway_origin": expression_context["source_text"] or article_understanding.get("thesis", ""),
        "source_takeaway_strategy": expression_context["strategy"],
        "expression_assessment": expression_context,
        "priority_lane": lane_id,
        "belief_used": belief_context["belief_used"],
        "belief_summary": belief_context["belief_summary"],
        "experience_anchor": belief_context["experience_anchor"],
        "experience_summary": belief_context["experience_summary"],
        "base_stance": belief_context["stance"],
        "stance": rendered_stance,
        "agreement_level": belief_context["agreement_level"],
        "role_safety": belief_context["role_safety"],
        "stance_comment_open": belief_context["stance_comment_open"],
        "stance_repost_open": belief_context["stance_repost_open"],
        "bridge_line": belief_context["bridge_line"],
        "article_understanding": article_understanding,
        "persona_retrieval": persona_retrieval,
        "johnnie_perspective": johnnie_perspective,
        "reaction_brief": reaction_brief,
        "response_type_packet": response_type_packet,
        "response_type_comment_open": response_type_packet.get("comment_open_override") or "",
        "response_type_repost_open": response_type_packet.get("repost_open_override") or "",
        "response_type_bridge": response_type_packet.get("bridge_override") or "",
    }


def preserve_source_structure(text: str | None, lane_id: str) -> str:
    cleaned = clean_sentence(text)
    if not cleaned:
        return ""

    lowered = cleaned.lower()

    if "what compounds is" in lowered:
        match = re.search(r"what compounds is (?P<rest>.+?)(?:\.|$)", cleaned, flags=re.IGNORECASE)
        if match:
            rest = clean_sentence(match.group("rest"))
            if "stops being the moat" in lowered:
                return ensure_period(f"Feature speed is no longer the moat by itself. What compounds is {rest}")
            return ensure_period(f"What compounds is {rest}")

    if "does not stay confined to" in lowered or "doesn't stay confined to" in lowered:
        confined_match = re.search(r"does not stay confined to (?P<scope>.+?)(?:\.|$)", cleaned, flags=re.IGNORECASE)
        follow_match = re.search(r"\.\s*(?P<follow>[A-Z][^.]+)", cleaned)
        scope = clean_sentence(confined_match.group("scope")) if confined_match else ""
        follow = clean_sentence(follow_match.group("follow")) if follow_match else ""
        if scope and follow:
            return ensure_period(
                f"The pressure does not stay confined to {scope}. It eventually shows up when {follow[0].lower() + follow[1:]}"
            )
        if scope:
            return ensure_period(f"The pressure does not stay confined to {scope}")

    if "long before" in lowered:
        sentence_match = re.search(r"(?P<sentence>[^.]*long before[^.]*\.)", cleaned, flags=re.IGNORECASE)
        sentence = normalize_inline_text(sentence_match.group("sentence")) if sentence_match else ""
        if sentence:
            return ensure_period(f"The timing gap is the real issue. {sentence}")

    hidden_match = re.search(
        r"the real (gap|issue|problem|constraint|question|test) (usually )?(shows up|sits|starts) in (?P<rest>.+?)(?:\.|$)",
        cleaned,
        flags=re.IGNORECASE,
    )
    if hidden_match:
        rest = clean_sentence(hidden_match.group("rest"))
        return ensure_period(f"The real gap usually shows up in {rest}")

    visible_match = re.search(
        r"the visible (?P<surface>.+?) is usually cleaner than the underlying (?P<hidden>.+?)(?:\.|$)",
        cleaned,
        flags=re.IGNORECASE,
    )
    if visible_match:
        surface = clean_sentence(visible_match.group("surface"))
        hidden = clean_sentence(visible_match.group("hidden"))
        return ensure_period(f"The visible {surface} is not the real system. The underlying {hidden} is where the break usually lives")

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

    model_strategy_match = re.search(
        r"model choice like the whole strategy\.\s*the real gap usually shows up in (?P<rest>.+?)\.\s*access to more models does not help if (?P<condition>.+)$",
        cleaned,
        flags=re.IGNORECASE,
    )
    if model_strategy_match:
        rest = clean_sentence(model_strategy_match.group("rest"))
        condition = clean_sentence(model_strategy_match.group("condition"))
        return ensure_period(f"The bottleneck is not model access by itself. It usually shows up in {rest}, especially when {condition}")

    real_gap_match = re.search(
        r"the real (gap|issue|problem|constraint|question|test) (usually )?(shows up|sits|starts) in (?P<rest>.+?)(?:\.|$)",
        cleaned,
        flags=re.IGNORECASE,
    )
    if real_gap_match:
        rest = clean_sentence(real_gap_match.group("rest"))
        return ensure_period(f"The real gap usually shows up in {rest}")

    rare_because_match = re.search(
        r"rarely .+? because (?P<a>.+?)\. (?:they|teams|people|operators|leaders) .+? because (?P<b>.+?)(?:\.|$)",
        cleaned,
        flags=re.IGNORECASE,
    )
    if rare_because_match:
        a = clean_sentence(rare_because_match.group("a"))
        b = clean_sentence(rare_because_match.group("b"))
        return ensure_period(f"The visible problem is rarely {a}. The real break usually happens because {b}")

    confined_match = re.search(r"does not stay confined to (?P<scope>.+?)(?:\.|$)", cleaned, flags=re.IGNORECASE)
    if confined_match:
        scope = clean_sentence(confined_match.group("scope"))
        return ensure_period(f"The pressure does not stay confined to {scope}")

    timing_match = re.search(r"(?P<sentence>[^.]*long before[^.]*)(?:\.|$)", cleaned, flags=re.IGNORECASE)
    if timing_match:
        sentence = clean_sentence(timing_match.group("sentence"))
        return ensure_period(f"The timing gap is the issue. {sentence}")

    trend_match = re.search(r"what compounds is (?P<rest>.+?)(?:\.|$)", cleaned, flags=re.IGNORECASE)
    if trend_match:
        rest = clean_sentence(trend_match.group("rest"))
        return ensure_period(f"What compounds is {rest}")

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


def select_source_takeaway(*, candidates: list[str], lane_id: str, article_understanding: dict[str, Any] | None = None) -> dict[str, Any]:
    article_understanding = article_understanding or {}
    candidate_pool: list[str] = []
    for candidate in [
        article_understanding.get("source_expression_text"),
        *(article_understanding.get("supporting_claims") or [])[:2],
        article_understanding.get("thesis"),
        *candidates,
    ]:
        cleaned_candidate = clean_sentence(candidate)
        if cleaned_candidate and cleaned_candidate.lower() not in {item.lower() for item in candidate_pool}:
            candidate_pool.append(cleaned_candidate)

    assessed_sources: list[dict[str, Any]] = []
    for candidate in candidate_pool:
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

        assessed_sources.append(social_expression_engine.choose_candidate(cleaned, rewrite_candidates))

    if assessed_sources:
        assessed_sources.sort(
            key=lambda item: (
                item["structure_preserved"] and item["source_structure"] not in {"none", "plain"},
                item["adjusted_output_quality"],
                -item["overlap_ratio"],
            ),
            reverse=True,
        )
        return assessed_sources[0]

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
    response_type_open = normalize_inline_text(ctx.get("response_type_comment_open"))
    stance = ctx.get("stance", "")
    stance_open = normalize_inline_text(ctx.get("stance_comment_open"))
    lane_open = normalize_inline_text(fallback)
    bank = (STANCE_OPEN_OPTIONS.get(stance, {}) or {}).get("comment", [])
    if response_type_open:
        return pick_option(ctx, "comment-open", [response_type_open, stance_open, lane_open, *bank], response_type_open)
    if stance in {"counter", "personal-anchor"}:
        return pick_option(ctx, "comment-open", [stance_open, lane_open, *bank], stance_open or lane_open)
    return pick_option(ctx, "comment-open", [lane_open, stance_open, *bank], lane_open or stance_open)


def repost_open(ctx: dict[str, Any], fallback: str) -> str:
    response_type_open = normalize_inline_text(ctx.get("response_type_repost_open"))
    stance = ctx.get("stance", "")
    stance_open = normalize_inline_text(ctx.get("stance_repost_open"))
    lane_open = normalize_inline_text(fallback)
    bank = (STANCE_OPEN_OPTIONS.get(stance, {}) or {}).get("repost", [])
    if response_type_open:
        return pick_option(ctx, "repost-open", [response_type_open, stance_open, lane_open, *bank], response_type_open)
    if stance in {"counter", "personal-anchor"}:
        return pick_option(ctx, "repost-open", [stance_open, lane_open, *bank], stance_open or lane_open)
    return pick_option(ctx, "repost-open", [lane_open, stance_open, *bank], lane_open or stance_open)


def bridge_line(ctx: dict[str, Any]) -> str:
    response_type_bridge = normalize_inline_text(ctx.get("response_type_bridge"))
    if response_type_bridge:
        return ensure_period(response_type_bridge)
    raw = normalize_inline_text(ctx.get("bridge_line"))
    if not raw:
        return ""
    lowered = raw.lower()
    if any(phrase in lowered for phrase in ABSTRACT_BRIDGE_PHRASES):
        return ""
    if re.match(r"^(keeps|builds|strengthens|creates|turns|solves)\b", lowered):
        return ensure_period(f"That {lowered}")
    return ensure_period(raw)


def stance_contrast_line(ctx: dict[str, Any], kind: str) -> str:
    stance = normalize_inline_text(ctx.get("stance")).lower()
    bank = (STANCE_CONTRAST_OPTIONS.get(stance, {}) or {}).get(kind, [])
    return pick_option(ctx, f"{kind}-contrast", bank, "")


def response_templates(kind: str, stance: str) -> list[list[str]]:
    normalized_kind = normalize_inline_text(kind).lower()
    normalized_stance = normalize_inline_text(stance).lower()

    if normalized_kind == "comment":
        if normalized_stance in {"counter", "nuance"}:
            return [
                ["open", "contrast", "takeaway", "main", "close"],
                ["open", "takeaway", "contrast", "main", "close"],
                ["open", "contrast", "main", "close"],
                ["open", "main", "contrast", "close"],
            ]
        if normalized_stance == "systemize":
            return [
                ["open", "contrast", "main", "close"],
                ["open", "takeaway", "contrast", "main", "close"],
                ["open", "main", "takeaway", "close"],
            ]
        if normalized_stance == "personal-anchor":
            return [
                ["open", "contrast", "main", "close"],
                ["open", "takeaway", "main", "close"],
                ["open", "main", "takeaway", "close"],
            ]
        return [
            ["open", "takeaway", "bridge", "main", "close"],
            ["open", "takeaway", "main", "close"],
            ["open", "contrast", "main", "close"],
            ["open", "main", "takeaway", "close"],
        ]

    if normalized_stance in {"counter", "nuance", "systemize"}:
        return [
            ["open", "contrast", "main", "close"],
            ["open", "main", "contrast", "close"],
            ["open", "main", "close"],
        ]
    if normalized_stance == "personal-anchor":
        return [
            ["open", "contrast", "main", "close"],
            ["open", "main", "close"],
            ["open", "takeaway", "main", "close"],
        ]
    return [
        ["open", "main", "close"],
        ["open", "contrast", "main", "close"],
        ["open", "takeaway", "main", "close"],
    ]


def compose_response(ctx: dict[str, Any], slot: str, kind: str, **parts: str) -> str:
    normalized_parts: dict[str, str] = {}
    for key, value in parts.items():
        normalized = normalize_inline_text(value)
        if normalized:
            normalized_parts[key] = normalized
    if not normalized_parts:
        return ""

    selected_template = pick_template(ctx, slot, response_templates(kind, ctx.get("stance", "")))
    ordered_keys: list[str] = []
    for key in selected_template:
        if key in normalized_parts and key not in ordered_keys:
            ordered_keys.append(key)
    for key in normalized_parts:
        if key not in ordered_keys:
            ordered_keys.append(key)
    text = join_parts([normalized_parts[key] for key in ordered_keys])
    social_template_composition_service.record_response(
        ctx,
        slot=slot,
        response_kind=kind,
        normalized_parts=normalized_parts,
        selected_template=selected_template,
        part_order=ordered_keys,
        text=text,
    )
    return text


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
        comment_signal = pick_option(
            ctx,
            "admissions-comment-signal",
            [
                "Those repeated questions usually tell you what the market is trying to say before the website or campaign catches up.",
                "You usually hear the real signal in the same questions long before it shows up in the official story.",
                "The repeated questions usually show where the message is still cleaner than the reality people are actually dealing with.",
            ],
        )
        comment_close = pick_option(
            ctx,
            "admissions-comment-close",
            [
                "When teams feed that back into messaging and follow-up, trust and enrollment get stronger.",
                "When teams work from that signal, follow-up gets tighter and trust gets easier to build.",
                "That is usually where better messaging, stronger follow-through, and a cleaner student journey start.",
            ],
        )
        repost_signal = pick_option(
            ctx,
            "admissions-repost-signal",
            [
                "Admissions teams usually hear the market first because they hear the same questions before everyone else does.",
                "Admissions usually hears the friction early because the same questions keep showing up before leadership names the pattern.",
                "Admissions teams often spot the gap first because they hear the confusion, objections, and hesitation in real time.",
            ],
        )
        repost_close = pick_option(
            ctx,
            "admissions-repost-close",
            [
                "That repetition is often the clearest signal about where message clarity, follow-up, or the student journey still needs work.",
                "The repeated questions usually tell you where the message, follow-up, or journey is still leaking trust.",
                "That pattern usually points to where the message is unclear or the student journey is carrying avoidable friction.",
            ],
        )
        return (
            compose_response(
                ctx,
                "admissions-comment-shape",
                "comment",
                open=comment_open(ctx, "That part matters."),
                takeaway=source_takeaway(ctx),
                bridge=bridge_line(ctx),
                contrast=stance_contrast_line(ctx, "comment"),
                main=comment_signal,
                close=comment_close,
            ),
            pick_option(
                ctx,
                "admissions-short",
                [
                    "The frontline questions are usually the strategy.",
                    "The repeated questions usually tell you where the work is.",
                    "The real signal usually sounds like the same question showing up again.",
                ],
            ),
            compose_response(
                ctx,
                "admissions-repost-shape",
                "repost",
                open=repost_open(ctx, repost_seed(ctx)),
                contrast=stance_contrast_line(ctx, "repost"),
                main=repost_signal,
                close=repost_close,
            ),
        )

    fallback_comment_signal = pick_option(
        ctx,
        "admissions-fallback-comment-signal",
        [
            "In admissions work, this same issue usually shows up when teams lose context between inquiry, follow-up, and handoff.",
            "In admissions, this usually shows up when context breaks between the first conversation, the next follow-up, and the real need.",
            "This same issue usually appears in admissions when teams lose the thread between inquiry, follow-up, and what the student or family actually needs.",
        ],
    )
    fallback_comment_close = pick_option(
        ctx,
        "admissions-fallback-comment-close",
        [
            "When that context is tighter, the experience feels more human and the pipeline gets stronger.",
            "When that context holds together, the experience gets clearer and the pipeline usually gets stronger too.",
            "When teams keep the context intact, the experience feels better and the downstream handoff gets cleaner.",
        ],
    )
    fallback_repost_signal = pick_option(
        ctx,
        "admissions-fallback-repost-signal",
        [
            "This same issue shows up when context breaks between the first conversation, the next follow-up, and what the student or family actually needs.",
            "You can usually see this same problem when the follow-up loses the context from the original conversation.",
            "This same pattern shows up when the handoff gets cleaner on paper but weaker in the actual student or family experience.",
        ],
    )
    fallback_repost_close = pick_option(
        ctx,
        "admissions-fallback-repost-close",
        [
            "That is usually where experience, trust, and conversion all start moving in the wrong direction.",
            "That is where trust usually starts weakening before the numbers make it obvious.",
            "That is usually where the student journey starts picking up avoidable friction.",
        ],
    )
    return (
        compose_response(
            ctx,
            "admissions-fallback-comment-shape",
            "comment",
            open=comment_open(ctx, "This is what teams miss."),
            takeaway=source_takeaway(ctx),
            bridge=bridge_line(ctx),
            contrast=stance_contrast_line(ctx, "comment"),
            main=fallback_comment_signal,
            close=fallback_comment_close,
        ),
        pick_option(
            ctx,
            "admissions-fallback-short",
            [
                "Context gaps show up fast in admissions.",
                "Weak context usually becomes admissions friction.",
                "Admissions feels the context gap fast.",
            ],
        ),
        compose_response(
            ctx,
            "admissions-fallback-repost-shape",
            "repost",
            open=repost_open(ctx, repost_seed(ctx)),
            contrast=stance_contrast_line(ctx, "repost"),
            main=fallback_repost_signal,
            close=fallback_repost_close,
        ),
    )


def build_entrepreneurship_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    return (
        compose_response(
            ctx,
            "entrepreneurship-comment-shape",
            "comment",
            open=comment_open(ctx, "There is a real builder lesson in this."),
            takeaway=source_takeaway(ctx),
            bridge=bridge_line(ctx),
            contrast=stance_contrast_line(ctx, "comment"),
                main=pick_option(
                    ctx,
                    "entrepreneurship-comment-main",
                    [
                        "Just because something works does not mean it is valuable enough to change behavior.",
                        "The edge is usually not the headline idea by itself. It is what you do with that signal operationally.",
                        "Most builder advantages come from what gets turned into process, not what gets noticed first.",
                        "Show me the artifact. The insight matters less than what the operator does with it after they see it.",
                    ],
            ),
                close=pick_option(
                    ctx,
                    "entrepreneurship-comment-close",
                    [
                        "Function is not the same thing as value. The compounding shows up when people actually come back.",
                        "The builders who turn repeated insight into process usually compound faster.",
                        "The teams that operationalize the signal early are usually the ones that pull away.",
                        "If the insight never becomes workflow, it is just another tab. That is usually where compounding starts.",
                    ],
            ),
        ),
        pick_option(
            ctx,
            "entrepreneurship-short",
            [
                "The edge is usually in the system.",
                "The compounding shows up in the process.",
                "The signal only matters once it gets operationalized.",
            ],
        ),
        compose_response(
            ctx,
            "entrepreneurship-repost-shape",
            "repost",
            open=repost_open(ctx, repost_seed(ctx)),
            contrast=stance_contrast_line(ctx, "repost"),
                main=pick_option(
                    ctx,
                    "entrepreneurship-repost-main",
                    [
                        "A product working is not the same thing as a product earning repeat behavior.",
                        "This feels more like an execution lesson than a content lesson.",
                        "The builder lesson here is operational, not aesthetic.",
                        "This reads like an execution signal more than a headline insight.",
                    ],
            ),
            close=pick_option(
                ctx,
                "entrepreneurship-repost-close",
                [
                    "The people closest to the work usually see the friction, demand, and language patterns first, which is where better systems tend to come from.",
                    "Operators usually see the real friction first. The question is whether they turn it into process before the signal goes stale.",
                    "The people closest to the work usually hear the pattern first. The win is turning that into a repeatable system.",
                ],
            ),
        ),
    )


def build_current_role_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    return (
        compose_response(
            ctx,
            "current-role-comment-shape",
            "comment",
            open=comment_open(ctx, "This lands for me in the day-to-day work."),
            takeaway=source_takeaway(ctx),
            bridge=bridge_line(ctx),
            contrast=stance_contrast_line(ctx, "comment"),
            main=pick_option(
                ctx,
                "current-role-comment-main",
                [
                    "In the current role, the real test is whether students, families, staff, or the next owner of the work actually feel the difference.",
                    "The day-to-day test is simple: does this change clarity, follow-through, or support for the people living inside the work?",
                    "In role-based work, the signal only matters if the next person in the chain actually feels the difference.",
                ],
            ),
            close=pick_option(
                ctx,
                "current-role-comment-close",
                [
                    "If it does not change follow-through, clarity, or support this week, it is still just a smart observation.",
                    "If it does not improve the next step, it is still theory.",
                    "If the people doing the work do not feel a difference, it is still just a good take.",
                ],
            ),
        ),
        pick_option(
            ctx,
            "current-role-short",
            [
                "If it does not change the next step, it is still theory.",
                "The work only counts if the next step gets better.",
                "If nobody feels the difference, it is still just a smart observation.",
            ],
        ),
        compose_response(
            ctx,
            "current-role-repost-shape",
            "repost",
            open=repost_open(ctx, repost_seed(ctx)),
            contrast=stance_contrast_line(ctx, "repost"),
            main=pick_option(
                ctx,
                "current-role-repost-main",
                [
                    "I keep reading this through the current-job lens.",
                    "The current-job lens makes this more practical fast.",
                    "This gets more useful once you read it through the actual day-to-day job.",
                ],
            ),
            close=pick_option(
                ctx,
                "current-role-repost-close",
                [
                    "The real question is what changes for students, families, staff, or execution this week because of it.",
                    "The real test is what changes in the lived experience of the work this week.",
                    "What matters is what shifts for the people actually carrying the work.",
                ],
            ),
        ),
    )


def build_personal_story_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    return (
        compose_response(
            ctx,
            "personal-comment-shape",
            "comment",
            open=comment_open(ctx, "This hits a nerve for me."),
            takeaway=source_takeaway(ctx),
            bridge=bridge_line(ctx),
            contrast=stance_contrast_line(ctx, "comment"),
            main=pick_option(
                ctx,
                "personal-comment-main",
                [
                    "A lot of these lessons only become obvious once you are the one carrying the follow-through instead of talking about it from a distance.",
                    "Some of these lessons only make sense once you are the one holding the weight on the other side of them.",
                    "A lot of this gets clearer once you are the one responsible for the follow-through instead of just the idea.",
                ],
            ),
            close=pick_option(
                ctx,
                "personal-comment-close",
                [
                    "That is usually where the insight stops being abstract and starts changing how you work.",
                    "That is where the idea stops sounding smart and starts becoming personal.",
                    "That is usually where the lesson stops being theory and starts changing your behavior.",
                ],
            ),
        ),
        pick_option(
            ctx,
            "personal-short",
            [
                "This one feels lived-in.",
                "Some lessons only make sense once you live them.",
                "This one sounds different once you have carried it.",
            ],
        ),
        compose_response(
            ctx,
            "personal-repost-shape",
            "repost",
            open=repost_open(ctx, repost_seed(ctx)),
            contrast=stance_contrast_line(ctx, "repost"),
            main=pick_option(
                ctx,
                "personal-repost-main",
                [
                    "I have learned some version of this the hard way.",
                    "I know this pattern from the lived side, not just the ideas side.",
                    "This one feels familiar because I have seen some version of it up close.",
                ],
            ),
            close=pick_option(
                ctx,
                "personal-repost-close",
                [
                    "The part that sticks is usually not the idea itself. It is what becomes clear once you are the person holding the responsibility on the other side of it.",
                    "The lesson usually changes once you are the one carrying the responsibility instead of commenting from a distance.",
                    "What stays with you is usually what becomes clear once you are the one holding the follow-through.",
                ],
            ),
        ),
    )


def build_program_leadership_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    return (
        compose_response(
            ctx,
            "program-leadership-comment-shape",
            "comment",
            open=comment_open(ctx, "This is where leadership either compounds the signal or wastes it."),
            takeaway=source_takeaway(ctx),
            bridge=bridge_line(ctx),
            contrast=stance_contrast_line(ctx, "comment"),
            main=pick_option(
                ctx,
                "program-leadership-comment-main",
                [
                    "The teams closest to the work usually hear the signal first, but leadership shows up in whether that becomes shared standards, coaching, and decision-making.",
                    "Leadership shows up after the pattern is spotted. The real question is whether it becomes shared standards, coaching, and clearer decisions.",
                    "The signal usually appears at the edge of the work first. Leadership matters in whether that gets translated into standards and follow-through.",
                ],
            ),
            close=pick_option(
                ctx,
                "program-leadership-comment-close",
                [
                    "If it never gets translated into something the broader team can repeat, it stays as an anecdote instead of becoming execution.",
                    "If it never becomes repeatable for the rest of the team, it stays as an anecdote.",
                    "If leaders do not turn it into something repeatable, the pattern dies as interesting chatter.",
                ],
            ),
        ),
        pick_option(
            ctx,
            "program-leadership-short",
            [
                "Leaders have to turn the pattern into something repeatable.",
                "Leadership starts when the pattern becomes repeatable.",
                "The pattern only counts once a team can repeat it.",
            ],
        ),
        compose_response(
            ctx,
            "program-leadership-repost-shape",
            "repost",
            open=repost_open(ctx, repost_seed(ctx)),
            contrast=stance_contrast_line(ctx, "repost"),
            main=pick_option(
                ctx,
                "program-leadership-repost-main",
                [
                    "This is a leadership signal as much as a content or systems signal.",
                    "This is a leadership problem before it is a content win.",
                    "The leadership layer matters as much as the original signal.",
                ],
            ),
            close=pick_option(
                ctx,
                "program-leadership-repost-close",
                [
                    "The job is not just spotting the pattern early. It is building the shared process and coaching around it before the drift gets expensive.",
                    "Spotting the pattern is the easy part. Building the shared process around it is the real leadership move.",
                    "The real job is translating the signal into standards and coaching before the drift gets expensive.",
                ],
            ),
        ),
    )


def build_therapy_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    profile = infer_signal_profile(ctx)
    if profile["is_therapy"] or profile["is_trust"]:
        return (
            compose_response(
                ctx,
                "therapy-comment-shape",
                "comment",
                open=comment_open(ctx, "This lands for me as an attunement and regulation issue, not just a systems issue."),
                takeaway=source_takeaway(ctx),
                bridge=bridge_line(ctx),
                contrast=stance_contrast_line(ctx, "comment"),
                main=pick_option(
                    ctx,
                    "therapy-comment-main",
                    [
                        "People can usually feel the difference between support that is merely efficient and support that is actually containing, clear, and attuned.",
                        "People usually know the difference between a system that is merely efficient and one that actually feels containing and clear.",
                        "The emotional read of a system changes fast when support feels clean but not actually attuned.",
                    ],
                ),
                close=pick_option(
                    ctx,
                    "therapy-comment-close",
                    [
                        "That is where the therapeutic layer shows up for me because the quality of the container changes what people can do inside it.",
                        "That is where the therapeutic layer shows up for me because the container changes what becomes possible inside it.",
                        "That is usually where attunement stops being abstract and starts changing the experience people are having.",
                    ],
                ),
            ),
            pick_option(
                ctx,
                "therapy-short",
                [
                    "People feel the quality of the container fast.",
                    "People know when the container stops feeling attuned.",
                    "The emotional container shows up fast.",
                ],
            ),
            compose_response(
                ctx,
                "therapy-repost-shape",
                "repost",
                open=repost_open(ctx, repost_seed(ctx)),
                contrast=stance_contrast_line(ctx, "repost"),
                main=pick_option(
                    ctx,
                    "therapy-repost-main",
                    [
                        "The part I keep coming back to is the emotional experience underneath the process.",
                        "The human experience underneath the process is the part I keep hearing.",
                        "What stands out to me is the emotional experience sitting underneath the system design.",
                    ],
                ),
                close=pick_option(
                    ctx,
                    "therapy-repost-close",
                    [
                        "Even a strong workflow can miss the mark if people do not feel accurately held, regulated, and understood inside it.",
                        "A clean workflow can still miss if people do not feel held, regulated, and understood inside it.",
                        "Process quality still falls short if the person inside it does not feel accurately held and understood.",
                    ],
                ),
            ),
        )

    return (
        compose_response(
            ctx,
            "therapy-fallback-comment-shape",
            "comment",
            open=comment_open(ctx, "Even when a post sounds practical, I still hear the attunement question underneath it."),
            takeaway=source_takeaway(ctx),
            bridge=bridge_line(ctx),
            contrast=stance_contrast_line(ctx, "comment"),
            main=pick_option(
                ctx,
                "therapy-fallback-comment-main",
                [
                    "A lot of people can tolerate friction if they still feel seen, but they usually disengage once the experience feels cold, dysregulating, or misattuned.",
                    "People can often tolerate imperfect process if they still feel seen, but they usually disengage once the experience feels cold or misattuned.",
                    "The human layer usually starts breaking once the experience feels efficient but emotionally thin.",
                ],
            ),
            close=pick_option(
                ctx,
                "therapy-fallback-comment-close",
                [
                    "That is what makes this feel like a therapy lens to me rather than only an ops lens.",
                    "That is what makes this feel like a therapy question to me, not only an operations question.",
                    "That is why I still hear an attunement question underneath the process language.",
                ],
            ),
        ),
        pick_option(
            ctx,
            "therapy-fallback-short",
            [
                "People know when the support stops feeling attuned.",
                "People feel misattunement fast.",
                "Attunement breaks are usually obvious to the person living inside them.",
            ],
        ),
        compose_response(
            ctx,
            "therapy-fallback-repost-shape",
            "repost",
            open=repost_open(ctx, repost_seed(ctx)),
            contrast=stance_contrast_line(ctx, "repost"),
            main=pick_option(
                ctx,
                "therapy-fallback-repost-main",
                [
                    "I keep hearing the human side of the experience in this.",
                    "I keep hearing the emotional layer underneath the process question.",
                    "This still sounds like a human-experience question to me.",
                ],
            ),
            close=pick_option(
                ctx,
                "therapy-fallback-repost-close",
                [
                    "A lot of process questions are also emotional-safety questions once a real person is living inside the system.",
                    "A lot of process questions become emotional-safety questions once a real person is living inside the system.",
                    "Once a real person is living inside the system, a lot of process language becomes emotional-safety language.",
                ],
            ),
        ),
    )


def build_referral_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    profile = infer_signal_profile(ctx)
    if profile["is_referral"] or profile["is_trust"] or profile["is_admissions"]:
        return (
            compose_response(
                ctx,
                "referral-comment-shape",
                "comment",
                open=comment_open(ctx, "This feels like a referral-confidence issue to me."),
                takeaway=source_takeaway(ctx),
                bridge=bridge_line(ctx),
                contrast=stance_contrast_line(ctx, "comment"),
                main=pick_option(
                    ctx,
                    "referral-comment-main",
                    [
                        "Strong referral ecosystems usually grow when partners trust what happens after the handoff, not just the pitch before it.",
                        "Referral systems usually get stronger when people trust the receiving experience, not just the original promise.",
                        "Referral confidence usually grows on the far side of the handoff, not in the pitch that comes before it.",
                    ],
                ),
                close=pick_option(
                    ctx,
                    "referral-comment-close",
                    [
                        "That confidence gets built through clarity, responsiveness, and a receiving experience someone would feel good putting their name behind again.",
                        "That confidence usually gets built through clarity, responsiveness, and a receiving experience someone would feel good putting their name behind again.",
                        "That is what makes people comfortable sending the next person with their own reputation attached.",
                    ],
                ),
            ),
            pick_option(
                ctx,
                "referral-short",
                [
                    "Referral trust usually lives after the handoff.",
                    "Referral confidence gets decided after the handoff.",
                    "Partners repeat what they can trust after the handoff.",
                ],
            ),
        compose_response(
            ctx,
            "referral-repost-shape",
            "repost",
            open=repost_open(ctx, repost_seed(ctx)),
            contrast=stance_contrast_line(ctx, "repost"),
            main=pick_option(
                ctx,
                "referral-repost-main",
                [
                    "I read this through the referral lens.",
                    "This reads like a referral-confidence question to me.",
                    "The referral lens changes how I hear this fast.",
                ],
            ),
            close=pick_option(
                ctx,
                "referral-repost-close",
                [
                    "The real question is whether a partner, parent, or trusted source would feel confident sending the next person into this experience again.",
                    "The real test is whether a partner, parent, or trusted source would confidently send the next person in again.",
                    "What matters is whether someone would feel good putting their own name behind the next handoff.",
                ],
            ),
        ),
    )

    return (
        compose_response(
            ctx,
            "referral-fallback-comment-shape",
            "comment",
            open=comment_open(ctx, "This still sounds like a referral-system question to me."),
            takeaway=source_takeaway(ctx),
            bridge=bridge_line(ctx),
            contrast=stance_contrast_line(ctx, "comment"),
            main=pick_option(
                ctx,
                "referral-fallback-comment-main",
                [
                    "Partnerships usually get stronger when expectations are clear and the receiving experience is easy to trust.",
                    "Partnerships usually get stronger when the receiving experience is clear enough to trust without extra explanation.",
                    "Partnership strength usually shows up when the handoff feels clear and dependable on the other side.",
                ],
            ),
            close=pick_option(
                ctx,
                "referral-fallback-comment-close",
                [
                    "That is what makes people send the next person with confidence instead of hesitation because their own reputation is on the line too.",
                    "That is what makes people send the next person with confidence instead of hesitation because their own reputation is riding on it too.",
                    "That is usually what decides whether the next referral happens with confidence or hesitation.",
                ],
            ),
        ),
        pick_option(
            ctx,
            "referral-fallback-short",
            [
                "Partners repeat what they can trust.",
                "Referral systems repeat what feels dependable.",
                "Trust decides whether the next referral happens.",
            ],
        ),
        compose_response(
            ctx,
            "referral-fallback-repost-shape",
            "repost",
            open=repost_open(ctx, repost_seed(ctx)),
            contrast=stance_contrast_line(ctx, "repost"),
            main=pick_option(
                ctx,
                "referral-fallback-repost-main",
                [
                    "The referral lens here is about confidence in the receiving system.",
                    "The referral lens here is really a confidence-in-the-receiving-system question.",
                    "The real referral question here is confidence in what happens after the handoff.",
                ],
            ),
            close=pick_option(
                ctx,
                "referral-fallback-repost-close",
                [
                    "If the experience is not clear and dependable after the handoff, the partnership eventually weakens no matter how good the relationship sounded up front.",
                    "If the experience is not clear and dependable after the handoff, the partnership weakens even if the relationship sounded strong up front.",
                    "If the receiving experience is weak, the partnership eventually softens no matter how warm the relationship felt up front.",
                ],
            ),
        ),
    )


def build_enrollment_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    profile = infer_signal_profile(ctx)
    if profile["is_admissions"] or profile["is_education"]:
        return (
            compose_response(
                ctx,
                "enrollment-comment-shape",
                "comment",
                open=comment_open(ctx, "This is an enrollment signal to me."),
                takeaway=source_takeaway(ctx),
                bridge=bridge_line(ctx),
                contrast=stance_contrast_line(ctx, "comment"),
                main=pick_option(
                    ctx,
                    "enrollment-comment-main",
                    [
                        "Repeated confusion is usually a journey problem before it becomes a conversion problem.",
                        "Most conversion problems show up earlier as repeated confusion in the journey.",
                        "The journey usually starts leaking before the conversion metric tells you it has a problem.",
                    ],
                ),
                close=pick_option(
                    ctx,
                    "enrollment-comment-close",
                    [
                        "The more clearly teams can hear and resolve that friction, the better the downstream fit and follow-through tend to be.",
                        "The better teams can hear and resolve that friction, the stronger the downstream fit and follow-through usually get.",
                        "When teams resolve that friction earlier, the downstream fit and follow-through usually improve too.",
                    ],
                ),
            ),
            pick_option(
                ctx,
                "enrollment-short",
                [
                    "Repeated confusion is usually a journey problem.",
                    "The journey usually leaks before the conversion drops.",
                    "Confusion usually shows up before the conversion problem does.",
                ],
            ),
            compose_response(
                ctx,
                "enrollment-repost-shape",
                "repost",
                open=repost_open(ctx, repost_seed(ctx)),
                contrast=stance_contrast_line(ctx, "repost"),
                main=pick_option(
                    ctx,
                    "enrollment-repost-main",
                    [
                        "I read this as an enrollment operations signal.",
                        "This reads like an enrollment-operations signal to me.",
                        "The enrollment lens here is operational fast.",
                    ],
                ),
                close=pick_option(
                    ctx,
                    "enrollment-repost-close",
                    [
                        "Small clarity gaps tend to show up later as weaker follow-up, lower conversion, or avoidable friction in the student journey.",
                        "Small clarity gaps usually show up later as weaker follow-up, lower conversion, or avoidable journey friction.",
                        "Small confusion points tend to show up later as weaker follow-up and avoidable student-journey friction.",
                    ],
                ),
            ),
        )

    return (
        compose_response(
            ctx,
            "enrollment-fallback-comment-shape",
            "comment",
            open=comment_open(ctx, "I still read this as an enrollment operations issue."),
            takeaway=source_takeaway(ctx),
            bridge=bridge_line(ctx),
            contrast=stance_contrast_line(ctx, "comment"),
            main=pick_option(
                ctx,
                "enrollment-fallback-comment-main",
                [
                    "This is what happens when teams do not have enough context to guide the next step well.",
                    "This is what happens when the team loses too much context to guide the next step cleanly.",
                    "This usually starts where the next step is being guided with weak or partial context.",
                ],
            ),
            close=pick_option(
                ctx,
                "enrollment-fallback-comment-close",
                [
                    "That usually shows up later as weaker follow-through and more avoidable friction.",
                    "That usually shows up later as weaker follow-through and friction that did not need to be there.",
                    "That usually shows up later as more drop-off, slower follow-through, and avoidable friction.",
                ],
            ),
        ),
        pick_option(
            ctx,
            "enrollment-fallback-short",
            [
                "Bad context usually becomes enrollment friction.",
                "Weak context usually becomes journey friction.",
                "Context gaps usually show up later as enrollment friction.",
            ],
        ),
        compose_response(
            ctx,
            "enrollment-fallback-repost-shape",
            "repost",
            open=repost_open(ctx, repost_seed(ctx)),
            contrast=stance_contrast_line(ctx, "repost"),
            main=pick_option(
                ctx,
                "enrollment-fallback-repost-main",
                [
                    "This still reads like an enrollment operations issue to me.",
                    "This still sounds like an enrollment-operations problem to me.",
                    "I still hear an enrollment-operations issue inside this.",
                ],
            ),
            close=pick_option(
                ctx,
                "enrollment-fallback-repost-close",
                [
                    "When context is weak, the next step gets weaker too, and that tends to show up later as drop-off, confusion, or slow follow-through.",
                    "When context is weak, the next step weakens too, and that usually shows up later as drop-off, confusion, or slow follow-through.",
                    "When context breaks, the next step usually gets weaker too, and that shows up later as confusion or slow follow-through.",
                ],
            ),
        ),
    )


def build_ai_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    profile = infer_signal_profile(ctx)
    if profile["is_ai"]:
        return (
            compose_response(
                ctx,
                "ai-comment-shape",
                "comment",
                open=comment_open(ctx, "The AI point here is stronger than people think."),
                takeaway=source_takeaway(ctx),
                bridge=bridge_line(ctx),
                contrast=stance_contrast_line(ctx, "comment"),
                main=pick_option(
                    ctx,
                    "ai-comment-main",
                    [
                        "AI is changing what competence looks like. The separation now is who can structure the problem and operate the system with judgment.",
                        "If you cannot rely on the output, you cannot really build with it. That is where constraints and evaluation start to matter.",
                        "AI literacy is not just tool familiarity. It is knowing how to ask better questions, pressure-test outputs, and keep human judgment in the loop.",
                        "The real divide is usually not access. It is whether people know how to question the output, direct the system well, and keep judgment in the loop.",
                        "AI literacy shows up in judgment: better questions, stronger pressure-testing, and a visible human layer.",
                    ],
                ),
                close=pick_option(
                    ctx,
                    "ai-comment-close",
                    [
                        "That is why AI compresses the gap between idea and execution faster than most teams are ready for.",
                        "That is usually the real divide once the technology is already in the room because access alone does not teach discernment.",
                        "Once the tool is in the room, the gap is usually discernment, not access.",
                        "Access does not teach discernment. Judgment does.",
                    ],
                ),
            ),
            pick_option(
                ctx,
                "ai-short",
                [
                    "AI literacy is judgment, not just access.",
                    "Access is not the same thing as discernment.",
                    "The AI gap is usually a judgment gap.",
                ],
            ),
            compose_response(
                ctx,
                "ai-repost-shape",
                "repost",
                open=repost_open(ctx, repost_seed(ctx)),
                contrast=stance_contrast_line(ctx, "repost"),
                main=pick_option(
                    ctx,
                    "ai-repost-main",
                    [
                        "I read this first through an AI lens.",
                        "The AI lens changes this quickly for me.",
                        "I still hear the AI question underneath this first.",
                    ],
                ),
                close=pick_option(
                    ctx,
                    "ai-repost-close",
                    [
                        "AI is changing what competence looks like faster than most teams are ready to admit.",
                        "The practical gap is rarely raw access anymore. It is whether people know how to direct the system well and challenge weak outputs when they show up.",
                        "The practical gap is rarely access anymore. It is whether people know how to direct the system well and challenge weak outputs when they show up.",
                        "The gap is usually not whether the tool exists. It is whether people know how to direct it well and challenge weak output when it shows up.",
                    ],
                ),
            ),
        )

    return (
        compose_response(
            ctx,
            "ai-fallback-comment-shape",
            "comment",
            open=comment_open(ctx, "Even when a post is not explicitly about AI, it still points to an AI-judgment question."),
            takeaway=source_takeaway(ctx),
            bridge=bridge_line(ctx),
            contrast=stance_contrast_line(ctx, "comment"),
            main=pick_option(
                ctx,
                "ai-fallback-comment-main",
                [
                    "The difference usually comes down to whether people can evaluate, translate, and apply the output with discernment.",
                    "The difference usually comes down to whether people can evaluate, translate, and apply the output with real judgment.",
                    "The judgment layer is usually the difference between weak AI use and useful AI use.",
                ],
            ),
            close=pick_option(
                ctx,
                "ai-fallback-comment-close",
                [
                    "That is what makes the AI lens different from a general operations lens because the judgment layer has to stay visible.",
                    "That is what makes the AI lens different from a general operations lens: the judgment layer has to stay visible.",
                    "That is why I still separate the AI question from the general ops question. The judgment layer has to stay visible.",
                ],
            ),
        ),
        pick_option(
            ctx,
            "ai-fallback-short",
            [
                "The AI layer is usually a judgment layer.",
                "The AI question is usually a judgment question.",
                "The real AI difference usually shows up in judgment.",
            ],
        ),
        compose_response(
            ctx,
            "ai-fallback-repost-shape",
            "repost",
            open=repost_open(ctx, repost_seed(ctx)),
            contrast=stance_contrast_line(ctx, "repost"),
            main=pick_option(
                ctx,
                "ai-fallback-repost-main",
                [
                    "I still see an AI question sitting underneath this.",
                    "I still hear an AI-use question underneath this.",
                    "There is still an AI-judgment question sitting under this for me.",
                ],
            ),
            close=pick_option(
                ctx,
                "ai-fallback-repost-close",
                [
                    "Once teams know how to direct, evaluate, and challenge the system well, the downstream quality changes a lot.",
                    "Once teams know how to direct, evaluate, and challenge the system well, the downstream quality usually changes quickly.",
                    "Once the judgment layer gets stronger, the downstream output usually changes a lot too.",
                ],
            ),
        ),
    )


def build_ops_pm_comment(ctx: dict[str, str]) -> tuple[str, str, str]:
    profile = infer_signal_profile(ctx)
    if profile["is_ops"] or profile["is_ai"]:
        return (
            compose_response(
                ctx,
                "ops-comment-shape",
                "comment",
                open=comment_open(ctx, "This reads like a delivery design problem before anything else."),
                takeaway=source_takeaway(ctx),
                bridge=bridge_line(ctx),
                contrast=stance_contrast_line(ctx, "comment"),
                main=pick_option(
                    ctx,
                    "ops-comment-main",
                    [
                        "Partial functionality can hide a real system failure because teams adapt to drag before they redesign it.",
                        "Most teams do not break at the strategy layer. They break at the handoff, ownership, cadence, and follow-through layer.",
                        "The idea usually survives the strategy meeting. It breaks at the handoff, ownership, and follow-through layer.",
                        "The real leak is usually not strategy. It is ownership, handoffs, cadence, and the follow-through layer.",
                    ],
                ),
                close=pick_option(
                    ctx,
                    "ops-comment-close",
                    [
                        "That is why friction is often a signal, not just an annoyance.",
                        "That is why this feels more like workflow design and project control than thought leadership to me.",
                        "That is why this feels more like workflow design than commentary to me.",
                        "That is why I read this as workflow design and project control more than thought leadership.",
                    ],
                ),
            ),
            pick_option(
                ctx,
                "ops-short",
                [
                    "Weak ownership usually kills the good idea.",
                    "The leak is usually in the ownership model.",
                    "The good idea usually dies in the handoff.",
                ],
            ),
            compose_response(
                ctx,
                "ops-repost-shape",
                "repost",
                open=repost_open(ctx, repost_seed(ctx)),
                contrast=stance_contrast_line(ctx, "repost"),
                main=pick_option(
                    ctx,
                    "ops-repost-main",
                    [
                        "I read this through an ops and PM lens.",
                        "The ops and PM lens changes this fast for me.",
                        "This reads like an ownership-and-workflow question to me.",
                    ],
                ),
                close=pick_option(
                    ctx,
                    "ops-repost-close",
                    [
                        "The real question is who owns the next step, how the work moves, and where the process is currently leaking before the delay becomes normal.",
                        "The real question is who owns the next step, how the work moves, and where the current process is leaking before the delay becomes normal.",
                        "What matters is who owns the next step, how the work moves, and where the process is already leaking before the delay gets normalized.",
                    ],
                ),
            ),
        )

    return (
        compose_response(
            ctx,
            "ops-fallback-comment-shape",
            "comment",
            open=comment_open(ctx, "Even if the post sounds strategic, I still hear a delivery problem inside it."),
            takeaway=source_takeaway(ctx),
            bridge=bridge_line(ctx),
            contrast=stance_contrast_line(ctx, "comment"),
            main=pick_option(
                ctx,
                "ops-fallback-comment-main",
                [
                    "Operations and project management usually show up in how work gets translated into repeatable action.",
                    "Operations and project management usually show up in how the work gets translated into something repeatable.",
                    "The ops and PM layer usually shows up in how the work becomes repeatable action instead of a smart idea.",
                ],
            ),
            close=pick_option(
                ctx,
                "ops-fallback-comment-close",
                [
                    "That is where clarity, cadence, accountability, and clean handoffs start mattering more than the original idea.",
                    "That is where clarity, cadence, accountability, and handoffs start mattering more than the original idea.",
                    "That is where clean handoffs and accountability start mattering more than the original framing.",
                ],
            ),
        ),
        pick_option(
            ctx,
            "ops-fallback-short",
            [
                "The delivery layer usually decides the outcome.",
                "The workflow usually decides whether the idea survives.",
                "The work usually breaks in the delivery layer first.",
            ],
        ),
        compose_response(
            ctx,
            "ops-fallback-repost-shape",
            "repost",
            open=repost_open(ctx, repost_seed(ctx)),
            contrast=stance_contrast_line(ctx, "repost"),
            main=pick_option(
                ctx,
                "ops-fallback-repost-main",
                [
                    "This sounds like an ops and PM question to me.",
                    "This still sounds like an ownership-and-workflow problem to me.",
                    "The ops and PM question here is hard to miss.",
                ],
            ),
            close=pick_option(
                ctx,
                "ops-fallback-repost-close",
                [
                    "If the ownership model and workflow are weak, the idea usually stalls no matter how strong it sounded up front.",
                    "If the ownership model and workflow are weak, the idea usually stalls no matter how strong it sounded up front.",
                    "If the ownership model and workflow are weak, the idea usually slows down before anyone admits it has a process problem.",
                ],
            ),
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
        composition_traces = {
            "comment": social_template_composition_service.build_trace(
                context,
                response_kind="comment",
                post_normalization_text=normalized_comment,
            ),
            "repost": social_template_composition_service.build_trace(
                context,
                response_kind="repost",
                post_normalization_text=normalized_repost,
            ),
        }
        belief_assessment = {
            "stance": context["stance"],
            "base_stance": context.get("base_stance", context["stance"]),
            "agreement_level": context["agreement_level"],
            "belief_used": context["belief_used"],
            "belief_summary": context["belief_summary"],
            "experience_anchor": context["experience_anchor"],
            "experience_summary": context["experience_summary"],
            "role_safety": context["role_safety"],
            "response_type": (context.get("response_type_packet") or {}).get("response_type", ""),
        }
        expression_assessment = context["expression_assessment"]
        technique_assessment = social_technique_engine.select_for_variant(signal, lens_id, belief_assessment)
        stage_evaluation = social_stage_evaluation_service.evaluate_variant(
            article_understanding=context.get("article_understanding"),
            persona_retrieval=context.get("persona_retrieval"),
            johnnie_perspective=context.get("johnnie_perspective"),
            reaction_brief=context.get("reaction_brief"),
            composition_traces=composition_traces,
            response_type_packet=context.get("response_type_packet"),
        )
        evaluation = social_evaluation_engine.evaluate_variant(
            lane_id=lens_id,
            signal=signal,
            belief=belief_assessment,
            technique=technique_assessment,
            expression=expression_assessment,
            comment=normalized_comment,
            repost=normalized_repost,
            short_comment=normalized_short_comment,
            article_understanding=context.get("article_understanding"),
            persona_retrieval=context.get("persona_retrieval"),
            johnnie_perspective=context.get("johnnie_perspective"),
            reaction_brief=context.get("reaction_brief"),
            composition_traces=composition_traces,
            response_type_packet=context.get("response_type_packet"),
            stage_evaluation=stage_evaluation,
        )
        variants[lens_id] = {
            "label": LENS_LABELS[lens_id],
            "comment": normalized_comment,
            "short_comment": normalized_short_comment,
            "repost": normalized_repost,
            "why_this_angle": (
                f"Use a {LENS_LABELS[lens_id].lower()} framing for this signal with a "
                f"{((context.get('response_type_packet') or {}).get('response_type') or 'default').replace('_', ' ')} response type. "
                f"{technique_assessment['reason']}."
            ),
            "stance": context["stance"],
            "agreement_level": context["agreement_level"],
            "belief_used": context["belief_used"],
            "belief_summary": context["belief_summary"],
            "experience_anchor": context["experience_anchor"],
            "experience_summary": context["experience_summary"],
            "role_safety": context["role_safety"],
            "article_understanding": context.get("article_understanding"),
            "persona_retrieval": context.get("persona_retrieval"),
            "johnnie_perspective": context.get("johnnie_perspective"),
            "reaction_brief": context.get("reaction_brief"),
            "response_type_packet": context.get("response_type_packet"),
            "composition_traces": composition_traces,
            "techniques": technique_assessment["techniques"],
            "emotional_profile": technique_assessment["emotional_profile"],
            "technique_reason": technique_assessment["reason"],
            "expression_assessment": expression_assessment,
            "stage_evaluation": stage_evaluation,
            "evaluation": evaluation,
            "context_snapshot": {
                "title": context["title"],
                "core_line": context["core_line"],
                "supporting_line": context["supporting_line"],
                "summary": context["summary"],
                "source_takeaway": context["source_takeaway"],
                "source_takeaway_origin": context["source_takeaway_origin"],
                "source_takeaway_strategy": context["source_takeaway_strategy"],
                "belief_used": context["belief_used"],
                "belief_summary": context["belief_summary"],
                "experience_anchor": context["experience_anchor"],
                "experience_summary": context["experience_summary"],
                "stance": context["stance"],
                "base_stance": context.get("base_stance", context["stance"]),
                "agreement_level": context["agreement_level"],
                "role_safety": context["role_safety"],
                "stance_comment_open": context["stance_comment_open"],
                "stance_repost_open": context["stance_repost_open"],
                "bridge_line": context["bridge_line"],
                "article_view": (context.get("reaction_brief") or {}).get("article_view", ""),
                "johnnie_view": (context.get("reaction_brief") or {}).get("johnnie_view", ""),
                "tension": (context.get("reaction_brief") or {}).get("tension", ""),
                "content_angle": (context.get("reaction_brief") or {}).get("content_angle", ""),
                "response_type": ((context.get("response_type_packet") or {}).get("response_type") or ""),
                "article_stance": ((context.get("article_understanding") or {}).get("article_stance") or ""),
            },
        }
    return variants
