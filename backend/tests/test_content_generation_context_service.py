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
    def test_linkedin_post_uses_public_safe_claims_and_story_beats(self) -> None:
        core_chunk = {
            "chunk": "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
            "metadata": {
                "bundle_path": "identity/claims.md",
                "memory_role": "core",
                "domain_tags": ["ai_systems", "operator_workflows", "identity_core"],
                "audience_tags": ["tech_ai"],
                "proof_strength": "none",
                "artifact_backed": False,
                "claim_type": "positioning",
            },
        }
        story_chunk = {
            "chunk": "Quiet Inefficiency Cleanup. Johnnie is especially strong in environments that are not fully chaotic but quietly inefficient, where duplicated work, scattered data, and low-trust reporting have been accepted as normal until he maps the system and removes the friction Story type: operator cleanup, systems friction, reporting redesign Use when: Use when talking about broken systems, reporting, workflow friction, or why normalized inefficiency is still failure",
            "metadata": {
                "bundle_path": "history/story_bank.md",
                "memory_role": "story",
                "domain_tags": ["ai_systems", "operator_workflows", "identity_core"],
                "audience_tags": ["tech_ai"],
                "proof_strength": "medium",
                "artifact_backed": False,
                "claim_type": "story",
            },
        }

        with (
            patch("app.services.content_generation_context_service.embed_text", return_value=[0.1, 0.2]),
            patch("app.services.content_generation_context_service.load_bundle_persona_chunks", return_value=[core_chunk, story_chunk]),
            patch("app.services.content_generation_context_service.retrieve_bundle_persona_chunks", return_value=[core_chunk, story_chunk]),
            patch("app.services.content_generation_context_service.retrieve_legacy_support_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_curated_example_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_bundle_example_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_content_reservoir_chunks", return_value=[]),
        ):
            context = build_content_generation_context(
                user_id="johnnie_fields",
                topic="agent orchestration",
                context="Use the operator systems angle.",
                content_type="linkedin_post",
                category="value",
                tone="expert_direct",
                audience="tech_ai",
                source_mode="persona_only",
                include_audit=True,
            )

        self.assertTrue(context.raw_primary_claims)
        self.assertIn("Johnnie treats prompting plus agent orchestration", context.raw_primary_claims[0])
        self.assertEqual(
            context.primary_claims[0],
            "AI helps when the workflow is coordinated, not improvised.",
        )
        self.assertEqual(context.public_safe_primary_claims[0]["transform_rule"], "generalize")
        self.assertIn("third_person_persona", context.public_safe_primary_claims[0]["policy_notes"])
        self.assertTrue(context.raw_story_beats)
        self.assertIn("Quiet Inefficiency Cleanup", context.raw_story_beats[0])
        self.assertEqual(
            context.story_beats[0],
            "The real problem is usually quiet inefficiency, not obvious chaos.",
        )
        self.assertEqual(context.public_safe_story_beats[0]["transform_rule"], "generalize")
        self.assertIn("label_only_story", context.public_safe_story_beats[0]["policy_notes"])
        self.assertNotIn("Johnnie treats", context.persona_context_summary or "")
        self.assertIn("raw_primary_claims", context.audit["selection"])
        self.assertIn("public_safe_primary_claims", context.audit["selection"])
        self.assertIn("raw_story_beats", context.audit["selection"])
        self.assertIn("public_safe_story_beats", context.audit["selection"])

    def test_linkedin_post_uses_public_safe_proof_packets_and_preserves_raw_packets(self) -> None:
        core_chunk = {
            "chunk": "Workflow clarity beats prompting alone.",
            "metadata": {
                "bundle_path": "identity/claims.md",
                "memory_role": "core",
                "domain_tags": ["ai_systems", "operator_workflows", "identity_core"],
                "audience_tags": ["tech_ai"],
                "proof_strength": "none",
                "artifact_backed": False,
                "claim_type": "positioning",
            },
        }
        proof_chunk = {
            "chunk": "AI Clone / Brain System -> Brain, Ops, daily briefs, planner, and long-form routing now read from the same routed workspace state instead of isolated views.",
            "persona_tag": "VENTURES",
            "metadata": {
                "source_kind": "content_reservoir",
                "source_lane": "content_reservoir",
                "source": "asset-1",
                "file_name": "asset-1",
                "memory_role": "proof",
                "domain_tags": ["ai_systems", "operator_workflows"],
                "audience_tags": ["tech_ai"],
                "proof_strength": "strong",
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
            patch("app.services.content_generation_context_service.retrieve_content_safe_operator_lesson_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_content_reservoir_chunks", return_value=[proof_chunk]),
        ):
            context = build_content_generation_context(
                user_id="johnnie_fields",
                topic="workflow clarity",
                context="Use the operator systems angle.",
                content_type="linkedin_post",
                category="value",
                tone="expert_direct",
                audience="tech_ai",
                source_mode="selected_source",
                include_audit=True,
            )

        self.assertTrue(context.raw_proof_packets)
        self.assertIn("AI Clone / Brain System", context.raw_proof_packets[0])
        self.assertTrue(context.proof_packets)
        self.assertNotIn("daily briefs", context.proof_packets[0].lower())
        self.assertNotIn("planner", context.proof_packets[0].lower())
        self.assertEqual(context.public_safe_proof_packets[0]["approval_status"], "auto")
        self.assertEqual(context.public_safe_proof_packets[0]["transform_rule"], "generalize")
        self.assertEqual(context.content_release_policy["raw_context_access"], "blocked")
        self.assertIn("raw_proof_packets", context.audit["selection"])
        self.assertIn("public_safe_proof_packets", context.audit["selection"])
        self.assertIn("content_release_policy", context.audit["selection"])

    def test_non_public_content_type_keeps_raw_proof_packets(self) -> None:
        core_chunk = {
            "chunk": "Workflow clarity beats prompting alone.",
            "metadata": {
                "bundle_path": "identity/claims.md",
                "memory_role": "core",
                "domain_tags": ["ai_systems", "operator_workflows", "identity_core"],
                "audience_tags": ["tech_ai"],
                "proof_strength": "none",
                "artifact_backed": False,
                "claim_type": "positioning",
            },
        }
        proof_chunk = {
            "chunk": "Fusion Academy Dashboard Transformation -> Daily, weekly, monthly, quarterly, and yearly metrics were unified in one Salesforce dashboard.",
            "persona_tag": "VENTURES",
            "metadata": {
                "source_kind": "content_reservoir",
                "source_lane": "content_reservoir",
                "source": "asset-1",
                "file_name": "asset-1",
                "memory_role": "proof",
                "domain_tags": ["ai_systems", "operator_workflows"],
                "audience_tags": ["tech_ai"],
                "proof_strength": "strong",
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
            patch("app.services.content_generation_context_service.retrieve_content_reservoir_chunks", return_value=[proof_chunk]),
        ):
            context = build_content_generation_context(
                user_id="johnnie_fields",
                topic="workflow clarity",
                context="Use the operator systems angle.",
                content_type="internal_memo",
                category="value",
                tone="expert_direct",
                audience="tech_ai",
                source_mode="selected_source",
            )

        self.assertEqual(context.content_release_policy["surface"], "internal")
        self.assertEqual(context.primary_claims, context.raw_primary_claims)
        self.assertEqual(context.proof_packets, context.raw_proof_packets)
        self.assertEqual(context.story_beats, context.raw_story_beats)
        self.assertEqual(context.public_safe_proof_packets[0]["visibility"], "internal")

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

    def test_selected_source_mode_prefers_content_safe_operator_lessons_for_linkedin_posts(self) -> None:
        core_chunk = {
            "chunk": "Workflow clarity is what keeps AI adoption honest.",
            "metadata": {
                "bundle_path": "identity/claims.md",
                "memory_role": "core",
                "domain_tags": ["ai_systems", "operator_workflows", "identity_core"],
                "audience_tags": ["tech_ai"],
                "proof_strength": "medium",
                "artifact_backed": False,
                "claim_type": "positioning",
            },
        }
        safe_chunk = {
            "chunk": "Workflow clarity becomes trustworthy when operators and AI read from the same reviewed system. Public-facing proof: Recent system work turned fragmented review into one shared operating layer. Use when: Show how AI adoption gets stronger when human review stays visible.",
            "persona_tag": "PUBLIC_PROOF",
            "metadata": {
                "source_kind": "content_safe_operator_lessons",
                "source_lane": "content_safe_operator_lessons",
                "source": "content-safe-lesson-1",
                "file_name": "memory/reports/content_safe_operator_lessons_latest.json",
                "memory_role": "proof",
                "domain_tags": ["ai_systems", "operator_workflows", "content_strategy"],
                "audience_tags": ["tech_ai", "entrepreneurs"],
                "proof_strength": "medium",
                "artifact_backed": True,
                "claim_type": "operational",
            },
        }
        reservoir_chunk = {
            "chunk": "This fallback reservoir chunk should not be used.",
            "persona_tag": "PHILOSOPHY",
            "metadata": {
                "memory_role": "proof",
                "domain_tags": ["ai_systems", "operator_workflows"],
                "audience_tags": ["tech_ai"],
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
            patch("app.services.content_generation_context_service.retrieve_content_safe_operator_lesson_chunks", return_value=[safe_chunk]),
            patch("app.services.content_generation_context_service.retrieve_content_reservoir_chunks", return_value=[reservoir_chunk]) as reservoir_mock,
        ):
            context = build_content_generation_context(
                user_id="johnnie_fields",
                topic="ai adoption",
                context="Use a public-safe operator lesson.",
                content_type="linkedin_post",
                category="value",
                tone="expert_direct",
                audience="tech_ai",
                source_mode="selected_source",
                include_audit=True,
            )

        self.assertEqual(len(context.content_reservoir_chunks), 1)
        self.assertEqual(context.content_signal_source, "content_safe_operator_lessons")
        self.assertEqual(context.content_signal_chunks, context.content_reservoir_chunks)
        self.assertEqual(
            (context.content_reservoir_chunks[0].get("metadata") or {}).get("source_kind"),
            "content_safe_operator_lessons",
        )
        self.assertIn(
            "Workflow clarity becomes trustworthy when operators and AI read from the same reviewed system.",
            context.raw_primary_claims,
        )
        self.assertTrue(any("shared operating layer" in packet.lower() for packet in context.proof_packets))
        self.assertEqual(context.audit["retrieval"]["content_signal_source"], "content_safe_operator_lessons")
        self.assertEqual(
            context.audit["retrieval"]["content_signal_candidates"]["count"],
            1,
        )
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
            patch("app.services.content_generation_context_service.retrieve_content_safe_operator_lesson_chunks", return_value=[]),
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
        self.assertEqual(context.content_signal_source, "content_reservoir")
        self.assertIn("student journey is leaking trust", context.content_reservoir_chunks[0]["chunk"])
        self.assertTrue(
            any(
                (item.get("metadata") or {}).get("source_lane") == "retrieval_support"
                for item in context.persona_chunks
            )
        )
        self.assertTrue(
            any("student journey is leaking trust" in claim.lower() for claim in context.primary_claims)
        )
        reservoir_mock.assert_called_once_with(
            topic="family trust in admissions",
            audience="education_admissions",
            category="value",
            top_k=8,
            strategy="ranked",
            allow_runtime_rebuild=True,
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
            patch("app.services.content_generation_context_service.retrieve_content_safe_operator_lesson_chunks", return_value=[]),
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
        self.assertEqual(context.content_signal_source, "content_reservoir")
        self.assertIn("AI systems fail when the human review layer disappears.", context.content_reservoir_chunks[0]["chunk"])
        self.assertTrue(
            any(
                (item.get("metadata") or {}).get("source_lane") == "retrieval_support"
                for item in context.persona_chunks
            )
        )
        self.assertTrue(
            any("human review layer disappears" in claim.lower() for claim in context.primary_claims)
        )
        reservoir_mock.assert_called_once_with(
            topic="agent orchestration",
            audience="tech_ai",
            category="value",
            top_k=8,
            strategy="recent",
            allow_runtime_rebuild=True,
        )

    def test_recent_signals_mode_does_not_promote_voice_fragments_to_primary_claims(self) -> None:
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
        proof_chunk = {
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
        voice_chunk = {
            "chunk": "Reusable Phrases: operator clarity. Use when: you need Johnnie-like phrasing.",
            "persona_tag": "VOICE_PATTERNS",
            "metadata": {
                "memory_role": "ambient",
                "domain_tags": ["ai_systems", "operator_workflows"],
                "audience_tags": ["tech_ai", "entrepreneurs"],
                "proof_strength": "weak",
                "artifact_backed": True,
                "claim_type": "voice",
            },
        }

        with (
            patch("app.services.content_generation_context_service.embed_text", return_value=[0.1, 0.2]),
            patch("app.services.content_generation_context_service.load_bundle_persona_chunks", return_value=[core_chunk]),
            patch("app.services.content_generation_context_service.retrieve_bundle_persona_chunks", return_value=[core_chunk]),
            patch("app.services.content_generation_context_service.retrieve_legacy_support_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_curated_example_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_bundle_example_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_content_safe_operator_lesson_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_content_reservoir_chunks", return_value=[proof_chunk, voice_chunk]),
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

        self.assertTrue(any("human review layer disappears" in claim.lower() for claim in context.primary_claims))
        self.assertFalse(any("reusable phrases" in claim.lower() for claim in context.primary_claims))

    def test_selected_source_mode_restores_source_backed_proof_when_domain_gate_is_too_strict(self) -> None:
        core_chunk = {
            "chunk": "If the workflow is unclear, AI just scales confusion.",
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
        retrieval_chunk = {
            "chunk": "Clarity failures compound when review rules stay implicit. Use when: you need a source-backed lesson.",
            "persona_tag": "PHILOSOPHY",
            "metadata": {
                "memory_role": "proof",
                "domain_tags": [],
                "audience_tags": [],
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
            patch("app.services.content_generation_context_service.retrieve_content_safe_operator_lesson_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_content_reservoir_chunks", return_value=[retrieval_chunk]),
        ):
            context = build_content_generation_context(
                user_id="johnnie_fields",
                topic="workflow clarity",
                context="Use the operator systems angle.",
                content_type="linkedin_post",
                category="value",
                tone="expert_direct",
                audience="tech_ai",
                source_mode="selected_source",
            )

        self.assertTrue(
            any(
                (item.get("metadata") or {}).get("source_lane") == "retrieval_support"
                for item in context.persona_chunks
            )
        )
        self.assertTrue(any("clarity failures compound" in claim.lower() for claim in context.primary_claims))

    def test_selected_source_mode_relabels_reservoir_candidates_as_retrieval_support(self) -> None:
        core_chunk = {
            "chunk": "If the workflow is unclear, AI just scales confusion.",
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
        retrieval_chunk = {
            "chunk": "Operator review breaks down when the system hides the next decision. Use when: you need a source-backed lesson.",
            "persona_tag": "PHILOSOPHY",
            "metadata": {
                "source_lane": "content_reservoir",
                "memory_role": "proof",
                "domain_tags": ["ai_systems", "operator_workflows"],
                "audience_tags": ["tech_ai"],
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
            patch("app.services.content_generation_context_service.retrieve_content_safe_operator_lesson_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_content_reservoir_chunks", return_value=[retrieval_chunk]),
        ):
            context = build_content_generation_context(
                user_id="johnnie_fields",
                topic="workflow clarity",
                context="Use the operator systems angle.",
                content_type="linkedin_post",
                category="value",
                tone="expert_direct",
                audience="tech_ai",
                source_mode="selected_source",
                include_audit=True,
            )

        curated = ((context.audit or {}).get("retrieval") or {}).get("curated_persona_chunks") or {}
        self.assertEqual((curated.get("counts_by_source_lane") or {}).get("retrieval_support"), 1)
        restored_chunk = next(
            item for item in context.persona_chunks if (item.get("metadata") or {}).get("source_lane") == "retrieval_support"
        )
        self.assertEqual((restored_chunk.get("metadata") or {}).get("origin_source_lane"), "content_reservoir")

    def test_selected_source_mode_generalizes_partial_source_fragments_for_public_claims_and_proofs(self) -> None:
        core_chunk = {
            "chunk": "Workflow clarity beats prompting alone.",
            "metadata": {
                "bundle_path": "identity/claims.md",
                "memory_role": "core",
                "domain_tags": ["ai_systems", "operator_workflows", "identity_core"],
                "audience_tags": ["tech_ai"],
                "proof_strength": "none",
                "artifact_backed": False,
                "claim_type": "positioning",
            },
        }
        proof_chunk_one = {
            "chunk": "And his approach to AI, use it to enhance workflows, but never at the expense of customer trust. Use when: you need a durable source-backed claim that may later deserve canon.",
            "persona_tag": "PHILOSOPHY",
            "metadata": {
                "memory_role": "proof",
                "domain_tags": ["ai_systems", "operator_workflows"],
                "audience_tags": ["tech_ai", "entrepreneurs"],
                "proof_strength": "strong",
                "artifact_backed": True,
                "claim_type": "support",
            },
        }
        proof_chunk_two = {
            "chunk": "From surviving the. com crash to managing a gradual desktop to cloud transition, AJ emphasized discipline, systems thinking, and earning customer trust over decades, not just quarters. Use when: you need a durable source-backed claim that may later deserve canon.",
            "persona_tag": "PHILOSOPHY",
            "metadata": {
                "memory_role": "proof",
                "domain_tags": ["ai_systems", "operator_workflows"],
                "audience_tags": ["tech_ai", "entrepreneurs"],
                "proof_strength": "strong",
                "artifact_backed": True,
                "claim_type": "support",
            },
        }

        with (
            patch("app.services.content_generation_context_service.embed_text", return_value=[0.1, 0.2]),
            patch("app.services.content_generation_context_service.load_bundle_persona_chunks", return_value=[core_chunk]),
            patch("app.services.content_generation_context_service.retrieve_bundle_persona_chunks", return_value=[core_chunk]),
            patch("app.services.content_generation_context_service.retrieve_legacy_support_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_curated_example_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_bundle_example_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_content_safe_operator_lesson_chunks", return_value=[]),
            patch(
                "app.services.content_generation_context_service.retrieve_content_reservoir_chunks",
                return_value=[proof_chunk_one, proof_chunk_two],
            ),
        ):
            context = build_content_generation_context(
                user_id="johnnie_fields",
                topic="workflow clarity",
                context="Use the operator systems angle.",
                content_type="linkedin_post",
                category="value",
                tone="expert_direct",
                audience="tech_ai",
                source_mode="selected_source",
            )

        self.assertIn(
            "AI should strengthen workflows without coming at the expense of customer trust.",
            context.primary_claims,
        )
        self.assertIn(
            "Discipline and customer trust matter more than chasing every technology cycle.",
            [item["public_claim"] for item in context.public_safe_primary_claims],
        )
        self.assertIn(
            "AI should strengthen workflows without coming at the expense of customer trust.",
            context.proof_packets,
        )
        self.assertIn(
            "Discipline and customer trust matter more than chasing every technology cycle.",
            context.proof_packets,
        )
        self.assertFalse(any(claim.lower().startswith("and his ") for claim in context.primary_claims))
        self.assertFalse(any("com crash" in claim.lower() for claim in context.primary_claims))

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
            patch("app.services.content_generation_context_service.retrieve_content_safe_operator_lesson_chunks", return_value=[]),
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
            allow_runtime_rebuild=True,
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

        with (
            patch(
                "app.services.content_generation_context_service._load_content_reservoir_payload",
                return_value=content_reservoir_payload,
            ),
            patch(
                "app.services.content_generation_context_service._load_source_assets_payload",
                return_value=source_assets_payload,
            ),
        ):
            chunks = retrieve_content_reservoir_chunks(
                topic="operator review",
                audience="tech_ai",
                category="value",
                top_k=2,
                strategy="recent",
            )

        self.assertEqual([item.get("source_file_id") for item in chunks], ["asset-new", "asset-old"])

    def test_instructional_guardrails_do_not_become_primary_claims(self) -> None:
        operator_chunk = {
            "chunk": "Workflow clarity is not a prompt problem. It is a system design problem.",
            "persona_tag": "CLAIMS",
            "metadata": {
                "bundle_path": "identity/claims.md",
                "source_kind": "canonical_bundle",
                "source_lane": "canonical_bundle",
                "source": "canonical persona bundle",
                "file_name": "identity/claims.md",
                "memory_role": "core",
                "domain_tags": ["ai_systems", "operator_workflows", "identity_core"],
                "audience_tags": ["tech_ai"],
                "proof_strength": "none",
                "artifact_backed": False,
                "claim_type": "positioning",
                "usage_modes": ["always_on", "topic_anchor"],
            },
        }
        guardrail_chunk = {
            "chunk": "Avoid flat consultant openers like workflow clarity is essential, the real value lies, or here's the takeaway.",
            "persona_tag": "PHILOSOPHY",
            "metadata": {
                "bundle_path": "prompts/content_guardrails.md",
                "source_kind": "canonical_bundle",
                "source_lane": "canonical_bundle",
                "source": "canonical persona bundle",
                "file_name": "prompts/content_guardrails.md",
                "memory_role": "core",
                "domain_tags": ["ai_systems", "operator_workflows", "identity_core"],
                "audience_tags": ["tech_ai"],
                "proof_strength": "none",
                "artifact_backed": False,
                "claim_type": "guidance",
                "usage_modes": ["always_on", "topic_anchor"],
            },
        }

        with (
            patch("app.services.content_generation_context_service.embed_text", return_value=[0.1, 0.2]),
            patch(
                "app.services.content_generation_context_service.load_bundle_persona_chunks",
                return_value=[operator_chunk, guardrail_chunk],
            ),
            patch(
                "app.services.content_generation_context_service.retrieve_bundle_persona_chunks",
                return_value=[operator_chunk, guardrail_chunk],
            ),
            patch("app.services.content_generation_context_service.retrieve_legacy_support_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_curated_example_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_bundle_example_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_content_reservoir_chunks", return_value=[]),
        ):
            context = build_content_generation_context(
                user_id="johnnie_fields",
                topic="workflow clarity",
                context="Use the operator systems angle.",
                content_type="linkedin_post",
                category="value",
                tone="expert_direct",
                audience="tech_ai",
                source_mode="persona_only",
            )

        self.assertIn("Workflow clarity is not a prompt problem.", context.primary_claims[0])
        self.assertFalse(any(claim.lower().startswith("avoid ") for claim in context.primary_claims))

    def test_build_context_can_emit_audit_payload(self) -> None:
        core_chunk = {
            "chunk": "Workflow clarity beats prompting alone.",
            "persona_tag": "CLAIMS",
            "metadata": {
                "bundle_path": "identity/claims.md",
                "source_kind": "canonical_bundle",
                "source_lane": "canonical_bundle",
                "source": "canonical persona bundle",
                "file_name": "identity/claims.md",
                "memory_role": "core",
                "domain_tags": ["ai_systems", "operator_workflows", "identity_core"],
                "audience_tags": ["tech_ai", "entrepreneurs"],
                "proof_strength": "none",
                "artifact_backed": False,
                "claim_type": "positioning",
                "usage_modes": ["always_on", "topic_anchor"],
            },
        }
        proof_chunk = {
            "chunk": "Brain, Ops, and planner now run on one routed workspace snapshot.",
            "persona_tag": "VENTURES",
            "source_id": "reservoir:1",
            "source_file_id": "asset-1",
            "captured_at": "2026-04-04T10:00:00Z",
            "similarity_score": 0.91,
            "weighted_score": 1.12,
            "metadata": {
                "source_kind": "content_reservoir",
                "source_lane": "content_reservoir",
                "source": "asset-1",
                "file_name": "asset-1",
                "memory_role": "proof",
                "domain_tags": ["ai_systems", "operator_workflows"],
                "audience_tags": ["tech_ai"],
                "proof_strength": "strong",
                "artifact_backed": True,
                "claim_type": "operational",
                "usage_modes": ["proof_anchor", "topic_anchor"],
                "content_reservoir_lane": "proof_point",
                "content_reservoir_reason": "Source-backed proof point.",
            },
        }

        with (
            patch("app.services.content_generation_context_service.embed_text", return_value=[0.1, 0.2]),
            patch("app.services.content_generation_context_service.load_bundle_persona_chunks", return_value=[core_chunk]),
            patch("app.services.content_generation_context_service.retrieve_bundle_persona_chunks", return_value=[core_chunk]),
            patch("app.services.content_generation_context_service.retrieve_legacy_support_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_curated_example_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_bundle_example_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_content_safe_operator_lesson_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_content_reservoir_chunks", return_value=[proof_chunk]),
            patch("app.services.content_generation_context_service._snapshot_store_configured", return_value=True),
            patch(
                "app.services.content_generation_context_service._runtime_source_assets_snapshot_summary",
                return_value={
                    "available": True,
                    "status": "available",
                    "generated_at": "2026-04-05T00:00:00Z",
                    "item_count": 1,
                    "counts": {"total": 1},
                },
            ),
            patch(
                "app.services.content_generation_context_service._runtime_content_reservoir_snapshot_summary",
                return_value={
                    "available": True,
                    "status": "available",
                    "generated_at": "2026-04-05T00:00:00Z",
                    "item_count": 1,
                    "counts": {"total": 1},
                },
            ),
            patch(
                "app.services.content_generation_context_service.get_snapshot_payload",
                side_effect=lambda workspace_key, snapshot_type: {
                    "generated_at": "2026-04-05T00:00:00Z",
                    "items": [{"asset_id": "asset-1"}] if snapshot_type == "source_assets" else [proof_chunk],
                    "counts": {"total": 1},
                },
            ),
        ):
            context = build_content_generation_context(
                user_id="johnnie_fields",
                topic="workflow clarity",
                context="Use the operator systems angle.",
                content_type="linkedin_post",
                category="value",
                tone="expert_direct",
                audience="tech_ai",
                source_mode="selected_source",
                include_audit=True,
            )

        self.assertEqual(context.audit["request"]["source_mode"], "selected_source")
        self.assertEqual(context.audit["snapshot_inputs"]["content_reservoir"]["item_count"], 1)
        self.assertEqual(context.audit["snapshot_inputs"]["content_reservoir"]["status"], "available")
        self.assertEqual(context.audit["runtime_snapshot_inputs"]["source_assets"]["status"], "available")
        self.assertEqual(context.audit["runtime_snapshot_inputs"]["content_reservoir"]["status"], "available")
        self.assertEqual(context.audit["retrieval"]["bundle_candidates"]["count"], 1)
        self.assertEqual(context.audit["retrieval"]["content_reservoir_candidates"]["count"], 1)
        self.assertEqual(
            context.audit["retrieval"]["content_reservoir_candidates"]["items"][0]["content_reservoir_lane"],
            "proof_point",
        )
        self.assertTrue(context.audit["selection"]["primary_claims"])

    def test_audit_reports_missing_legacy_and_snapshot_inputs(self) -> None:
        core_chunk = {
            "chunk": "Workflow clarity beats prompting alone.",
            "persona_tag": "CLAIMS",
            "metadata": {
                "bundle_path": "identity/claims.md",
                "memory_role": "core",
                "domain_tags": ["ai_systems", "operator_workflows", "identity_core"],
                "audience_tags": ["tech_ai"],
                "proof_strength": "none",
                "artifact_backed": False,
                "claim_type": "positioning",
            },
        }

        with (
            patch("app.services.content_generation_context_service.embed_text", return_value=[0.1, 0.2]),
            patch("app.services.content_generation_context_service.load_bundle_persona_chunks", return_value=[core_chunk]),
            patch("app.services.content_generation_context_service.retrieve_bundle_persona_chunks", return_value=[core_chunk]),
            patch("app.services.content_generation_context_service.retrieve_legacy_support_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_curated_example_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_bundle_example_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.retrieve_content_reservoir_chunks", return_value=[]),
            patch("app.services.content_generation_context_service.get_firestore_client", return_value=None),
            patch("app.services.content_generation_context_service._snapshot_store_configured", return_value=False),
            patch(
                "app.services.content_generation_context_service._runtime_source_assets_snapshot_summary",
                return_value={
                    "available": True,
                    "status": "available",
                    "generated_at": "2026-04-05T00:00:00Z",
                    "item_count": 38,
                    "counts": {"total": 38},
                },
            ),
            patch(
                "app.services.content_generation_context_service._runtime_content_reservoir_snapshot_summary",
                return_value={
                    "available": True,
                    "status": "available",
                    "generated_at": "2026-04-05T00:00:00Z",
                    "item_count": 171,
                    "counts": {"total": 171},
                },
            ),
            patch("app.services.content_generation_context_service.get_snapshot_payload", return_value=None),
        ):
            context = build_content_generation_context(
                user_id="johnnie_fields",
                topic="workflow clarity",
                context="Use the operator systems angle.",
                content_type="linkedin_post",
                category="value",
                tone="expert_direct",
                audience="tech_ai",
                source_mode="persona_only",
                include_audit=True,
            )

        self.assertFalse(context.audit["environment"]["snapshot_store_configured"])
        self.assertEqual(context.audit["environment"]["legacy_embedding_store_status"], "firestore_unavailable")
        self.assertEqual(context.audit["snapshot_inputs"]["source_assets"]["status"], "missing_persisted_snapshot")
        self.assertEqual(context.audit["snapshot_inputs"]["content_reservoir"]["status"], "missing_persisted_snapshot")
        self.assertEqual(context.audit["runtime_snapshot_inputs"]["source_assets"]["item_count"], 38)
        self.assertEqual(context.audit["runtime_snapshot_inputs"]["content_reservoir"]["item_count"], 171)
        self.assertIn("Legacy Firestore retrieval is unavailable in this runtime.", context.audit["warnings"])
        self.assertIn("Open Brain snapshot store is not configured in this runtime.", context.audit["warnings"])


if __name__ == "__main__":
    unittest.main()
