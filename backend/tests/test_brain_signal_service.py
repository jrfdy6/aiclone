from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models import BrainSignal, BrainSignalCreateRequest, BrainSignalReviewRequest, BrainSignalRouteRequest, PMCard, PersonaDelta  # noqa: E402
from app.services import brain_signal_service  # noqa: E402


class BrainSignalServiceTests(unittest.TestCase):
    def test_default_write_seeds_legacy_history_without_mutating_project_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_root = root / "project"
            state_root = root / "private-state"
            legacy_path = project_root / "memory" / "brain_signals.jsonl"
            legacy_path.parent.mkdir(parents=True)
            legacy = BrainSignal(
                id="legacy-signal",
                source_kind="manual",
                source_ref="legacy-source",
                source_workspace_key="future-workspace",
                raw_summary="Preserve this complete legacy signal history.",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            legacy_text = legacy.model_dump_json() + "\n"
            legacy_path.write_text(legacy_text, encoding="utf-8")

            with (
                patch.object(brain_signal_service, "ROOT", project_root),
                patch.object(brain_signal_service, "STATE_ROOT", state_root),
                patch.object(brain_signal_service, "SIGNALS_PATH", None),
            ):
                created = brain_signal_service.create_signal(
                    BrainSignalCreateRequest(
                        source_kind="manual",
                        source_ref="new-source",
                        source_workspace_key="future-workspace",
                        raw_summary="Write this only to private generated state.",
                    )
                )
                snapshot = brain_signal_service.build_local_brain_signal_snapshot()

            private_path = state_root / "memory" / "brain_signals.jsonl"
            self.assertTrue(private_path.exists())
            self.assertEqual(snapshot["count"], 2)
            self.assertIn(created.id, {item["id"] for item in snapshot["signals"]})
            self.assertEqual(legacy_path.read_text(encoding="utf-8"), legacy_text)
            self.assertFalse((project_root / "memory" / "brain_signals.jsonl.lock").exists())

    def test_default_read_uses_legacy_history_without_implicitly_copying_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_root = root / "project"
            state_root = root / "private-state"
            legacy_path = project_root / "memory" / "runtime" / "brain_signals.jsonl"
            legacy_path.parent.mkdir(parents=True)
            legacy = BrainSignal(
                id="runtime-legacy-signal",
                source_kind="manual",
                source_ref="runtime-legacy-source",
                raw_summary="Legacy runtime history remains readable before migration.",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            legacy_path.write_text(legacy.model_dump_json() + "\n", encoding="utf-8")

            with (
                patch.object(brain_signal_service, "ROOT", project_root),
                patch.object(brain_signal_service, "STATE_ROOT", state_root),
                patch.object(brain_signal_service, "SIGNALS_PATH", None),
                patch.object(brain_signal_service, "_load_persisted_signals", return_value=None),
            ):
                signals = brain_signal_service.list_signals()

            self.assertEqual([item.id for item in signals], ["runtime-legacy-signal"])
            self.assertFalse((state_root / "memory" / "brain_signals.jsonl").exists())

    def test_signal_create_retries_by_action_card_even_without_source_ref(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            signals_path = Path(temp_dir) / "brain_signals.jsonl"
            request = BrainSignalCreateRequest(source_kind="manual", raw_summary="Create this signal once.")
            with patch.object(brain_signal_service, "SIGNALS_PATH", signals_path):
                first = brain_signal_service.create_signal(request, action_card_id="create-card")
                second = brain_signal_service.create_signal(request, action_card_id="create-card")
                snapshot = brain_signal_service.build_local_brain_signal_snapshot()

        self.assertEqual(first.id, second.id)
        self.assertEqual(snapshot["count"], 1)
        self.assertEqual(first.route_decision["brain_local_action_create_card_id"], "create-card")

    def test_canonical_route_validation_requires_allowlisted_targets_only(self) -> None:
        with self.assertRaises(ValidationError):
            BrainSignalRouteRequest(route="canonical_memory", summary="Promote this.")
        with self.assertRaises(ValidationError):
            BrainSignalRouteRequest(
                route="workspace_local",
                summary="Keep this local.",
                canonical_memory_targets=["learnings"],
            )

    def test_persona_route_effect_is_idempotent_and_recorded_in_history(self) -> None:
        now = datetime.now(timezone.utc)
        signal = BrainSignal(
            id="persona-signal",
            source_kind="manual",
            source_ref="source-1",
            raw_summary="This may represent a durable part of the worldview.",
            created_at=now,
            updated_at=now,
        )
        route = BrainSignalRouteRequest(
            route="persona_canon",
            summary="Candidate belief: interfaces shape how systems become usable.",
        )
        created_delta = PersonaDelta(
            id="persona-delta",
            persona_target="feeze.core",
            trait=route.summary or "",
            status="draft",
            metadata={"brain_local_action_card_id": "persona-card"},
            created_at=now,
        )
        with (
            patch.object(brain_signal_service.persona_delta_service, "list_deltas", return_value=[]),
            patch.object(brain_signal_service.persona_delta_service, "create_delta", return_value=created_delta) as create,
        ):
            effect = brain_signal_service.build_signal_route_effect(signal, route, action_card_id="persona-card")

        self.assertFalse(effect["reused"])
        create_payload = create.call_args.args[0]
        self.assertEqual(create_payload.metadata["brain_local_action_card_id"], "persona-card")
        self.assertTrue(create_payload.metadata["talking_points"])

        with patch.object(brain_signal_service.persona_delta_service, "list_deltas", return_value=[created_delta]):
            reused = brain_signal_service.build_signal_route_effect(signal, route, action_card_id="persona-card")
        self.assertTrue(reused["reused"])

        with tempfile.TemporaryDirectory() as temp_dir:
            signals_path = Path(temp_dir) / "brain_signals.jsonl"
            with patch.object(brain_signal_service, "SIGNALS_PATH", signals_path):
                local = brain_signal_service.create_signal(
                    BrainSignalCreateRequest(source_kind="manual", source_ref="persona-source", raw_summary=signal.raw_summary)
                )
                routed = brain_signal_service.route_signal(
                    local.id,
                    route,
                    route_effect=effect,
                    action_card_id="persona-card",
                )

        self.assertIsNotNone(routed)
        latest = routed.route_decision["latest"]
        self.assertEqual(latest["brain_local_action_card_id"], "persona-card")
        self.assertEqual(latest["persona_delta"]["id"], "persona-delta")

    def test_list_signals_with_count_reads_snapshot_once(self) -> None:
        now = datetime.now(timezone.utc)
        signals = []
        for index in range(3):
            signals.append(
                brain_signal_service.BrainSignal(
                    id=f"signal-{index}",
                    source_kind="test",
                    source_ref=f"ref-{index}",
                    source_workspace_key="shared_ops",
                    raw_summary=f"Signal {index}",
                    workspace_candidates=["shared_ops"],
                    review_status="new",
                    created_at=now,
                    updated_at=now.replace(microsecond=index),
                )
            )

        with patch.object(brain_signal_service, "_filtered_signals", return_value=signals) as load:
            preview, count = brain_signal_service.list_signals_with_count(limit=2)

        load.assert_called_once_with(review_status=None, workspace_key=None)
        self.assertEqual(count, 3)
        self.assertEqual([signal.id for signal in preview], ["signal-2", "signal-1"])

    def test_shared_read_falls_back_when_sibling_lock_file_is_not_writable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            signals_path = Path(temp_dir) / "brain_signals.jsonl"
            signal = BrainSignal(
                id="read-only-signal",
                source_kind="test",
                source_ref="read-only-ref",
                raw_summary="A deployed snapshot remains readable without a writable sibling lock.",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            signals_path.write_text(signal.model_dump_json() + "\n", encoding="utf-8")
            original_open = Path.open

            def deny_lock_open(path: Path, *args, **kwargs):
                if path.name.endswith(".lock"):
                    raise PermissionError(13, "lock file is read-only", str(path))
                return original_open(path, *args, **kwargs)

            with (
                patch.object(brain_signal_service, "SIGNALS_PATH", signals_path),
                patch.object(brain_signal_service, "get_snapshot_payload", return_value=None),
                patch.object(Path, "open", new=deny_lock_open),
            ):
                signals = brain_signal_service.list_signals()

        self.assertEqual([item.id for item in signals], ["read-only-signal"])

    def test_exclusive_write_fails_closed_when_lock_file_is_not_writable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            signals_path = Path(temp_dir) / "brain_signals.jsonl"
            original_open = Path.open

            def deny_lock_open(path: Path, *args, **kwargs):
                if path.name.endswith(".lock"):
                    raise PermissionError(13, "lock file is read-only", str(path))
                return original_open(path, *args, **kwargs)

            with (
                patch.object(brain_signal_service, "SIGNALS_PATH", signals_path),
                patch.object(Path, "open", new=deny_lock_open),
                self.assertRaises(PermissionError),
            ):
                brain_signal_service.create_signal(
                    BrainSignalCreateRequest(
                        source_kind="test",
                        source_ref="write-ref",
                        raw_summary="This write must not bypass the exclusive lock.",
                    )
                )

            self.assertFalse(signals_path.exists())

    def test_create_dedupes_by_source_signature_and_reviews_signal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            signals_path = Path(temp_dir) / "brain_signals.jsonl"
            with patch.object(brain_signal_service, "SIGNALS_PATH", signals_path):
                first = brain_signal_service.create_signal(
                    BrainSignalCreateRequest(
                        source_kind="source_intelligence",
                        source_ref="video-123",
                        source_workspace_key="linkedin-os",
                        raw_summary="AI systems need clearer routing.",
                        signal_types=["source", "strategy"],
                        workspace_candidates=["fusion-os"],
                    )
                )
                second = brain_signal_service.create_signal(
                    BrainSignalCreateRequest(
                        source_kind="source_intelligence",
                        source_ref="video-123",
                        source_workspace_key="linkedin-os",
                        raw_summary="AI systems need clearer routing and PM boundaries.",
                        signal_types=["pm"],
                    )
                )

                self.assertEqual(first.id, second.id)
                self.assertEqual(second.source_workspace_key, "feezie-os")
                self.assertIn("fusion-os", second.workspace_candidates)
                self.assertIn("pm", second.signal_types)

                reviewed = brain_signal_service.review_signal(
                    second.id,
                    BrainSignalReviewRequest(
                        digest="Route this through executive review before PM.",
                        review_status="reviewed",
                        executive_interpretation={
                            "yoda_meaning": "Protect direction.",
                            "neo_system_impact": "This affects routing standards.",
                            "jean_claude_operational_translation": "Tighten PM gates.",
                        },
                    ),
                )

                self.assertIsNotNone(reviewed)
                self.assertEqual(reviewed.review_status, "reviewed")
                self.assertEqual(reviewed.digest, "Route this through executive review before PM.")
                self.assertEqual(len(brain_signal_service.list_signals()), 1)

    def test_legacy_linkedin_route_metadata_normalizes_for_brain_signal_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            signals_path = Path(temp_dir) / "brain_signals.jsonl"
            now = datetime.now(timezone.utc).isoformat()
            legacy_signal = {
                "id": "legacy-signal",
                "source_kind": "source_intelligence",
                "source_ref": "legacy-route",
                "source_workspace_key": "linkedin-os",
                "raw_summary": "Legacy route metadata should not leak the old workspace key.",
                "digest": "Legacy route metadata should normalize at the Brain boundary.",
                "signal_types": ["source_intelligence"],
                "durability": "durable",
                "confidence": "high",
                "actionability": "medium",
                "identity_relevance": "medium",
                "workspace_candidates": ["shared_ops", "linkedin-os"],
                "executive_interpretation": {},
                "route_decision": {
                    "workspace_routing": {
                        "recommendation": {
                            "workspace_keys": ["shared_ops", "linkedin-os"],
                            "suggestion_details": [
                                {
                                    "workspace_key": "linkedin-os",
                                    "label": "LinkedIn OS",
                                    "contract_excerpt": (
                                        "Run the public-facing operating system for Feeze's visibility, "
                                        "starting with LinkedIn and expanding over time into a broader "
                                        "personal-brand and career-positioning lane."
                                    ),
                                    "reasons": [
                                        "FEEZIE OS stays in the loop by default.",
                                        "The persona target is explicitly aligned to Feeze / LinkedIn.",
                                    ],
                                }
                            ],
                        },
                        "workspace_keys": ["shared_ops", "linkedin-os"],
                    },
                    "source_paths": ["workspaces/linkedin-content-os/drafts/example.md"],
                },
                "review_status": "new",
                "created_at": now,
                "updated_at": now,
            }
            signals_path.write_text(json.dumps(legacy_signal) + "\n", encoding="utf-8")

            with patch.object(brain_signal_service, "SIGNALS_PATH", signals_path):
                [signal] = brain_signal_service.list_signals()

            serialized = json.dumps(signal.model_dump(mode="json"), sort_keys=True)
            self.assertEqual(signal.source_workspace_key, "feezie-os")
            self.assertEqual(signal.workspace_candidates, ["shared_ops", "feezie-os"])
            self.assertNotIn('"linkedin-os"', serialized)
            self.assertNotIn("LinkedIn OS", serialized)
            self.assertNotIn("Feeze / LinkedIn", serialized)
            self.assertIn("workspaces/linkedin-content-os/drafts/example.md", serialized)
            recommendation = signal.route_decision["workspace_routing"]["recommendation"]
            self.assertEqual(recommendation["workspace_keys"], ["shared_ops", "feezie-os"])
            self.assertEqual(recommendation["suggestion_details"][0]["workspace_key"], "feezie-os")
            self.assertEqual(recommendation["suggestion_details"][0]["label"], "FEEZIE OS")

    def test_route_signal_to_pm_uses_guardrail_and_records_route_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            signals_path = Path(temp_dir) / "brain_signals.jsonl"
            now = datetime.now(timezone.utc)
            created_cards: list[object] = []

            def _fake_create_card(payload):
                created_cards.append(payload)
                return PMCard(
                    id="pm-signal-1",
                    title=payload.title,
                    owner=payload.owner,
                    status=payload.status,
                    source=payload.source,
                    link_type=payload.link_type,
                    link_id=payload.link_id,
                    payload=payload.payload,
                    created_at=now,
                    updated_at=now,
                )

            with (
                patch.object(brain_signal_service, "SIGNALS_PATH", signals_path),
                patch.object(brain_signal_service.pm_card_service, "find_card_by_signature", return_value=None),
                patch.object(brain_signal_service.pm_card_service, "find_active_card_by_title", return_value=None),
                patch.object(brain_signal_service.pm_card_service, "create_card", side_effect=_fake_create_card),
            ):
                signal = brain_signal_service.create_signal(
                    BrainSignalCreateRequest(
                        source_kind="cron",
                        source_ref="cron-123",
                        source_workspace_key="shared_ops",
                        raw_summary="Automation output found a bounded workspace issue.",
                    )
                )
                routed = brain_signal_service.route_signal(
                    signal.id,
                    BrainSignalRouteRequest(
                        route="pm",
                        workspace_key="shared_ops",
                        summary="Automation output found a bounded workspace issue that needs a concrete fix.",
                        route_reason="The signal is actionable and has a clear PM boundary.",
                        pm_title="Resolve automation workspace issue",
                        executive_interpretation={
                            "neo_system_impact": "This affects the workspace operating loop.",
                        },
                    ),
                )

            self.assertIsNotNone(routed)
            self.assertEqual(routed.review_status, "routed")
            self.assertEqual(len(created_cards), 1)
            self.assertEqual(created_cards[0].link_type, "brain_signal")
            self.assertTrue(created_cards[0].payload.get("route_guardrail", {}).get("ok"))
            self.assertTrue(created_cards[0].payload.get("writeback_requirements", {}).get("require_writeback"))
            latest = routed.route_decision.get("latest") or {}
            self.assertEqual(latest.get("route"), "pm")
            self.assertEqual(latest.get("pm_card", {}).get("id"), "pm-signal-1")
            self.assertEqual(len(routed.route_decision.get("history") or []), 1)

    def test_route_signal_rejects_duplicate_pm_card(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            signals_path = Path(temp_dir) / "brain_signals.jsonl"
            now = datetime.now(timezone.utc)
            existing = PMCard(
                id="pm-existing",
                title="Resolve automation workspace issue",
                owner="Jean-Claude",
                status="todo",
                source="brain-signal:sig:shared_ops",
                link_type="brain_signal",
                link_id="sig",
                payload={"workspace_key": "shared_ops"},
                created_at=now,
                updated_at=now,
            )

            with (
                patch.object(brain_signal_service, "SIGNALS_PATH", signals_path),
                patch.object(brain_signal_service.pm_card_service, "find_card_by_signature", return_value=existing),
                patch.object(brain_signal_service.pm_card_service, "find_active_card_by_title", return_value=None),
                patch.object(brain_signal_service.pm_card_service, "create_card") as create_mock,
            ):
                signal = brain_signal_service.create_signal(
                    BrainSignalCreateRequest(
                        source_kind="cron",
                        source_ref="cron-duplicate",
                        raw_summary="Automation output found a bounded workspace issue.",
                    )
                )
                with self.assertRaises(ValueError) as context:
                    brain_signal_service.route_signal(
                        signal.id,
                        BrainSignalRouteRequest(
                            route="pm",
                            workspace_key="shared_ops",
                            summary="Automation output found a bounded workspace issue that needs a concrete fix.",
                            route_reason="The signal is actionable and has a clear PM boundary.",
                            pm_title="Resolve automation workspace issue",
                        ),
                    )

            create_mock.assert_not_called()
            self.assertIn("duplicate", str(context.exception).lower())


if __name__ == "__main__":
    unittest.main()
