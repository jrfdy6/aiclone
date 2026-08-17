from __future__ import annotations

import asyncio
import hashlib
import json
import os
import socket
import subprocess
import tempfile
from copy import deepcopy
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
import pytest

from app.main import validation_exception_handler
from app.routes import content_generation
from app.services import linkedin_owner_review_service as owner_review_service
from app.services import (
    neo_public_knowledge_service,
    persona_bundle_writer,
    voice_fidelity_service,
)
from app.services.linkedin_performance_ledger_service import (
    LinkedinPerformanceLedgerService,
    linkedin_content_version_sha256,
)
from app.utils.runtime_workspace_root import resolve_runtime_workspace_root


PUBLIC_STRATEGY_HASH = "a" * 64
PUBLIC_REVIEWED_AT = "2026-01-15T12:00:00+00:00"
PUBLIC_OPTIONS = (
    (
        "Fluent copy can hide missing evidence.\n\n"
        "A deterministic preflight makes that failure visible before drafting begins. "
        "It checks the action, the concrete problem, and the observed lesson as separate inputs.\n\n"
        "That diagnosis keeps unsupported confidence out of review."
    ),
    (
        "Before approving a draft, verify its evidence contract.\n\n"
        "The rule gives reviewers a repeatable boundary: supported claims can advance, while incomplete "
        "claims return to evidence collection. The decision no longer depends on polished phrasing.\n\n"
        "Verify the evidence boundary before approval."
    ),
)


def test_clean_public_backend_root_resolves_without_private_staging_markers() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        service_root = Path(temp_dir) / "service"
        module_path = service_root / "app" / "services" / "example.py"
        module_path.parent.mkdir(parents=True)
        module_path.touch()
        (service_root / "app" / "main.py").touch()
        (service_root / "runtime_paths.py").touch()

        with patch.dict(os.environ, {}, clear=True), patch(
            "pathlib.Path.cwd",
            return_value=service_root / "elsewhere",
        ):
            resolved = resolve_runtime_workspace_root(module_path)

    assert resolved == service_root.resolve()


def _synthetic_public_knowledge_pack() -> dict:
    return {
        "schema_version": "neo_public_knowledge_pack/v1",
        "pack_version": "1.0.0",
        "source_bundle_version": "1.0",
        "curated_on": "2026-01-15",
        "persona_id": "public_operator",
        "display_name": "Public Operator",
        "audiences": ["professional_readers"],
        "purpose": "Bounded approved professional facts for a public deployment test.",
        "source_policy": "canonical_claims_stories_wins_bio_resume_timeline_only",
        "review_status": "approved_public",
        "entries": [
            {
                "id": "claim-system-proof",
                "kind": "claim",
                "title": "System proof",
                "statement": "The operator validates a workflow before calling it complete.",
                "evidence": "The operator validates a workflow before calling it complete.",
                "use_when": "Use for questions about validation and system design.",
                "topics": ["systems_design"],
                "keywords": ["systems", "validation", "workflow"],
                "default_rank": 1,
                "review_status": "approved_public",
            }
        ],
    }


def test_clean_public_source_can_load_approved_knowledge_from_private_runtime_configuration() -> None:
    pack = _synthetic_public_knowledge_pack()
    with patch.dict(
        os.environ,
        {
            neo_public_knowledge_service.PUBLIC_KNOWLEDGE_ENV: json.dumps(pack),
        },
        clear=False,
    ), patch.object(
        neo_public_knowledge_service,
        "resolve_public_knowledge_path",
        side_effect=AssertionError("clean source must not require a persona file"),
    ), patch.object(
        neo_public_knowledge_service,
        "APPROVED_PUBLIC_KNOWLEDGE_PACK_VERSION",
        pack["pack_version"],
    ), patch.object(
        neo_public_knowledge_service,
        "APPROVED_PUBLIC_KNOWLEDGE_SHA256",
        neo_public_knowledge_service.public_knowledge_pack_sha256(pack),
    ):
        status = neo_public_knowledge_service.build_public_knowledge_status()
        selected = neo_public_knowledge_service.select_public_knowledge(
            "How are systems validated?",
            limit=1,
        )

    assert status["state"] == "ready"
    assert status["ready"] is True
    assert status["integrity_verified"] is True
    assert status["source_mode"] == "runtime_environment"
    assert status["entry_count"] == 1
    assert status["data_policy"]["identity_included"] is False
    assert pack["display_name"] not in json.dumps(status)
    assert [entry["id"] for entry in selected] == ["claim-system-proof"]


