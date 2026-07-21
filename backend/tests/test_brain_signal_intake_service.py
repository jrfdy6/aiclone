from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import brain_signal_intake_service as service  # noqa: E402
from app.services import brain_signal_service  # noqa: E402


class BrainSignalIntakeServiceTests(unittest.TestCase):
    def test_source_intelligence_intake_dedupes_and_keeps_generic_ai_out_of_project_fanout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            signals_path = temp_root / "brain_signals.jsonl"
            index_path = temp_root / "knowledge" / "source-intelligence" / "index.json"
            index_path.parent.mkdir(parents=True)
            index_path.write_text(
                json.dumps(
                    {
                        "schema_version": "source_intelligence_index/v1",
                        "generated_at": "2026-04-19T12:00:00Z",
                        "counts": {"total": 2, "digested": 1, "routed": 1},
                        "sources": [
                            {
                                "source_id": "generic-ai",
                                "source_kind": "machine_ingestion",
                                "source_channel": "youtube",
                                "source_type": "transcript",
                                "title": "AI agents are changing how teams operate",
                                "summary": "This AI system affects portfolio workflow and operating rhythm.",
                                "status": "digested",
                                "digest_path": "knowledge/ingestions/generic/shared_source_packet.json",
                            },
                            {
                                "source_id": "fashion-ai",
                                "source_kind": "machine_ingestion",
                                "source_channel": "youtube",
                                "source_type": "transcript",
                                "title": "AI styling systems need better outfit context",
                                "summary": "This is about fashion, wardrobe context, and digital closet recommendation quality.",
                                "status": "routed",
                                "digest_path": "knowledge/ingestions/fashion/shared_source_packet.json",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(brain_signal_service, "SIGNALS_PATH", signals_path), patch.object(
                service,
                "_source_index_candidates",
                return_value=[index_path],
            ):
                first = service.run_brain_signal_intake(
                    include_workspace_attention=False,
                    include_automation_outputs=False,
                )
                second = service.run_brain_signal_intake(
                    include_workspace_attention=False,
                    include_automation_outputs=False,
                )
                signals = brain_signal_service.list_signals(limit=20)

        self.assertEqual(first["buckets"]["source_intelligence"]["created"], 2)
        self.assertEqual(second["buckets"]["source_intelligence"]["created"], 0)
        self.assertEqual(second["buckets"]["source_intelligence"]["updated"], 2)
        self.assertEqual(len(signals), 2)
        by_ref = {signal.source_ref: signal for signal in signals}
        generic_candidates = by_ref["generic-ai"].workspace_candidates
        self.assertIn("shared_ops", generic_candidates)
        self.assertIn("feezie-os", generic_candidates)
        self.assertNotIn("fusion-os", generic_candidates)
        self.assertNotIn("easyoutfitapp", generic_candidates)
        self.assertNotIn("ai-swag-store", generic_candidates)
        self.assertNotIn("agc", generic_candidates)
        fashion_candidates = by_ref["fashion-ai"].workspace_candidates
        self.assertIn("easyoutfitapp", fashion_candidates)
        self.assertNotIn("fusion-os", fashion_candidates)
        self.assertNotIn("agc", fashion_candidates)

    def test_workspace_attention_and_automation_outputs_become_signals(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            signals_path = temp_root / "brain_signals.jsonl"
            report_path = temp_root / "memory" / "reports" / "fallback_watchdog_latest.json"
            report_path.parent.mkdir(parents=True)
            report_path.write_text(
                json.dumps(
                    {
                        "generated_at": "2026-04-19T12:00:00Z",
                        "source": "fallback_watchdog",
                        "status": "warning",
                        "active": True,
                        "active_count": 1,
                        "brain_context": {"errors": ["portfolio unavailable"]},
                    }
                ),
                encoding="utf-8",
            )
            snapshot = {
                "generated_at": "2026-04-19T12:00:00Z",
                "schema_version": "portfolio_workspace_snapshot/v1",
                "workspaces": [
                    {
                        "workspace_key": "fusion-os",
                        "display_name": "Fusion OS",
                        "counts": {"attention_pm_cards": 1, "standup_blockers": 1, "active_pm_cards": 1},
                        "needs_brain_attention": True,
                        "latest_standups": [{"blockers": ["Needs owner review."]}],
                        "active_pm_cards": [{"title": "Validate Fusion proof", "status": "blocked"}],
                        "source_paths": ["workspaces/fusion-os/docs/operating_model.md"],
                    }
                ],
            }

            with patch.object(brain_signal_service, "SIGNALS_PATH", signals_path), patch.object(
                service,
                "build_portfolio_workspace_snapshot",
                return_value=snapshot,
            ), patch.object(
                service,
                "AUTOMATION_REPORT_SPECS",
                (
                    {
                        "automation_id": "fallback_watchdog",
                        "label": "Fallback watchdog",
                        "workspace_key": "shared_ops",
                        "path": report_path,
                    },
                ),
            ):
                result = service.run_brain_signal_intake(include_source_intelligence=False)
                signals = brain_signal_service.list_signals(limit=20)

        self.assertEqual(result["buckets"]["workspace_attention"]["created"], 1)
        self.assertEqual(result["buckets"]["automation_outputs"]["created"], 1)
        by_kind = {signal.source_kind: signal for signal in signals}
        workspace_signal = by_kind["workspace_snapshot"]
        self.assertEqual(workspace_signal.source_workspace_key, "fusion-os")
        self.assertIn("standup_blocker", workspace_signal.signal_types)
        automation_signal = by_kind["automation_output"]
        self.assertIn("automation_error", automation_signal.signal_types)
        self.assertEqual(automation_signal.source_workspace_key, "shared_ops")


if __name__ == "__main__":
    unittest.main()
