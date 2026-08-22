from __future__ import annotations

import hashlib
import json
from typing import Any, Awaitable, Callable, Mapping

from app.services.content_lifecycle_service import ContentLifecycleConflict, ContentLifecycleService
from app.services.integrated_system_store import _canonical_json, _utcnow
from app.services.integrated_production_generator_service import (
    CODEX_REMOTE_MODEL,
    CODEX_REMOTE_REASONING_EFFORT,
    CODEX_REMOTE_EXECUTION_BOUNDARY,
    CODEX_SUBPROCESS_CONTRACT_SCHEMA,
    CONTENT_POST_GENERATION_CONTEXT_SCHEMA,
    GENERATOR_RECEIPT_SCHEMA,
    OWNER_INTEGRITY_GATE_SCHEMA,
    OWNER_GENERATION_STRATEGY,
    OWNER_PERSONA_GATE_SCHEMA,
    OWNER_VOICE_GATE_SCHEMA,
    REMOTE_PACKET_SCHEMA,
    REMOTE_PACKET_RECEIPT_SCHEMA,
    bounded_remote_source_excerpt,
    normalized_remote_controls,
    _subprocess_contract_receipt,
    unpack_integrated_generation_result,
)
from app.services.source_sharing_policy_service import (
    REMOTE_SHAREABLE_CLASSIFICATIONS,
    source_remote_sharing as _source_remote_sharing,
)