def test_approved_public_knowledge_status_is_control_plane_only(monkeypatch) -> None:
    pack = _synthetic_public_knowledge_pack()
    service_token = "public-status-control-token"
    worker_token = "public-status-worker-token"
    monkeypatch.setenv("CONTROL_PLANE_AUTH_REQUIRED", "1")
    monkeypatch.setenv("CONTROL_PLANE_SERVICE_TOKEN", service_token)
    monkeypatch.setenv("LOCAL_CODEX_BRIDGE_TOKEN", worker_token)
    monkeypatch.setenv(
        neo_public_knowledge_service.PUBLIC_KNOWLEDGE_ENV,
        json.dumps(pack),
    )
    monkeypatch.setattr(
        neo_public_knowledge_service,
        "APPROVED_PUBLIC_KNOWLEDGE_PACK_VERSION",
        pack["pack_version"],
    )
    monkeypatch.setattr(
        neo_public_knowledge_service,
        "APPROVED_PUBLIC_KNOWLEDGE_SHA256",
        neo_public_knowledge_service.public_knowledge_pack_sha256(pack),
    )

    from app.main import app

    client = TestClient(app)
    endpoint = "/api/neo/admin/knowledge-status"

    anonymous = client.get(endpoint)
    assert anonymous.status_code == 401
    assert anonymous.headers["Cache-Control"] == "no-store, max-age=0"
    assert pack["display_name"] not in anonymous.text

    wrong_scope = client.get(
        endpoint,
        headers={"X-Local-Codex-Token": worker_token},
    )
    assert wrong_scope.status_code == 401
    assert wrong_scope.headers["Cache-Control"] == "no-store, max-age=0"
    assert pack["display_name"] not in wrong_scope.text

    authorized = client.get(
        endpoint,
        headers={"Authorization": f"Bearer {service_token}"},
    )
    assert authorized.status_code == 200
    assert authorized.headers["Cache-Control"] == "no-store, max-age=0"
    assert authorized.json() == {
        "schema_version": "neo_public_knowledge_status/v1",
        "state": "ready",
        "ready": True,
        "integrity_verified": True,
        "source_mode": "runtime_environment",
        "pack_version": "1.0.0",
        "entry_count": 1,
        "review_status": "approved_public",
        "reason_codes": [],
        "data_policy": {
            "aggregate_only": True,
            "knowledge_content_included": False,
            "identity_included": False,
        },
    }
    assert pack["display_name"] not in authorized.text
    assert pack["entries"][0]["statement"] not in authorized.text


def test_well_formed_self_approved_runtime_pack_cannot_replace_exact_release() -> None:
    pack = _synthetic_public_knowledge_pack()
    pack["pack_version"] = (
        neo_public_knowledge_service.APPROVED_PUBLIC_KNOWLEDGE_PACK_VERSION
    )
    with patch.dict(
        os.environ,
        {neo_public_knowledge_service.PUBLIC_KNOWLEDGE_ENV: json.dumps(pack)},
        clear=False,
    ), patch.object(
        neo_public_knowledge_service,
        "resolve_public_knowledge_path",
        side_effect=AssertionError("invalid runtime source must not fall back to a file"),
    ):
        with pytest.raises(
            neo_public_knowledge_service.NeoPublicKnowledgeError,
            match="approved release receipt",
        ):
            neo_public_knowledge_service.load_public_knowledge_pack()
        status = neo_public_knowledge_service.build_public_knowledge_status()

    assert status["state"] == "unavailable"
    assert status["ready"] is False
    assert status["integrity_verified"] is False
    assert status["reason_codes"] == ["approved_public_knowledge_unavailable"]


