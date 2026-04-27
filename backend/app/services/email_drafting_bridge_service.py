from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from app.models.email_ops import (
    EmailDraftEngine,
    EmailDraftMode,
    EmailDraftSourceMode,
    EmailMessage,
    EmailThread,
    EmailThreadDraftRequest,
)


DEFAULT_DRAFT_MODE: EmailDraftMode = "email_reply"
DEFAULT_DRAFT_ENGINE: EmailDraftEngine = "template"
DEFAULT_SOURCE_MODE: EmailDraftSourceMode = "email_thread_grounded"
LOCAL_CODEX_EMAIL_WORKSPACE_SLUG = os.getenv("EMAIL_DRAFT_LOCAL_CODEX_WORKSPACE_SLUG", "email-drafts")
LOCAL_CODEX_EMAIL_MODEL = os.getenv("LOCAL_CODEX_BRIDGE_MODEL", "gpt-5.4-mini")

CONTENT_GENERATION_WORKSPACE_CONFIG: dict[str, dict[str, Any]] = {
    "feezie-os": {
        "allowed_lanes": {"primary"},
        "user_id": "johnnie_fields",
        "audience": "entrepreneurs",
        "workspace_slug": LOCAL_CODEX_EMAIL_WORKSPACE_SLUG,
    },
    "fusion-os": {
        "allowed_lanes": {"primary"},
        "user_id": "johnnie_fields",
        "audience": "education_admissions",
        "workspace_slug": LOCAL_CODEX_EMAIL_WORKSPACE_SLUG,
    },
}


def resolve_draft_mode(payload: EmailThreadDraftRequest) -> EmailDraftMode:
    return payload.draft_mode or DEFAULT_DRAFT_MODE


def resolve_draft_engine(payload: EmailThreadDraftRequest) -> EmailDraftEngine:
    return payload.draft_engine or DEFAULT_DRAFT_ENGINE


def resolve_source_mode(payload: EmailThreadDraftRequest) -> EmailDraftSourceMode:
    return payload.source_mode or DEFAULT_SOURCE_MODE


def _grounded_draft_eligibility(
    thread: EmailThread,
    payload: EmailThreadDraftRequest,
    *,
    required_engine: EmailDraftEngine,
) -> tuple[bool, str]:
    if resolve_draft_engine(payload) != required_engine:
        return False, "draft_engine_not_requested"
    workspace_config = CONTENT_GENERATION_WORKSPACE_CONFIG.get(thread.workspace_key)
    if not workspace_config:
        return False, "workspace_not_enabled"
    if thread.lane not in set(workspace_config.get("allowed_lanes") or set()):
        return False, "lane_not_enabled"
    if thread.needs_human:
        return False, "thread_requires_human_review"
    if thread.high_value:
        return False, "thread_marked_high_value"
    if thread.high_risk:
        return False, "thread_marked_high_risk"
    return True, "eligible"


def content_generation_eligibility(thread: EmailThread, payload: EmailThreadDraftRequest) -> tuple[bool, str]:
    return _grounded_draft_eligibility(thread, payload, required_engine="content_generation")


def codex_job_eligibility(thread: EmailThread, payload: EmailThreadDraftRequest) -> tuple[bool, str]:
    return _grounded_draft_eligibility(thread, payload, required_engine="codex_job")


def build_content_generation_request_payload(
    thread: EmailThread,
    *,
    payload: EmailThreadDraftRequest,
    draft_type: str,
    signature_block: str,
) -> dict[str, Any]:
    workspace_config = CONTENT_GENERATION_WORKSPACE_CONFIG.get(thread.workspace_key) or {}
    draft_mode = resolve_draft_mode(payload)
    audience = str(workspace_config.get("audience") or "general")
    category = "sales" if draft_type == "qualify" else "value"
    latest_inbound = _latest_inbound_message(thread)
    latest_body = (latest_inbound.body_text if latest_inbound else "").strip()
    topic = thread.subject.strip() or f"{thread.workspace_key} email reply"
    context_parts = [
        f"Draft mode: {draft_mode}.",
        f"Workspace: {thread.workspace_key}.",
        f"Lane: {thread.lane}.",
        f"Thread summary: {thread.summary or thread.excerpt or thread.subject}.",
    ]
    if latest_body:
        context_parts.append(f"Latest inbound message: {latest_body}")
    context_parts.append(f"Reply goal: {_cta_goal(thread, draft_type=draft_type)}.")
    context_parts.append("Use short, skimmable paragraphs and one clear next action.")
    context_parts.append("Do not invent pricing, compliance claims, or relationship history.")
    context_parts.append(f"Close with this signature block exactly:\n{signature_block}")
    if payload.operator_notes:
        context_parts.append(f"Operator notes: {payload.operator_notes}")
    return {
        "user_id": str(workspace_config.get("user_id") or "johnnie_fields"),
        "topic": topic,
        "context": "\n\n".join(context_parts).strip(),
        "content_type": draft_mode,
        "category": category,
        "tone": "expert_direct",
        "audience": audience,
        "source_mode": resolve_source_mode(payload),
        "workspace_slug": str(workspace_config.get("workspace_slug") or LOCAL_CODEX_EMAIL_WORKSPACE_SLUG),
    }


