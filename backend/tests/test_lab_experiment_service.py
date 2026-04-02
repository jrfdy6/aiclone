from __future__ import annotations

import asyncio
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
        ):
            record = asyncio.run(lab_experiment_service.run_content_fallback_experiment())

        self.assertEqual(record["status"], "investigating")
        self.assertGreater(record["current"]["structural_fallback_rate"], 0.0)
        self.assertIn("recovered_missing_planned_options", record["current"]["top_failure_modes"])
        self.assertIn("provider_failover", record["current"]["top_failure_modes"])
        self.assertEqual(len(record["history"]), 1)

    def test_run_content_fallback_experiment_captures_probe_errors(self) -> None:
        with patch.object(
            lab_experiment_service.content_generation,
            "run_content_generation",
            new=AsyncMock(side_effect=RuntimeError("critic payload malformed")),
        ):
            record = asyncio.run(lab_experiment_service.run_content_fallback_experiment())

        self.assertEqual(record["status"], "investigating")
        self.assertIn("probe_errors", record["current"]["top_failure_modes"])
        self.assertEqual(record["current"]["stage_breakdown"]["probe_errors"], len(lab_experiment_service.CONTENT_PROBES))
        self.assertTrue(all("probe_error" in item["structural_fallbacks"] for item in record["sample_runs"]))

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
        record = asyncio.run(lab_experiment_service.run_source_handoff_matrix_experiment())

        self.assertEqual(record["id"], lab_experiment_service.SOURCE_HANDOFF_EXPERIMENT_ID)
        self.assertEqual(len(record["sample_runs"]), len(lab_experiment_service.SOURCE_HANDOFF_PROBES))
        self.assertEqual(record["current"]["metric_cards"][0]["id"], "exact_match_rate")
        self.assertEqual(record["current"]["metric_cards"][0]["value"], 100.0)
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