@pytest.mark.parametrize(
    "runtime_payload",
    [
        pytest.param("{", id="malformed-json"),
        pytest.param(
            "x" * (neo_public_knowledge_service.MAX_PUBLIC_PACK_BYTES + 1),
            id="oversized-json",
        ),
        pytest.param(
            json.dumps(
                {
                    **_synthetic_public_knowledge_pack(),
                    "review_status": "pending",
                }
            ),
            id="unapproved-pack",
        ),
    ],
)
def test_invalid_runtime_pack_fails_closed_without_file_fallback(
    runtime_payload: str,
) -> None:
    with patch.dict(
        os.environ,
        {neo_public_knowledge_service.PUBLIC_KNOWLEDGE_ENV: runtime_payload},
        clear=False,
    ), patch.object(
        neo_public_knowledge_service,
        "resolve_public_knowledge_path",
        side_effect=AssertionError("invalid runtime source must not fall back to a file"),
    ):
        with pytest.raises(neo_public_knowledge_service.NeoPublicKnowledgeError):
            neo_public_knowledge_service.load_public_knowledge_pack()
        status = neo_public_knowledge_service.build_public_knowledge_status()

    assert status["state"] == "unavailable"
    assert status["ready"] is False
    assert status["integrity_verified"] is False
    assert status["source_mode"] == "runtime_environment"
    assert status["reason_codes"] == ["approved_public_knowledge_unavailable"]


def test_validation_error_response_and_logs_never_echo_submitted_private_context(capsys) -> None:
    canary = "PUBLIC-SMOKE-PRIVATE-CANARY-DO-NOT-ECHO"
    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "https",
            "path": "/api/brain/workspace-snapshots/sync",
            "raw_path": b"/api/brain/workspace-snapshots/sync",
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 50000),
            "server": ("testserver", 443),
        }
    )
    error = RequestValidationError(
        [
            {
                "type": "value_error",
                "loc": ("body", "feezie_runtime_context"),
                "msg": f"Invalid persona_chunks proof text: {canary}",
                "input": {
                    "persona_chunks": [{"text": canary}],
                    "anonymized_proof_records": [{"public_proof": canary}],
                },
                "ctx": {"error": ValueError(canary)},
            }
        ]
    )

    response = asyncio.run(validation_exception_handler(request, error))
    captured = capsys.readouterr()
    combined = (response.body.decode("utf-8") + captured.out + captured.err).lower()

    assert response.status_code == 422
    assert response.body == b'{"status":"error","message":"Validation error","errors":[{"type":"value_error"}]}'
    for prohibited in (canary.lower(), "persona_chunks", "anonymized_proof_records", '"input"'):
        assert prohibited not in combined


def _public_evidence_readiness() -> dict:
    return {
        "schema_version": "feezie_evidence_readiness/v1",
        "status": "ready",
        "ready": True,
        "contract": {
            "schema_version": "feezie_publish_ready_evidence/v1",
            "concrete_action": "Built a deterministic preflight for a public-safe test workflow.",
            "exact_problem": "A vague request could reach drafting without complete evidence.",
            "observable_lesson": "The preflight showed that separate evidence fields make review decisions reproducible.",
        },
    }


