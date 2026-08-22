from __future__ import annotations

import hashlib
import json
from typing import Any, Awaitable, Callable, Mapping

from app.services.content_lifecycle_service import ContentLifecycleConflict, ContentLifecycleService
from app.services.integrated_production_generator_service import (
    CODEX_REMOTE_EXECUTION_BOUNDARY,
    GENERATOR_RECEIPT_SCHEMA,
    OWNER_VARIANT_INTEGRITY_GATE_SCHEMA,
    REMOTE_PACKET_RECEIPT_SCHEMA,
    REMOTE_PARENT_BINDING_SCHEMA,
    unpack_integrated_generation_result,
)
from app.services.integrated_system_store import _canonical_json


ALLOWED_PLATFORMS = frozenset({"linkedin", "instagram"})
ALLOWED_CONTROLS = frozenset({"audience_emphasis", "value_emphasis", "tone", "hook", "length", "story_emphasis", "evidence_emphasis", "call_to_action"})
VARIANT_PARENT_NOT_REMOTE_BOUND = "variant_parent_not_remote_bound"
VARIANT_PARENT_BINDING_INVALID = "variant_parent_binding_invalid"
VARIANT_POST_ALREADY_PUBLISHED = "variant_post_already_published"
VARIANT_GENERATION_MESSAGES = {
    VARIANT_POST_ALREADY_PUBLISHED: (
        "This post is already published. Variant generation is disabled because this lifecycle "
        "cannot select or reject new post-publication revisions."
    ),
    VARIANT_PARENT_NOT_REMOTE_BOUND: (
        "This revision cannot be used for remote variant generation because its exact bytes "
        "are not bound to a verified safe generation receipt."
    ),
    VARIANT_PARENT_BINDING_INVALID: (
        "This revision cannot be used for remote variant generation because its exact-byte "
        "safety binding is invalid."
    ),
}


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _receipt_sha256(receipt: Mapping[str, Any]) -> str:
    return _sha256_text(_canonical_json(dict(receipt)))


def _validate_remote_receipt(
    receipt: Mapping[str, Any],
    *,
    body_sha256: str,
    source_mode: str,
) -> None:
    trace = receipt.get("provider_trace")
    packet = receipt.get("remote_packet")
    if (
        receipt.get("schema_version") != GENERATOR_RECEIPT_SCHEMA
        or receipt.get("source_mode") != source_mode
        or receipt.get("option_count") != 1
        or receipt.get("execution_boundary") != CODEX_REMOTE_EXECUTION_BOUNDARY
        or receipt.get("provider_fallback_used") is not False
        or receipt.get("llm_request_count") != 1
        or receipt.get("output_sha256") != body_sha256
        or not isinstance(trace, list)
        or len(trace) != 1
        or not isinstance(trace[0], dict)
        or trace[0].get("status") != "success"
        or trace[0].get("attempt") != 1
        or not isinstance(packet, dict)
        or packet.get("schema_version") != REMOTE_PACKET_RECEIPT_SCHEMA
        or packet.get("classification") != "public_cloud_safe"
        or packet.get("raw_private_memory_included") is not False
        or packet.get("unreviewed_persona_included") is not False
        or packet.get("local_paths_included") is not False
        or packet.get("credentials_included") is not False
        or packet.get("provider_api_keys_inherited") is not False
    ):
        raise ContentLifecycleConflict("variant generation receipt is not bound to one remote-safe result")


def _parent_remote_binding(
    lifecycle: ContentLifecycleService,
    *,
    post_id: str,
    parent: Mapping[str, Any],
    body_sha256: str,
) -> dict[str, str] | None:
    """Return a binding only for bytes already produced by the safe remote path."""

    parent_row = dict(parent)
    receipt: dict[str, Any] | None = None
    source_mode = "selected_source"
    with lifecycle.store.connection() as connection:
        if str(parent_row.get("revision_kind") or "") == "base":
            events = connection.execute(
                """SELECT payload_json FROM system_events
                WHERE event_type='canonical_post.generation_receipt' AND aggregate_id=?
                ORDER BY occurred_at DESC""",
                (post_id,),
            ).fetchall()
            for event in events:
                try:
                    payload = json.loads(event["payload_json"])
                except json.JSONDecodeError:
                    continue
                if payload.get("revision_id") != parent_row.get("revision_id"):
                    continue
                raw = payload.get("generation_receipt")
                if isinstance(raw, dict):
                    receipt = raw
                    break
        else:
            events = connection.execute(
                """SELECT payload_json FROM system_events
                WHERE event_type='content_variant.generation_receipt' AND aggregate_id=?
                ORDER BY occurred_at DESC""",
                (post_id,),
            ).fetchall()
            for event in events:
                try:
                    payload = json.loads(event["payload_json"])
                except json.JSONDecodeError:
                    continue
                if payload.get("revision_id") != parent_row.get("revision_id"):
                    continue
                raw = payload.get("generation_receipt")
                if isinstance(raw, dict):
                    receipt = raw
                    source_mode = "linked_parent_revision"
                    break
    if receipt is None:
        return None
    _validate_remote_receipt(receipt, body_sha256=body_sha256, source_mode=source_mode)
    return {
        "schema_version": REMOTE_PARENT_BINDING_SCHEMA,
        "classification": "public_cloud_safe",
        "body_sha256": body_sha256,
        "generation_receipt_sha256": _receipt_sha256(receipt),
    }


