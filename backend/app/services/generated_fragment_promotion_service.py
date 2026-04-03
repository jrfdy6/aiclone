from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
from typing import Any

from app.models import PersonaDeltaCreate, PersonaDeltaUpdate
from app.services import persona_delta_service
from app.services.persona_bundle_writer import (
    TARGET_CLAIMS,
    TARGET_CONTENT_PILLARS,
    TARGET_DECISION_PRINCIPLES,
    TARGET_STORIES,
    TARGET_VOICE,
)
from app.services.persona_promotion_service import promote_delta_to_canon
from app.services.persona_review_queue_service import annotate_for_brain_queue

TARGET_WINS = "history/wins.md"

_METRIC_RE = re.compile(r"\b\d+(?:\.\d+)?(?:x|%|k|m|b)?\b", re.IGNORECASE)
_FIRST_PERSON_RE = re.compile(r"\b(i|i'm|i’ve|i'd|my|me|mine|we|we're|we've|our|ours)\b", re.IGNORECASE)
_QUOTE_STYLE_RE = re.compile(r"^[\"'“”‘’].+[\"'“”‘’]$")
_CONTRAST_RE = re.compile(r"\b(not|instead|but|however|rather than|without)\b", re.IGNORECASE)
_PRINCIPLE_RE = re.compile(
    r"\b(trust|clarity|judgment|workflow|operator|leadership|process|system|systems|review|discipline|structure|principle|principles)\b",
    re.IGNORECASE,
)
_PILLAR_RE = re.compile(
    r"\b(ai|agents?|automation|content|brand|audience|admissions?|education|leadership|entrepreneurship|operators?)\b",
    re.IGNORECASE,
)
_STORY_RE = re.compile(
    r"\b(when i|i was|we were|my team|my client|a family|a student|a customer|one day|at fusion|at work|during)\b",
    re.IGNORECASE,
)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def _trim_fragment(value: str) -> str:
    text = _clean_text(value)
    text = text.strip(" \t\n\r-•")
    return text


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", text))


def _first_text(*values: Any) -> str:
    for value in values:
        text = _clean_text(value)
        if text:
            return text
    return ""


def _evidence_from_support(support_items: list[dict[str, Any]]) -> str | None:
    evidence_parts: list[str] = []
    seen: set[str] = set()
    for item in support_items[:3]:
        title = _first_text(item.get("title"), item.get("source_path"), item.get("source_url"))
        lane = _first_text(item.get("reservoir_lane"))
        text = _first_text(item.get("text"))
        snippet = text[:120] if text else ""
        part = " · ".join(piece for piece in (title, lane or None, snippet or None) if piece)
        if not part:
            continue
        key = part.lower()
        if key in seen:
            continue
        seen.add(key)
        evidence_parts.append(part)
    if not evidence_parts:
        return None
    return " | ".join(evidence_parts)


def _review_key(target_file: str, text: str) -> str:
    digest = hashlib.sha1(f"{target_file}||{text.lower()}".encode("utf-8")).hexdigest()[:16]
    return f"generated-fragment:{digest}"


@dataclass(frozen=True)
class GeneratedFragmentRoute:
    route_key: str
    target_file: str
    target_label: str
    kind: str
    label: str
    reason: str