def _validate_generation_receipt_binding(
    receipt: Mapping[str, Any],
    *,
    body: str,
    source_id: str,
    evidence_id: str,
    artifact_sha256: str,
    source_excerpt: str,
    controls: Mapping[str, Any],
    expected_draft_authority: str = "owner_requested",
) -> None:
    """Prove a production receipt describes the exact bytes being persisted."""

    if set(receipt) != {
        "schema_version",
        "source_mode",
        "draft_authority",
        "content_type",
        "option_count",
        "generation_strategy",
        "grounding_mode",
        "provider_fallback_used",
        "primary_provider",
        "execution_boundary",
        "llm_request_count",
        "provider_trace",
        "subprocess_contract",
        "subprocess_contract_sha256",
        "remote_packet",
        "prompt_contract_sha256",
        "output_sha256",
        "integrity_gate",
        "voice_gate",
        "persona_grounding",
    }:
        raise ContentLifecycleConflict(
            "canonical generation receipt contains undeclared fields"
        )
    if (
        receipt.get("schema_version") != GENERATOR_RECEIPT_SCHEMA
        or receipt.get("source_mode") != "selected_source"
        or receipt.get("draft_authority") != expected_draft_authority
        or receipt.get("content_type") != "canonical_post"
        or receipt.get("option_count") != 1
        or receipt.get("generation_strategy") != OWNER_GENERATION_STRATEGY
        or receipt.get("grounding_mode")
        != "approved_public_persona_plus_classified_source_evidence"
        or receipt.get("primary_provider") != "codex_cli_saved_login"
        or receipt.get("execution_boundary") != CODEX_REMOTE_EXECUTION_BOUNDARY
        or receipt.get("provider_fallback_used") is not False
        or receipt.get("llm_request_count") != 1
        or not _is_sha256(receipt.get("prompt_contract_sha256"))
        or receipt.get("output_sha256") != hashlib.sha256(body.encode("utf-8")).hexdigest()
    ):
        raise ContentLifecycleConflict("owner-requested generation receipt contract is invalid")
    trace = receipt.get("provider_trace")
    if (
        not isinstance(trace, list)
        or len(trace) != 1
        or not isinstance(trace[0], dict)
        or trace[0]
        != {
            "provider": "codex_cli_saved_login",
            "requested_model": CODEX_REMOTE_MODEL,
            "actual_model": CODEX_REMOTE_MODEL,
            "status": "success",
            "attempt": 1,
        }
    ):
        raise ContentLifecycleConflict("owner-requested generation receipt has no successful provider call")
    remote_packet = receipt.get("remote_packet")
    bounded_excerpt = bounded_remote_source_excerpt(source_excerpt)
    if (
        not isinstance(remote_packet, dict)
        or set(remote_packet)
        != {
            "schema_version",
            "packet_schema_version",
            "packet_sha256",
            "classification",
            "source_sharing_classification",
            "controls_sha256",
            "source_excerpt_projection",
            "evidence_excerpt_sha256",
            "evidence_excerpt_chars",
            "raw_private_memory_included",
            "unreviewed_persona_included",
            "local_paths_included",
            "credentials_included",
            "provider_api_keys_inherited",
        }
        or remote_packet.get("schema_version") != REMOTE_PACKET_RECEIPT_SCHEMA
        or remote_packet.get("packet_schema_version") != REMOTE_PACKET_SCHEMA
        or remote_packet.get("classification") != "public_cloud_safe"
        or remote_packet.get("source_sharing_classification")
        not in REMOTE_SHAREABLE_CLASSIFICATIONS
        or remote_packet.get("controls_sha256")
        != hashlib.sha256(
            _canonical_json(normalized_remote_controls(controls)).encode("utf-8")
        ).hexdigest()
        or not _is_sha256(remote_packet.get("packet_sha256"))
        or remote_packet.get("source_excerpt_projection")
        != "bounded_whitespace_compaction/v1"
        or remote_packet.get("evidence_excerpt_sha256")
        != hashlib.sha256(bounded_excerpt.encode("utf-8")).hexdigest()
        or remote_packet.get("evidence_excerpt_chars") != len(bounded_excerpt)
        or remote_packet.get("raw_private_memory_included") is not False
        or remote_packet.get("unreviewed_persona_included") is not False
        or remote_packet.get("local_paths_included") is not False
        or remote_packet.get("credentials_included") is not False
        or remote_packet.get("provider_api_keys_inherited") is not False
    ):
        raise ContentLifecycleConflict("owner-requested generation receipt has no public-safe packet binding")
    subprocess_contract = receipt.get("subprocess_contract")
    expected_subprocess_contract = _subprocess_contract_receipt()
    if (
        not isinstance(subprocess_contract, dict)
        or subprocess_contract.get("schema_version") != CODEX_SUBPROCESS_CONTRACT_SCHEMA
        or subprocess_contract != expected_subprocess_contract
        or subprocess_contract.get("authentication") != "saved_chatgpt_login"
        or subprocess_contract.get("model") != CODEX_REMOTE_MODEL
        or subprocess_contract.get("reasoning_effort")
        != CODEX_REMOTE_REASONING_EFFORT
        or subprocess_contract.get("provider_api_keys_inherited") is not False
        or subprocess_contract.get("retry_count") != 0
        or receipt.get("subprocess_contract_sha256")
        != hashlib.sha256(_canonical_json(subprocess_contract).encode("utf-8")).hexdigest()
    ):
        raise ContentLifecycleConflict("owner-requested generation receipt has no saved-login subprocess binding")
    integrity = receipt.get("integrity_gate")
    if (
        not isinstance(integrity, dict)
        or integrity.get("schema_version") != OWNER_INTEGRITY_GATE_SCHEMA
        or integrity.get("passed") is not True
        or integrity.get("body_sha256") != hashlib.sha256(body.encode("utf-8")).hexdigest()
        or integrity.get("source_id") != source_id
        or integrity.get("evidence_id") != evidence_id
        or integrity.get("artifact_sha256") != artifact_sha256
        or integrity.get("thesis_retained") is not True
        or integrity.get("evidence_retained") is not True
        or integrity.get("visible_attribution_retained") is not True
        or integrity.get("truth_safety_privacy_constraints_passed") is not True
    ):
        raise ContentLifecycleConflict("owner-requested generation receipt is not bound to the generated copy")
    voice = receipt.get("voice_gate")
    if (
        not isinstance(voice, dict)
        or voice.get("schema_version") != OWNER_VOICE_GATE_SCHEMA
        or voice.get("passed") is not True
        or voice.get("status") != "scored"
        or not isinstance(voice.get("score"), (int, float))
        or float(voice["score"]) < float(voice.get("minimum_score") or 0)
        or voice.get("contamination_warnings") not in ([], ())
    ):
        raise ContentLifecycleConflict("owner-requested generation receipt has no passing voice gate")
    persona = receipt.get("persona_grounding")
    if (
        not isinstance(persona, dict)
        or persona.get("schema_version") != OWNER_PERSONA_GATE_SCHEMA
        or persona.get("passed") is not True
        or int(persona.get("constraint_count") or 0) < 1
        or not _is_sha256(persona.get("constraint_digest"))
    ):
        raise ContentLifecycleConflict("owner-requested generation receipt has no canonical persona grounding")


def _is_sha256(value: Any) -> bool:
    raw = str(value or "")
    return len(raw) == 64 and all(character in "0123456789abcdef" for character in raw)


