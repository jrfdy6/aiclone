from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Awaitable, Callable, Mapping

from app.services.content_lifecycle_service import ContentLifecycleConflict, ContentLifecycleService
from app.services.integrated_system_store import _canonical_json, _utcnow
from app.services.integrated_production_generator_service import (
    CODEX_REMOTE_MODEL,
    CODEX_REMOTE_REASONING_EFFORT,
    CODEX_REMOTE_EXECUTION_BOUNDARY,
    CODEX_SUBPROCESS_CONTRACT_SCHEMA,
    CONTENT_POST_GENERATION_CONTEXT_SCHEMA,
    DREAM_MEMORY_READINESS_SCHEMA,
    FULL_SYSTEM_GROUNDING_MODE,
    GENERATOR_RECEIPT_SCHEMA,
    LEGACY_GROUNDING_MODE,
    LEGACY_OWNER_PERSONA_GATE_SCHEMA,
    OWNER_INTEGRITY_GATE_SCHEMA,
    OWNER_GENERATION_STRATEGY,
    OWNER_PERSONA_GATE_SCHEMA,
    OWNER_VOICE_GATE_SCHEMA,
    PERSONA_CONTEXT_RECEIPT_SCHEMA,
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


def bind_owner_requested_interpretation_lineage(
    *,
    lifecycle: ContentLifecycleService,
    opportunity_id: str,
    evidence_id: str,
) -> dict[str, Any]:
    """Bind every current source-bound interpretation to an owner-requested opportunity.

    Owner requests bypass portfolio delay, not provenance.  Evidence and lenses may
    be written before the owner supplies a thesis, so this repair-safe boundary
    attaches the exact interpretation identities without re-running generation.
    """

    opportunity_id = str(opportunity_id or "").strip()
    evidence_id = str(evidence_id or "").strip()
    if not opportunity_id or not evidence_id:
        raise ValueError("owner-requested interpretation lineage requires opportunity and evidence")
    with lifecycle.store.connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            evidence = connection.execute(
                "SELECT source_id,artifact_id FROM evidence_records WHERE evidence_id=?",
                (evidence_id,),
            ).fetchone()
            opportunity = connection.execute(
                "SELECT metadata_json FROM content_opportunities WHERE opportunity_id=?",
                (opportunity_id,),
            ).fetchone()
            if not evidence or not opportunity:
                raise ContentLifecycleConflict(
                    "owner-requested interpretation lineage target is missing"
                )
            if not connection.execute(
                "SELECT 1 FROM opportunity_sources WHERE opportunity_id=? AND source_id=?",
                (opportunity_id, evidence["source_id"]),
            ).fetchone():
                raise ContentLifecycleConflict(
                    "owner-requested interpretation lineage is not source-bound"
                )
            interpretation_ids = [
                str(row["interpretation_id"])
                for row in connection.execute(
                    """SELECT interpretation_id FROM interpretations
                    WHERE evidence_id=? ORDER BY created_at,interpretation_id""",
                    (evidence_id,),
                )
            ]
            try:
                metadata = json.loads(opportunity["metadata_json"] or "{}")
            except json.JSONDecodeError as exc:
                raise ContentLifecycleConflict(
                    "owner-requested opportunity metadata is malformed"
                ) from exc
            if not isinstance(metadata, dict):
                raise ContentLifecycleConflict(
                    "owner-requested opportunity metadata is not an object"
                )
            original_metadata_json = _canonical_json(metadata)
            bound_evidence_id = str(metadata.get("evidence_id") or "").strip()
            if bound_evidence_id and bound_evidence_id != evidence_id:
                raise ContentLifecycleConflict(
                    "owner-requested opportunity has conflicting evidence lineage"
                )
            existing = metadata.get("interpretation_ids", [])
            if not isinstance(existing, list) or any(
                not isinstance(item, str) or not item.strip() for item in existing
            ):
                raise ContentLifecycleConflict(
                    "owner-requested interpretation lineage is malformed"
                )
            existing_ids = sorted(set(existing))
            if existing_ids:
                placeholders = ",".join("?" for _ in existing_ids)
                valid_existing = connection.execute(
                    f"""SELECT COUNT(*) FROM interpretations
                    WHERE evidence_id=? AND interpretation_id IN ({placeholders})""",
                    (evidence_id, *existing_ids),
                ).fetchone()[0]
                if valid_existing != len(existing_ids):
                    raise ContentLifecycleConflict(
                        "owner-requested opportunity contains foreign interpretation lineage"
                    )
            merged_ids = sorted(set(existing_ids) | set(interpretation_ids))
            metadata["evidence_id"] = evidence_id
            metadata["interpretation_ids"] = merged_ids
            metadata_json = _canonical_json(metadata)
            binding_sha256 = hashlib.sha256(
                _canonical_json(
                    {
                        "evidence_id": evidence_id,
                        "interpretation_ids": merged_ids,
                        "opportunity_id": opportunity_id,
                    }
                ).encode("utf-8")
            ).hexdigest()
            event_key = (
                f"owner-post-interpretation-lineage:{opportunity_id}:{binding_sha256}"
            )
            event_id = str(
                uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:event:{event_key}")
            )
            now = _utcnow()
            if metadata_json != original_metadata_json:
                connection.execute(
                    """UPDATE content_opportunities SET metadata_json=?,updated_at=?
                    WHERE opportunity_id=?""",
                    (metadata_json, now, opportunity_id),
                )
            connection.execute(
                """INSERT INTO system_events(
                    event_id,event_type,aggregate_type,aggregate_id,occurred_at,
                    actor_type,payload_json,provenance_json,artifact_refs_json,
                    idempotency_key
                ) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING""",
                (
                    event_id,
                    "content_opportunity.interpretation_lineage_bound",
                    "content_opportunity",
                    opportunity_id,
                    now,
                    "owner_request_router",
                    _canonical_json(
                        {
                            "binding_sha256": binding_sha256,
                            "evidence_id": evidence_id,
                            "interpretation_ids": merged_ids,
                        }
                    ),
                    _canonical_json(
                        {
                            "binding_kind": "available_source_interpretations",
                            "router_version": "owner_requested_post_service/v2",
                        }
                    ),
                    _canonical_json(
                        [evidence["artifact_id"]] if evidence["artifact_id"] else []
                    ),
                    event_key,
                ),
            )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
    return {
        "binding_sha256": binding_sha256,
        "evidence_id": evidence_id,
        "interpretation_ids": merged_ids,
        "opportunity_id": opportunity_id,
    }


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
        not in {FULL_SYSTEM_GROUNDING_MODE, LEGACY_GROUNDING_MODE}
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
    common_persona_invalid = (
        not isinstance(persona, dict)
        or persona.get("passed") is not True
        or int(persona.get("constraint_count") or 0) < 1
        or not _is_sha256(persona.get("constraint_digest"))
    )
    if common_persona_invalid:
        raise ContentLifecycleConflict("owner-requested generation receipt has no canonical persona grounding")
    if receipt.get("grounding_mode") == LEGACY_GROUNDING_MODE:
        if persona.get("schema_version") != LEGACY_OWNER_PERSONA_GATE_SCHEMA:
            raise ContentLifecycleConflict(
                "owner-requested legacy generation receipt has invalid persona grounding"
            )
        return

    context_receipt = persona.get("context_receipt")
    role_counts = (
        context_receipt.get("role_counts")
        if isinstance(context_receipt, dict)
        else None
    )
    source_counts = (
        context_receipt.get("source_counts")
        if isinstance(context_receipt, dict)
        else None
    )
    typed_counts = (
        context_receipt.get("typed_public_safe_counts")
        if isinstance(context_receipt, dict)
        else None
    )
    blocked_counts = (
        context_receipt.get("blocked_projection_counts")
        if isinstance(context_receipt, dict)
        else None
    )
    dream_memory = (
        context_receipt.get("dream_memory_readiness")
        if isinstance(context_receipt, dict)
        else None
    )
    expected_role_keys = {"core", "proof", "story", "ambient", "example", "other"}
    expected_source_keys = {
        "canonical_bundle",
        "committed_overlay",
        "persisted_runtime",
        "legacy_support",
        "dream_safe_lesson",
        "other",
    }
    expected_typed_keys = {"claims", "proof", "stories", "voice_directives"}
    expected_blocked_keys = {"claims", "proof", "stories"}

    def nonnegative_counts(value: Any, expected: set[str]) -> bool:
        return (
            isinstance(value, dict)
            and set(value) == expected
            and all(isinstance(count, int) and not isinstance(count, bool) and count >= 0 for count in value.values())
        )

    if (
        persona.get("schema_version") != OWNER_PERSONA_GATE_SCHEMA
        or persona.get("source")
        != "full_typed_persona_context_plus_integrity_pinned_public_pack"
        or not _is_sha256(persona.get("projection_sha256"))
        or int(persona.get("claims_count") or 0) < 1
        or int(persona.get("proof_count") or 0) < 0
        or int(persona.get("story_count") or 0) < 0
        or not isinstance(persona.get("draft_anchor_terms"), list)
        or not isinstance(persona.get("supported_first_person_experience"), list)
        or not isinstance(persona.get("supported_first_person_worldview"), list)
        or not isinstance(context_receipt, dict)
        or set(context_receipt)
        != {
            "schema_version",
            "builder",
            "source_mode",
            "release_surface",
            "release_policy_version",
            "grounding_mode",
            "voice_domain",
            "selected_context_count",
            "role_counts",
            "source_counts",
            "typed_public_safe_counts",
            "blocked_projection_counts",
            "selected_context_sha256",
            "grounding_reason_sha256",
            "approved_public_pack_sha256",
            "typed_projection_sha256",
            "remote_projection_sha256",
            "full_context_connected",
            "raw_private_memory_sent_remote",
            "unreviewed_persona_sent_remote",
            "dream_memory_readiness",
        }
        or context_receipt.get("schema_version") != PERSONA_CONTEXT_RECEIPT_SCHEMA
        or context_receipt.get("builder")
        != "content_generation_context_service.build_content_generation_context"
        or context_receipt.get("source_mode")
        not in {"verified_memory", "persona_only"}
        or context_receipt.get("release_surface") != "linkedin_post"
        or not str(context_receipt.get("release_policy_version") or "")
        or context_receipt.get("grounding_mode")
        not in {"proof_ready", "story_supported", "principle_only"}
        or context_receipt.get("voice_domain")
        not in {None, "tech_ai", "education", "leadership"}
        or not isinstance(context_receipt.get("selected_context_count"), int)
        or isinstance(context_receipt.get("selected_context_count"), bool)
        or int(context_receipt.get("selected_context_count") or 0) < 1
        or not nonnegative_counts(role_counts, expected_role_keys)
        or not nonnegative_counts(source_counts, expected_source_keys)
        or not nonnegative_counts(typed_counts, expected_typed_keys)
        or not nonnegative_counts(blocked_counts, expected_blocked_keys)
        or sum(role_counts.values()) != context_receipt.get("selected_context_count")
        or sum(source_counts.values()) != context_receipt.get("selected_context_count")
        or not _is_sha256(context_receipt.get("selected_context_sha256"))
        or not _is_sha256(context_receipt.get("grounding_reason_sha256"))
        or not _is_sha256(context_receipt.get("approved_public_pack_sha256"))
        or not _is_sha256(context_receipt.get("typed_projection_sha256"))
        or context_receipt.get("remote_projection_sha256")
        != persona.get("projection_sha256")
        or context_receipt.get("full_context_connected") is not True
        or context_receipt.get("raw_private_memory_sent_remote") is not False
        or context_receipt.get("unreviewed_persona_sent_remote") is not False
        or not isinstance(dream_memory, dict)
        or set(dream_memory)
        != {
            "schema_version",
            "state",
            "latest_status",
            "failed_component_present",
            "verified_entry_count",
            "lane_counts",
            "readiness_id_sha256",
            "last_verified_memory_at",
            "age_seconds",
            "freshness_reason",
        }
        or dream_memory.get("schema_version")
        != DREAM_MEMORY_READINESS_SCHEMA
        or dream_memory.get("state") not in {"ready", "degraded", "unavailable"}
        or not isinstance(dream_memory.get("failed_component_present"), bool)
        or not isinstance(dream_memory.get("verified_entry_count"), int)
        or isinstance(dream_memory.get("verified_entry_count"), bool)
        or dream_memory.get("verified_entry_count", 0) < 0
        or dream_memory.get("freshness_reason")
        not in {
            "fresh",
            "stale",
            "future_timestamp",
            "invalid_timestamp",
            "latest_not_ready",
            "no_receipt",
            "database_unavailable",
        }
        or (
            dream_memory.get("age_seconds") is not None
            and (
                not isinstance(dream_memory.get("age_seconds"), int)
                or isinstance(dream_memory.get("age_seconds"), bool)
            )
        )
        or not nonnegative_counts(
            dream_memory.get("lane_counts"),
            {
                "factual_continuity",
                "operational_continuity",
                "reversible_pattern",
                "identity_candidate",
            },
        )
        or sum(dream_memory.get("lane_counts", {}).values())
        != dream_memory.get("verified_entry_count")
        or (
            dream_memory.get("state") == "ready"
            and (
                dream_memory.get("latest_status") != "ready"
                or dream_memory.get("freshness_reason") != "fresh"
                or not _is_sha256(dream_memory.get("readiness_id_sha256"))
                or context_receipt.get("source_mode") != "verified_memory"
            )
        )
        or (
            dream_memory.get("state") != "ready"
            and (
                context_receipt.get("source_mode") != "persona_only"
                or source_counts.get("dream_safe_lesson") != 0
            )
        )
        or not isinstance(voice.get("typed_context_directive_count"), int)
        or voice.get("typed_context_directive_count") != typed_counts["voice_directives"]
        or not _is_sha256(voice.get("typed_context_directive_digest"))
        or voice.get("typed_context_voice_domain") != context_receipt.get("voice_domain")
    ):
        raise ContentLifecycleConflict(
            "owner-requested generation receipt has no fully connected persona context"
        )


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
        interpretation_ids = [
            str(row["interpretation_id"])
            for row in connection.execute(
                """SELECT interpretation_id FROM interpretations
                WHERE evidence_id=? ORDER BY created_at,interpretation_id""",
                (evidence["evidence_id"],),
            )
        ]
    opportunity = lifecycle.create_or_reuse_opportunity(
        thesis=thesis,
        idempotency_key=f"owner-post:{idempotency_key}",
        source_ids=[source_id],
        owner_requested=True,
        metadata={
            "evidence_id": evidence["evidence_id"],
            "interpretation_ids": interpretation_ids,
            "controls": dict(controls),
        },
    )["opportunity"]
    bind_owner_requested_interpretation_lineage(
        lifecycle=lifecycle,
        opportunity_id=opportunity["opportunity_id"],
        evidence_id=evidence["evidence_id"],
    )
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
