from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.content_generation_context_service import build_content_generation_context


class ContentGenerationContextSourceModeTests(unittest.TestCase):
    def test_persona_only_mode_skips_recent_weighted_retrieval(self) -> None:
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
            patch("app.services.content_generation_context_service.retrieve_weighted", return_value=[]) as weighted_mock,
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
        weighted_mock.assert_not_called()

    def test_selected_source_mode_allows_recent_weighted_retrieval(self) -> None:
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
            patch("app.services.content_generation_context_service.retrieve_weighted", return_value=[]) as weighted_mock,
        ):
            build_content_generation_context(
                user_id="johnnie_fields",
                topic="family trust in admissions",
                context="Use the selected school article as the anchor.",
                content_type="linkedin_post",
                category="value",
                tone="expert_direct",
                audience="education_admissions",
                source_mode="selected_source",
            )

        weighted_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
