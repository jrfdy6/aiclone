from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from app.models import BrainWorkspaceSnapshotSyncRequest
from app.routes import brain as brain_routes
from app.services import (
    content_generation_context_service,
    feezie_positioning_contract_service,
    feezie_runtime_context_service,
    local_codex_context_cache_service,
    persona_bundle_context_service,
    portfolio_workspace_snapshot_service,
)


GENERATED_AT = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _persona_chunk(
    bundle_path: str,
    memory_role: str,
    text: str,
    *,
    index: int = 0,
    artifact_backed: bool = False,
) -> dict[str, object]:
    return {
        "source_id": f"bundle:{bundle_path}:{index}",
        "source_file_id": bundle_path,
        "chunk_index": index,
        "chunk": text,
        "persona_tag": "LINKEDIN_EXAMPLES" if memory_role == "example" else "PHILOSOPHY",
        "metadata": {
            "bundle_path": bundle_path,
            "memory_role": memory_role,
            "domain_tags": ["ai_systems"],
            "audience_tags": ["tech_ai"],
            "proof_kind": "initiative" if memory_role == "proof" else "guiding_rule",
            "proof_strength": "strong" if artifact_backed else "none",
            "artifact_backed": artifact_backed,
            "usage_modes": ["proof_anchor"] if memory_role == "proof" else ["always_on"],
            "source_kind": "canonical_bundle",
        },
    }


def _persona_chunks() -> list[dict[str, object]]:
    return [
        _persona_chunk(
            "identity/VOICE_PATTERNS.md",
            "core",
            "Use direct sentences, honest tension, and concrete operating detail.",
        ),
        _persona_chunk(
            "identity/claims.md",
            "core",
            "Technology should make human judgment clearer instead of hiding it.",
        ),
        _persona_chunk(
            "prompts/content_guardrails.md",
            "core",
            "Never invent outcomes, private metrics, or employer endorsement.",
        ),
        _persona_chunk(
            "prompts/content_examples.md",
            "example",
            "I rebuilt the handoff because the first version made ownership harder to see.",
        ),
        _persona_chunk(
            "history/initiatives.md",
            "proof",
            "A bounded workflow now preserves review state across the full handoff.",
            artifact_backed=True,
        ),
    ]


def _public_safe_lessons() -> list[dict[str, object]]:
    return [
        {
            "id": "private-local-id-that-must-not-persist",
            "source_signal_id": "another-private-id-that-must-not-persist",
            "visibility": "public_safe",
            "macro_thesis": "A system is not done when motion stops; closure must be explicit.",
            "public_takeaway": "Design the final review state before automating the handoff.",
            "public_proof": "A recent workflow revision made review state durable across handoffs.",
            "safe_angle": "execution",
            "topic_tags": ["workflow", "execution"],
        }
    ]


def _synthetic_strategy_contract() -> dict[str, object]:
    positioning = {key: {} for key in feezie_runtime_context_service._POSITIONING_KEYS}
    positioning.update(
        {
            "schema_version": "positioning_contract/v1",
            "status": "owner_approved",
            "approved_at": "2026-01-01T00:00:00Z",
            "owner": "public-owner",
            "career_posture": {
                "mode": "proof_led_technology_expansion",
                "public_job_search": False,
                "explicit_transition_default": "blocked",
                "employer_specific_default": "owner_review_required",
                "publication_requires_owner_approval": True,
            },
            "generation_quality_contract": {
                "required_option_count": 2,
                "maximum_option_count": 2,
                "meaningful_difference_required": True,
                "independent_critic_required": True,
                "critic_dimensions": ["truth", "safety", "intent", "voice", "hook"],
                "hook_variants_per_option": 8,
                "owner_review_requires_critic_ready": True,
            },
        }
    )
    editorial = {key: {} for key in feezie_runtime_context_service._EDITORIAL_KEYS}
    editorial.update(
        {
            "schema_version": "editorial_mix/v1",
            "status": "owner_approved",
            "approved_at": "2026-01-01T00:00:00Z",
            "owner": "public-owner",
            "rolling_topic_mix": {
                "window": 10,
                "counts": {"ai_native": 4, "leadership_operator": 4, "trust_systems": 2},
            },
            "intent_mix": {
                "window": 11,
                "counts": {"value": 9, "invitation": 1, "personal": 1},
            },
        }
    )
    positioning_sha = "1" * 64
    editorial_sha = "2" * 64
    return {
        "schema_version": "feezie_strategy_contract/v1",
        "contract_hash": hashlib.sha256(
            f"{positioning_sha}:{editorial_sha}".encode("utf-8")
        ).hexdigest(),
        "positioning": positioning,
        "editorial_mix": editorial,
        "sources": {
            "positioning": {
                "path": "workspaces/linkedin-content-os/docs/positioning_contract.md",
                "sha256": positioning_sha,
            },
            "editorial_mix": {
                "path": "workspaces/linkedin-content-os/docs/editorial_mix.md",
                "sha256": editorial_sha,
            },
        },
    }


