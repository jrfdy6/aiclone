from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = WORKSPACE_ROOT / "scripts"
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

SPEC = importlib.util.spec_from_file_location("brain_automation_context", SCRIPTS_ROOT / "brain_automation_context.py")
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

from app.models import BrainSignal  # noqa: E402
from app.services import brain_signal_service, portfolio_workspace_snapshot_service  # noqa: E402


class BrainAutomationContextTests(unittest.TestCase):
    def test_build_context_compacts_signals_portfolio_and_source_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_index = Path(temp_dir) / "index.json"
            source_index.write_text(
                json.dumps(
                    {
                        "schema_version": "source_intelligence_index/v1",
                        "generated_at": "2026-04-19T12:00:00Z",
                        "counts": {"total": 2, "digested": 1, "reviewed": 1, "routed": 1},
                        "sources": [
                            {"source_id": "old", "title": "Old source", "status": "digested"},
                            {"source_id": "new", "title": "New source", "status": "routed", "source_url": "https://example.test"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            signal = BrainSignal(
                id="signal-1",
                source_kind="cron",
                source_ref="cron-1",
                source_workspace_key="shared_ops",
                raw_summary="Automation found a workspace issue that needs routing.",
                signal_types=["automation"],
                workspace_candidates=["fusion-os"],
                route_decision={"latest": {"route": "standup", "workspace_key": "fusion-os"}},
                review_status="routed",
                created_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
                updated_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
            )
            snapshot = {
                "generated_at": "2026-04-19T12:00:00Z",
                "schema_version": "portfolio_workspace_snapshot/v1",
                "counts": {"workspaces": 1, "needs_brain_attention": 1},
                "workspaces": [
                    {
                        "workspace_key": "fusion-os",
                        "display_name": "Fusion OS",
                        "status": "active",
                        "description": "Fusion operating state.",
                        "needs_brain_attention": True,
                        "latest_standups": [{"blockers": ["Needs owner review."]}],
                        "active_pm_cards": [{"id": "pm-1", "title": "Resolve Fusion blocker", "status": "blocked"}],
                        "counts": {"active_pm_cards": 1, "attention_pm_cards": 1, "standup_blockers": 1},
                        "source_paths": ["/tmp/fusion.md"],
                    }
                ],
            }

            with patch.object(MODULE, "SOURCE_INDEX_PATH", source_index), patch.object(
                brain_signal_service,
                "SIGNALS_PATH",
                Path(temp_dir) / "brain_signals.jsonl",
            ), patch.object(brain_signal_service, "list_signals", return_value=[signal]), patch.object(
                portfolio_workspace_snapshot_service,
                "build_portfolio_workspace_snapshot",
                return_value=snapshot,
            ):
                context = MODULE.build_brain_automation_context(signal_limit=3)

        self.assertTrue(context["available"])
        self.assertEqual(context["brain_signals"][0]["id"], "signal-1")
        self.assertEqual(context["portfolio_snapshot"]["workspaces"][0]["workspace_key"], "fusion-os")
        self.assertEqual(context["source_intelligence"]["counts"]["total"], 2)
        self.assertIn("/tmp/fusion.md", context["source_paths"])
        self.assertTrue(MODULE.brain_signal_lines(context))
        self.assertTrue(MODULE.portfolio_attention_lines(context))
        self.assertTrue(MODULE.workspace_brain_signal_lines(context, "fusion-os"))
        self.assertTrue(MODULE.source_intelligence_lines(context))


if __name__ == "__main__":
    unittest.main()
