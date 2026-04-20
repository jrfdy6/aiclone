from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models import BrainSignalCreateRequest, BrainSignalReviewRequest, BrainSignalRouteRequest, PMCard  # noqa: E402
from app.services import brain_signal_service  # noqa: E402


class BrainSignalServiceTests(unittest.TestCase):
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
