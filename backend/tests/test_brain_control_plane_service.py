from __future__ import annotations

import sys
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import brain_control_plane_service  # noqa: E402


class BrainControlPlaneServiceTests(unittest.TestCase):
    def test_build_brain_control_plane_uses_live_workspace_snapshot(self) -> None:
        workspace_snapshot = {
            "doc_entries": [{"path": "docs/example.md"}],
            "workspace_files": [{"path": "knowledge/persona/feeze/identity/claims.md"}],
            "persona_review_summary": {"counts": {"brain_pending_review": 3, "workspace_saved": 2}},
            "source_assets": {"counts": {"total": 9}},
        }
        brain_memory_sync = {"queued_route_count": 4}
        health = SimpleNamespace(model_dump=lambda: {"database_connected": True, "search_ready": True})

        with patch.object(brain_control_plane_service, "list_automations", return_value=[SimpleNamespace(status="active")]) as list_mock, patch.object(
            brain_control_plane_service.open_brain_metrics,
            "fetch_metrics",
            return_value={"captures": {"total": 11}, "vectors": {}, "recent_captures": []},
        ), patch.object(
            brain_control_plane_service.open_brain_service,
            "fetch_health",
            return_value=health,
        ), patch.object(
            brain_control_plane_service.workspace_snapshot_service,
            "get_linkedin_os_snapshot",
            return_value=workspace_snapshot,
        ) as snapshot_mock, patch.object(
            brain_control_plane_service,
            "get_snapshot_payload",
            return_value=brain_memory_sync,
        ):
            payload = brain_control_plane_service.build_brain_control_plane()

        list_mock.assert_called_once_with()
        snapshot_mock.assert_called_once_with(
            persisted_only=True,
            include_workspace_files=False,
            include_doc_entries=False,
        )
        self.assertEqual((payload.get("summary") or {}).get("pending_review_count"), 3)
        self.assertEqual((payload.get("summary") or {}).get("workspace_saved_count"), 2)
        self.assertEqual((payload.get("summary") or {}).get("doc_count"), 1)
        self.assertEqual((payload.get("summary") or {}).get("workspace_file_count"), 1)
        self.assertEqual((payload.get("summary") or {}).get("brain_memory_sync_queue_count"), 4)
        self.assertEqual((payload.get("workspace_snapshot") or {}).get("doc_entries"), workspace_snapshot["doc_entries"])

    def test_build_brain_control_plane_returns_portfolio_signal_and_source_summary(self) -> None:
        workspace_snapshot = {
            "doc_entries": [],
            "workspace_files": [],
            "persona_review_summary": {"counts": {}},
            "source_assets": {"counts": {"total": 0}},
        }
        portfolio_snapshot = {
            "schema_version": "portfolio_workspace_snapshot/v1",
            "counts": {"workspaces": 6, "needs_brain_attention": 2, "active_pm_cards": 4, "standup_blockers": 1},
            "workspaces": [
                {
                    "workspace_key": "fusion-os",
                    "display_name": "Fusion OS",
                    "needs_brain_attention": True,
                    "counts": {"active_pm_cards": 1, "attention_pm_cards": 1, "standup_blockers": 1},
                }
            ],
        }
        brain_signal = SimpleNamespace(
            model_dump=lambda mode="json": {
                "id": "signal-1",
                "source_kind": "cron",
                "raw_summary": "Cron output needs routing.",
                "review_status": "new",
                "route_decision": {},
            }
        )
        source_index = {
            "schema_version": "source_intelligence_index/v1",
            "generated_at": "2026-04-19T12:00:00Z",
            "counts": {"total": 91, "digested": 78, "reviewed": 4, "routed": 9, "promoted": 0, "ignored": 0},
            "recent_sources": [{"source_id": "source-1", "title": "Recent source", "status": "routed"}],
        }

        with patch.object(brain_control_plane_service, "list_automations", return_value=[]), patch.object(
            brain_control_plane_service.open_brain_metrics,
            "fetch_metrics",
            return_value={"captures": {"total": 0}, "vectors": {}, "recent_captures": []},
        ), patch.object(
            brain_control_plane_service.open_brain_service,
            "fetch_health",
            return_value=SimpleNamespace(model_dump=lambda: {"database_connected": False, "search_ready": False}),
        ), patch.object(
            brain_control_plane_service.workspace_snapshot_service,
            "get_linkedin_os_snapshot",
            return_value=workspace_snapshot,
        ), patch.object(
            brain_control_plane_service,
            "get_snapshot_payload",
            return_value={"queued_route_count": 0},
        ), patch.object(
            brain_control_plane_service,
            "build_portfolio_workspace_snapshot",
            return_value=portfolio_snapshot,
        ), patch.object(
            brain_control_plane_service,
            "list_signals",
            return_value=[brain_signal],
        ), patch.object(
            brain_control_plane_service,
            "_load_source_intelligence_index",
            return_value=source_index,
        ):
            payload = brain_control_plane_service.build_brain_control_plane()

        self.assertEqual((payload.get("portfolio_snapshot") or {}).get("counts", {}).get("workspaces"), 6)
        self.assertEqual((payload.get("summary") or {}).get("portfolio_workspace_count"), 6)
        self.assertEqual((payload.get("summary") or {}).get("portfolio_attention_count"), 2)
        self.assertEqual((payload.get("summary") or {}).get("brain_signal_count"), 1)
        self.assertEqual((payload.get("brain_signals") or [{}])[0].get("id"), "signal-1")
        self.assertEqual((payload.get("summary") or {}).get("source_intelligence_total"), 91)
        self.assertEqual((payload.get("summary") or {}).get("source_intelligence_routed"), 9)
        self.assertEqual((payload.get("source_intelligence_index") or {}).get("recent_sources", [{}])[0].get("source_id"), "source-1")

    def test_source_intelligence_index_loader_uses_fallback_candidates(self) -> None:
        with TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "knowledge" / "source-intelligence" / "index.json.txt"
            index_path.parent.mkdir(parents=True)
            index_path.write_text(
                """
                {
                  "schema_version": "source_intelligence_index/v1",
                  "generated_at": "2026-04-19T12:00:00Z",
                  "counts": {"total": 2, "routed": 1},
                  "sources": [
                    {
                      "source_id": "source-1",
                      "title": "Fallback source",
                      "status": "routed",
                      "raw_path": "knowledge/source-intelligence/raw/source-1.md"
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )
            missing_path = Path(temp_dir) / "missing" / "index.json"

            with patch.object(
                brain_control_plane_service,
                "_source_intelligence_index_candidates",
                return_value=[missing_path, index_path],
            ):
                payload = brain_control_plane_service._load_source_intelligence_index()

        self.assertEqual((payload or {}).get("schema_version"), "source_intelligence_index/v1")
        self.assertEqual((payload or {}).get("source_ref"), str(index_path))
        self.assertEqual(((payload or {}).get("counts") or {}).get("total"), 2)
        self.assertEqual(((payload or {}).get("recent_sources") or [{}])[0].get("source_id"), "source-1")

    def test_compact_workspace_snapshot_keeps_brain_preview_fields_only(self) -> None:
        snapshot = {
            "source_assets": {
                "workspace": "linkedin-content-os",
                "generated_at": "2026-04-19T12:00:00+00:00",
                "counts": {"total": 14, "pending_segmentation": 2},
                "items": [
                    {
                        "asset_id": f"asset-{index}",
                        "title": f"Asset {index}",
                        "source_channel": "youtube",
                        "source_type": "video",
                        "source_path": f"knowledge/ingestions/{index}.md",
                        "structured_summary": "large source detail",
                    }
                    for index in range(14)
                ],
            },
            "social_feed": {
                "workspace": "linkedin-content-os",
                "generated_at": "2026-04-19T12:00:00+00:00",
                "strategy_mode": "operator",
                "items": [
                    {
                        "id": f"feed-{index}",
                        "title": f"Feed {index}",
                        "author": "Author",
                        "summary": "short summary",
                        "standout_lines": ["one", "two", "three", "four"],
                        "evaluation": {"overall": 8.5, "expression": "large hidden block"},
                        "ranking": {"total": 91.0, "breakdown": {"extra": 1}},
                        "lens_variants": {"full": "large render variants"},
                    }
                    for index in range(8)
                ],
            },
            "content_reservoir": {
                "workspace": "linkedin-content-os",
                "generated_at": "2026-04-19T12:00:00+00:00",
                "counts": {"total": 409},
                "items": [{"text": "large reusable content chunk"} for _ in range(20)],
            },
            "long_form_routes": {
                "assets_considered": 14,
                "segments_total": 50,
                "route_counts": {"persona_candidate": 8},
                "primary_route_counts": {"content_reservoir": 5},
                "candidates": [{"summary": "large route candidate"}],
            },
        }

        compacted = brain_control_plane_service._compact_workspace_snapshot(snapshot)

        source_assets = compacted["source_assets"]
        self.assertEqual(len(source_assets["items"]), brain_control_plane_service.SOURCE_ASSET_PREVIEW_LIMIT)
        self.assertNotIn("structured_summary", source_assets["items"][0])
        social_feed = compacted["social_feed"]
        self.assertEqual(len(social_feed["items"]), brain_control_plane_service.SOCIAL_FEED_PREVIEW_LIMIT)
        self.assertEqual(social_feed["items"][0]["standout_lines"], ["one", "two", "three"])
        self.assertNotIn("lens_variants", social_feed["items"][0])
        self.assertNotIn("items", compacted["content_reservoir"])
        self.assertNotIn("candidates", compacted["long_form_routes"])


if __name__ == "__main__":
    unittest.main()