def _variant_generation_state(
    lifecycle: ContentLifecycleService,
    *,
    post_id: str,
    post_status: str,
    parent: Mapping[str, Any],
    body_sha256: str,
) -> tuple[dict[str, Any], dict[str, str] | None]:
    if post_status == "published":
        reason_code = VARIANT_POST_ALREADY_PUBLISHED
        return (
            {
                "eligible": False,
                "reason_code": reason_code,
                "message": VARIANT_GENERATION_MESSAGES[reason_code],
            },
            None,
        )
    try:
        binding = _parent_remote_binding(
            lifecycle,
            post_id=post_id,
            parent=parent,
            body_sha256=body_sha256,
        )
    except ContentLifecycleConflict:
        reason_code = VARIANT_PARENT_BINDING_INVALID
        return (
            {
                "eligible": False,
                "reason_code": reason_code,
                "message": VARIANT_GENERATION_MESSAGES[reason_code],
            },
            None,
        )
    if binding is None:
        reason_code = VARIANT_PARENT_NOT_REMOTE_BOUND
        return (
            {
                "eligible": False,
                "reason_code": reason_code,
                "message": VARIANT_GENERATION_MESSAGES[reason_code],
            },
            None,
        )
    return (
        {"eligible": True, "reason_code": None, "message": None},
        binding,
    )


def project_variant_generation_eligibility(
    lifecycle: ContentLifecycleService,
    *,
    post_id: str,
    post_status: str,
    parent: Mapping[str, Any],
    body_sha256: str,
) -> dict[str, Any]:
    """Project only the bounded exact-byte safety decision, never its binding."""

    eligibility, _binding = _variant_generation_state(
        lifecycle,
        post_id=post_id,
        post_status=post_status,
        parent=parent,
        body_sha256=body_sha256,
    )
    return eligibility


def validate_variant_generation_eligibility(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "eligible",
        "reason_code",
        "message",
    }:
        raise ValueError("invalid variant-generation eligibility")
    if value.get("eligible") is True:
        if value.get("reason_code") is not None or value.get("message") is not None:
            raise ValueError("eligible variant-generation state cannot include a reason")
        return {"eligible": True, "reason_code": None, "message": None}
    reason_code = value.get("reason_code")
    if (
        value.get("eligible") is not False
        or reason_code not in VARIANT_GENERATION_MESSAGES
        or value.get("message") != VARIANT_GENERATION_MESSAGES[reason_code]
    ):
        raise ValueError("invalid variant-generation ineligibility reason")
    return {
        "eligible": False,
        "reason_code": reason_code,
        "message": VARIANT_GENERATION_MESSAGES[reason_code],
    }


def _validate_variant_receipt(
    receipt: Mapping[str, Any], *, body: str, parent_body_sha256: str
) -> None:
    body_sha256 = _sha256_text(body)
    _validate_remote_receipt(
        receipt,
        body_sha256=body_sha256,
        source_mode="linked_parent_revision",
    )
    integrity = receipt.get("integrity_gate")
    if (
        not isinstance(integrity, dict)
        or integrity.get("schema_version") != OWNER_VARIANT_INTEGRITY_GATE_SCHEMA
        or integrity.get("passed") is not True
        or integrity.get("body_sha256") != body_sha256
        or integrity.get("parent_body_sha256") != parent_body_sha256
        or integrity.get("thesis_retained") is not True
        or integrity.get("evidence_retained") is not True
        or integrity.get("attribution_retained") is not True
        or integrity.get("truth_safety_privacy_constraints_passed") is not True
    ):
        raise ContentLifecycleConflict("variant generation receipt failed its exact-byte integrity binding")