def _public_context_packet() -> dict:
    return {
        "workspace_slug": "linkedin-content-os",
        "prompt": "Public-safe deterministic lifecycle fixture; no model execution is permitted.",
        "expected_option_count": 2,
        "draft_contract": {
            "schema_version": "feezie_draft_contract/v1",
            "required_option_count": 2,
            "maximum_option_count": 2,
            "meaningful_difference_required": True,
            "independent_writer_calls_required": True,
            "writer_calls_per_option": 1,
            "independent_critic_required": True,
            "critic_reviews_per_option": 1,
            "hook_variants_per_option": 8,
        },
        "intent": "value",
        "strategy_contract": {
            "schema_version": "feezie_positioning_contract/v1",
            "contract_hash": PUBLIC_STRATEGY_HASH,
        },
        "candidate_classification": {
            "publish_posture": "owner_review_required",
            "employer_safety": "pass",
            "proof_posture": "verified_public",
            "audience": "technical operators",
            "distinct_thesis": "Evidence gates make editorial decisions reproducible.",
        },
        "grounding_mode": "proof_ready",
        "proof_packets": [],
        "planned_option_briefs": [
            {
                "option_number": 1,
                "framing_mode": "operator_lesson",
                "primary_claim": "Fluent copy can conceal incomplete evidence.",
                "proof_packet": "A deterministic preflight checks three evidence fields independently.",
                "story_beat": "The missing input becomes visible before drafting.",
                "public_lane": "diagnosis",
                "thesis_treatment": "diagnose hidden evidence drift",
                "proof_progression": "symptom to mechanism to review consequence",
                "payoff": "expose unsupported confidence early",
                "mechanism_focus": "polished wording can conceal an incomplete evidence contract",
                "recognition_basis": "reviewers otherwise discover missing support after drafting",
                "decision_rule_basis": "",
                "required_context_concepts": "",
                "consequence_basis": "",
                "proof_facet_id": "preflight_diagnosis",
                "semantic_payload_version": "feezie_role_payload/v3",
            },
            {
                "option_number": 2,
                "framing_mode": "practical_framework",
                "primary_claim": "Approval should require a verified evidence contract.",
                "proof_packet": "A bounded rule separates supported and incomplete claims.",
                "story_beat": "The reviewer applies the same boundary every time.",
                "public_lane": "application",
                "thesis_treatment": "apply a repeatable approval boundary",
                "proof_progression": "rule to decision to operational payoff",
                "payoff": "advance only supported copy",
                "mechanism_focus": "",
                "recognition_basis": "",
                "decision_rule_basis": (
                    "decision action: verify | decision object: evidence contract | "
                    "boundary: before approval | rule posture: require"
                ),
                "required_context_concepts": "evidence contract and review boundary",
                "consequence_basis": "incomplete claims return to evidence collection",
                "proof_facet_id": "approval_boundary",
                "semantic_payload_version": "feezie_role_payload/v3",
            },
        ],
        "remote_prompt_policy": {
            "schema_version": "feezie_remote_prompt_policy/v4",
            "raw_context_excluded": True,
            "private_paths_excluded": True,
            "raw_voice_examples_excluded": True,
            "source_bodies_excluded": True,
        },
    }


def _blind_critic_receipt() -> dict:
    critic_order = [
        {"critic_option_id": "draft_0000000000000002", "canonical_option_index": 2},
        {"critic_option_id": "draft_0000000000000001", "canonical_option_index": 1},
    ]
    mapping_json = json.dumps(critic_order, sort_keys=True, separators=(",", ":"))
    return {
        "schema_version": "feezie_blind_critic_receipt/v1",
        "independent_execution": True,
        "opaque_identity_used": True,
        "original_numbering_withheld_from_critic": True,
        "original_order_withheld_from_critic": True,
        "writer_option_plan_withheld_from_critic": True,
        "deterministic_shuffle": True,
        "non_identity_permutation": True,
        "order_strategy": "job_scoped_sha256_sort_non_identity/v1",
        "option_count": 2,
        "job_scope_sha256": "0" * 64,
        "critic_order": critic_order,
        "mapping_commitment_sha256": hashlib.sha256(mapping_json.encode("utf-8")).hexdigest(),
        "contains_draft_copy": False,
        "opaque_role_contracts_used": True,
        "contains_role_payload_copy": False,
        "role_contract_commitment_sha256": "1" * 64,
    }