def build_email_drafting_packet(
    thread: EmailThread,
    *,
    payload: EmailThreadDraftRequest,
    draft_type: str,
    generated_at: datetime,
    signature_block: str,
) -> dict[str, Any]:
    draft_mode = resolve_draft_mode(payload)
    draft_engine = resolve_draft_engine(payload)
    source_mode = resolve_source_mode(payload)
    latest_inbound = _latest_inbound_message(thread)
    recent_history = _recent_thread_history(thread)
    thread_summary = thread.summary or thread.excerpt or thread.subject

    return {
        "thread_id": thread.id,
        "provider": thread.provider,
        "workspace_key": thread.workspace_key,
        "lane": thread.lane,
        "draft_mode": draft_mode,
        "draft_engine": draft_engine,
        "draft_type": draft_type,
        "source_mode": source_mode,
        "subject": thread.subject,
        "from_address": thread.from_address,
        "from_name": thread.from_name,
        "organization": thread.organization,
        "to_addresses": list(thread.to_addresses),
        "thread_summary": thread_summary,
        "latest_inbound_message": latest_inbound.body_text if latest_inbound else "",
        "recent_thread_history": recent_history,
        "routing_reasons": list(thread.routing_reasons),
        "needs_human": thread.needs_human,
        "high_value": thread.high_value,
        "high_risk": thread.high_risk,
        "sla_at_risk": thread.sla_at_risk,
        "confidence_score": thread.confidence_score,
        "allowed_claims": _allowed_claims(thread),
        "disallowed_claims": _disallowed_claims(thread),
        "cta_goal": _cta_goal(thread, draft_type=draft_type),
        "operator_notes": payload.operator_notes,
        "signature_block": signature_block,
        "generated_at": generated_at.isoformat(),
    }


def build_local_codex_email_request_payload(
    thread: EmailThread,
    *,
    payload: EmailThreadDraftRequest,
    draft_type: str,
    signature_block: str,
) -> dict[str, Any]:
    workspace_config = CONTENT_GENERATION_WORKSPACE_CONFIG.get(thread.workspace_key) or {}
    draft_mode = resolve_draft_mode(payload)
    audience = str(workspace_config.get("audience") or "general")
    category = "sales" if draft_type == "qualify" else "value"
    latest_inbound = _latest_inbound_message(thread)
    latest_body = (latest_inbound.body_text if latest_inbound else "").strip()
    topic = thread.subject.strip() or f"{thread.workspace_key} email reply"
    context_parts = [
        f"Draft mode: {draft_mode}.",
        f"Workspace: {thread.workspace_key}.",
        f"Lane: {thread.lane}.",
        f"Thread summary: {thread.summary or thread.excerpt or thread.subject}.",
    ]
    if latest_body:
        context_parts.append(f"Latest inbound message: {latest_body}")
    context_parts.append(f"Reply goal: {_cta_goal(thread, draft_type=draft_type)}.")
    context_parts.append("Use short, skimmable paragraphs and one clear next action.")
    context_parts.append("Do not invent pricing, compliance claims, or relationship history.")
    context_parts.append(f"Close with this signature block exactly:\n{signature_block}")
    if payload.operator_notes:
        context_parts.append(f"Operator notes: {payload.operator_notes}")
    return {
        "user_id": str(workspace_config.get("user_id") or "johnnie_fields"),
        "topic": topic,
        "context": "\n\n".join(context_parts).strip(),
        "content_type": draft_mode,
        "category": category,
        "tone": "expert_direct",
        "audience": audience,
        "source_mode": resolve_source_mode(payload),
        "workspace_slug": str(workspace_config.get("workspace_slug") or LOCAL_CODEX_EMAIL_WORKSPACE_SLUG),
    }


