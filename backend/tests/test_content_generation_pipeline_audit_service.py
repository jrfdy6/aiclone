from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.content_generation_pipeline_audit_service import build_content_generation_pipeline_audit


def _fake_context(
    claims: list[str],
    *,
    signal_count: int,
    retrieval_support_count: int,
    signal_source: str = "content_reservoir",
) -> SimpleNamespace:
    return SimpleNamespace(
        grounding_mode="proof_ready",
        grounding_reason="ready",
        framing_modes=["operator_lesson"],
        primary_claims=claims,
        proof_packets=["proof"],
        story_beats=[],
        persona_context_summary="summary",
        persona_chunks=[{"chunk": "x"}] * max(1, retrieval_support_count),
        content_signal_chunks=[{"chunk": "x"}] * signal_count,
        content_signal_source=signal_source,
        content_reservoir_chunks=[{"chunk": "x"}] * signal_count,
        audit={
            "retrieval": {
                "content_signal_source": signal_source,
                "curated_persona_chunks": {
                    "count": max(1, retrieval_support_count),
                    "counts_by_source_lane": {
                        "canonical_bundle": 4,
                        **({"retrieval_support": retrieval_support_count} if retrieval_support_count else {}),
                    },
                },
                "content_signal_candidates": {
                    "count": signal_count,
                    "counts_by_memory_role": {"proof": max(0, signal_count - 1), "ambient": 1 if signal_count else 0},
                },
                "content_reservoir_candidates": {
                    "count": signal_count,
                    "counts_by_memory_role": {"proof": max(0, signal_count - 1), "ambient": 1 if signal_count else 0},
                },
                "example_chunks": {"count": 2},
            }
        },
    )


class ContentGenerationPipelineAuditServiceTests(unittest.TestCase):
    def test_audit_flags_snapshot_drift_and_source_mode_collapse(self) -> None:
        persona_only = _fake_context(["claim-a", "claim-b"], signal_count=0, retrieval_support_count=0, signal_source="persona_only")
        selected_source = _fake_context(["claim-a", "claim-b"], signal_count=4, retrieval_support_count=0, signal_source="content_safe_operator_lessons")
        recent_signals = _fake_context(["claim-a", "claim-b"], signal_count=5, retrieval_support_count=0)

        with (
            patch("app.services.content_generation_pipeline_audit_service._load_source_assets_payload", return_value={"items": []}) as load_source_assets_mock,
            patch("app.services.content_generation_pipeline_audit_service._load_content_safe_operator_lessons_payload", return_value={"lessons": []}) as load_safe_lessons_mock,
            patch("app.services.content_generation_pipeline_audit_service._load_content_reservoir_payload", return_value={"items": []}) as load_reservoir_mock,
            patch("app.services.content_generation_pipeline_audit_service.load_bundle_persona_chunks", return_value=[]),
            patch(
                "app.services.content_generation_pipeline_audit_service._source_assets_snapshot_summary",
                return_value={"item_count": 10, "generated_at": "2026-04-01T00:00:00Z"},
            ),
            patch(
                "app.services.content_generation_pipeline_audit_service._runtime_source_assets_snapshot_summary",
                return_value={"item_count": 20, "generated_at": "2026-04-07T00:00:00Z"},
            ),
            patch(
                "app.services.content_generation_pipeline_audit_service._content_safe_operator_lessons_snapshot_summary",
                return_value={"item_count": 3, "generated_at": "2026-04-01T00:00:00Z"},
            ),
            patch(
                "app.services.content_generation_pipeline_audit_service._runtime_content_safe_operator_lessons_snapshot_summary",
                return_value={"item_count": 8, "generated_at": "2026-04-07T00:00:00Z"},
            ),
            patch(
                "app.services.content_generation_pipeline_audit_service._content_reservoir_snapshot_summary",
                return_value={"item_count": 30, "generated_at": "2026-04-01T00:00:00Z"},
            ),
            patch(
                "app.services.content_generation_pipeline_audit_service._runtime_content_reservoir_snapshot_summary",
                return_value={"item_count": 60, "generated_at": "2026-04-07T00:00:00Z"},
            ),
            patch(
                "app.services.content_generation_pipeline_audit_service.build_content_generation_context",
                side_effect=[persona_only, selected_source, recent_signals],
            ),
        ):
            payload = build_content_generation_pipeline_audit(
                user_id="johnnie_fields",
                topic="workflow clarity",
                context="Use the operator systems angle.",
                content_type="linkedin_post",
                category="value",
                tone="expert_direct",
                audience="tech_ai",
            )

        load_source_assets_mock.assert_called_once_with(allow_runtime_rebuild=True)
        load_safe_lessons_mock.assert_called_once_with(allow_runtime_rebuild=True)
        load_reservoir_mock.assert_called_once_with(allow_runtime_rebuild=True)
        issues = payload["issues"]
        summaries = [issue["summary"] for issue in issues]
        self.assertTrue(any("Persisted source assets are lagging runtime inputs." == summary for summary in summaries))
        self.assertTrue(any("Persisted content-safe operator lessons are lagging runtime inputs." == summary for summary in summaries))
        self.assertTrue(any("Persisted content reservoir is lagging runtime inputs." == summary for summary in summaries))
        self.assertTrue(any("selected_source retrieved source-backed support" in summary for summary in summaries))
        self.assertTrue(any("recent_signals retrieved source-backed support" in summary for summary in summaries))
        self.assertTrue(any("selected_source is landing on the same primary claims as persona_only." == summary for summary in summaries))
        self.assertEqual(
            payload["phases"]["source_modes"]["selected_source"]["content_signal_source"],
            "content_safe_operator_lessons",
        )


if __name__ == "__main__":
    unittest.main()