async def generate_owner_requested_post(
    *,
    lifecycle: ContentLifecycleService,
    source_id: str,
    thesis: str,
    controls: Mapping[str, Any],
    idempotency_key: str,
    generator: Callable[[dict[str, Any]], Awaitable[Any]],
) -> dict[str, Any]:
    thesis = " ".join(thesis.split()).strip()
    if not thesis:
        raise ValueError("owner-requested post requires a thesis")
    requires_generated_preflight = False
    with lifecycle.store.connection() as connection:
        source = connection.execute("SELECT * FROM sources WHERE source_id=?", (source_id,)).fetchone()
        if not source:
            raise ValueError("unknown source")
        if source["merged_into_source_id"]:
            raise ValueError("owner-requested post must use the active canonical source")
        if source["admissibility_state"] != "admissible" or source["rights_state"] in {"blocked", "restricted"}:
            raise ValueError("source is not admissible for drafting")
        evidence = connection.execute("SELECT * FROM evidence_records WHERE source_id=? ORDER BY created_at DESC LIMIT 1", (source_id,)).fetchone()
        if not evidence or not evidence["artifact_id"]:
            raise ValueError("source has no authoritative evidence artifact")
        artifact = connection.execute("SELECT * FROM artifacts WHERE artifact_id=?", (evidence["artifact_id"],)).fetchone()
    opportunity = lifecycle.create_or_reuse_opportunity(
        thesis=thesis,
        idempotency_key=f"owner-post:{idempotency_key}",
        source_ids=[source_id],
        owner_requested=True,
        metadata={"evidence_id": evidence["evidence_id"], "controls": dict(controls)},
    )["opportunity"]
    base_revision_key = f"owner-post-base:{idempotency_key}"
    with lifecycle.store.connection() as connection:
        existing = connection.execute(
            """SELECT r.post_id,p.opportunity_id,o.metadata_json FROM content_revisions r
            JOIN canonical_posts p ON p.post_id=r.post_id
            JOIN content_opportunities o ON o.opportunity_id=p.opportunity_id
            WHERE r.idempotency_key=?""",
            (base_revision_key,),
        ).fetchone()
    if existing:
        if existing["opportunity_id"] != opportunity["opportunity_id"]:
            raise ContentLifecycleConflict(
                "owner-requested post idempotency key belongs to a different opportunity"
            )
        try:
            existing_metadata = json.loads(existing["metadata_json"] or "{}")
        except json.JSONDecodeError as exc:
            raise ContentLifecycleConflict(
                "owner-requested post metadata is malformed"
            ) from exc
        if _canonical_json(existing_metadata.get("controls") or {}) != _canonical_json(
            dict(controls)
        ):
            raise ContentLifecycleConflict(
                "owner-requested post idempotency key conflicts with generation controls"
            )
        return lifecycle.get_post(existing["post_id"])
    effective_attribution_state = "required"
    with lifecycle.store.connection() as connection:
        current = connection.execute(
            "SELECT * FROM content_opportunities WHERE opportunity_id=?",
            (opportunity["opportunity_id"],),
        ).fetchone()
        if not current or current["truth_state"] == "blocked" or current["safety_state"] == "blocked" or current["attribution_state"] == "blocked":
            raise ContentLifecycleConflict("owner-requested opportunity has a truth, safety, privacy, or attribution blocker")
        metadata = json.loads(current["metadata_json"])
        integrity = metadata.get("integrity") if isinstance(metadata.get("integrity"), dict) else {}
        requires_generated_preflight = current["safety_state"] == "pending"
        safety_state = current["safety_state"] if not requires_generated_preflight else "owner_review_required"
        default_attribution_state = "pass" if source["rights_state"] == "owner_controlled" else "required"
        effective_attribution_state = (
            current["attribution_state"]
            if current["attribution_state"] != "pending"
            else default_attribution_state
        )
        integrity["privacy_state"] = str(integrity.get("privacy_state") or ("pass" if safety_state == "pass" else "owner_review_required"))
        if requires_generated_preflight:
            integrity["assessment"] = "owner_requested_generated_copy_preflight_pending/v1"
        metadata["integrity"] = integrity
        connection.execute(
            """UPDATE content_opportunities
            SET truth_state=?,safety_state=?,attribution_state=?,metadata_json=?,updated_at=?
            WHERE opportunity_id=?""",
            (
                current["truth_state"] if current["truth_state"] != "pending" else "pass",
                safety_state,
                effective_attribution_state,
                _canonical_json(metadata),
                _utcnow(),
                current["opportunity_id"],
            ),
        )
    source_body = lifecycle.artifact_store.read_text(artifact["logical_ref"])
    if hashlib.sha256(source_body.encode("utf-8")).hexdigest() != artifact["content_sha256"]:
        raise ContentLifecycleConflict("authoritative evidence artifact hash mismatch")
    source_body = bounded_remote_source_excerpt(source_body)
    request = {
        "topic": thesis,
        "context": {
            "schema_version": CONTENT_POST_GENERATION_CONTEXT_SCHEMA,
            "draft_authority": "owner_requested",
            "source_id": source_id,
            "evidence_id": evidence["evidence_id"],
            "artifact_sha256": artifact["content_sha256"],
            "source_excerpt": source_body,
            "source_title": source["title"],
            "source_author": source["author_or_publisher"],
            "source_url": source["canonical_url"],
            # A missing value is intentional and fail-closed for the production
            # Codex generator. Deterministic/local test generators may still
            # exercise lifecycle behavior without crossing a remote boundary.
            "source_sharing": _source_remote_sharing(source),
            "controls": dict(controls),
            "rules": [
                "Do not present external ideas as firsthand experience",
                "Preserve explicit attribution",
                "Use owner persona and approved worldview only",
            ],
        },
        "content_type": "canonical_post",
    }
    generated_value = await generator(request)
    generated_options, generation_receipt = unpack_integrated_generation_result(generated_value)
    options = [item.strip() for item in generated_options if item.strip()]
    if not options:
        raise RuntimeError("owner-requested generator returned no usable draft")
    if generation_receipt is not None:
        _validate_generation_receipt_binding(
            generation_receipt,
            body=options[0],
            source_id=source_id,
            evidence_id=evidence["evidence_id"],
            artifact_sha256=artifact["content_sha256"],
            source_excerpt=source_body,
            controls=controls,
        )
    public_source_name = source["author_or_publisher"] or source["title"] or "Original source"
    attribution = {
        "required": effective_attribution_state == "required",
        "in_copy_required": effective_attribution_state == "required",
        "public_source_name": public_source_name if effective_attribution_state == "required" else None,
        "public_source_url": source["canonical_url"],
    }
    grounding_anchors = lifecycle.derive_grounding_anchors(
        source_body=source_body,
        draft_body=options[0],
        exclude_text=public_source_name,
        limit=2,
    )
    if len(grounding_anchors) < 2:
        raise ContentLifecycleConflict(
            "owner-requested canonical copy does not retain enough authoritative evidence anchors"
        )
    evidence_binding = {
        "evidence_id": evidence["evidence_id"],
        "artifact_sha256": artifact["content_sha256"],
        "source_id": source_id,
        "required_terms": grounding_anchors,
    }
    # Inspect the actual generated bytes.  A prompt instruction alone is not an
    # integrity gate, so an unattributed or thesis-replacing first option fails.
    lifecycle.validate_variant_integrity(
        parent_body=options[0],
        variant_body=options[0],
        thesis=thesis,
        evidence_binding=evidence_binding,
        attribution=attribution,
    )
    if requires_generated_preflight:
        with lifecycle.store.connection() as connection:
            current = connection.execute(
                "SELECT metadata_json FROM content_opportunities WHERE opportunity_id=?",
                (opportunity["opportunity_id"],),
            ).fetchone()
            if not current:
                raise ContentLifecycleConflict("owner-requested opportunity disappeared before integrity clearance")
            metadata = json.loads(current["metadata_json"])
            integrity = metadata.get("integrity") if isinstance(metadata.get("integrity"), dict) else {}
            integrity.update(
                {
                    "privacy_state": "owner_review_required",
                    "assessment": "owner_requested_generated_copy_preflight/v1",
                    "checks": [
                        "authoritative_evidence_bound",
                        "thesis_lexical_continuity",
                        "visible_external_attribution",
                        "private_literal_denylist",
                    ],
                    "owner_integrity_confirmation_required": True,
                }
            )
            metadata["integrity"] = integrity
            connection.execute(
                "UPDATE content_opportunities SET safety_state='owner_review_required',metadata_json=?,updated_at=? WHERE opportunity_id=?",
                (_canonical_json(metadata), _utcnow(), opportunity["opportunity_id"]),
            )
    return lifecycle.create_canonical_post(
        opportunity_id=opportunity["opportunity_id"], body=options[0],
        evidence_binding=evidence_binding,
        attribution=attribution,
        controls=controls,
        idempotency_key=base_revision_key,
        generation_receipt=generation_receipt,
    )