def build_local_codex_email_context_packet(
    thread: EmailThread,
    *,
    payload: EmailThreadDraftRequest,
    draft_type: str,
    signature_block: str,
    generated_at: datetime,
) -> dict[str, Any]:
    draft_packet = build_email_drafting_packet(
        thread,
        payload=payload,
        draft_type=draft_type,
        generated_at=generated_at,
        signature_block=signature_block,
    )
    request_payload = build_local_codex_email_request_payload(
        thread,
        payload=payload,
        draft_type=draft_type,
        signature_block=signature_block,
    )
    history_lines = []
    for item in draft_packet["recent_thread_history"]:
        direction = str(item.get("direction") or "inbound")
        sender = str(item.get("from_address") or "")
        body = str(item.get("body_text") or "").strip()
        if not body:
            continue
        history_lines.append(f"- {direction} | {sender}: {body}")
    history_text = "\n".join(history_lines) or "- No recent thread history available."
    allowed_claims = "\n".join(f"- {claim}" for claim in draft_packet["allowed_claims"]) or "- Acknowledge receipt and propose a concrete next step."
    disallowed_claims = "\n".join(f"- {claim}" for claim in draft_packet["disallowed_claims"]) or "- Do not invent facts."
    operator_notes = str(draft_packet.get("operator_notes") or "").strip()
    operator_note_text = operator_notes or "None."
    latest_message = str(draft_packet.get("latest_inbound_message") or "").strip() or "No latest inbound message available."
    thread_summary = str(draft_packet.get("thread_summary") or thread.subject or "").strip() or "No summary available."
    prompt = f"""You are drafting one grounded email for a live inbox thread.

Return only JSON.
Return an object with exactly one key: "options".
"options" must be an array with exactly 1 string.
That string must be the final email body only.
Do not include a subject line.
Do not include markdown fences or commentary.

EMAIL DRAFT RULES:
- Write one email body that matches the live thread.
- Use only facts grounded in the thread and allowed claims below.
- Keep it warm, direct, and operationally useful.
- Use 2 to 5 short paragraphs.
- End with one clear next action.
- Do not invent pricing, timing promises, compliance claims, or relationship history.
- Do not imply the email has already been sent or approved.
- Close with this signature block exactly:
{signature_block}

THREAD CONTEXT:
- Thread id: {thread.id}
- Workspace: {thread.workspace_key}
- Lane: {thread.lane}
- Draft mode: {resolve_draft_mode(payload)}
- Draft type: {draft_type}
- CTA goal: {_cta_goal(thread, draft_type=draft_type)}
- Summary: {thread_summary}

LATEST INBOUND MESSAGE:
{latest_message}

RECENT THREAD HISTORY:
{history_text}

ALLOWED CLAIMS:
{allowed_claims}

DISALLOWED CLAIMS:
{disallowed_claims}

OPERATOR NOTES:
{operator_note_text}
""".strip()
    return {
        "job_kind": "email_draft",
        "format": "email_draft_v1",
        "thread_id": thread.id,
        "workspace_key": thread.workspace_key,
        "lane": thread.lane,
        "draft_type": draft_type,
        "draft_mode": resolve_draft_mode(payload),
        "draft_engine": resolve_draft_engine(payload),
        "source_mode": resolve_source_mode(payload),
        "signature_block": signature_block,
        "persona_context_summary": request_payload["context"],
        "prompt": prompt,
        "requested_model": LOCAL_CODEX_EMAIL_MODEL,
        "expected_option_count": 1,
        "email_drafting_packet": draft_packet,
        "request_payload": request_payload,
    }