def _build_bundle(*, generated_at: str = GENERATED_AT) -> dict[str, object]:
    strategy = _synthetic_strategy_contract()
    return feezie_runtime_context_service.build_feezie_runtime_context_bundle(
        generated_at=generated_at,
        strategy_contract=strategy,
        persona_chunks=_persona_chunks(),
        content_safe_operator_lessons=_public_safe_lessons(),
    )


def _stage_public_strategy_placeholders(root: Path) -> None:
    for relative_path in (
        "workspaces/linkedin-content-os/docs/positioning_contract.md",
        "workspaces/linkedin-content-os/docs/editorial_mix.md",
    ):
        destination = root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("# Public-safe strategy fixture\n", encoding="utf-8")


class FeezieRuntimeContextServiceTests(unittest.TestCase):
    def test_builder_creates_bounded_self_contained_hash_bound_bundle(self) -> None:
        bundle = _build_bundle()

        validated = feezie_runtime_context_service.validate_feezie_runtime_context_bundle(bundle)

        self.assertEqual(validated["schema_version"], "feezie_runtime_context/v1")
        self.assertEqual(validated["counts"]["chunk_count"], 5)
        self.assertEqual(validated["counts"]["anonymized_proof_count"], 1)
        self.assertLess(len(json.dumps(validated).encode("utf-8")), 2 * 1024 * 1024)
        rendered = json.dumps(validated)
        self.assertNotIn("private-local-id", rendered)
        self.assertNotIn("source_signal_id", rendered)
        self.assertNotIn('"raw_source":', rendered)

    def test_validator_rejects_content_tampering_even_when_schema_is_unchanged(self) -> None:
        bundle = _build_bundle()
        tampered = copy.deepcopy(bundle)
        tampered["persona_chunks"][0]["text"] = "Changed after the receipt was created."

        with self.assertRaisesRegex(
            feezie_runtime_context_service.FeezieRuntimeContextError,
            "chunk_id does not match",
        ):
            feezie_runtime_context_service.validate_feezie_runtime_context_bundle(tampered)

    def test_builder_rejects_private_path_and_credential_canaries(self) -> None:
        strategy = _synthetic_strategy_contract()
        unsafe_values = (
            "/" + "Users/example/private/context.json",
            "/" + "Volumes/private/context.json",
            "/" + "root/.config/secret",
            "/" + "etc/passwd",
            "file:" + "///private/context.json",
            "C:" + r"\Users\Owner\secret.txt",
            "\\\\" + "server" + "\\" + "share" + "\\" + "secret.txt",
            "owner" + chr(64) + "example" + "." + "test",
            "api_" + "key=" + ("A" * 24),
            "eyJ" + "hbGciOiJIUzI1NiJ9." + "eyJzdWIiOiIxMjM0NTY3ODkwIn0." + "signaturevalue123456",
            "AKIA" + ("A" * 16),
            "Bearer" + " " + ("b" * 32),
            "postgresql:" + "//service:secret-value" + chr(64) + "database.internal/app",
        )
        for unsafe_value in unsafe_values:
            chunks = _persona_chunks()
            chunks[0]["chunk"] = unsafe_value
            with self.subTest(unsafe_value=unsafe_value[:10]):
                with self.assertRaises(feezie_runtime_context_service.FeezieRuntimeContextError):
                    feezie_runtime_context_service.build_feezie_runtime_context_bundle(
                        generated_at=GENERATED_AT,
                        strategy_contract=strategy,
                        persona_chunks=chunks,
                        content_safe_operator_lessons=_public_safe_lessons(),
                    )

    def test_strategy_contract_hash_and_paths_are_anchored_to_canonical_sources(self) -> None:
        strategy = _synthetic_strategy_contract()

        wrong_hash = copy.deepcopy(strategy)
        wrong_hash["contract_hash"] = "0" * 64
        with self.assertRaisesRegex(
            feezie_runtime_context_service.FeezieRuntimeContextError,
            "does not match its canonical source hashes",
        ):
            feezie_runtime_context_service.build_feezie_runtime_context_bundle(
                generated_at=GENERATED_AT,
                strategy_contract=wrong_hash,
                persona_chunks=_persona_chunks(),
                content_safe_operator_lessons=_public_safe_lessons(),
            )

        wrong_path = copy.deepcopy(strategy)
        wrong_path["sources"]["positioning"]["path"] = "docs/positioning_contract.md"
        with self.assertRaisesRegex(
            feezie_runtime_context_service.FeezieRuntimeContextError,
            "not the canonical strategy source",
        ):
            feezie_runtime_context_service.build_feezie_runtime_context_bundle(
                generated_at=GENERATED_AT,
                strategy_contract=wrong_path,
                persona_chunks=_persona_chunks(),
                content_safe_operator_lessons=_public_safe_lessons(),
            )

    def test_strategy_and_persona_loaders_use_valid_persisted_fallback_when_files_are_absent(self) -> None:
        bundle = _build_bundle()
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing_root = Path(temporary_directory) / "clean-public-checkout"
            missing_state = Path(temporary_directory) / "missing-state"
            missing_seed = Path(temporary_directory) / "missing-seed"
            with patch.object(
                feezie_runtime_context_service,
                "get_snapshot_payload",
                return_value=bundle,
            ):
                strategy = feezie_positioning_contract_service.load_feezie_strategy_contract(
                    missing_root
                )
                with (
                    patch.object(
                        persona_bundle_context_service,
                        "resolve_persona_bundle_state_root",
                        return_value=missing_state,
                    ),
                    patch.object(
                        persona_bundle_context_service,
                        "resolve_persona_bundle_root",
                        return_value=missing_seed,
                    ),
                ):
                    chunks = persona_bundle_context_service.load_bundle_persona_chunks()

        self.assertEqual(strategy["contract_hash"], bundle["strategy_contract"]["contract_hash"])
        self.assertEqual(len(chunks), bundle["counts"]["chunk_count"])
        self.assertTrue(all(item["metadata"]["runtime_context_backed"] for item in chunks))

    def test_strategy_loader_uses_matching_runtime_context_when_only_private_identity_files_are_absent(self) -> None:
        bundle = _build_bundle()
        with tempfile.TemporaryDirectory() as temporary_directory:
            staged_root = Path(temporary_directory) / "privacy-reduced-stage"
            _stage_public_strategy_placeholders(staged_root)
            with (
                patch.object(
                    feezie_positioning_contract_service,
                    "_load_feezie_strategy_contract",
                    side_effect=[
                        feezie_positioning_contract_service.FeeziePositioningContractError(
                            "Private identity references are absent from the public stage."
                        ),
                        copy.deepcopy(bundle["strategy_contract"]),
                    ],
                ) as staged_loader,
                patch.object(
                    feezie_positioning_contract_service,
                    "_load_persisted_strategy_contract",
                    return_value=copy.deepcopy(bundle["strategy_contract"]),
                ) as persisted_loader,
            ):
                strategy = feezie_positioning_contract_service.load_feezie_strategy_contract(
                    staged_root
                )

        self.assertEqual(strategy, bundle["strategy_contract"])
        self.assertEqual(staged_loader.call_count, 2)
        self.assertTrue(
            staged_loader.call_args_list[1].kwargs["allow_missing_private_identity_files"]
        )
        persisted_loader.assert_called_once_with()

    def test_strategy_loader_does_not_hide_a_missing_public_runtime_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            staged_root = Path(temporary_directory) / "invalid-stage"
            _stage_public_strategy_placeholders(staged_root)
            with (
                patch.object(
                    feezie_positioning_contract_service,
                    "_load_feezie_strategy_contract",
                    side_effect=[
                        feezie_positioning_contract_service.FeeziePositioningContractError(
                            "Private identity references are absent from the public stage."
                        ),
                        feezie_positioning_contract_service.FeeziePositioningContractError(
                            "qualification_runtime references a missing file"
                        ),
                    ],
                ) as staged_loader,
                patch.object(
                    feezie_positioning_contract_service,
                    "_load_persisted_strategy_contract",
                ) as persisted_loader,
                self.assertRaisesRegex(
                    feezie_positioning_contract_service.FeeziePositioningContractError,
                    "qualification_runtime references a missing file",
                ),
            ):
                feezie_positioning_contract_service.load_feezie_strategy_contract(staged_root)
        self.assertEqual(staged_loader.call_count, 2)
        persisted_loader.assert_not_called()

    def test_strategy_loader_rejects_runtime_context_that_does_not_match_staged_contracts(self) -> None:
        bundle = _build_bundle()
        staged_contract = copy.deepcopy(bundle["strategy_contract"])
        staged_contract["contract_hash"] = "0" * 64
        with tempfile.TemporaryDirectory() as temporary_directory:
            staged_root = Path(temporary_directory) / "mismatched-stage"
            _stage_public_strategy_placeholders(staged_root)
            with (
                patch.object(
                    feezie_positioning_contract_service,
                    "_load_feezie_strategy_contract",
                    side_effect=[
                        feezie_positioning_contract_service.FeeziePositioningContractError(
                            "Private identity references are absent from the public stage."
                        ),
                        staged_contract,
                    ],
                ),
                patch.object(
                    feezie_positioning_contract_service,
                    "_load_persisted_strategy_contract",
                    return_value=copy.deepcopy(bundle["strategy_contract"]),
                ),
                self.assertRaisesRegex(
                    feezie_positioning_contract_service.FeeziePositioningContractError,
                    "does not match the staged strategy contracts",
                ),
            ):
                feezie_positioning_contract_service.load_feezie_strategy_contract(staged_root)

    def test_missing_or_invalid_persisted_fallback_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing_root = Path(temporary_directory) / "clean-public-checkout"
            missing_state = Path(temporary_directory) / "missing-state"
            missing_seed = Path(temporary_directory) / "missing-seed"
            with patch.object(
                feezie_runtime_context_service,
                "get_snapshot_payload",
                return_value=None,
            ):
                with self.assertRaisesRegex(
                    feezie_positioning_contract_service.FeeziePositioningContractError,
                    "no private runtime context",
                ):
                    feezie_positioning_contract_service.load_feezie_strategy_contract(missing_root)
                with (
                    patch.object(
                        persona_bundle_context_service,
                        "resolve_persona_bundle_state_root",
                        return_value=missing_state,
                    ),
                    patch.object(
                        persona_bundle_context_service,
                        "resolve_persona_bundle_root",
                        return_value=missing_seed,
                    ),
                    self.assertRaisesRegex(
                        feezie_runtime_context_service.FeezieRuntimeContextError,
                        "no private FEEZIE runtime context",
                    ),
                ):
                    persona_bundle_context_service.load_bundle_persona_chunks()

            invalid = _build_bundle()
            invalid["payload_sha256"] = "0" * 64
            with patch.object(
                feezie_runtime_context_service,
                "get_snapshot_payload",
                return_value=invalid,
            ):
                with self.assertRaisesRegex(
                    feezie_positioning_contract_service.FeeziePositioningContractError,
                    "invalid",
                ):
                    feezie_positioning_contract_service.load_feezie_strategy_contract(missing_root)

    def test_content_generation_uses_bundled_anonymized_proof_when_legacy_row_is_absent(self) -> None:
        bundle = _build_bundle()
        with (
            patch.object(
                content_generation_context_service,
                "get_snapshot_payload",
                return_value=None,
            ),
            patch.object(
                feezie_runtime_context_service,
                "get_snapshot_payload",
                return_value=bundle,
            ),
        ):
            payload = content_generation_context_service._load_content_safe_operator_lessons_payload(
                allow_runtime_rebuild=False
            )

        self.assertEqual(payload["counts"]["total"], 1)
        self.assertEqual(payload["lessons"][0]["visibility"], "public_safe")
        self.assertNotIn("source_signal_id", payload["lessons"][0])

    def test_context_cache_hash_includes_private_runtime_bundle(self) -> None:
        bundle = _build_bundle()
        updated_bundle = copy.deepcopy(bundle)
        updated_bundle["generated_at"] = "2026-08-16T12:01:00Z"

        current = {"value": bundle}

        def load_snapshot(workspace_key: str, snapshot_type: str):
            if workspace_key == "feezie-os" and snapshot_type == "feezie_runtime_context":
                return current["value"]
            return None

        with patch.object(
            local_codex_context_cache_service,
            "get_snapshot_payload",
            side_effect=load_snapshot,
        ):
            first = local_codex_context_cache_service._snapshot_hash("linkedin-content-os")
            current["value"] = updated_bundle
            second = local_codex_context_cache_service._snapshot_hash("linkedin-content-os")

        self.assertNotEqual(first, second)

    def test_aggregate_status_never_exposes_private_bundle_content_or_hashes(self) -> None:
        now = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
        bundle = _build_bundle(
            generated_at=(now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        )
        with patch.object(
            feezie_runtime_context_service,
            "get_snapshot_payload",
            return_value=bundle,
        ):
            status = feezie_runtime_context_service.build_feezie_private_runtime_context_status(
                now=now
            )

        self.assertTrue(status["ready"])
        self.assertEqual(status["state"], "ready")
        self.assertNotIn("generated_at", status)
        self.assertEqual(status["checked_at"], "2026-08-16T12:00:00Z")
        self.assertEqual(status["context_generated_at"], "2026-08-16T11:00:00Z")
        self.assertEqual(status["age_seconds"], 3_600)
        self.assertEqual(status["stale_after_seconds"], 36 * 60 * 60)
        self.assertEqual(status["approved_voice_examples"]["count"], 1)
        self.assertEqual(status["anonymized_proof"]["count"], 1)
        rendered = json.dumps(status).lower()
        for prohibited in ("sha256", "macro_thesis", "bundle_path", "content_examples.md"):
            self.assertNotIn(prohibited, rendered)

    def test_status_rejects_stale_and_future_context_with_stable_truth_fields(self) -> None:
        now = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
        cases = (
            (
                now - timedelta(hours=36, seconds=1),
                "stale",
                "runtime_context_stale",
            ),
            (
                now + timedelta(minutes=5, seconds=1),
                "invalid",
                "runtime_context_future",
            ),
        )
        for generated_at, expected_state, expected_reason in cases:
            bundle = _build_bundle(
                generated_at=generated_at.isoformat().replace("+00:00", "Z")
            )
            with (
                self.subTest(reason=expected_reason),
                patch.object(
                    feezie_runtime_context_service,
                    "get_snapshot_payload",
                    return_value=bundle,
                ),
            ):
                status = feezie_runtime_context_service.build_feezie_private_runtime_context_status(
                    now=now
                )

            self.assertFalse(status["ready"])
            self.assertEqual(status["state"], expected_state)
            self.assertEqual(status["reason_codes"], [expected_reason])
            self.assertEqual(status["checked_at"], "2026-08-16T12:00:00Z")
            self.assertEqual(status["context_generated_at"], bundle["generated_at"])

    def test_current_bundle_validator_allows_five_minute_skew_and_rejects_stale_or_future(self) -> None:
        now = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
        allowed = _build_bundle(
            generated_at=(now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
        )
        self.assertEqual(
            feezie_runtime_context_service.require_current_feezie_runtime_context_bundle(
                allowed,
                now=now,
            )["payload_sha256"],
            allowed["payload_sha256"],
        )

        stale = _build_bundle(
            generated_at=(now - timedelta(hours=36, seconds=1)).isoformat().replace("+00:00", "Z")
        )
        future = _build_bundle(
            generated_at=(now + timedelta(minutes=5, seconds=1)).isoformat().replace("+00:00", "Z")
        )
        with self.assertRaisesRegex(
            feezie_runtime_context_service.FeezieRuntimeContextError,
            "stale",
        ):
            feezie_runtime_context_service.require_current_feezie_runtime_context_bundle(
                stale,
                now=now,
            )
        with self.assertRaisesRegex(
            feezie_runtime_context_service.FeezieRuntimeContextError,
            "future",
        ):
            feezie_runtime_context_service.require_current_feezie_runtime_context_bundle(
                future,
                now=now,
            )

    def test_persisted_runtime_reader_fails_closed_on_stale_context(self) -> None:
        stale = _build_bundle(
            generated_at=(
                datetime.now(timezone.utc) - timedelta(hours=36, minutes=1)
            ).isoformat(timespec="microseconds").replace("+00:00", "Z")
        )
        with (
            patch.object(
                feezie_runtime_context_service,
                "get_snapshot_payload",
                return_value=stale,
            ),
            self.assertRaisesRegex(
                feezie_runtime_context_service.FeezieRuntimeContextError,
                "stale",
            ),
        ):
            feezie_runtime_context_service.load_persisted_feezie_runtime_context_bundle()

    def test_portfolio_snapshot_type_inventory_hides_private_runtime_row(self) -> None:
        with patch.object(
            portfolio_workspace_snapshot_service,
            "list_snapshot_payloads",
            return_value={
                "feezie_runtime_context": {"private": True},
                "publication_performance_summary": {"counts": {}},
            },
        ):
            visible = portfolio_workspace_snapshot_service._safe_snapshot_types(
                "feezie-os",
                "linkedin-content-os",
            )

        rendered = json.dumps(visible)
        self.assertNotIn("feezie_runtime_context", rendered)
        self.assertIn("publication_performance_summary", rendered)


class FeezieRuntimeContextSyncTests(unittest.TestCase):
    def test_sync_model_and_route_store_context_monotonically_under_private_type(self) -> None:
        bundle = _build_bundle()
        request = BrainWorkspaceSnapshotSyncRequest(
            generated_at=GENERATED_AT,
            feezie_runtime_context=bundle,
        )
        stored = {
            "id": "runtime-context-row",
            "workspace_key": "feezie-os",
            "snapshot_type": "feezie_runtime_context",
            "payload": bundle,
            "updated_at": GENERATED_AT,
        }
        with patch.object(
            brain_routes,
            "upsert_snapshot_monotonic",
            return_value=(stored, True),
        ) as upsert:
            response = brain_routes.publish_brain_workspace_snapshots(request)

        self.assertTrue(response["stored"])
        self.assertEqual(set(response["snapshots"]), {"feezie_runtime_context"})
        runtime_ack = response["snapshots"]["feezie_runtime_context"]
        self.assertEqual(runtime_ack["workspace_key"], "feezie-os")
        self.assertEqual(runtime_ack["snapshot_type"], "feezie_runtime_context")
        self.assertEqual(runtime_ack["disposition"], "stored")
        self.assertEqual(runtime_ack["payload_sha256"], bundle["payload_sha256"])
        self.assertEqual(
            upsert.call_args.args[:2],
            ("feezie-os", "feezie_runtime_context"),
        )
        self.assertEqual(upsert.call_args.args[2]["payload_sha256"], bundle["payload_sha256"])

    def test_sync_model_rejects_hash_tampering_and_envelope_timestamp_mismatch(self) -> None:
        bundle = _build_bundle()
        tampered = copy.deepcopy(bundle)
        tampered["payload_sha256"] = "0" * 64
        with self.assertRaises(ValidationError):
            BrainWorkspaceSnapshotSyncRequest(
                generated_at=GENERATED_AT,
                feezie_runtime_context=tampered,
            )

        with self.assertRaises(ValidationError):
            BrainWorkspaceSnapshotSyncRequest(
                generated_at=(
                    datetime.fromisoformat(GENERATED_AT.replace("Z", "+00:00"))
                    + timedelta(seconds=1)
                ).isoformat().replace("+00:00", "Z"),
                feezie_runtime_context=bundle,
            )

    def test_sync_model_requires_current_runtime_context(self) -> None:
        stale_generated_at = (
            datetime.now(timezone.utc) - timedelta(hours=36, seconds=1)
        ).isoformat(timespec="microseconds").replace("+00:00", "Z")
        future_generated_at = (
            datetime.now(timezone.utc) + timedelta(minutes=5, seconds=1)
        ).isoformat(timespec="microseconds").replace("+00:00", "Z")
        for generated_at in (stale_generated_at, future_generated_at):
            bundle = _build_bundle(generated_at=generated_at)
            with self.subTest(generated_at=generated_at), self.assertRaises(ValidationError):
                BrainWorkspaceSnapshotSyncRequest(
                    generated_at=generated_at,
                    feezie_runtime_context=bundle,
                )

    def test_runtime_sync_reports_idempotent_same_hash(self) -> None:
        bundle = _build_bundle()
        request = BrainWorkspaceSnapshotSyncRequest(
            generated_at=GENERATED_AT,
            feezie_runtime_context=bundle,
        )
        current = {
            "id": "runtime-context-row",
            "workspace_key": "feezie-os",
            "snapshot_type": "feezie_runtime_context",
            "payload": bundle,
            "updated_at": GENERATED_AT,
        }
        with patch.object(
            brain_routes,
            "upsert_snapshot_monotonic",
            return_value=(current, False),
        ):
            response = brain_routes.publish_brain_workspace_snapshots(request)

        runtime_ack = response["snapshots"]["feezie_runtime_context"]
        self.assertFalse(runtime_ack["stored"])
        self.assertEqual(runtime_ack["disposition"], "idempotent_same_hash")
        self.assertEqual(runtime_ack["payload_sha256"], bundle["payload_sha256"])

    def test_runtime_sync_reports_the_hash_of_a_retained_different_current_row(self) -> None:
        bundle = _build_bundle()
        newer_generated_at = (
            datetime.fromisoformat(GENERATED_AT.replace("Z", "+00:00"))
            + timedelta(seconds=1)
        ).isoformat().replace("+00:00", "Z")
        newer = _build_bundle(generated_at=newer_generated_at)
        request = BrainWorkspaceSnapshotSyncRequest(
            generated_at=GENERATED_AT,
            feezie_runtime_context=bundle,
        )
        current = {
            "id": "newer-runtime-context-row",
            "workspace_key": "feezie-os",
            "snapshot_type": "feezie_runtime_context",
            "payload": newer,
            "updated_at": newer_generated_at,
        }
        with patch.object(
            brain_routes,
            "upsert_snapshot_monotonic",
            return_value=(current, False),
        ):
            response = brain_routes.publish_brain_workspace_snapshots(request)

        runtime_ack = response["snapshots"]["feezie_runtime_context"]
        self.assertFalse(runtime_ack["stored"])
        self.assertEqual(runtime_ack["disposition"], "retained_newer")
        self.assertEqual(runtime_ack["payload_sha256"], newer["payload_sha256"])
        self.assertNotEqual(runtime_ack["payload_sha256"], bundle["payload_sha256"])

    def test_runtime_sync_recovers_only_its_invalid_far_future_persisted_row(self) -> None:
        bundle = _build_bundle()
        poisoned_generated_at = (
            datetime.now(timezone.utc) + timedelta(days=30)
        ).isoformat(timespec="microseconds").replace("+00:00", "Z")
        poisoned = _build_bundle(generated_at=poisoned_generated_at)
        request = BrainWorkspaceSnapshotSyncRequest(
            generated_at=GENERATED_AT,
            feezie_runtime_context=bundle,
        )
        existing = {
            "id": "poisoned-runtime-row",
            "workspace_key": "feezie-os",
            "snapshot_type": "feezie_runtime_context",
            "payload": poisoned,
            "updated_at": GENERATED_AT,
        }
        recovered = {
            **existing,
            "id": "recovered-runtime-row",
            "payload": bundle,
        }
        with (
            patch.object(
                brain_routes,
                "upsert_snapshot_monotonic",
                return_value=(existing, False),
            ),
            patch.object(
                brain_routes,
                "upsert_snapshot",
                return_value=recovered,
            ) as exact_upsert,
        ):
            response = brain_routes.publish_brain_workspace_snapshots(request)

        runtime_ack = response["snapshots"]["feezie_runtime_context"]
        self.assertTrue(runtime_ack["stored"])
        self.assertEqual(runtime_ack["disposition"], "recovered_invalid_runtime")
        self.assertEqual(runtime_ack["payload_sha256"], bundle["payload_sha256"])
        self.assertEqual(
            exact_upsert.call_args.args[:3],
            ("feezie-os", "feezie_runtime_context", bundle),
        )


if __name__ == "__main__":
    unittest.main()
