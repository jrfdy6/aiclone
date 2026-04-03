from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.content_generation_context_service import (
    build_content_generation_context,
    retrieve_content_reservoir_chunks,
)


class ContentGenerationContextSourceModeTests(unittest.TestCase):
    def test_persona_only_mode_skips_reservoir_retrieval(self) -> None:
        core_chunk = {
            "chunk": "Admissions is not just enrollment. It is translation.",
            "metadata": {
                "bundle_path": "identity/claims.md",
                "memory_role": "core",
                "domain_tags": ["education_admissions", "identity_core"],
                "audience_tags": ["education_admissions"],
                "proof_strength": "medium",
                "artifact_backed": False,
                "claim_type": "mission",
            },
        }

        with (
            patch("app.services.content_generation_context_service.embed_text", return_value=[0.1, 0.2]),
            patch("app.services.content_generation_context_service.load_bundle_persona_chunks", return_value=[core_chunk]),
            patch("app.services.content_generation_context_service.retrieve_bundle_persona_chunks", return_value=[core_chunk]),
            patch("app.services.content_generation_context_service.retrieve_legacy_support_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_curated_example_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_bundle_example_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_content_reservoir_chunks", return_value=[]) as reservoir_mock,
        ):
            context = build_content_generation_context(
                user_id="johnnie_fields",
                topic="education admissions leadership",
                context="A value post about trust and family clarity.",
                content_type="linkedin_post",
                category="value",
                tone="expert_direct",
                audience="education_admissions",
                source_mode="persona_only",
            )

        self.assertTrue(context.primary_claims)
        reservoir_mock.assert_not_called()

    def test_selected_source_mode_uses_ranked_content_reservoir_support(self) -> None:
        core_chunk = {
            "chunk": "Admissions is not just enrollment. It is translation.",
            "metadata": {
                "bundle_path": "identity/claims.md",
                "memory_role": "core",
                "domain_tags": ["education_admissions", "identity_core"],
                "audience_tags": ["education_admissions"],
                "proof_strength": "medium",
                "artifact_backed": False,
                "claim_type": "mission",
            },
        }
        reservoir_chunk = {
            "chunk": "The repeated questions usually tell you where the student journey is leaking trust.",
            "persona_tag": "PHILOSOPHY",
            "captured_at": "2026-04-02T20:00:00Z",
            "metadata": {
                "memory_role": "proof",
                "domain_tags": ["education_admissions"],
                "audience_tags": ["education_admissions"],
                "proof_strength": "medium",
                "artifact_backed": True,
                "claim_type": "operational",
                "captured_at": "2026-04-02T20:00:00Z",
            },
        }

        with (
            patch("app.services.content_generation_context_service.embed_text", return_value=[0.1, 0.2]),
            patch("app.services.content_generation_context_service.load_bundle_persona_chunks", return_value=[core_chunk]),
            patch("app.services.content_generation_context_service.retrieve_bundle_persona_chunks", return_value=[core_chunk]),
            patch("app.services.content_generation_context_service.retrieve_legacy_support_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_curated_example_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_bundle_example_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_content_reservoir_chunks", return_value=[reservoir_chunk]) as reservoir_mock,
        ):
            context = build_content_generation_context(
                user_id="johnnie_fields",
                topic="family trust in admissions",
                context="Use the selected school article as the anchor.",
                content_type="linkedin_post",
                category="value",
                tone="expert_direct",
                audience="education_admissions",
                source_mode="selected_source",
            )

        self.assertEqual(len(context.content_reservoir_chunks), 1)
        self.assertIn("student journey is leaking trust", context.content_reservoir_chunks[0]["chunk"])
        reservoir_mock.assert_called_once_with(
            topic="family trust in admissions",
            audience="education_admissions",
            category="value",
            top_k=8,
            strategy="ranked",
        )

    def test_recent_signals_mode_prefers_content_reservoir_over_weighted_retrieval(self) -> None:
        core_chunk = {
            "chunk": "Workflow clarity matters because operator trust breaks when review disappears.",
            "metadata": {
                "bundle_path": "identity/claims.md",
                "memory_role": "core",
                "domain_tags": ["ai_systems", "operator_workflows", "identity_core"],
                "audience_tags": ["tech_ai", "entrepreneurs"],
                "proof_strength": "medium",
                "artifact_backed": False,
                "claim_type": "mission",
            },
        }
        reservoir_chunk = {
            "chunk": "AI systems fail when the human review layer disappears. Use when: you need a source-backed lesson.",
            "persona_tag": "PHILOSOPHY",
            "metadata": {
                "memory_role": "proof",
                "domain_tags": ["ai_systems", "operator_workflows"],
                "audience_tags": ["tech_ai", "entrepreneurs"],
                "proof_strength": "medium",
                "artifact_backed": True,
                "claim_type": "operational",
            },
        }

        with (
            patch("app.services.content_generation_context_service.embed_text", return_value=[0.1, 0.2]),
            patch("app.services.content_generation_context_service.load_bundle_persona_chunks", return_value=[core_chunk]),
            patch("app.services.content_generation_context_service.retrieve_bundle_persona_chunks", return_value=[core_chunk]),
            patch("app.services.content_generation_context_service.retrieve_legacy_support_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_curated_example_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_bundle_example_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_content_reservoir_chunks", return_value=[reservoir_chunk]) as reservoir_mock,
        ):
            context = build_content_generation_context(
                user_id="johnnie_fields",
                topic="agent orchestration",
                context="Blend recent source material into the post.",
                content_type="linkedin_post",
                category="value",
                tone="expert_direct",
                audience="tech_ai",
                source_mode="recent_signals",
            )

        self.assertEqual(len(context.content_reservoir_chunks), 1)
        self.assertIn("AI systems fail when the human review layer disappears.", context.content_reservoir_chunks[0]["chunk"])
        reservoir_mock.assert_called_once_with(
            topic="agent orchestration",
            audience="tech_ai",
            category="value",
            top_k=8,
            strategy="recent",
        )

    def test_recent_signals_mode_leaves_reservoir_empty_when_recent_slice_is_empty(self) -> None:
        core_chunk = {
            "chunk": "Workflow clarity matters because operator trust breaks when review disappears.",
            "metadata": {
                "bundle_path": "identity/claims.md",
                "memory_role": "core",
                "domain_tags": ["ai_systems", "operator_workflows", "identity_core"],
                "audience_tags": ["tech_ai", "entrepreneurs"],
                "proof_strength": "medium",
                "artifact_backed": False,
                "claim_type": "mission",
            },
        }
        with (
            patch("app.services.content_generation_context_service.embed_text", return_value=[0.1, 0.2]),
            patch("app.services.content_generation_context_service.load_bundle_persona_chunks", return_value=[core_chunk]),
            patch("app.services.content_generation_context_service.retrieve_bundle_persona_chunks", return_value=[core_chunk]),
            patch("app.services.content_generation_context_service.retrieve_legacy_support_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_curated_example_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_bundle_example_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_content_reservoir_chunks", return_value=[]) as reservoir_mock,
        ):
            context = build_content_generation_context(
                user_id="johnnie_fields",
                topic="agent orchestration",
                context="Blend recent source material into the post.",
                content_type="linkedin_post",
                category="value",
                tone="expert_direct",
                audience="tech_ai",
                source_mode="recent_signals",
            )

        self.assertEqual(context.content_reservoir_chunks, [])
        reservoir_mock.assert_called_once_with(
            topic="agent orchestration",
            audience="tech_ai",
            category="value",
            top_k=8,
            strategy="recent",
        )

    def test_recent_reservoir_strategy_prefers_newer_captured_assets(self) -> None:
        content_reservoir_payload = {
            "items": [
                {
                    "asset_id": "asset-old",
                    "text": "Older workflow lesson about operator review.",
                    "chunk": "Older workflow lesson about operator review. Use when: you need a source-backed lesson.",
                    "content_priority": 120,
                    "score": 9,
                    "reservoir_lane": "proof_point",
                    "persona_tag": "PHILOSOPHY",
                    "metadata": {
                        "memory_role": "proof",
                        "domain_tags": ["ai_systems", "operator_workflows"],
                        "audience_tags": ["tech_ai"],
                        "proof_strength": "medium",
                        "artifact_backed": True,
                        "claim_type": "operational",
                    },
                },
                {
                    "asset_id": "asset-new",
                    "text": "Newer workflow lesson about operator review.",
                    "chunk": "Newer workflow lesson about operator review. Use when: you need a source-backed lesson.",
                    "content_priority": 40,
                    "score": 6,
                    "reservoir_lane": "proof_point",
                    "persona_tag": "PHILOSOPHY",
                    "metadata": {
                        "memory_role": "proof",
                        "domain_tags": ["ai_systems", "operator_workflows"],
                        "audience_tags": ["tech_ai"],
                        "proof_strength": "medium",
                        "artifact_backed": True,
                        "claim_type": "operational",
                    },
                },
            ]
        }
        source_assets_payload = {
            "items": [
                {"asset_id": "asset-old", "captured_at": "2026-04-01T10:00:00Z"},
                {"asset_id": "asset-new", "captured_at": "2026-04-03T10:00:00Z"},
            ]
        }

        def snapshot_side_effect(workspace_key: str, snapshot_type: str):
            self.assertEqual(workspace_key, "linkedin-content-os")
            if snapshot_type == "content_reservoir":
                return content_reservoir_payload
            if snapshot_type == "source_assets":
                return source_assets_payload
            return None

        with patch("app.services.content_generation_context_service.get_snapshot_payload", side_effect=snapshot_side_effect):
            chunks = retrieve_content_reservoir_chunks(
                topic="operator review",
                audience="tech_ai",
                category="value",
                top_k=2,
                strategy="recent",
            )

        self.assertEqual([item.get("source_file_id") for item in chunks], ["asset-new", "asset-old"])


if __name__ == "__main__":
    unittest.main()
