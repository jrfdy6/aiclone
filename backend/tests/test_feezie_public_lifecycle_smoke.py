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
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
import pytest

from app.models import BrainWorkspaceSnapshotSyncRequest
from app.main import validation_exception_handler
from app.routes import brain as brain_routes
from app.routes import content_generation
from app.services import linkedin_owner_review_service as owner_review_service
from app.services import (
    local_content_generation_execution_service,
    neo_public_knowledge_service,
    persona_bundle_writer,
    voice_fidelity_service,
    workspace_snapshot_service as workspace_snapshot_module,
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


def _synthetic_signed_weekly_plan(*, title: str) -> dict:
    return {
        "schema_version": workspace_snapshot_module.FEEZIE_WEEKLY_PLAN_PROJECTION_SCHEMA,
        "generated_at": "2026-08-18T01:47:00+00:00",
        "workspace": "linkedin-content-os",
        "strategy_contract": {
            "schema_version": "feezie_strategy_contract/v1",
            "contract_hash": PUBLIC_STRATEGY_HASH,
        },
        "positioning_model": ["Education operations leader and technology builder"],
        "priority_lanes": ["AI implementation"],
        "pillar_coverage": {
            "counts": {"ai_native": 1},
            "unmapped_count": 0,
            "missing_pillars": [],
            "warnings": [],
        },
        "development_card_count": 1,
        "recommendations": [
            {
                "title": title,
                "intent": "value",
                "priority_lane": "AI implementation",
                "publish_posture": "develop",
                "canonical_pillar": "ai_native",
                "career_signal": "tech_proof",
                "employer_proximity": "personal_build",
                "employer_safety": "pass",
                "proof_posture": "verified_public",
                "audience": "AI systems operators",
                "audience_consequence": "Make a validation boundary reusable.",
                "distinct_thesis": "A green state needs identity-bound evidence.",
                "why_now": "The exact refresh path was just repaired and verified.",
                "development_status": "ready_to_develop",
                "source_kind": "post_seed",
            }
        ],
        "publishing_board": {
            "schema_version": "feezie_seven_day_publishing_board/v1",
            "window_days": 7,
            "primary": [],
            "backup": [],
            "developing": [],
            "publication_authority": "owner_only",
            "may_publish_fewer": True,
            "exact_copy_rule": "Only the owner may approve exact copy.",
        },
        "portfolio_learning": {
            "schema_version": "feezie_portfolio_learning_receipt/v1",
            "learning_mode": "collect_only",
            "confidence": "insufficient_sample",
            "decision_policy": {"strategy_contract_mutation_allowed": False},
        },
        "source_counts": {"total": 1},
        "data_policy": dict(workspace_snapshot_module.FEEZIE_WEEKLY_PLAN_DATA_POLICY),
    }


def _workspace_snapshot_for_weekly_plan(
    *,
    weekly_plan: dict,
    linkedin_root: Path,
    social_feed: dict | None = None,
) -> tuple[dict, object, object]:
    refresh_status = {"running": False, "last_run": None, "started_at": None, "error": None}

    def load_snapshot(snapshot_type: str):
        if snapshot_type == workspace_snapshot_module.SNAPSHOT_WEEKLY_PLAN:
            return deepcopy(weekly_plan)
        if snapshot_type == workspace_snapshot_module.SNAPSHOT_SOCIAL_FEED:
            return deepcopy(social_feed)
        return None

    with ExitStack() as stack:
        stack.enter_context(
            patch.object(workspace_snapshot_module, "_load_snapshot", side_effect=load_snapshot)
        )
        stack.enter_context(
            patch.object(workspace_snapshot_module, "_discover_linkedin_root", return_value=linkedin_root)
        )
        stack.enter_context(
            patch.object(workspace_snapshot_module, "_load_current_feezie_strategy_contract", return_value=None)
        )
        stack.enter_context(
            patch.object(
                workspace_snapshot_module.social_feed_refresh_service,
                "get_status",
                return_value=refresh_status,
            )
        )
        stack.enter_context(
            patch.object(
                workspace_snapshot_module,
                "build_feezie_private_runtime_context_status",
                return_value={"schema_version": "feezie_private_runtime_context_status/v1", "state": "unavailable"},
            )
        )
        stack.enter_context(
            patch(
                "app.services.linkedin_owner_review_service.list_owner_review_items",
                return_value={"items": []},
            )
        )
        lifecycle_builder = stack.enter_context(
            patch.object(
                workspace_snapshot_module,
                "build_source_lifecycle",
                wraps=workspace_snapshot_module.build_source_lifecycle,
            )
        )
        activity_builder = stack.enter_context(
            patch.object(
                workspace_snapshot_module,
                "_build_activity_feed_payload",
                wraps=workspace_snapshot_module._build_activity_feed_payload,
            )
        )
        snapshot = workspace_snapshot_module.workspace_snapshot_service.get_linkedin_os_snapshot(
            include_workspace_files=False,
            include_doc_entries=False,
        )
    return snapshot, lifecycle_builder, activity_builder


def test_legacy_weekly_rows_cannot_reenter_browser_derived_lifecycle_state() -> None:
    canary = "PUBLIC-LEGACY-WEEKLY-CANARY-8f31"
    synthetic_home = str(Path("/").joinpath("Users", "private"))
    private_path = str(Path(synthetic_home) / f"{canary}.md")
    legacy_weekly_plan = {
        "generated_at": "2026-08-18T01:47:00+00:00",
        "workspace": "linkedin-content-os",
        "positioning_model": ["Legacy private plan"],
        "priority_lanes": ["Legacy lane"],
        "recommendations": [
            {
                "title": canary,
                "source_path": private_path,
                "priority_lane": "Legacy lane",
            }
        ],
    }
    social_feed = {
        "generated_at": "2026-08-18T01:48:00+00:00",
        "items": [
            {
                "id": "public-safe-feed-item",
                "title": "A public-safe feed item",
                "source_url": "https://example.com/public-safe-item",
                "ranking": {"total": 8.0},
            }
        ],
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        linkedin_root = Path(temp_dir) / "linkedin-content-os"
        linkedin_root.mkdir()
        snapshot, lifecycle_builder, activity_builder = _workspace_snapshot_for_weekly_plan(
            weekly_plan=legacy_weekly_plan,
            linkedin_root=linkedin_root,
            social_feed=social_feed,
        )

    lifecycle_weekly = lifecycle_builder.call_args.kwargs["weekly_plan"]
    activity_weekly = activity_builder.call_args.kwargs["weekly_plan"]
    for derived_input in (lifecycle_weekly, activity_weekly):
        assert derived_input["schema_version"] == workspace_snapshot_module.FEEZIE_WEEKLY_PLAN_LEGACY_BROWSER_SCHEMA
        assert derived_input["state"] == "legacy_redacted"
        assert derived_input["recommendations"] == []
        assert canary not in json.dumps(derived_input)
        assert private_path not in json.dumps(derived_input)

    browser_snapshot = workspace_snapshot_module.project_linkedin_os_snapshot_for_browser(snapshot)
    assert browser_snapshot["weekly_plan"]["recommendation_count"] == 1
    assert browser_snapshot["weekly_plan"]["recommendations"] == []
    assert browser_snapshot["source_lifecycle"]["counts"]["total"] == 1
    assert browser_snapshot["source_lifecycle"]["items"][0]["title"] == "A public-safe feed item"
    assert browser_snapshot["activity_feed"]["total_count"] == 1
    rendered = json.dumps(browser_snapshot)
    assert canary not in rendered
    assert private_path not in rendered
    assert synthetic_home not in rendered


def test_signed_weekly_recommendation_remains_lifecycle_visible_without_source_path() -> None:
    title = "A signed public-safe validation recommendation"
    signed_weekly_plan = _synthetic_signed_weekly_plan(title=title)

    with tempfile.TemporaryDirectory() as temp_dir:
        linkedin_root = Path(temp_dir) / "linkedin-content-os"
        linkedin_root.mkdir()
        snapshot, lifecycle_builder, activity_builder = _workspace_snapshot_for_weekly_plan(
            weekly_plan=signed_weekly_plan,
            linkedin_root=linkedin_root,
        )

    lifecycle_weekly = lifecycle_builder.call_args.kwargs["weekly_plan"]
    activity_weekly = activity_builder.call_args.kwargs["weekly_plan"]
    for derived_input in (lifecycle_weekly, activity_weekly):
        assert derived_input["schema_version"] == workspace_snapshot_module.FEEZIE_WEEKLY_PLAN_PROJECTION_SCHEMA
        assert derived_input["recommendations"][0]["title"] == title
        assert "source_path" not in derived_input["recommendations"][0]

    lifecycle_items = snapshot["source_lifecycle"]["items"]
    assert len(lifecycle_items) == 1
    assert lifecycle_items[0]["title"] == title
    assert lifecycle_items[0]["stage"] == "weekly_plan"
    assert lifecycle_items[0]["source_path"] == ""
    assert lifecycle_items[0]["artifact_paths"] == []
    assert lifecycle_items[0]["evidence"] == {
        "weekly_plan_source_kind": "post_seed",
        "publish_posture": "develop",
        "priority_lane": "AI implementation",
    }

    browser_snapshot = workspace_snapshot_module.project_linkedin_os_snapshot_for_browser(snapshot)
    assert browser_snapshot["weekly_plan"]["recommendations"][0]["title"] == title
    assert browser_snapshot["source_lifecycle"]["items"][0]["title"] == title
    rendered = json.dumps(browser_snapshot)
    assert "/Users/" not in rendered
    assert "source_path" not in json.dumps(browser_snapshot["weekly_plan"]["recommendations"][0])


def test_strategy_freshness_uses_verified_runtime_contract_when_local_files_are_absent() -> None:
    contract_hash = "b" * 64
    weekly_plan = _synthetic_signed_weekly_plan(title="A current strategy recommendation")
    weekly_plan["strategy_contract"]["contract_hash"] = contract_hash
    runtime_contract = {
        "contract_hash": contract_hash,
        "positioning": {"approved_at": "2026-08-17T12:00:00+00:00"},
        "editorial_mix": {"approved_at": "2026-08-17T13:00:00+00:00"},
    }

    with patch.object(Path, "is_file", return_value=False), patch(
        "app.services.feezie_positioning_contract_service.load_feezie_strategy_contract",
        side_effect=AssertionError("No local strategy loader is allowed without a complete local pair."),
    ) as local_loader, patch.object(
        workspace_snapshot_module,
        "load_persisted_feezie_strategy_contract",
        return_value=runtime_contract,
    ) as runtime_loader:
        freshness = workspace_snapshot_module._strategy_contract_freshness(
            weekly_plan,
            now=datetime.fromisoformat("2026-08-18T02:00:00+00:00"),
        )

    local_loader.assert_not_called()
    runtime_loader.assert_called_once_with()
    assert freshness == {
        "state": "current",
        "planned_hash": contract_hash,
        "current_hash": contract_hash,
        "approved_at": "2026-08-17T13:00:00+00:00",
        "checked_at": "2026-08-18T02:00:00+00:00",
    }


def test_partial_or_invalid_local_strategy_never_falls_back_to_runtime_mirror() -> None:
    def partial_pair(path: Path) -> bool:
        return path.name == "positioning_contract.md"

    with patch.object(Path, "is_file", new=partial_pair), patch.object(
        workspace_snapshot_module,
        "load_persisted_feezie_strategy_contract",
        side_effect=AssertionError("A partial local pair must fail closed."),
    ) as runtime_loader:
        assert workspace_snapshot_module._load_current_feezie_strategy_contract() is None
    runtime_loader.assert_not_called()

    with patch.object(Path, "is_file", return_value=True), patch(
        "app.services.feezie_positioning_contract_service.load_feezie_strategy_contract",
        side_effect=RuntimeError("invalid local strategy"),
    ) as local_loader, patch.object(
        workspace_snapshot_module,
        "load_persisted_feezie_strategy_contract",
        side_effect=AssertionError("An invalid complete local pair must fail closed."),
    ) as runtime_loader:
        assert workspace_snapshot_module._load_current_feezie_strategy_contract() is None
    local_loader.assert_called_once()
    runtime_loader.assert_not_called()


def test_runtime_strategy_mismatch_or_validation_failure_stays_fail_closed() -> None:
    weekly_plan = _synthetic_signed_weekly_plan(title="A strategy comparison recommendation")
    planned_hash = weekly_plan["strategy_contract"]["contract_hash"]
    different_hash = "c" * 64

    with patch.object(Path, "is_file", return_value=False), patch.object(
        workspace_snapshot_module,
        "load_persisted_feezie_strategy_contract",
        return_value={
            "contract_hash": different_hash,
            "positioning": {"approved_at": "2026-08-17T12:00:00+00:00"},
            "editorial_mix": {"approved_at": "2026-08-17T13:00:00+00:00"},
        },
    ):
        stale = workspace_snapshot_module._strategy_contract_freshness(weekly_plan)
    assert stale["state"] == "stale"
    assert stale["planned_hash"] == planned_hash
    assert stale["current_hash"] == different_hash

    with patch.object(Path, "is_file", return_value=False), patch.object(
        workspace_snapshot_module,
        "load_persisted_feezie_strategy_contract",
        side_effect=RuntimeError("invalid, stale, or unavailable runtime context"),
    ):
        unavailable = workspace_snapshot_module._strategy_contract_freshness(weekly_plan)
    assert unavailable["state"] == "unavailable"
    assert unavailable["planned_hash"] == planned_hash
    assert unavailable["current_hash"] is None


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


def test_public_workspace_persona_refresh_is_command_only_and_receipt_only() -> None:
    request_generated_at = "2026-08-17T12:00:00Z"
    request = BrainWorkspaceSnapshotSyncRequest(
        generated_at=request_generated_at,
        persona_review_refresh="recompute_db_owned",
    )
    receipt = {
        "workspace_key": "linkedin-content-os",
        "stored": True,
        "disposition": "stored",
        "snapshot_type": "persona_review_summary",
        "payload_sha256": "b" * 64,
        "snapshot_id": "public-safe-persona-receipt",
        "updated_at": "2026-08-17T12:01:00Z",
        "request_generated_at": request_generated_at,
    }
    with patch.object(
        brain_routes.workspace_snapshot_service,
        "recompute_and_persist_persona_review_summary",
        return_value=receipt,
    ) as recompute:
        response = brain_routes.publish_brain_workspace_snapshots(request)

    recompute.assert_called_once_with(request_generated_at=request_generated_at)
    assert response["snapshots"] == {"persona_review_summary": receipt}
    assert set(receipt) == {
        "workspace_key",
        "stored",
        "disposition",
        "snapshot_type",
        "payload_sha256",
        "snapshot_id",
        "updated_at",
        "request_generated_at",
    }
    rendered = json.dumps(response)
    for prohibited in (
        "persona_review_refresh",
        "brain_pending_review",
        "recent",
        "trait",
        "persona_target",
    ):
        assert prohibited not in rendered


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
        "revision_contract": {
            "schema_version": "feezie_critic_guided_revision_contract/v1",
            "enabled": True,
            "trigger": "non_ready_after_initial_blind_critic",
            "revision_calls_per_non_ready_option": 1,
            "model_retries_per_revision": 0,
            "preserve_ready_sibling_exactly": True,
            "fresh_blind_critic_required_after_revision": True,
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

    critic_review = {
        "status": "completed",
        "blind_review_receipt": _blind_critic_receipt(),
        "draft_distinctness": {
            "passed": True,
            "reason": "The drafts use diagnosis and application treatments.",
        },
        "reviews": critic_reviews,
    }
    option_hashes = [
        hashlib.sha256(option.strip().encode("utf-8")).hexdigest()
        for option in PUBLIC_OPTIONS
    ]
    pair_sha = hashlib.sha256(
        json.dumps(option_hashes, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    voice_contamination_receipt = {
        "schema_version": "feezie_voice_exemplar_contamination/v2",
        "passed": True,
        "exemplar_count": 0,
        "evaluated_option_count": len(PUBLIC_OPTIONS),
        "blocked_option_count": 0,
        "blocker_codes": [],
        "pair_sha256": pair_sha,
        "option_results": [
            {
                "option_index": option_index,
                "option_sha256": option_hashes[option_index - 1],
                "passed": True,
                "blocker_codes": [],
                "findings": [],
            }
            for option_index in (1, 2)
        ],
        "contains_exemplar_text": False,
    }
    critic_sha = hashlib.sha256(
        json.dumps(
            critic_review,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
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
                "draft_distinctness": {
                    "passed": True,
                    "reason": "The drafts use diagnosis and application treatments.",
                },
                "voice_exemplar_contamination": voice_contamination_receipt,
            },
            "technical_completion": {
                "status": "completed",
                "writer_status": "completed",
                "draft_count": 2,
                "drafts_preserved": True,
            },
            "critic_review": critic_review,
            "revision_execution": {
                "schema_version": "feezie_revision_execution_receipt/v1",
                "status": "not_required",
                "failure_code": "",
                "canonical_order_preserved": True,
                "retry_allowed": False,
                "initial_critic_call_count": 1,
                "initial_critic_status": "completed",
                "initial_critic_reason": "",
                "revision_call_count": 0,
                "final_critic_call_count": 0,
                "final_critic_status": "completed",
                "final_critic_reason": "",
                "original_pair_sha256": pair_sha,
                "final_pair_sha256": pair_sha,
                "initial_critic_receipt_sha256": critic_sha,
                "final_critic_receipt_sha256": critic_sha,
                "options": [
                    {
                        "canonical_option_index": option_index,
                        "action": "preserved",
                        "attempt_count": 0,
                        "original_post_sha256": option_hashes[option_index - 1],
                        "final_post_sha256": option_hashes[option_index - 1],
                        "revision_prompt_sha256": "",
                        "bounded_findings_sha256": "",
                        "role_contract_sha256": str(option_index) * 64,
                        "attempt_output_sha256": "",
                        "changed": False,
                        "error_code": "",
                    }
                    for option_index in (1, 2)
                ],
                "contains_post_copy": False,
                "contains_critic_issue_copy": False,
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
    server_quality_gate = deepcopy(result_payload["diagnostics"]["quality_gate"])
    server_quality_gate.pop("voice_exemplar_contamination", None)
    captured_review_items: list[dict] = []
    lifecycle_requests: list[tuple[str, dict]] = []
    recorded_decisions: list[tuple[str, str]] = []

    def capture_owner_review(**kwargs) -> dict:
        assert kwargs.pop("legacy_compatibility", None) is True
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
                    local_content_generation_execution_service,
                    "evaluate_local_quality",
                    return_value=deepcopy(server_quality_gate),
                )
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

                diagnostics = result_payload["diagnostics"]
                blind_plan = content_generation._feezie_expected_blind_critic_plan(
                    job_scope=f"{job_id}:initial",
                    options=list(PUBLIC_OPTIONS),
                )
                blind_receipt = diagnostics["critic_review"]["blind_review_receipt"]
                blind_receipt["job_scope_sha256"] = blind_plan["job_scope_sha256"]
                blind_receipt["critic_order"] = blind_plan["critic_order"]
                blind_receipt["mapping_commitment_sha256"] = hashlib.sha256(
                    json.dumps(
                        blind_plan["critic_order"],
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest()
                option_ids = {
                    canonical_index: critic_option_id
                    for critic_option_id, canonical_index in blind_plan["option_id_to_index"].items()
                }
                for review in diagnostics["critic_review"]["reviews"]:
                    review["critic_option_id"] = option_ids[int(review["option_index"])]
                diagnostics["editorial_readiness"] = content_generation._build_feezie_editorial_readiness(
                    critic_review=diagnostics["critic_review"],
                    deterministic_quality_gate=diagnostics["quality_gate"],
                )
                critic_sha = hashlib.sha256(
                    json.dumps(
                        diagnostics["critic_review"],
                        ensure_ascii=True,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest()
                diagnostics["revision_execution"]["initial_critic_receipt_sha256"] = critic_sha
                diagnostics["revision_execution"]["final_critic_receipt_sha256"] = critic_sha

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
                        "artifacts": [
                            {
                                "kind": "editorial_critic",
                                "label": "initial-editorial-critic-review.json",
                                "filename": "initial-editorial-critic-review.json",
                                "mime_type": "application/json",
                                "content": json.dumps(
                                    result_payload["diagnostics"]["critic_review"],
                                    indent=2,
                                )
                                + "\n",
                            }
                        ],
                    },
                )
                assert complete_response.status_code == 200, complete_response.text
                assert complete_response.json()["status"] == "completed"

                poll_response = client.get(f"/api/content-generation/codex-jobs/{job_id}")
                assert poll_response.status_code == 200
                polled = poll_response.json()
                assert polled["status"] == "completed"
                assert polled["result"]["options"] == list(PUBLIC_OPTIONS)
                assert polled["result"]["diagnostics"]["llm_provider_trace"] == []

                review_response = client.post(
                    f"/api/content-generation/codex-jobs/{job_id}/send-to-review?legacy_compatibility=true",
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
                legacy_compatibility=True,
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
                legacy_compatibility=True,
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