def _route_from_text(
    *,
    fragment_text: str,
    source_mode: str,
    support_items: list[dict[str, Any]],
    option_brief: dict[str, Any] | None,
) -> GeneratedFragmentRoute:
    normalized = _trim_fragment(fragment_text)
    lowered = normalized.lower()
    support_lanes = {
        _clean_text(item.get("reservoir_lane")) or _clean_text(item.get("metadata", {}).get("content_reservoir_lane"))
        for item in support_items
        if isinstance(item, dict)
    }
    support_lanes.discard("")
    support_types = {
        _clean_text(item.get("primary_type")) or _clean_text(item.get("metadata", {}).get("claim_type"))
        for item in support_items
        if isinstance(item, dict)
    }
    support_types.discard("")
    framing_mode = _clean_text((option_brief or {}).get("framing_mode")).lower()
    story_hint = _clean_text((option_brief or {}).get("story_beat"))

    word_count = _word_count(normalized)
    metric_like = bool(_METRIC_RE.search(normalized))
    first_person = bool(_FIRST_PERSON_RE.search(normalized))
    quote_like = bool(_QUOTE_STYLE_RE.match(normalized)) or (word_count <= 14 and bool(_CONTRAST_RE.search(normalized)))
    story_like = bool(_STORY_RE.search(lowered)) or bool(story_hint) or framing_mode in {"drama_tension", "story_first"}
    principle_like = bool(_PRINCIPLE_RE.search(normalized)) or "proof_point" in support_lanes or "canon_bridge" in support_lanes
    pillar_like = bool(_PILLAR_RE.search(normalized)) or "post_seed" in support_lanes

    if story_like or "story_bank" in support_lanes or "anecdote" in support_types:
        return GeneratedFragmentRoute(
            route_key="chronicle",
            target_file=TARGET_STORIES,
            target_label="Story Bank",
            kind="anecdote",
            label="Anecdote",
            reason="The selected fragment reads like a lived story beat and belongs in the story bank.",
        )
    if metric_like:
        return GeneratedFragmentRoute(
            route_key="proof_support",
            target_file=TARGET_WINS,
            target_label="Wins",
            kind="stat",
            label="Proof point",
            reason="The selected fragment carries explicit proof or metric language and should strengthen the proof layer.",
        )
    if quote_like or "voice_guidance" in support_lanes or "voice" in support_types:
        return GeneratedFragmentRoute(
            route_key="voice_guidance",
            target_file=TARGET_VOICE,
            target_label="Voice Patterns",
            kind="phrase_candidate",
            label="Phrase candidate",
            reason="The selected fragment is strongest as reusable phrasing, cadence, or contrast language.",
        )
    if "canon_bridge" in support_lanes and not first_person:
        return GeneratedFragmentRoute(
            route_key="core_canon",
            target_file=TARGET_CLAIMS,
            target_label="Claims",
            kind="talking_point",
            label="Claim",
            reason="The supporting source already points toward canon, so this fragment should harden into a core claim.",
        )
    if principle_like:
        target_file = TARGET_DECISION_PRINCIPLES
        target_label = "Decision Principles"
        reason = "The selected fragment reads like an operating principle that should shape future judgment and writing."
        if pillar_like and source_mode == "recent_signals":
            target_file = TARGET_CONTENT_PILLARS
            target_label = "Content Pillars"
            reason = "The selected fragment reads like a recurring public-facing theme that should stay available as a content pillar."
        return GeneratedFragmentRoute(
            route_key="optional_canon",
            target_file=target_file,
            target_label=target_label,
            kind="framework",
            label="Framework",
            reason=reason,
        )
    if pillar_like:
        return GeneratedFragmentRoute(
            route_key="optional_canon",
            target_file=TARGET_CONTENT_PILLARS,
            target_label="Content Pillars",
            kind="framework",
            label="Framework",
            reason="The selected fragment is more useful as a recurring theme or pillar than as a one-off line.",
        )
    if word_count <= 18:
        return GeneratedFragmentRoute(
            route_key="voice_guidance",
            target_file=TARGET_VOICE,
            target_label="Voice Patterns",
            kind="phrase_candidate",
            label="Phrase candidate",
            reason="The selected fragment is compact enough to preserve as reusable voice guidance.",
        )
    return GeneratedFragmentRoute(
        route_key="optional_canon",
        target_file=TARGET_DECISION_PRINCIPLES,
        target_label="Decision Principles",
        kind="framework",
        label="Framework",
        reason="The selected fragment should stay in Brain as a reusable principle rather than getting stranded in a single draft.",
    )


def _promotion_item(
    *,
    delta_id: str,
    fragment_text: str,
    route: GeneratedFragmentRoute,
    evidence: str | None,
) -> dict[str, Any]:
    promotion_id = hashlib.sha1(f"{delta_id}|{route.target_file}|{fragment_text}".encode("utf-8")).hexdigest()[:16]
    return {
        "id": f"{delta_id}:{promotion_id}",
        "kind": route.kind,
        "label": route.label,
        "content": fragment_text,
        "evidence": evidence,
        "targetFile": route.target_file,
        "gateDecision": "allow",
        "gateReason": route.reason,
    }


def _delta_trait(fragment_text: str, route: GeneratedFragmentRoute) -> str:
    prefix = {
        "voice_guidance": "Generated voice fragment",
        "chronicle": "Generated story beat",
        "optional_canon": "Generated canon candidate",
        "core_canon": "Generated core claim",
        "proof_support": "Generated proof point",
    }.get(route.route_key, "Generated fragment")
    return f"{prefix}: {fragment_text[:120]}"


