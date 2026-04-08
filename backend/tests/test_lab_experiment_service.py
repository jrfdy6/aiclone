from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import lab_experiment_service


class LabExperimentServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        lab_experiment_service._EXPERIMENT_CACHE.clear()

    def _fake_pipeline_audit(self) -> dict[str, object]:
        return {
            "generated_at": "2026-04-06T00:00:00Z",
            "request": {
                "topic": "workflow clarity",
                "context": "Use the operator systems angle.",
                "content_type": "linkedin_post",
                "category": "value",
                "tone": "expert_direct",
                "audience": "tech_ai",
            },
            "phases": {
                "persona_bundle": {"total": 300, "by_domain_tag": {"ai": 40, "ops": 20}},
                "source_assets": {
                    "persisted": {"item_count": 23},
                    "runtime": {"item_count": 38},
                },
                "content_reservoir": {
                    "persisted": {"item_count": 121},
                    "runtime": {"item_count": 171},
                },
                "source_modes": {
                    "persona_only": {
                        "grounding_mode": "proof_ready",
                        "grounding_reason": "Canon-led baseline.",
                        "primary_claims": ["Canon claim."],
                        "curated_persona_chunk_count": 8,
                        "content_reservoir_chunk_count": 0,
                        "retrieval_support_count": 0,
                        "canonical_bundle_count": 8,
                        "reservoir_candidate_count": 0,
                        "reservoir_candidate_memory_roles": {},
                        "example_count": 0,
                    },
                    "selected_source": {
                        "grounding_mode": "proof_ready",
                        "grounding_reason": "Source-backed context reached the packet.",
                        "primary_claims": ["Source claim."],
                        "curated_persona_chunk_count": 9,
                        "content_reservoir_chunk_count": 2,
                        "retrieval_support_count": 2,
                        "canonical_bundle_count": 7,
                        "reservoir_candidate_count": 8,
                        "reservoir_candidate_memory_roles": {"proof": 2, "ambient": 1},
                        "example_count": 1,
                    },
                    "recent_signals": {
                        "grounding_mode": "proof_ready",
                        "grounding_reason": "Recent signals still collapse to canon.",
                        "primary_claims": ["Canon claim."],
                        "curated_persona_chunk_count": 9,
                        "content_reservoir_chunk_count": 2,
                        "retrieval_support_count": 2,
                        "canonical_bundle_count": 7,
                        "reservoir_candidate_count": 8,
                        "reservoir_candidate_memory_roles": {"proof": 1, "ambient": 3},
                        "example_count": 1,
                    },
                },
            },
            "issues": [
                {
                    "severity": "high",
                    "phase": "source_assets",
                    "summary": "Persisted source assets are lagging runtime inputs.",
                    "details": {"persisted_count": 23, "runtime_count": 38},
                },
                {
                    "severity": "high",
                    "phase": "content_reservoir",
                    "summary": "Persisted content reservoir is lagging runtime inputs.",
                    "details": {"persisted_count": 121, "runtime_count": 171},
                },
                {
                    "severity": "medium",
                    "phase": "source_mode_effect",
                    "summary": "recent_signals is landing on the same primary claims as persona_only.",
                    "details": {"mode": "recent_signals"},
                },
            ],
        }

    def test_default_experiment_is_available_before_run(self) -> None:
        experiments = lab_experiment_service.list_lab_experiments()
        self.assertEqual(len(experiments), 3)
        self.assertEqual(
            {item["id"] for item in experiments},
            {
                lab_experiment_service.EXPERIMENT_ID,
                lab_experiment_service.SOCIAL_EXPERIMENT_ID,
                lab_experiment_service.SOURCE_HANDOFF_EXPERIMENT_ID,
            },
        )
        self.assertTrue(all(item["status"] == "not_run" for item in experiments))

    def test_run_content_fallback_experiment_summarizes_probe_results(self) -> None:
        fake_response = AsyncMock()
        fake_response.diagnostics = {
            "generation_strategy": "planner_writer_critic",
            "fallback_trace": {
                "events": [{"stage": "writer", "reason": "writer_returned_too_few_options"}],
                "recovered_missing_option_count": 1,
                "critic_used_rough_options": False,
                "legacy_fallback_triggered": False,
            },
            "provider_fallback_used": True,
            "llm_provider_trace": [{"provider": "gemini", "status": "success"}],
            "taste_scores": [{"warnings": ["low_contrast"]}],
            "grounding_mode": "proof_ready",
        }
        fake_response.options = ["Prompting alone is not an AI strategy."]

        with patch.object(
            lab_experiment_service.content_generation,
            "run_content_generation",
            new=AsyncMock(return_value=fake_response),
        ), patch.object(
            lab_experiment_service,
            "build_content_generation_pipeline_audit",
            return_value=self._fake_pipeline_audit(),
        ):
            record = asyncio.run(lab_experiment_service.run_content_fallback_experiment())

        self.assertEqual(record["status"], "investigating")
        self.assertGreater(record["current"]["structural_fallback_rate"], 0.0)
        self.assertIn("recovered_missing_planned_options", record["current"]["top_failure_modes"])
        self.assertIn("provider_failover", record["current"]["top_failure_modes"])
        self.assertEqual(record["pipeline_audit"]["issue_count"], 3)
        self.assertEqual(record["pipeline_audit"]["snapshot_drift_count"], 2)
        self.assertEqual(record["pipeline_audit"]["source_mode_collapse_count"], 1)
        self.assertEqual(record["golden_evaluation"]["total"], len(lab_experiment_service.CONTENT_PROBES))
        self.assertTrue(all("golden_benchmark" in item for item in record["sample_runs"]))
        self.assertTrue(
            {
                "golden_publishable_rate",
                "golden_close_rate",
                "golden_fail_rate",
                "golden_score_avg",
                "golden_score_floor",
                "golden_hard_fail_count",
            }.issubset({card["id"] for card in record["golden_evaluation"]["metric_cards"]})
        )
        self.assertEqual(len(record["history"]), 1)

    def test_run_content_fallback_experiment_captures_probe_errors(self) -> None:
        with patch.object(
            lab_experiment_service.content_generation,
            "run_content_generation",
            new=AsyncMock(side_effect=RuntimeError("critic payload malformed")),
        ), patch.object(
            lab_experiment_service,
            "build_content_generation_pipeline_audit",
            return_value=self._fake_pipeline_audit(),
        ):
            record = asyncio.run(lab_experiment_service.run_content_fallback_experiment())

        self.assertEqual(record["status"], "investigating")
        self.assertIn("probe_errors", record["current"]["top_failure_modes"])
        self.assertEqual(record["current"]["stage_breakdown"]["probe_errors"], len(lab_experiment_service.CONTENT_PROBES))
        self.assertTrue(all("probe_error" in item["structural_fallbacks"] for item in record["sample_runs"]))
        self.assertEqual(record["pipeline_audit"]["issue_count"], 3)
        self.assertEqual(record["golden_evaluation"]["fail_count"], len(lab_experiment_service.CONTENT_PROBES))

    def test_lab_provider_lane_sets_and_restores_stability_env(self) -> None:
        with patch.dict(os.environ, {"CONTENT_GENERATION_PROVIDER_ORDER": "gemini", "CONTENT_GENERATION_STABILITY_MODE": "custom"}):
            with lab_experiment_service._lab_provider_lane():
                self.assertEqual(os.environ.get("CONTENT_GENERATION_PROVIDER_ORDER"), "openai")
                self.assertEqual(os.environ.get("CONTENT_GENERATION_STABILITY_MODE"), "benchmark")

            self.assertEqual(os.environ.get("CONTENT_GENERATION_PROVIDER_ORDER"), "gemini")
            self.assertEqual(os.environ.get("CONTENT_GENERATION_STABILITY_MODE"), "custom")

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CONTENT_GENERATION_PROVIDER_ORDER", None)
            os.environ.pop("CONTENT_GENERATION_STABILITY_MODE", None)

            with lab_experiment_service._lab_provider_lane():
                self.assertEqual(os.environ.get("CONTENT_GENERATION_PROVIDER_ORDER"), "openai")
                self.assertEqual(os.environ.get("CONTENT_GENERATION_STABILITY_MODE"), "benchmark")

            self.assertNotIn("CONTENT_GENERATION_PROVIDER_ORDER", os.environ)
            self.assertNotIn("CONTENT_GENERATION_STABILITY_MODE", os.environ)

    def test_evaluate_content_golden_benchmark_marks_publishable_when_contract_is_met(self) -> None:
        diagnostics = {
            "grounding_mode": "proof_ready",
            "primary_claims": ["If the workflow is unclear, AI just scales confusion."],
            "proof_packets": [
                "AI Clone / Brain System -> Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot; content generation reads canon through structured lanes."
            ],
            "planned_option_briefs": [
                {
                    "option_number": 1,
                    "framing_mode": "operator_lesson",
                    "primary_claim": "If the workflow is unclear, AI just scales confusion.",
                    "proof_packet": "AI Clone / Brain System -> Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot; content generation reads canon through structured lanes.",
                    "story_beat": "",
                }
            ],
        }
        row = lab_experiment_service._evaluate_content_golden_benchmark(
            probe={
                "topic": "workflow clarity",
                "audience": "tech_ai",
                "category": "value",
                "tone": "expert_direct",
            },
            diagnostics=diagnostics,
            top_option=(
                "If the workflow is unclear, AI just scales confusion.\n\n"
                "AI Clone / Brain System made the handoff visible.\n\n"
                "One routed workspace snapshot now keeps context alive.\n\n"
                "Shared state keeps context alive across the handoff."
            ),
            top_warnings=[],
        )

        self.assertEqual(row["status"], "publishable")
        self.assertTrue(row["required_checks_passed"])
        self.assertGreaterEqual(row["score"], row["minimum_score"])

    def test_evaluate_content_golden_benchmark_accepts_proof_shaped_operator_opening(self) -> None:
        diagnostics = {
            "grounding_mode": "proof_ready",
            "primary_claims": ["If the workflow is unclear, AI just scales confusion."],
            "proof_packets": [
                "AI Clone / Brain System -> Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot; content generation reads canon through structured lanes."
            ],
            "planned_option_briefs": [
                {
                    "option_number": 1,
                    "framing_mode": "operator_lesson",
                    "primary_claim": "If the workflow is unclear, AI just scales confusion.",
                    "proof_packet": "AI Clone / Brain System -> Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot; content generation reads canon through structured lanes.",
                    "story_beat": "",
                }
            ],
        }

        row = lab_experiment_service._evaluate_content_golden_benchmark(
            probe={
                "topic": "workflow clarity",
                "audience": "tech_ai",
                "category": "value",
                "tone": "expert_direct",
            },
            diagnostics=diagnostics,
            top_option=(
                "One routed workspace snapshot now keeps context alive.\n\n"
                "AI Clone / Brain System made the handoff visible.\n\n"
                "Content generation now reads canon through typed lanes.\n\n"
                "That is the operating model."
            ),
            top_warnings=[],
        )

        self.assertEqual(row["status"], "publishable")
        claim_check = next(check for check in row["checks"] if check["id"] == "claim_led")
        self.assertEqual(claim_check["status"], "pass")

    def test_evaluate_content_golden_benchmark_accepts_education_policy_anchor_variants(self) -> None:
        diagnostics = {
            "grounding_mode": "proof_ready",
            "primary_claims": ["Admissions is not just enrollment; it is translation."],
            "proof_packets": [
                "Fusion Academy Dashboard Transformation -> Daily, weekly, and quarterly metrics were unified so outreach and execution became clearer for school teams."
            ],
            "planned_option_briefs": [
                {
                    "option_number": 1,
                    "framing_mode": "operator_lesson",
                    "primary_claim": "Admissions is not just enrollment; it is translation.",
                    "proof_packet": "Fusion Academy Dashboard Transformation -> Daily, weekly, and quarterly metrics were unified so outreach and execution became clearer for school teams.",
                    "story_beat": "",
                }
            ],
        }

        row = lab_experiment_service._evaluate_content_golden_benchmark(
            probe={
                "topic": "Kentucky Senate passes bill making it easier to cut faculty",
                "audience": "education_admissions",
                "category": "value",
                "tone": "expert_direct",
            },
            diagnostics=diagnostics,
            top_option=(
                "Admissions is not just enrollment; it is translation.\n\n"
                "Policy shocks land with families first.\n\n"
                "If faculty cuts keep stacking up, trust gets harder to hold with educators and school communities.\n\n"
                "The Fusion Academy Dashboard Transformation made the next action easier to see."
            ),
            top_warnings=[],
        )

        anchor_check = next(check for check in row["checks"] if check["id"] == "anchor_contract")
        self.assertEqual(anchor_check["status"], "pass")

    def test_warning_matches_prefix_ignores_genericity_one(self) -> None:
        self.assertFalse(lab_experiment_service._warning_matches_prefix(["genericity:1"], ["genericity:"]))
        self.assertTrue(lab_experiment_service._warning_matches_prefix(["genericity:2"], ["genericity:"]))

    def test_run_social_response_matrix_experiment_covers_all_lanes(self) -> None:
        record = asyncio.run(lab_experiment_service.run_social_response_matrix_experiment())

        self.assertEqual(record["id"], lab_experiment_service.SOCIAL_EXPERIMENT_ID)
        self.assertEqual(len(record["sample_runs"]), len(lab_experiment_service.ARTICLE_RESPONSE_PROBES))
        self.assertEqual(record["current"]["lane_coverage_rate"], 100.0)
        self.assertIn("missing_stage_rate", record["current"])
        self.assertTrue(all(len(item["matrix_rows"]) == len(lab_experiment_service.SOCIAL_LANE_MATRIX) for item in record["sample_runs"]))
        self.assertTrue(all("comment_status" in row and "repost_status" in row for item in record["sample_runs"] for row in item["matrix_rows"]))
        self.assertTrue(all("signal_snapshot" in item for item in record["sample_runs"]))
        required_stage_ids = {
            "article_stance",
            "persona_retrieval",
            "johnnie_perspective",
            "reaction_brief",
            "template_composition",
            "response_type_selection",
            "humor_safety",
        }
        for item in record["sample_runs"]:
            stage_ids = {stage["id"] for stage in item["stage_results"]}
            self.assertTrue(required_stage_ids.issubset(stage_ids))
            for row in item["matrix_rows"]:
                self.assertIn("article_understanding", row)
                self.assertIn("persona_retrieval", row)
                self.assertIn("johnnie_perspective", row)
                self.assertIn("reaction_brief", row)
                self.assertIn("response_type_packet", row)
                self.assertIn("composition_traces", row)
                self.assertIn("stage_evaluation", row)

    def test_run_social_response_matrix_experiment_keeps_lane_diversity_visible(self) -> None:
        record = asyncio.run(lab_experiment_service.run_social_response_matrix_experiment())

        first_probe_rows = record["sample_runs"][0]["matrix_rows"]
        beliefs = {row.get("belief_used") for row in first_probe_rows if row.get("belief_used")}
        experiences = {row.get("experience_anchor") for row in first_probe_rows if row.get("experience_anchor")}
        response_types = {row.get("response_type") for row in first_probe_rows if row.get("response_type")}
        technique_bundles = {tuple(row.get("techniques") or []) for row in first_probe_rows if row.get("techniques")}

        self.assertGreaterEqual(len(beliefs), 3)
        self.assertGreaterEqual(len(experiences), 3)
        self.assertGreaterEqual(len(response_types), 2)
        self.assertGreaterEqual(len(technique_bundles), 3)

    def test_run_social_response_matrix_experiment_surfaces_tuning_metric_cards(self) -> None:
        record = asyncio.run(lab_experiment_service.run_social_response_matrix_experiment())

        metric_ids = {card["id"] for card in record["current"]["metric_cards"]}
        self.assertTrue(
            {
                "article_stance_avg",
                "source_expression_avg",
                "belief_relevance_avg",
                "experience_relevance_avg",
                "voice_match_avg",
                "expression_quality_avg",
            }.issubset(metric_ids)
        )

    def test_run_source_handoff_matrix_experiment_surfaces_expected_vs_actual_lanes(self) -> None:
        fake_audit = {
            "source": "runtime_corpus",
            "generated_at": "2026-04-02T00:00:00Z",
            "asset_count": 3,
            "candidate_count": 4,
            "segments_total": 4,
            "quality_metrics": {
                "summary_coverage_rate": 100.0,
                "structured_summary_rate": 66.7,
                "lesson_coverage_rate": 66.7,
                "anecdote_coverage_rate": 33.3,
                "quote_coverage_rate": 66.7,
                "noisy_summary_rate": 33.3,
                "package_readiness_rate": 66.7,
            },
            "origin_breakdown": {
                "media_pipeline": {
                    "asset_count": 2,
                    "quality_metrics": {
                        "summary_coverage_rate": 100.0,
                        "structured_summary_rate": 100.0,
                        "lesson_coverage_rate": 100.0,
                        "anecdote_coverage_rate": 50.0,
                        "quote_coverage_rate": 50.0,
                        "noisy_summary_rate": 0.0,
                        "package_readiness_rate": 100.0,
                    },
                    "issue_counts": {"quotes_missing": 1},
                    "deep_harvest_fragments": 16,
                }
            },
            "slice_counts": {
                "handoff_lane_counts": {"brief_only": 2, "persona_candidate": 2},
                "primary_route_counts": {"belief_evidence": 3, "post_seed": 1},
                "channel_counts": {"youtube": 3},
                "target_file_counts": {"identity/claims.md": 3, "history/story_bank.md": 1},
                "origin_counts": {"media_pipeline": 2, "transcript_library": 1},
                "summary_origin_counts": {"derived_transcript": 2, "provided": 1},
                "issue_counts": {"summary_needs_cleanup": 1, "anecdotes_missing": 2},
            },
            "top_issues": [{"id": "summary_needs_cleanup", "label": "summary needs cleanup", "count": 1}],
            "candidate_samples": [
                {
                    "topic": "Operator Judgment",
                    "audience": "live_source_sample",
                    "generation_strategy": "source_handoff_live_sample",
                    "llm_request_count": 0,
                    "platform": "youtube",
                    "source_type": "long_form_segment",
                    "structural_fallbacks": [],
                    "top_warnings": ["persona-worthy worldview evidence"],
                    "stage_results": [],
                    "top_option_preview": "Workflow clarity matters more than tool abundance because operator judgment earns trust.",
                    "signal_snapshot": {
                        "source_channel": "youtube",
                        "actual_handoff_lane": "persona_candidate",
                        "primary_route": "comment",
                        "target_file": "identity/claims.md",
                    },
                }
            ],
            "asset_samples": [
                {
                    "title": "Operator Judgment",
                    "source_channel": "youtube",
                    "summary": "Workflow clarity matters more than tool abundance because operator judgment earns trust.",
                    "structured_summary": "Workflow clarity matters more than tool abundance because operator judgment earns trust.",
                    "summary_origin": "derived_transcript",
                    "lessons_learned": ["Workflow clarity matters more than tool abundance because operator judgment earns trust."],
                    "key_anecdotes": ["When my team called the customer, they were relieved a human answered the phone."],
                    "reusable_quotes": ["Use your tokens on meaningful work instead of noisy busywork."],
                    "quality_flags": [],
                }
            ],
        }

        with patch.object(lab_experiment_service, "_build_live_source_handoff_audit", return_value=fake_audit):
            record = asyncio.run(lab_experiment_service.run_source_handoff_matrix_experiment())

        self.assertEqual(record["id"], lab_experiment_service.SOURCE_HANDOFF_EXPERIMENT_ID)
        self.assertEqual(len(record["sample_runs"]), len(lab_experiment_service.SOURCE_HANDOFF_PROBES))
        self.assertEqual(record["current"]["metric_cards"][0]["id"], "exact_match_rate")
        self.assertEqual(record["current"]["metric_cards"][0]["value"], 100.0)
        self.assertEqual(record["live_audit"]["source"], "runtime_corpus")
        self.assertEqual(record["live_audit"]["asset_count"], 3)
        self.assertEqual(record["live_audit"]["origin_breakdown"]["media_pipeline"]["asset_count"], 2)
        self.assertEqual(record["live_samples"][0]["signal_snapshot"]["actual_handoff_lane"], "persona_candidate")
        self.assertTrue(
            {
                "exact_match_rate",
                "handoff_mismatch_rate",
                "persona_false_positive_rate",
                "persona_false_negative_rate",
                "post_false_negative_rate",
                "pm_alignment_rate",
                "source_guardrail_success_rate",
            }.issubset({card["id"] for card in record["current"]["metric_cards"]})
        )
        for item in record["sample_runs"]:
            snapshot = item.get("signal_snapshot") or {}
            self.assertIn("expected_handoff_lane", snapshot)
            self.assertIn("actual_handoff_lane", snapshot)
            self.assertIn("primary_route", snapshot)
            self.assertEqual(snapshot.get("expected_handoff_lane"), snapshot.get("actual_handoff_lane"))
            stage_ids = {stage["id"] for stage in item["stage_results"]}
            self.assertTrue({"source_contract", "route_classification", "handoff_decision"}.issubset(stage_ids))

    def test_build_live_source_handoff_audit_breaks_metrics_out_by_origin(self) -> None:
        source_assets_payload = {
            "items": [
                {
                    "title": "Operator Judgment",
                    "origin": "media_pipeline",
                    "source_channel": "youtube",
                    "source_type": "transcript",
                    "source_path": "knowledge/ingestions/2026/04/operator-judgment/normalized.md",
                    "source_url": "https://example.com/operator-judgment",
                    "summary": "Workflow clarity matters more than tool abundance because operator judgment earns trust.",
                    "structured_summary": "Workflow clarity matters more than tool abundance because operator judgment earns trust.",
                    "summary_origin": "derived_transcript",
                    "lessons_learned": ["Workflow clarity matters more than tool abundance because operator judgment earns trust."],
                    "key_anecdotes": ["A customer relaxed the second a human answered the phone."],
                    "reusable_quotes": ["Trust and clarity beat persuasion."],
                    "quality_flags": [],
                    "deep_harvest_fragments": [
                        {
                            "text": "Trust and clarity beat persuasion.",
                            "primary_type": "quote",
                            "labels": ["quote", "voice_pattern"],
                            "score": 8,
                            "word_count": 5,
                            "likely_handoff_lane": "post_candidate",
                            "promotion_recommendation": "voice_guidance_only",
                            "promotion_reason": "This source fragment is better as voice guidance than as canon.",
                            "source_section": "reusable_quotes",
                        }
                    ],
                    "deep_harvest_counts": {"total": 1, "voice_guidance_only_count": 1, "by_recommendation": {"voice_guidance_only": 1}},
                },
                {
                    "title": "Bootcamp Notes",
                    "origin": "transcript_library",
                    "source_channel": "manual",
                    "source_type": "transcript_note",
                    "source_path": "knowledge/aiclone/transcripts/bootcamp.md",
                    "source_url": "",
                    "summary": "Bedrock notes",
                    "structured_summary": "Bedrock notes",
                    "summary_origin": "transcript_note",
                    "lessons_learned": [],
                    "key_anecdotes": [],
                    "reusable_quotes": [],
                    "quality_flags": ["lessons_missing", "anecdotes_missing", "quotes_missing"],
                    "deep_harvest_fragments": [
                        {
                            "text": "Operator judgment and workflow clarity matter because trust breaks when review handoffs hide the human too early.",
                            "primary_type": "canon_candidate",
                            "labels": ["lesson", "worldview", "operational", "canon_candidate"],
                            "score": 10,
                            "word_count": 14,
                            "likely_handoff_lane": "persona_candidate",
                            "promotion_recommendation": "canon_suggestion",
                            "promotion_reason": "This persona-interview fragment reads like durable self-model material and deserves canon review.",
                            "source_section": "lessons_learned",
                        }
                    ],
                    "deep_harvest_counts": {"total": 1, "canon_suggestion_count": 1, "by_recommendation": {"canon_suggestion": 1}},
                },
            ],
            "counts": {"by_channel": {"youtube": 1, "manual": 1}},
        }
        long_form_routes_payload = {
            "candidates": [
                {
                    "title": "Operator Judgment",
                    "segment": "Workflow clarity matters more than tool abundance because operator judgment earns trust.",
                    "source_channel": "youtube",
                    "source_path": "knowledge/ingestions/2026/04/operator-judgment/normalized.md",
                    "source_url": "https://example.com/operator-judgment",
                    "handoff_lane": "persona_candidate",
                    "primary_route": "belief_evidence",
                    "lane_hint": "ai",
                    "target_file": "identity/claims.md",
                    "secondary_consumers": ["brief"],
                }
            ],
            "handoff_lane_counts": {"persona_candidate": 1},
            "primary_route_counts": {"belief_evidence": 1},
        }

        with patch.object(
            lab_experiment_service,
            "_load_live_source_payloads",
            return_value=(source_assets_payload, long_form_routes_payload, "runtime_corpus"),
        ):
            audit = lab_experiment_service._build_live_source_handoff_audit(limit_candidates=4, limit_assets=4)

        self.assertEqual(audit["slice_counts"]["origin_counts"]["media_pipeline"], 1)
        self.assertEqual(audit["slice_counts"]["origin_counts"]["transcript_library"], 1)
        self.assertEqual(audit["origin_breakdown"]["media_pipeline"]["quality_metrics"]["quote_coverage_rate"], 100.0)
        self.assertEqual(audit["origin_breakdown"]["transcript_library"]["quality_metrics"]["quote_coverage_rate"], 0.0)
        self.assertEqual(audit["candidate_samples"][0]["signal_snapshot"]["source_origin"], "media_pipeline")
        self.assertEqual(audit["asset_samples"][1]["origin"], "transcript_library")
        self.assertEqual(audit["slice_counts"]["fragment_recommendation_counts"]["voice_guidance_only"], 1)
        self.assertEqual(audit["slice_counts"]["fragment_recommendation_counts"]["canon_suggestion"], 1)
        self.assertEqual(audit["deep_harvest_metrics"]["voice_guidance_only_rate"], 50.0)
        self.assertEqual(audit["deep_harvest_metrics"]["canon_suggestion_rate"], 50.0)
        self.assertEqual(audit["fragment_samples"][0]["promotion_recommendation"], "canon_suggestion")