def _precomputed_public_result() -> dict:
    critic_reviews = []
    readiness_reviews = []
    for option_index in (1, 2):
        hooks = [
            f"Public-safe evidence hook {option_index}.{hook_index}"
            for hook_index in range(1, 9)
        ]
        critic_reviews.append(
            {
                "option_index": option_index,
                "critic_option_id": f"draft_{option_index:016x}",
                "score": 9,
                "verdict": "ready",
                "dimension_scores": {
                    "truth": 9,
                    "safety": 9,
                    "intent": 9,
                    "voice": 9,
                    "hook": 9,
                },
                "issues": [],
                "hook_variants": hooks,
            }
        )
        readiness_reviews.append(
            {
                "option_index": option_index,
                "score": 9,
                "verdict": "ready",
                "editorially_ready": True,
                "deterministic_quality_passed": True,
                "deterministic_blocked": False,
                "deterministic_blocking_reasons": [],
                "deterministic_score": 92,
                "deterministic_threshold": 68,
                "issues": [],
                "hook_variants": hooks,
            }
        )

    return {
        "success": True,
        "options": list(PUBLIC_OPTIONS),
        "persona_context": None,
        "examples_used": [],
        "diagnostics": {
            "quality_gate": {
                "schema_version": "feezie_deterministic_quality_gate/v2",
                "passed": True,
                "selection_admission_passed": True,
                "shared_constraints": {
                    "passed": True,
                    "failed_reasons": [],
                    "required_option_count": 2,
                    "evaluated_option_count": 2,
                },
                "option_results": [
                    {
                        "option_index": option_index,
                        "passed": True,
                        "score": 92,
                        "threshold": 68,
                        "failed_reasons": [],
                    }
                    for option_index in (1, 2)
                ],
                "failed_reasons": [],
                "required_option_count": 2,
                "evaluated_option_count": 2,
            },
            "technical_completion": {
                "status": "completed",
                "writer_status": "completed",
                "draft_count": 2,
                "drafts_preserved": True,
            },
            "critic_review": {
                "status": "completed",
                "blind_review_receipt": _blind_critic_receipt(),
                "draft_distinctness": {
                    "passed": True,
                    "reason": "The drafts use diagnosis and application treatments.",
                },
                "reviews": critic_reviews,
            },
            "editorial_readiness": {
                "ready": True,
                "status": "ready",
                "critic_status": "completed",
                "quality_gate_schema_version": "feezie_deterministic_quality_gate/v2",
                "deterministic_quality_receipt_valid": True,
                "deterministic_quality_gate_passed": True,
                "batch_all_options_quality_passed": True,
                "shared_constraints_passed": True,
                "selection_admission_passed": True,
                "semantic_distinctness_passed": True,
                "blocking_reasons": [],
                "option_reviews": readiness_reviews,
            },
            "execution_source": "precomputed_public_fixture",
        },
    }


def _recorded_decision(item: dict, decision: str) -> dict:
    return {
        "items": [],
        "pending_count": 0,
        "resolved_count": 1,
        "workflow": {"status": "recorded_in_memory"},
        "owner_decision_receipt": {
            "schema_version": "feezie_owner_decision_receipt/v1",
            "queue_id": item["queue_id"],
            "decision": decision,
            "reviewed_at": PUBLIC_REVIEWED_AT,
            "decision_recorded": True,
            "replay": False,
        },
    }


def test_public_v2_quality_gate_admits_only_the_independently_ready_sibling() -> None:
    context_packet = _public_context_packet()
    result_payload = _precomputed_public_result()
    diagnostics = result_payload["diagnostics"]
    diagnostics["draft_distinctness"] = {"passed": True}
    quality_gate = diagnostics["quality_gate"]
    failed = quality_gate["option_results"][0]
    failed.update(
        {
            "passed": False,
            "score": 60,
            "failed_reasons": ["claim_not_leading"],
        }
    )
    quality_gate.update(
        {
            "passed": False,
            "selection_admission_passed": True,
            "failed_reasons": ["option_1_claim_not_leading"],
        }
    )
    readiness = diagnostics["editorial_readiness"]
    readiness["batch_all_options_quality_passed"] = False
    readiness["option_reviews"][0].update(
        {
            "score": 6,
            "verdict": "revise",
            "editorially_ready": False,
            "deterministic_quality_passed": False,
            "deterministic_blocked": True,
            "deterministic_blocking_reasons": ["claim_not_leading"],
        }
    )

    with patch.object(
        content_generation,
        "load_feezie_strategy_contract",
        return_value={"contract_hash": PUBLIC_STRATEGY_HASH},
    ):
        selected = content_generation._require_editorially_ready_option(
            result_payload=result_payload,
            context_packet=context_packet,
            option_index=1,
        )
        assert selected["option_index"] == 2
        assert selected["editorially_ready"] is True

        with pytest.raises(ValueError, match="Selected option is not editorially ready"):
            content_generation._require_editorially_ready_option(
                result_payload=result_payload,
                context_packet=context_packet,
                option_index=0,
            )

    missing_selected_receipt = deepcopy(quality_gate)
    missing_selected_receipt.pop("selection_admission_passed")
    with pytest.raises(ValueError, match="Selected option did not pass"):
        content_generation._require_v2_selected_quality_result(
            quality_gate=missing_selected_receipt,
            selected_option_index=2,
            expected_option_count=2,
        )