def promote_generated_fragment(
    *,
    user_id: str,
    fragment_text: str,
    option_text: str,
    option_index: int | None,
    topic: str,
    audience: str,
    category: str,
    content_type: str,
    source_mode: str,
    support_items: list[dict[str, Any]] | None = None,
    option_brief: dict[str, Any] | None = None,
    published: bool = False,
) -> dict[str, Any]:
    cleaned_fragment = _trim_fragment(fragment_text)
    if not cleaned_fragment:
        raise ValueError("Provide a non-empty fragment_text.")

    normalized_support_items = [item for item in (support_items or []) if isinstance(item, dict)]
    route = _route_from_text(
        fragment_text=cleaned_fragment,
        source_mode=source_mode,
        support_items=normalized_support_items,
        option_brief=option_brief,
    )
    review_key = _review_key(route.target_file, cleaned_fragment)
    existing = persona_delta_service.get_delta_by_review_key(review_key)
    if existing and existing.status == "committed":
        return {
            "success": True,
            "duplicate": True,
            "delta_id": existing.id,
            "route_key": route.route_key,
            "route_reason": route.reason,
            "target_file": route.target_file,
            "target_label": route.target_label,
            "delta": annotate_for_brain_queue(existing).model_dump(mode="json"),
            "written_files": (existing.metadata or {}).get("bundle_written_files") or [],
            "message": f'Already stored in {route.target_label}.',
        }

    evidence = _evidence_from_support(normalized_support_items)
    now = datetime.now(timezone.utc).isoformat()
    metadata = {
        "review_key": review_key,
        "review_source": "linkedin_workspace.generated_fragment",
        "approval_state": "approved_from_generation",
        "review_state": "approved",
        "target_file": route.target_file,
        "auto_route_key": route.route_key,
        "auto_route_reason": route.reason,
        "owner_response_kind": "language",
        "owner_response_excerpt": cleaned_fragment[:4000],
        "owner_response_updated_at": now,
        "last_reviewed_at": now,
        "pending_promotion": True,
        "input_mode": "generated_fragment_click",
        "generated_fragment_text": cleaned_fragment,
        "generated_option_text": _trim_fragment(option_text),
        "generated_option_index": option_index,
        "generated_option_brief": option_brief or {},
        "content_generation_topic": _clean_text(topic),
        "content_generation_audience": _clean_text(audience),
        "content_generation_category": _clean_text(category),
        "content_generation_content_type": _clean_text(content_type),
        "content_generation_source_mode": _clean_text(source_mode),
        "content_generation_user_id": _clean_text(user_id),
        "support_trace": normalized_support_items[:8],
        "published_signal": bool(published),
    }
    if evidence:
        metadata["evidence_source"] = evidence

    if existing is None:
        delta = persona_delta_service.create_delta(
            PersonaDeltaCreate(
                persona_target="feeze.core",
                trait=_delta_trait(cleaned_fragment, route),
                notes=evidence or cleaned_fragment[:500],
                metadata=metadata,
            )
        )
    else:
        delta = persona_delta_service.update_delta(
            existing.id,
            PersonaDeltaUpdate(
                notes=evidence or cleaned_fragment[:500],
                metadata=metadata,
            ),
        ) or existing

    promotion_item = _promotion_item(
        delta_id=delta.id,
        fragment_text=cleaned_fragment,
        route=route,
        evidence=evidence,
    )
    approved = persona_delta_service.update_delta(
        delta.id,
        PersonaDeltaUpdate(
            status="approved",
            metadata={
                **metadata,
                "selected_promotion_items": [promotion_item],
                "selected_promotion_item_ids": [promotion_item["id"]],
                "selected_promotion_count": 1,
                "promotion_state": "queued_from_generation",
            },
        ),
    )
    committed = promote_delta_to_canon((approved or delta).id)
    if committed is None:
        raise ValueError("Unable to commit generated fragment to canon.")

    return {
        "success": True,
        "duplicate": False,
        "delta_id": committed.id,
        "route_key": route.route_key,
        "route_reason": route.reason,
        "target_file": route.target_file,
        "target_label": route.target_label,
        "delta": annotate_for_brain_queue(committed).model_dump(mode="json"),
        "written_files": (committed.metadata or {}).get("bundle_written_files") or [],
        "message": f'Saved to {route.target_label}.',
    }
