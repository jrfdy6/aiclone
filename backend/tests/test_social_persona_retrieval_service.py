from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.social_persona_retrieval_service import SocialPersonaRetrievalService


class SocialPersonaRetrievalServiceTests(unittest.TestCase):
    def test_external_references_are_exposed_but_not_selected_as_persona_truth(self) -> None:
        service = SocialPersonaRetrievalService()
        canonical_claim = {
            "chunk": "People, process, and culture are the main levers of leadership.",
            "source_kind": "canonical_bundle",
            "metadata": {
                "bundle_path": "identity/philosophy.md",
                "memory_role": "core",
                "domain_tags": ["leadership", "education_admissions"],
                "audience_tags": ["leadership"],
                "proof_strength": "none",
                "artifact_backed": False,
            },
        }
        canonical_story = {
            "chunk": (
                "Coffee and Convo. Johnnie creates rooms where dialogue matters, not just promotional moments. "
                "Story type: event leadership. Use when: trust and community."
            ),
            "source_kind": "canonical_bundle",
            "metadata": {
                "bundle_path": "history/story_bank.md",
                "memory_role": "story",
                "domain_tags": ["leadership", "education_admissions", "lived_experience"],
                "audience_tags": ["leadership", "education_admissions"],
                "proof_strength": "medium",
                "artifact_backed": True,
            },
        }
        external_reference = {
            "chunk": "External Belief Packets: Skills are becoming more important than credentials in AI-disrupted work.",
            "source_kind": "external_reference",
            "metadata": {
                "bundle_path": "references/external_reference_packets.md",
                "memory_role": "example",
                "domain_tags": ["education_admissions", "leadership", "content_strategy"],
                "audience_tags": ["leadership", "education_admissions"],
                "proof_strength": "weak",
                "artifact_backed": False,
            },
        }

        signal = {
            "raw_text": "Schools need to help students build durable skills and trust, not just chase credentials.",
        }
        article_understanding = {
            "thesis": "Schools should optimize for skills over prestige signals.",
            "world_context": "AI is shifting work toward judgment and execution.",
            "world_stakes": "Students and families need trust, adaptability, and clearer outcomes.",
            "world_domains": ["education", "leadership"],
            "audience_impacted": ["students", "families"],
        }

        with patch(
            "app.services.social_persona_retrieval_service.load_committed_overlay_chunks",
            return_value=[],
        ), patch(
            "app.services.social_persona_retrieval_service.load_bundle_persona_chunks",
            return_value=[external_reference, canonical_claim, canonical_story],
        ):
            result = service.retrieve(signal, "admissions", article_understanding)

        self.assertEqual(result["selected_belief"].get("source_kind"), "canonical_bundle")
        self.assertEqual(result["selected_experience"].get("source_kind"), "canonical_bundle")
        self.assertTrue(result["external_reference_candidates"])
        self.assertEqual(result["external_reference_candidates"][0].get("source_kind"), "external_reference")

    def test_article_specific_mission_belief_beats_generic_positioning_claim(self) -> None:
        service = SocialPersonaRetrievalService()
        mission_claim = {
            "chunk": (
                "Technology can help close gaps in education access and equity, but only if adoption is real. "
                "Evidence: Johnnie connects AI and education work to trust, access, and actual fit for students and families. "
                "Usage: Use when linking AI, education, adoption, trust, or long-term mission."
            ),
            "source_kind": "canonical_bundle",
            "metadata": {
                "bundle_path": "identity/claims.md",
                "memory_role": "core",
                "domain_tags": ["education_admissions", "leadership"],
                "audience_tags": ["education_admissions"],
                "proof_strength": "none",
                "artifact_backed": False,
                "claim_type": "mission",
            },
        }
        generic_positioning_claim = {
            "chunk": (
                "Johnnie is building at the intersection of education, AI systems, entrepreneurship, and style. "
                "Evidence: Broad positioning across active lanes. "
                "Usage: Use as broad positioning, but avoid flattening every lane into the same level of authority."
            ),
            "source_kind": "canonical_bundle",
            "metadata": {
                "bundle_path": "identity/claims.md",
                "memory_role": "core",
                "domain_tags": ["identity_core", "content_strategy", "education_admissions", "ai_systems"],
                "audience_tags": ["general", "entrepreneurs"],
                "proof_strength": "none",
                "artifact_backed": False,
                "claim_type": "positioning",
            },
        }
        canonical_story = {
            "chunk": (
                "Coffee and Convo. Johnnie creates rooms where dialogue matters, not just promotional moments. "
                "Story type: event leadership. Use when: trust and community."
            ),
            "source_kind": "canonical_bundle",
            "metadata": {
                "bundle_path": "history/story_bank.md",
                "memory_role": "story",
                "domain_tags": ["leadership", "education_admissions", "lived_experience"],
                "audience_tags": ["leadership", "education_admissions"],
                "proof_strength": "medium",
                "artifact_backed": True,
            },
        }
        external_reference = {
            "chunk": (
                "External Belief Packets: Skills, trust, and education relevance matter more than prestige signals alone "
                "when AI is changing work."
            ),
            "source_kind": "external_reference",
            "metadata": {
                "bundle_path": "references/external_reference_packets.md",
                "memory_role": "example",
                "domain_tags": ["education_admissions", "leadership", "content_strategy"],
                "audience_tags": ["education_admissions", "leadership"],
                "proof_strength": "weak",
                "artifact_backed": False,
            },
        }
        signal = {
            "raw_text": "Families need schools to prove relevance, trust, and real outcomes as AI changes the labor market.",
        }
        article_understanding = {
            "thesis": "Education has to prove relevance and trust, not just prestige, in an AI-shifting labor market.",
            "world_context": "Students and families are rethinking cost, skills, and outcomes.",
            "world_stakes": "Schools that cannot translate education into real trust and outcomes will lose families.",
            "world_domains": ["education", "leadership"],
            "audience_impacted": ["students", "families"],
            "article_kind": "analysis",
            "article_stance": "advocate",
        }

        with patch(
            "app.services.social_persona_retrieval_service.load_committed_overlay_chunks",
            return_value=[],
        ), patch(
            "app.services.social_persona_retrieval_service.load_bundle_persona_chunks",
            return_value=[generic_positioning_claim, mission_claim, canonical_story, external_reference],
        ):
            result = service.retrieve(signal, "admissions", article_understanding)

        self.assertIn("education access", (result["selected_belief"].get("text") or "").lower())
        self.assertEqual(result["selected_belief"].get("claim_type"), "mission")
        self.assertGreater(
            float(result["selected_belief"].get("selection_fit_score") or 0.0),
            float((result["belief_candidates"][1] if len(result["belief_candidates"]) > 1 else {}).get("selection_fit_score") or 0.0),
        )

    def test_product_article_prefers_specific_experience_over_generic_ai_clone_anchor(self) -> None:
        service = SocialPersonaRetrievalService()
        belief_claim = {
            "chunk": (
                "Prompting alone is not an AI strategy. Evidence: Johnnie keeps moving work from isolated prompting "
                "into structured workflows, typed retrieval, domain gates, proof packets, and shared state. "
                "Usage: Use as a thesis line when the topic is AI adoption, orchestration, workflow design, or operator maturity."
            ),
            "source_kind": "canonical_bundle",
            "metadata": {
                "bundle_path": "identity/claims.md",
                "memory_role": "core",
                "domain_tags": ["ai_systems", "operator_workflows"],
                "audience_tags": ["tech_ai", "entrepreneurs"],
                "proof_strength": "none",
                "artifact_backed": False,
                "claim_type": "contrarian",
            },
        }
        generic_ai_clone = {
            "chunk": (
                "AI Clone / Brain System. Build a restart-safe AI operating system for memory, persona review, source routing, planning, "
                "and content execution. Value: operator-grade AI system design. Proof: routed workspace snapshot."
            ),
            "source_kind": "canonical_bundle",
            "metadata": {
                "bundle_path": "history/initiatives.md",
                "memory_role": "proof",
                "domain_tags": ["ai_systems", "operator_workflows", "public_proof"],
                "audience_tags": ["tech_ai", "entrepreneurs"],
                "proof_strength": "strong",
                "artifact_backed": True,
            },
        }
        specific_product_story = {
            "chunk": (
                "Cheap Models, Better Systems. Johnnie learned AI by building on weaker and cheaper models first, "
                "which forced better structure, clearer validation, and stronger systems thinking instead of relying on frontier-model magic. "
                "Story type: AI systems, constraint-led building. Use when: AI maturity, system design, validation, context engineering."
            ),
            "source_kind": "canonical_bundle",
            "metadata": {
                "bundle_path": "history/story_bank.md",
                "memory_role": "story",
                "domain_tags": ["ai_systems", "operator_workflows", "lived_experience"],
                "audience_tags": ["tech_ai", "entrepreneurs"],
                "proof_strength": "medium",
                "artifact_backed": True,
            },
        }
        easy_outfit = {
            "chunk": (
                "Easy Outfit Metadata And Validation Layer. Move wardrobe intelligence from loose naming logic to metadata-driven decisions "
                "with explicit validation. Value: product logic, validation, scalable AI systems. Proof: the app stopped producing obviously bad combinations."
            ),
            "source_kind": "canonical_bundle",
            "metadata": {
                "bundle_path": "history/initiatives.md",
                "memory_role": "proof",
                "domain_tags": ["ai_systems", "content_strategy", "public_proof"],
                "audience_tags": ["entrepreneurs", "general"],
                "proof_strength": "strong",
                "artifact_backed": True,
            },
        }
        signal = {
            "raw_text": "Small AI products cannot rely on feature speed alone. Distribution, validation, and operational coherence compound into a moat.",
        }
        article_understanding = {
            "thesis": "Small AI products win through distribution, validation, and operational coherence rather than feature speed alone.",
            "world_context": "The market is shifting from model novelty toward product discipline and customer trust.",
            "world_stakes": "Builders need systems that hold up in real usage, not just demos.",
            "world_domains": ["ai", "entrepreneurship"],
            "audience_impacted": ["builders", "founders"],
            "article_kind": "trend",
            "article_stance": "nuance",
        }

        with patch(
            "app.services.social_persona_retrieval_service.load_committed_overlay_chunks",
            return_value=[],
        ), patch(
            "app.services.social_persona_retrieval_service.load_bundle_persona_chunks",
            return_value=[belief_claim, generic_ai_clone, specific_product_story, easy_outfit],
        ):
            result = service.retrieve(signal, "entrepreneurship", article_understanding)

        self.assertIn(
            result["selected_experience"].get("title"),
            {"Cheap Models, Better Systems", "Easy Outfit Metadata And Validation Layer"},
        )
        self.assertNotEqual(result["selected_experience"].get("title"), "AI Clone / Brain System")

    def test_change_management_article_splits_beliefs_across_lanes(self) -> None:
        service = SocialPersonaRetrievalService()
        workflow_claim = {
            "chunk": "If the workflow is unclear, AI just scales confusion. Evidence: repeated system work focused on handoffs and role clarity. Usage: clarity, adoption, handoffs, change management.",
            "source_kind": "canonical_bundle",
            "metadata": {
                "bundle_path": "identity/claims.md",
                "memory_role": "core",
                "domain_tags": ["ai_systems", "operator_workflows"],
                "audience_tags": ["tech_ai", "leadership"],
                "proof_strength": "none",
                "artifact_backed": False,
                "claim_type": "operational",
            },
        }
        people_adopt_claim = {
            "chunk": "People adopt what makes their life easier, not what leadership tells them to use. Evidence: dashboard and operating-system work improved uptake by making next actions clearer. Usage: adoption, rollout design, change management.",
            "source_kind": "canonical_bundle",
            "metadata": {
                "bundle_path": "identity/claims.md",
                "memory_role": "core",
                "domain_tags": ["leadership", "education_admissions", "operator_workflows"],
                "audience_tags": ["leadership", "education_admissions"],
                "proof_strength": "none",
                "artifact_backed": False,
                "claim_type": "operational",
            },
        }
        leadership_claim = {
            "chunk": "Johnnie values people, process, and culture as the main levers of leadership. Evidence: recurring philosophy across persona docs and operating decisions. Usage: execution, adoption, change management.",
            "source_kind": "canonical_bundle",
            "metadata": {
                "bundle_path": "identity/claims.md",
                "memory_role": "core",
                "domain_tags": ["leadership", "operator_workflows"],
                "audience_tags": ["leadership"],
                "proof_strength": "none",
                "artifact_backed": False,
                "claim_type": "philosophical",
            },
        }
        coherence_claim = {
            "chunk": "Systems become useful by being coherent, not by being endlessly flexible. Evidence: Johnnie tightens systems around constraints, artifacts, validation, and shared state instead of maximizing optionality. Usage: coherent systems, process design, change management.",
            "source_kind": "canonical_bundle",
            "metadata": {
                "bundle_path": "identity/claims.md",
                "memory_role": "core",
                "domain_tags": ["operator_workflows", "content_strategy"],
                "audience_tags": ["entrepreneurs", "leadership"],
                "proof_strength": "none",
                "artifact_backed": False,
                "claim_type": "philosophical",
            },
        }
        story = {
            "chunk": "Best Practices Initiative. The system improved metrics and also improved team participation. Story type: team enablement. Use when: coaching, systems, performance improvement.",
            "source_kind": "canonical_bundle",
            "metadata": {
                "bundle_path": "history/story_bank.md",
                "memory_role": "story",
                "domain_tags": ["leadership", "operator_workflows", "lived_experience"],
                "audience_tags": ["leadership"],
                "proof_strength": "medium",
                "artifact_backed": True,
            },
        }
        signal = {
            "raw_text": "Change fails when leaders announce too early and teams cannot repeat the process for themselves.",
        }
        article_understanding = {
            "thesis": "Change fails when leaders announce before teams can repeat the process.",
            "world_context": "This is a change-management and adoption problem, not just a communication problem.",
            "world_stakes": "Teams disengage when process repetition and adoption lag leadership messaging.",
            "world_domains": ["leadership", "ops"],
            "audience_impacted": ["teams", "leaders"],
            "article_kind": "analysis",
            "article_stance": "warn",
        }

        with patch(
            "app.services.social_persona_retrieval_service.load_committed_overlay_chunks",
            return_value=[],
        ), patch(
            "app.services.social_persona_retrieval_service.load_bundle_persona_chunks",
            return_value=[workflow_claim, people_adopt_claim, leadership_claim, coherence_claim, story],
        ):
            ai_result = service.retrieve(signal, "ai", article_understanding)
            admissions_result = service.retrieve(signal, "admissions", article_understanding)
            leadership_result = service.retrieve(signal, "program-leadership", article_understanding)
            entrepreneurship_result = service.retrieve(signal, "entrepreneurship", article_understanding)

        unique_beliefs = {
            result["selected_belief"].get("title")
            for result in [ai_result, admissions_result, leadership_result, entrepreneurship_result]
            if result["selected_belief"].get("title")
        }
        self.assertIn("workflow is unclear", (ai_result["selected_belief"].get("text") or "").lower())
        self.assertIn("people adopt", (admissions_result["selected_belief"].get("text") or "").lower())
        self.assertIn("coherent", (entrepreneurship_result["selected_belief"].get("text") or "").lower())
        self.assertGreaterEqual(len(unique_beliefs), 3)

    def test_ai_article_can_prefer_constraint_story_over_generic_ai_clone(self) -> None:
        service = SocialPersonaRetrievalService()
        belief_claim = {
            "chunk": (
                "Real AI maturity comes from building useful systems under constraints, not just using the best model money can buy. "
                "Evidence: Johnnie learned on weaker cheaper models and tightened structure, validation, and workflow discipline first. "
                "Usage: contrast operator skill with model hype."
            ),
            "source_kind": "canonical_bundle",
            "metadata": {
                "bundle_path": "identity/claims.md",
                "memory_role": "core",
                "domain_tags": ["ai_systems", "operator_workflows"],
                "audience_tags": ["tech_ai", "entrepreneurs"],
                "proof_strength": "none",
                "artifact_backed": False,
                "claim_type": "contrarian",
            },
        }
        generic_ai_clone = {
            "chunk": (
                "AI Clone / Brain System. Build a restart-safe AI operating system for memory, persona review, source routing, planning, "
                "and content execution. Value: operator-grade AI system design. Proof: routed workspace snapshot."
            ),
            "source_kind": "canonical_bundle",
            "metadata": {
                "bundle_path": "history/initiatives.md",
                "memory_role": "proof",
                "domain_tags": ["ai_systems", "operator_workflows", "public_proof"],
                "audience_tags": ["tech_ai", "entrepreneurs"],
                "proof_strength": "strong",
                "artifact_backed": True,
            },
        }
        constraint_story = {
            "chunk": (
                "AI Constraint Breakthrough. The first real AI breakthrough came when inconsistent outputs stopped looking like a model problem "
                "and started looking like an instruction-layer problem, which pushed Johnnie toward tighter schemas, stronger constraints, "
                "and system design instead of prompt wishfulness. Story type: AI building. Use when: reliability, schema discipline, validation."
            ),
            "source_kind": "canonical_bundle",
            "metadata": {
                "bundle_path": "history/story_bank.md",
                "memory_role": "story",
                "domain_tags": ["ai_systems", "operator_workflows", "lived_experience"],
                "audience_tags": ["tech_ai", "entrepreneurs"],
                "proof_strength": "medium",
                "artifact_backed": True,
            },
        }
        signal = {
            "raw_text": "Teams keep treating model choice like strategy when the real issue is whether outputs can be trusted enough to build on.",
        }
        article_understanding = {
            "thesis": "The real AI bottleneck is not model access but whether teams can trust outputs enough to build reliable systems.",
            "world_context": "AI changes what competence looks like once building depends on evaluation, constraints, and judgment.",
            "world_stakes": "Teams that cannot stabilize outputs cannot really operationalize AI.",
            "world_domains": ["ai", "ops"],
            "audience_impacted": ["teams", "builders"],
            "article_kind": "analysis",
            "article_stance": "warn",
        }

        with patch(
            "app.services.social_persona_retrieval_service.load_committed_overlay_chunks",
            return_value=[],
        ), patch(
            "app.services.social_persona_retrieval_service.load_bundle_persona_chunks",
            return_value=[belief_claim, generic_ai_clone, constraint_story],
        ):
            result = service.retrieve(signal, "ai", article_understanding)

        self.assertIn(
            result["selected_experience"].get("title"),
            {"AI Constraint Breakthrough", "Cheap Models, Better Systems"},
        )
        self.assertNotEqual(result["selected_experience"].get("title"), "AI Clone / Brain System")

    def test_distribution_article_can_surface_easy_outfit_story_over_generic_ai_clone(self) -> None:
        service = SocialPersonaRetrievalService()
        belief_claim = {
            "chunk": (
                "Systems become useful by being coherent, not by being endlessly flexible. "
                "Evidence: Johnnie keeps tightening systems around constraints, artifacts, validation, and shared state instead of maximizing optionality. "
                "Usage: product systems, coherent execution, founder tradeoffs."
            ),
            "source_kind": "canonical_bundle",
            "metadata": {
                "bundle_path": "identity/claims.md",
                "memory_role": "core",
                "domain_tags": ["ai_systems", "operator_workflows", "content_strategy"],
                "audience_tags": ["tech_ai", "entrepreneurs"],
                "proof_strength": "medium",
                "artifact_backed": False,
                "claim_type": "philosophical",
            },
        }
        generic_ai_clone = {
            "chunk": (
                "AI Clone / Brain System. Build a restart-safe AI operating system for memory, persona review, source routing, planning, "
                "and content execution. Value: operator-grade AI system design. Proof: routed workspace snapshot."
            ),
            "source_kind": "canonical_bundle",
            "metadata": {
                "bundle_path": "history/initiatives.md",
                "memory_role": "proof",
                "domain_tags": ["ai_systems", "operator_workflows", "public_proof"],
                "audience_tags": ["tech_ai", "entrepreneurs"],
                "proof_strength": "strong",
                "artifact_backed": True,
            },
        }
        easy_outfit_story = {
            "chunk": (
                "Easy Outfit Build And Adoption Lesson. Johnnie learned AI by building Easy Outfit end to end over six months, "
                "and the deeper lesson was that something can work technically and still not matter enough to change user behavior. "
                "Story type: AI building, product learning, function vs value. Use when: product reality, adoption, repeat behavior."
            ),
            "source_kind": "canonical_bundle",
            "metadata": {
                "bundle_path": "history/story_bank.md",
                "memory_role": "story",
                "domain_tags": ["ai_systems", "content_strategy", "lived_experience"],
                "audience_tags": ["entrepreneurs", "general"],
                "proof_strength": "medium",
                "artifact_backed": True,
            },
        }
        easy_outfit_initiative = {
            "chunk": (
                "Easy Outfit Metadata And Validation Layer. Move wardrobe intelligence from loose naming logic to metadata-driven decisions "
                "with explicit validation. Value: product logic, validation, scalable AI systems."
            ),
            "source_kind": "canonical_bundle",
            "metadata": {
                "bundle_path": "history/initiatives.md",
                "memory_role": "proof",
                "domain_tags": ["ai_systems", "content_strategy", "public_proof"],
                "audience_tags": ["entrepreneurs", "general"],
                "proof_strength": "strong",
                "artifact_backed": True,
            },
        }
        high_score_fillers = []
        for index in range(30):
            high_score_fillers.append(
                {
                    "chunk": (
                        f"Filler Initiative {index}. Builder workflow distribution systems product process market trust "
                        f"to keep the initial ranking crowded ahead of lower-overlap stories."
                    ),
                    "source_kind": "canonical_bundle",
                    "metadata": {
                        "bundle_path": "history/wins.md",
                        "memory_role": "proof",
                        "domain_tags": ["ai_systems", "content_strategy", "public_proof"],
                        "audience_tags": ["entrepreneurs", "tech_ai"],
                        "proof_strength": "strong",
                        "artifact_backed": True,
                    },
                }
            )
        signal = {
            "raw_text": (
                "Small AI products can ship features quickly now, which means feature speed alone stops being the moat. "
                "What compounds is distribution, user trust, and the operational system that keeps insight close to the product."
            ),
        }
        article_understanding = {
            "thesis": "Small AI products can ship features quickly now, which means feature speed alone stops being the moat.",
            "world_context": "What compounds is distribution, user trust, and the operational system that keeps insight close to the product.",
            "world_stakes": "A product can work and still fail to change user behavior.",
            "world_domains": ["ai", "entrepreneurship", "ops"],
            "audience_impacted": ["builders", "founders"],
            "article_kind": "trend",
            "article_stance": "nuance",
        }

        with patch(
            "app.services.social_persona_retrieval_service.load_committed_overlay_chunks",
            return_value=[],
        ), patch(
            "app.services.social_persona_retrieval_service.load_bundle_persona_chunks",
            return_value=[belief_claim, generic_ai_clone, easy_outfit_story, easy_outfit_initiative, *high_score_fillers],
        ):
            result = service.retrieve(signal, "entrepreneurship", article_understanding)

        self.assertIn(
            result["selected_experience"].get("title"),
            {"Easy Outfit Build And Adoption Lesson", "Easy Outfit Metadata And Validation Layer"},
        )
        self.assertNotEqual(result["selected_experience"].get("title"), "AI Clone / Brain System")


if __name__ == "__main__":
    unittest.main()