def test_public_safe_precomputed_feezie_result_traverses_lifecycle_without_side_effects() -> None:
    context_packet = _public_context_packet()
    result_payload = _precomputed_public_result()
    captured_review_items: list[dict] = []
    lifecycle_requests: list[tuple[str, dict]] = []
    recorded_decisions: list[tuple[str, str]] = []

    def capture_owner_review(**kwargs) -> dict:
        item = owner_review_service._generated_owner_review_item(**kwargs)
        captured_review_items.append(deepcopy(item))
        return {
            "card_id": "public-smoke-review-card",
            "queue_id": item["queue_id"],
            "duplicate": False,
            "item": item,
            "message": "Public-safe option sent to owner review.",
        }

    def record_decision(item: dict, decision: str, _notes=None, **_kwargs) -> dict:
        recorded_decisions.append((item["queue_id"], decision))
        return _recorded_decision(item, decision)

    def enqueue_lifecycle(action: str, parameters: dict):
        lifecycle_requests.append((action, deepcopy(parameters)))
        return SimpleNamespace(id=f"public-lifecycle-{len(lifecycle_requests)}"), "queued"

    with tempfile.TemporaryDirectory() as store_dir, patch.dict(
        os.environ,
        {
            "LOCAL_CODEX_JOB_STORE_DIR": store_dir,
            "LOCAL_CODEX_BRIDGE_TOKEN": "test-only",
            "CONTENT_GENERATION_RUNTIME": "local",
        },
        clear=False,
    ):
        app = FastAPI()
        app.include_router(content_generation.router, prefix="/api/content-generation")

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    content_generation,
                    "build_context_cache_key",
                    return_value=("public-safe-cache-key", "2" * 64),
                )
            )
            stack.enter_context(
                patch.object(content_generation, "load_cached_context_packet", return_value=None)
            )
            cache_write = stack.enter_context(
                patch.object(content_generation, "write_cached_context_packet")
            )
            stack.enter_context(
                patch.object(content_generation, "build_content_generation_context", return_value=object())
            )
            stack.enter_context(
                patch.object(
                    content_generation,
                    "_feezie_evidence_readiness",
                    return_value=_public_evidence_readiness(),
                )
            )
            stack.enter_context(
                patch.object(
                    content_generation,
                    "_build_local_codex_context_packet",
                    return_value=deepcopy(context_packet),
                )
            )
            stack.enter_context(
                patch.object(
                    content_generation,
                    "load_feezie_strategy_contract",
                    return_value={"contract_hash": PUBLIC_STRATEGY_HASH},
                )
            )
            stack.enter_context(
                patch.object(
                    owner_review_service,
                    "load_feezie_strategy_contract",
                    return_value={"contract_hash": PUBLIC_STRATEGY_HASH},
                )
            )
            stack.enter_context(
                patch.object(
                    content_generation,
                    "ensure_generated_owner_review_item",
                    side_effect=capture_owner_review,
                )
            )
            stack.enter_context(
                patch.object(
                    owner_review_service,
                    "_record_owner_decision_for_item",
                    side_effect=record_decision,
                )
            )
            stack.enter_context(
                patch.object(
                    owner_review_service,
                    "enqueue_brain_local_action",
                    side_effect=enqueue_lifecycle,
                )
            )
            model_provider = stack.enter_context(
                patch.object(
                    content_generation,
                    "get_openai_client",
                    side_effect=AssertionError("model/provider access is forbidden in this smoke test"),
                )
            )
            embed_provider = stack.enter_context(
                patch.object(
                    content_generation,
                    "embed_text",
                    side_effect=AssertionError("embedding/provider access is forbidden in this smoke test"),
                )
            )
            snapshot_read = stack.enter_context(
                patch.object(
                    content_generation,
                    "get_snapshot_payload",
                    side_effect=AssertionError("private snapshot reads are forbidden in this smoke test"),
                )
            )
            persona_read = stack.enter_context(
                patch.object(
                    content_generation,
                    "retrieve_bundle_persona_chunks",
                    side_effect=AssertionError("persona reads are forbidden in this smoke test"),
                )
            )
            semantic_retrieval = stack.enter_context(
                patch.object(
                    content_generation,
                    "retrieve_similar",
                    side_effect=AssertionError("retrieval access is forbidden in this smoke test"),
                )
            )
            weighted_retrieval = stack.enter_context(
                patch.object(
                    content_generation,
                    "retrieve_weighted",
                    side_effect=AssertionError("retrieval access is forbidden in this smoke test"),
                )
            )
            learning_read = stack.enter_context(
                patch.object(
                    content_generation,
                    "build_feezie_portfolio_learning_receipt",
                    side_effect=AssertionError("learning reads are forbidden in this smoke test"),
                )
            )
            fragment_promotion = stack.enter_context(
                patch.object(
                    content_generation,
                    "promote_generated_fragment",
                    side_effect=AssertionError("promotion is forbidden in this smoke test"),
                )
            )
            persona_path_read = stack.enter_context(
                patch.object(
                    persona_bundle_writer,
                    "resolve_persona_bundle_read_path",
                    side_effect=AssertionError("raw persona files are forbidden in this smoke test"),
                )
            )
            persona_write = stack.enter_context(
                patch.object(
                    persona_bundle_writer,
                    "write_promotion_items_to_bundle",
                    side_effect=AssertionError("persona mutation is forbidden in this smoke test"),
                )
            )
            persona_remove = stack.enter_context(
                patch.object(
                    persona_bundle_writer,
                    "remove_promotion_items_from_bundle",
                    side_effect=AssertionError("persona mutation is forbidden in this smoke test"),
                )
            )
            voice_write = stack.enter_context(
                patch.object(
                    voice_fidelity_service,
                    "append_voice_example",
                    side_effect=AssertionError("voice learning is forbidden in this smoke test"),
                )
            )
            ledger_write = stack.enter_context(
                patch.object(
                    LinkedinPerformanceLedgerService,
                    "append_event",
                    side_effect=AssertionError("publishing/performance mutation is forbidden in this smoke test"),
                )
            )
            network_create_connection = stack.enter_context(
                patch.object(
                    socket,
                    "create_connection",
                    side_effect=AssertionError("network access is forbidden in this smoke test"),
                )
            )
            network_socket_connect = stack.enter_context(
                patch.object(
                    socket.socket,
                    "connect",
                    side_effect=AssertionError("network access is forbidden in this smoke test"),
                )
            )
            subprocess_run = stack.enter_context(
                patch.object(
                    subprocess,
                    "run",
                    side_effect=AssertionError("subprocess/model execution is forbidden in this smoke test"),
                )
            )

            with TestClient(app) as client:
                create_response = client.post(
                    "/api/content-generation/codex-jobs",
                    json={
                        "user_id": "public_smoke_user",
                        "topic": "deterministic editorial review",
                        "context": "Use only this public-safe test fixture.",
                        "content_type": "linkedin_post",
                        "category": "value",
                        "tone": "expert_direct",
                        "audience": "tech_ai",
                        "source_mode": "persona_only",
                        "workspace_slug": "linkedin-content-os",
                    },
                )
                assert create_response.status_code == 200, create_response.text
                created = create_response.json()
                assert created["status"] == "pending"
                assert created["evidence_readiness"]["ready"] is True
                job_id = created["job_id"]

                pending_response = client.get(f"/api/content-generation/codex-jobs/{job_id}")
                assert pending_response.status_code == 200
                assert pending_response.json()["status"] == "pending"

                claim_response = client.post(
                    "/api/content-generation/codex-jobs/claim-next",
                    headers={"X-Local-Codex-Token": "test-only"},
                    json={
                        "worker_id": "public-smoke-worker",
                        "workspace_slug": "linkedin-content-os",
                    },
                )
                assert claim_response.status_code == 200, claim_response.text
                claimed = claim_response.json()
                assert claimed["job_available"] is True
                assert claimed["job_id"] == job_id
                assert claimed["status"] == "running"

                complete_response = client.post(
                    f"/api/content-generation/codex-jobs/{job_id}/complete",
                    headers={"X-Local-Codex-Token": "test-only"},
                    json={
                        "worker_id": "public-smoke-worker",
                        "result_payload": result_payload,
                    },
                )
                assert complete_response.status_code == 200, complete_response.text
                assert complete_response.json()["status"] == "completed"

                poll_response = client.get(f"/api/content-generation/codex-jobs/{job_id}")
                assert poll_response.status_code == 200
                polled = poll_response.json()
                assert polled["status"] == "completed"
                assert polled["result"]["options"] == list(PUBLIC_OPTIONS)
                assert "llm_provider_trace" not in polled["result"]["diagnostics"]

                review_response = client.post(
                    f"/api/content-generation/codex-jobs/{job_id}/send-to-review",
                    json={"option_index": 1},
                )
                assert review_response.status_code == 200, review_response.text
                review_payload = review_response.json()
                assert review_payload["owner_review_required"] is True
                assert review_payload["option_index"] == 1
                assert review_payload["owner_review_item"]["first_pass_draft"] == PUBLIC_OPTIONS[1]

            selected_item = review_payload["owner_review_item"]
            approved = owner_review_service._record_owner_decision_with_lifecycle_for_item(
                deepcopy(selected_item),
                "approve",
            )
            expected_selected_hash = linkedin_content_version_sha256(PUBLIC_OPTIONS[1])
            assert approved["owner_decision_receipt"]["exact_copy_bound"] is True
            assert approved["owner_decision_receipt"]["content_version_sha256"] == expected_selected_hash
            assert approved["lifecycle_queue"]["approval_verified"] is False
            assert approved["lifecycle_queue"]["event_recorded"] is False

            sibling_item = owner_review_service._generated_owner_review_item(
                job_id=job_id,
                option_index=0,
                option_text=PUBLIC_OPTIONS[0],
                request_payload={
                    "topic": "deterministic editorial review",
                    "content_type": "linkedin_post",
                    "audience": "tech_ai",
                },
                context_packet=context_packet,
                generation_diagnostics=result_payload["diagnostics"],
            )
            parked = owner_review_service._record_owner_decision_with_lifecycle_for_item(
                sibling_item,
                "park",
            )
            assert parked["owner_decision_receipt"]["decision"] == "park"
            assert parked["owner_decision_receipt"]["exact_copy_bound"] is True
            assert parked["owner_decision_receipt"]["content_version_sha256"] == linkedin_content_version_sha256(
                PUBLIC_OPTIONS[0]
            )

            assert [decision for _, decision in recorded_decisions] == ["approve", "park"]
            assert len(captured_review_items) == 1
            assert len(lifecycle_requests) == 2
            assert [parameters["request"]["owner_decision"] for _, parameters in lifecycle_requests] == [
                "approve",
                "park",
            ]
            for action, parameters in lifecycle_requests:
                request = parameters["request"]
                assert action == "linkedin_performance_record"
                assert request["event_type"] == "owner_reviewed"
                assert request["event_type"] != "published"
                assert set(request) == {
                    "event_type",
                    "idempotency_key",
                    "content_id",
                    "content_version_sha256",
                    "occurred_at",
                    "owner_decision",
                    "audience",
                    "unavailable_metrics",
                    "quality_flags",
                }
                assert not {
                    "copy_text",
                    "notes",
                    "publication_url",
                    "source_url",
                    "source_path",
                    "draft_path",
                    "owner_packet_path",
                }.intersection(request)

            persisted_public_fixture = "\n".join(
                path.read_text(encoding="utf-8", errors="replace")
                for path in Path(store_dir).rglob("*")
                if path.is_file()
            )
            for forbidden_fragment in (
                "test-only",
                "/Users/",
                "/home/",
                "PRIVATE_RAW_FIXTURE",
                "sk-",
            ):
                assert forbidden_fragment not in persisted_public_fixture

            cache_write.assert_called_once()
            model_provider.assert_not_called()
            embed_provider.assert_not_called()
            snapshot_read.assert_not_called()
            persona_read.assert_not_called()
            semantic_retrieval.assert_not_called()
            weighted_retrieval.assert_not_called()
            learning_read.assert_not_called()
            fragment_promotion.assert_not_called()
            persona_path_read.assert_not_called()
            persona_write.assert_not_called()
            persona_remove.assert_not_called()
            voice_write.assert_not_called()
            ledger_write.assert_not_called()
            network_create_connection.assert_not_called()
            network_socket_connect.assert_not_called()
            subprocess_run.assert_not_called()