def validate_variant_controls(platform: str, controls: Mapping[str, Any]) -> dict[str, str]:
    if platform not in ALLOWED_PLATFORMS:
        raise ValueError("unsupported variant platform")
    if not controls or set(controls) - ALLOWED_CONTROLS:
        raise ValueError("variant controls are empty or unsupported")
    normalized = {str(key): " ".join(str(value).split())[:300] for key, value in controls.items() if str(value).strip()}
    if not normalized:
        raise ValueError("variant controls are empty")
    return normalized


async def generate_integrated_variant(
    *,
    lifecycle: ContentLifecycleService,
    post_id: str,
    parent_revision_id: str,
    platform: str,
    controls: Mapping[str, Any],
    idempotency_key: str,
    generator: Callable[[dict[str, Any]], Awaitable[Any]],
) -> dict[str, Any]:
    normalized = validate_variant_controls(platform, controls)
    current = lifecycle.get_post(post_id)
    parent = next((row for row in current["revisions"] if row["revision_id"] == parent_revision_id), None)
    if parent is None:
        raise ValueError("unknown parent revision")
    post = current["post"]
    with lifecycle.store.connection() as connection:
        existing = connection.execute(
            "SELECT * FROM content_revisions WHERE idempotency_key=?",
            (idempotency_key,),
        ).fetchone()
        if existing:
            if (
                existing["post_id"] != post_id
                or existing["parent_revision_id"] != parent_revision_id
                or existing["revision_kind"] != "variant"
                or existing["platform"] != platform
                or existing["control_json"] != _canonical_json(normalized)
            ):
                raise ContentLifecycleConflict("variant idempotency key belongs to different work")
            return current
        if post["status"] == "published":
            raise ContentLifecycleConflict(
                VARIANT_GENERATION_MESSAGES[VARIANT_POST_ALREADY_PUBLISHED]
            )
        thesis = connection.execute(
            "SELECT thesis FROM content_opportunities WHERE opportunity_id=?",
            (post["opportunity_id"],),
        ).fetchone()[0]
        artifact = connection.execute(
            "SELECT logical_ref,content_sha256 FROM artifacts WHERE artifact_id=?",
            (parent["body_artifact_id"],),
        ).fetchone()
        evidence_binding = json.loads(parent["evidence_binding_json"])
        attribution = json.loads(parent["attribution_json"])
    body = lifecycle.artifact_store.read_text(artifact["logical_ref"])
    if _sha256_text(body) != artifact["content_sha256"]:
        raise ContentLifecycleConflict("variant parent artifact hash mismatch")
    parent_binding = _parent_remote_binding(
        lifecycle,
        post_id=post_id,
        parent=parent,
        body_sha256=artifact["content_sha256"],
    )
    request = {
        "topic": thesis,
        "context": {
            "base_post": body,
            "controls": normalized,
            "invariants": {
                "preserve_thesis": True,
                "preserve_evidence": True,
                "preserve_attribution": True,
                "preserve_truth_safety_privacy": True,
            },
            # Local deterministic harnesses may receive no binding. The
            # production remote generator rejects that state before any
            # subprocess or network boundary receives the parent bytes.
            "parent_remote_binding": parent_binding,
            # This remains local and is never included in the remote packet.
            "integrity_context": {
                "evidence_binding": evidence_binding,
                "attribution": attribution,
                "parent_body_sha256": artifact["content_sha256"],
            },
        },
        "content_type": "linkedin_post" if platform == "linkedin" else "instagram_post",
        "platform": platform,
    }
    generated_options, generation_receipt = unpack_integrated_generation_result(
        await generator(request)
    )
    options = [item.strip() for item in generated_options if item.strip()]
    if not options:
        raise RuntimeError("variant generator returned no usable draft")
    if generation_receipt is not None:
        _validate_variant_receipt(
            generation_receipt,
            body=options[0],
            parent_body_sha256=artifact["content_sha256"],
        )
    result = lifecycle.create_variant(
        post_id=post_id,
        parent_revision_id=parent_revision_id,
        body=options[0],
        platform=platform,
        controls=normalized,
        idempotency_key=idempotency_key,
        thesis=thesis,
        generation_receipt=generation_receipt,
    )
    return result