def build_local_codex_email_result_payload(
    *,
    request_payload: dict[str, Any],
    context_packet: dict[str, Any],
    options: list[str],
    model: str | None,
    raw_output: str | None,
    command_stdout: str | None,
    command_stderr: str | None,
) -> dict[str, Any]:
    normalized_options = [str(item).strip() for item in options if str(item).strip()]
    packet = context_packet.get("email_drafting_packet")
    signature_block = str(context_packet.get("signature_block") or "").strip()
    if isinstance(packet, dict):
        signature_block = str(packet.get("signature_block") or signature_block).strip()
    if signature_block:
        normalized_options = [
            normalize_generated_email_body(option, signature_block=signature_block)
            for option in normalized_options
        ]
    return {
        "success": True,
        "options": normalized_options[:1],
        "persona_context": context_packet.get("persona_context_summary"),
        "examples_used": [],
        "diagnostics": {
            "grounding_mode": "email_thread_grounded",
            "generation_strategy": "codex_terminal",
            "draft_mode": context_packet.get("draft_mode"),
            "draft_type": context_packet.get("draft_type"),
            "email_thread_id": context_packet.get("thread_id"),
            "source_mode": request_payload.get("source_mode"),
            "llm_provider_trace": [
                {
                    "provider": "codex_terminal",
                    "actual_model": model or str(context_packet.get("requested_model") or LOCAL_CODEX_EMAIL_MODEL),
                    "status": "success",
                }
            ],
            "raw_codex_output_preview": (raw_output or "")[:800],
            "runner_stdout_preview": (command_stdout or "")[-800:],
            "runner_stderr_preview": (command_stderr or "")[-800:],
        },
    }


def _latest_inbound_message(thread: EmailThread) -> EmailMessage | None:
    inbound = [message for message in thread.messages if message.direction == "inbound"]
    if inbound:
        return max(inbound, key=lambda item: item.received_at)
    if thread.messages:
        return max(thread.messages, key=lambda item: item.received_at)
    return None


def _recent_thread_history(thread: EmailThread, *, limit: int = 4) -> list[dict[str, Any]]:
    ordered = sorted(thread.messages, key=lambda item: item.received_at, reverse=True)[:limit]
    history: list[dict[str, Any]] = []
    for message in ordered:
        history.append(
            {
                "message_id": message.id,
                "direction": message.direction,
                "from_address": message.from_address,
                "subject": message.subject,
                "received_at": message.received_at.isoformat(),
                "body_text": message.body_text,
            }
        )
    return history


def _allowed_claims(thread: EmailThread) -> list[str]:
    claims = ["Acknowledge receipt and propose a concrete next step grounded in the thread."]
    if thread.workspace_key == "agc":
        claims.append("Request scope, timing, and buyer-context details before suggesting next actions.")
    if thread.workspace_key == "fusion-os":
        claims.append("Offer intake coordination without promising placement outcomes.")
    if thread.workspace_key == "feezie-os":
        claims.append("Respond in a warm, relational tone while keeping the ask specific.")
    if thread.workspace_key == "shared_ops":
        claims.append("Stay concise and operational, especially for billing or admin issues.")
    return claims


def _disallowed_claims(thread: EmailThread) -> list[str]:
    claims = [
        "Do not fabricate relationship history, pricing, compliance posture, or delivery commitments.",
        "Do not imply approval or send-state changes before a human/operator actually approves them.",
    ]
    if thread.high_risk:
        claims.append("Do not make legal, contract, insurance, or compliance claims not already verified.")
    if thread.high_value:
        claims.append("Do not send capability-heavy or quote-shaped commitments without human review.")
    return claims


def _cta_goal(thread: EmailThread, *, draft_type: str) -> str:
    if draft_type == "qualify":
        return "collect_scope_details"
    if draft_type == "schedule":
        return "coordinate_meeting_times"
    if draft_type == "decline_or_redirect":
        return "redirect_cleanly"
    if thread.workspace_key == "fusion-os":
        return "advance_intake"
    return "acknowledge_and_request_context"


def normalize_generated_email_body(body: str, *, signature_block: str) -> str:
    normalized = " ".join((body or "").replace("\r", "\n").split())
    if not normalized:
        return ""
    normalized = normalized.replace(" .", ".").replace(" ,", ",")
    paragraphs = [segment.strip() for segment in body.replace("\r\n", "\n").split("\n\n") if segment.strip()]
    cleaned = "\n\n".join(paragraphs).strip() if paragraphs else normalized.strip()
    if signature_block.strip().lower() not in cleaned.lower():
        cleaned = f"{cleaned}\n\nThanks,\n{signature_block}".strip()
    return cleaned
