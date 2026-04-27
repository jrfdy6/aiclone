from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes import content_generation
from app.services.content_release_policy_service import (
    build_public_safe_primary_claims,
    build_public_safe_proof_packets,
)
from app.services import local_content_generation_execution_service
from app.services.content_generation_context_service import ContentGenerationContext
from app.services.local_codex_generation_service import read_job_artifact_content


def _fake_context() -> ContentGenerationContext:
    core_chunk = {
        "chunk": "Workflow clarity beats prompting alone.",
        "persona_tag": "CLAIMS",
        "metadata": {"memory_role": "core", "source": "identity/claims.md"},
    }
    return ContentGenerationContext(
        persona_chunks=[core_chunk],
        example_chunks=[],
        core_chunks=[core_chunk],
        proof_chunks=[],
        story_chunks=[],
        ambient_chunks=[],
        topic_anchor_chunks=[core_chunk],
        proof_anchor_chunks=[],
        story_anchor_chunks=[],
        grounding_mode="principle_only",
        grounding_reason="No proof anchors were available.",
        framing_modes=["operator_lesson"],
        primary_claims=["Workflow clarity beats prompting alone."],
        proof_packets=[],
        story_beats=[],
        disallowed_moves=["Do not default to generic leadership filler."],
        persona_context_summary="Workflow clarity beats prompting alone.",
        content_signal_chunks=[],
        content_signal_source="persona_only",
        content_reservoir_chunks=[],
        audit={},
    )


def _fake_result_payload(provider: str = "local_template") -> dict:
    return {
        "success": True,
        "options": [
            "Workflow clarity beats prompting alone. The workflow tells the truth faster than the prompt does. That is operator work.",
            "The prompt is not the system. The workflow is. Agreement is easy. Operational follow-through is harder. That is the part worth carrying forward.",
            "Most AI advice stops at the prompt. Real operator work starts at the workflow. That is where the real work starts.",
        ],
        "persona_context": "Workflow clarity beats prompting alone.",
        "examples_used": [],
        "diagnostics": {
            "llm_provider_trace": [
                {
                    "provider": provider,
                    "actual_model": "local-template-v1" if provider == "local_template" else "gpt-5.4-mini",
                    "status": "success",
                }
            ]
        },
    }


class ContentGenerationCodexJobsRouteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_store = os.environ.get("LOCAL_CODEX_JOB_STORE_DIR")
        self.previous_token = os.environ.get("LOCAL_CODEX_BRIDGE_TOKEN")
        self.previous_runtime = os.environ.get("CONTENT_GENERATION_RUNTIME")
        os.environ["LOCAL_CODEX_JOB_STORE_DIR"] = self.temp_dir.name
        os.environ["LOCAL_CODEX_BRIDGE_TOKEN"] = "test-token"
        os.environ["CONTENT_GENERATION_RUNTIME"] = "local"
        app = FastAPI()
        app.include_router(content_generation.router, prefix="/api/content-generation")
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()
        if self.previous_store is None:
            os.environ.pop("LOCAL_CODEX_JOB_STORE_DIR", None)
        else:
            os.environ["LOCAL_CODEX_JOB_STORE_DIR"] = self.previous_store
        if self.previous_token is None:
            os.environ.pop("LOCAL_CODEX_BRIDGE_TOKEN", None)
        else:
            os.environ["LOCAL_CODEX_BRIDGE_TOKEN"] = self.previous_token
        if self.previous_runtime is None:
            os.environ.pop("CONTENT_GENERATION_RUNTIME", None)
        else:
            os.environ["CONTENT_GENERATION_RUNTIME"] = self.previous_runtime

    def test_create_claim_complete_and_poll_job(self) -> None:
        with patch("app.services.local_codex_context_cache_service.get_snapshot_payload", return_value={}), patch.object(
            content_generation,
            "build_content_generation_context",
            return_value=_fake_context(),
        ):
            create_response = self.client.post(
                "/api/content-generation/codex-jobs",
                json={
                    "user_id": "johnnie_fields",
                    "topic": "workflow clarity",
                    "context": "Use the operator angle.",
                    "content_type": "linkedin_post",
                    "category": "value",
                    "tone": "expert_direct",
                    "audience": "tech_ai",
                    "source_mode": "persona_only",
                    "workspace_slug": "linkedin-content-os",
                },
            )

        self.assertEqual(create_response.status_code, 200)
        job_id = create_response.json()["job_id"]
        status_response = self.client.get(f"/api/content-generation/codex-jobs/{job_id}")
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["artifact_count"], 2)

        artifacts_response = self.client.get(f"/api/content-generation/codex-jobs/{job_id}/artifacts")
        self.assertEqual(artifacts_response.status_code, 200)
        self.assertEqual(len(artifacts_response.json()["artifacts"]), 2)
        context_artifact = next(item for item in artifacts_response.json()["artifacts"] if item["kind"] == "context_packet")
        context_content = read_job_artifact_content(job_id=job_id, artifact_id=context_artifact["artifact_id"])
        self.assertIn('"cache_hit": false', context_content)
        self.assertIn('"content_signal_source": "persona_only"', context_content)
        self.assertIn('"content_signal_count": 0', context_content)

        claim_response = self.client.post(
            "/api/content-generation/codex-jobs/claim-next",
            headers={"X-Local-Codex-Token": "test-token"},
            json={"worker_id": "local-bridge", "workspace_slug": "linkedin-content-os"},
        )
        self.assertEqual(claim_response.status_code, 200)
        self.assertTrue(claim_response.json()["job_available"])
        self.assertEqual(claim_response.json()["job_id"], job_id)

        complete_response = self.client.post(
            f"/api/content-generation/codex-jobs/{job_id}/complete",
            headers={"X-Local-Codex-Token": "test-token"},
            json={
                "worker_id": "local-bridge",
                "model": "local-template-v1",
                "result_payload": _fake_result_payload(),
                "artifacts": [
                    {
                        "kind": "quality_gate",
                        "label": "quality-gate.json",
                        "filename": "quality-gate.json",
                        "mime_type": "application/json",
                        "content": "{\n  \"passed\": true\n}\n",
                    }
                ],
            },
        )
        self.assertEqual(complete_response.status_code, 200)
        self.assertEqual(complete_response.json()["status"], "completed")
        self.assertEqual(len(complete_response.json()["result"]["options"]), 3)
        self.assertEqual(complete_response.json()["artifact_count"], 3)

        status_response = self.client.get(f"/api/content-generation/codex-jobs/{job_id}")
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], "completed")
        self.assertEqual(
            status_response.json()["result"]["diagnostics"]["llm_provider_trace"][0]["provider"],
            "local_template",
        )
        artifacts_response = self.client.get(f"/api/content-generation/codex-jobs/{job_id}/artifacts")
        self.assertEqual(artifacts_response.status_code, 200)
        self.assertEqual(len(artifacts_response.json()["artifacts"]), 3)
        quality_gate_artifact = next(item for item in artifacts_response.json()["artifacts"] if item["kind"] == "quality_gate")
        quality_gate_content = read_job_artifact_content(job_id=job_id, artifact_id=quality_gate_artifact["artifact_id"])
        self.assertIn('"passed": true', quality_gate_content)

    def test_repeated_enqueue_reuses_cached_context_packet(self) -> None:
        payload = {
            "user_id": "johnnie_fields",
            "topic": "workflow clarity",
            "context": "Use the operator angle.",
            "content_type": "linkedin_post",
            "category": "value",
            "tone": "expert_direct",
            "audience": "tech_ai",
            "source_mode": "persona_only",
            "workspace_slug": "linkedin-content-os",
        }
        with patch("app.services.local_codex_context_cache_service.get_snapshot_payload", return_value={}):
            with patch.object(content_generation, "build_content_generation_context", return_value=_fake_context()) as builder:
                first_create = self.client.post("/api/content-generation/codex-jobs", json=payload)

            self.assertEqual(first_create.status_code, 200)
            self.assertEqual(builder.call_count, 1)
            first_job_id = first_create.json()["job_id"]

            claim_response = self.client.post(
                "/api/content-generation/codex-jobs/claim-next",
                headers={"X-Local-Codex-Token": "test-token"},
                json={"worker_id": "local-bridge", "workspace_slug": "linkedin-content-os"},
            )
            self.assertEqual(claim_response.status_code, 200)
            self.assertEqual(claim_response.json()["job_id"], first_job_id)

            complete_response = self.client.post(
                f"/api/content-generation/codex-jobs/{first_job_id}/complete",
                headers={"X-Local-Codex-Token": "test-token"},
                json={
                    "worker_id": "local-bridge",
                    "model": "local-template-v1",
                    "result_payload": _fake_result_payload(),
                },
            )
            self.assertEqual(complete_response.status_code, 200)

            with patch.object(content_generation, "build_content_generation_context", side_effect=AssertionError("cache should bypass context rebuild")) as builder:
                second_create = self.client.post("/api/content-generation/codex-jobs", json=payload)

            self.assertEqual(second_create.status_code, 200)
            self.assertEqual(builder.call_count, 0)
            second_job_id = second_create.json()["job_id"]

            artifacts_response = self.client.get(f"/api/content-generation/codex-jobs/{second_job_id}/artifacts")
            self.assertEqual(artifacts_response.status_code, 200)
            context_artifact = next(item for item in artifacts_response.json()["artifacts"] if item["kind"] == "context_packet")
            context_content = read_job_artifact_content(job_id=second_job_id, artifact_id=context_artifact["artifact_id"])
            self.assertIn('"cache_hit": true', context_content)

    def test_explicit_idempotency_key_reuses_pending_job(self) -> None:
        payload = {
            "user_id": "johnnie_fields",
            "topic": "workflow clarity",
            "context": "Use the operator angle.",
            "content_type": "linkedin_post",
            "category": "value",
            "tone": "expert_direct",
            "audience": "tech_ai",
            "source_mode": "persona_only",
            "workspace_slug": "linkedin-content-os",
            "idempotency_key": "content-test-key-1",
        }

        with patch("app.services.local_codex_context_cache_service.get_snapshot_payload", return_value={}), patch.object(
            content_generation,
            "build_content_generation_context",
            return_value=_fake_context(),
        ) as builder:
            first = self.client.post("/api/content-generation/codex-jobs", json=payload)
            second = self.client.post("/api/content-generation/codex-jobs", json=payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["job_id"], second.json()["job_id"])
        self.assertEqual(builder.call_count, 1)

    def test_context_audit_route_returns_upstream_diagnostics(self) -> None:
        fake_context = _fake_context()
        fake_context.audit = {
            "request": {"topic": "workflow clarity", "source_mode": "persona_only"},
            "retrieval": {
                "curated_persona_chunks": {
                    "count": 1,
                    "items": [
                        {
                            "chunk": "Workflow clarity beats prompting alone.",
                            "memory_role": "core",
                            "source_kind": "canonical_bundle",
                        }
                    ],
                }
            },
            "selection": {"primary_claims": ["Workflow clarity beats prompting alone."]},
        }
        with patch.object(content_generation, "build_content_generation_context", return_value=fake_context) as builder:
            response = self.client.post(
                "/api/content-generation/context-audit",
                json={
                    "user_id": "johnnie_fields",
                    "topic": "workflow clarity",
                    "context": "Use the operator angle.",
                    "content_type": "linkedin_post",
                    "category": "value",
                    "tone": "expert_direct",
                    "audience": "tech_ai",
                    "source_mode": "persona_only",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["persona_context"], "Workflow clarity beats prompting alone.")
        self.assertEqual(response.json()["audit"]["retrieval"]["curated_persona_chunks"]["count"], 1)
        builder.assert_called_once()

    def test_local_quality_gate_rejects_internal_public_leak(self) -> None:
        context_packet = {
            "planned_option_briefs": [
                {
                    "option_number": 1,
                    "framing_mode": "operator_lesson",
                    "public_lane": "build_in_public",
                    "primary_claim": "We stopped making the writer do infrastructure work.",
                    "proof_packet": "Content generation now reads persona through typed core, proof, story, and example lanes; applies domain gates; and enforces approved proof packets before final drafts.",
                    "story_beat": "",
                }
            ],
            "primary_claims": ["We stopped making the writer do infrastructure work."],
            "proof_packets": [
                "Content generation now reads persona through typed core, proof, story, and example lanes; applies domain gates; and enforces approved proof packets before final drafts."
            ],
            "story_beats": [],
            "grounding_mode": "proof_ready",
        }

        gate = local_content_generation_execution_service.evaluate_local_quality(
            context_packet,
            [
                "We finally stopped sending persona soup to the writer.\n\nContent generation now reads persona through typed core, proof, story, and example lanes, applies domain gates, and enforces approved proof packets before final drafts."
            ],
        )

        self.assertFalse(gate["passed"])
        self.assertTrue(any("internal_public_leak" in reason for reason in gate["failed_reasons"]))

    def test_local_quality_gate_rejects_borderline_template_scaffold_batch(self) -> None:
        context_packet = {
            "planned_option_briefs": [
                {
                    "option_number": 1,
                    "framing_mode": "operator_lesson",
                    "public_lane": "operator_lesson",
                    "primary_claim": "Prompting alone is not an AI strategy.",
                    "proof_packet": "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone -> Brain, Ops, daily briefs, planner, long-form routing, and content generation now depend on explicit handoffs, shared workspace state, and proof-aware prompts instead of isolated prompting.",
                    "story_beat": "AI Constraint Breakthrough.",
                },
                {
                    "option_number": 2,
                    "framing_mode": "contrarian_reframe",
                    "public_lane": "market_insight",
                    "primary_claim": "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
                    "proof_packet": "Fusion Academy Dashboard Transformation -> Daily, weekly, monthly, quarterly, and yearly metrics were unified in one Salesforce dashboard; high-priority, active-pipeline, and gray-area outreach became clearer; territory coordination improved; meetings rose by more than 20%; referrals rose by more than 50%; leadership engagement increased because execution was easier to see.",
                    "story_beat": "AI Constraint Breakthrough.",
                },
                {
                    "option_number": 3,
                    "framing_mode": "warning",
                    "public_lane": "build_in_public",
                    "primary_claim": "Johnnie is building at the intersection of education, AI systems, entrepreneurship, and style.",
                    "proof_packet": "Prompting alone is not an AI strategy -> Johnnie keeps moving work from isolated prompting into structured workflows, typed retrieval, domain gates, proof packets, and shared state.",
                    "story_beat": "AI Constraint Breakthrough.",
                },
            ],
            "primary_claims": [
                "Prompting alone is not an AI strategy.",
                "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
                "Johnnie is building at the intersection of education, AI systems, entrepreneurship, and style.",
            ],
            "proof_packets": [
                "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone -> Brain, Ops, daily briefs, planner, long-form routing, and content generation now depend on explicit handoffs, shared workspace state, and proof-aware prompts instead of isolated prompting.",
                "Fusion Academy Dashboard Transformation -> Daily, weekly, monthly, quarterly, and yearly metrics were unified in one Salesforce dashboard; high-priority, active-pipeline, and gray-area outreach became clearer; territory coordination improved; meetings rose by more than 20%; referrals rose by more than 50%; leadership engagement increased because execution was easier to see.",
                "Prompting alone is not an AI strategy -> Johnnie keeps moving work from isolated prompting into structured workflows, typed retrieval, domain gates, proof packets, and shared state.",
            ],
            "story_beats": ["AI Constraint Breakthrough.", "AI Constraint Breakthrough.", "AI Constraint Breakthrough."],
            "grounding_mode": "proof_ready",
        }

        gate = local_content_generation_execution_service.evaluate_local_quality(
            context_packet,
            [
                "Prompting alone is not an AI strategy.\n\nThe prompt is not the system. The workflow is.\n\nClearer handoffs and clearer proof rules made the workflow more reliable.\n\nAI Constraint Breakthrough.\n\nOperator clarity wins.",
                "Prompting alone is not the strategy.\n\nNot more reporting. Clearer action.\n\nThe edge comes from clarity, not from piling on more tools.\n\nDaily, weekly, monthly, quarterly, and yearly metrics were unified in one Salesforce dashboard. high-priority, active-pipeline, and gray-area outreach became clearer.\n\nAI Constraint Breakthrough.\n\nClarity keeps the advantage.",
                "Johnnie is building at the intersection of education, AI systems, entrepreneurship, and style.\n\nPrompting alone is not an AI strategy makes this concrete.\n\nThat lesson showed up in the build before it showed up in the copy.\n\nJohnnie keeps moving work from isolated prompting into structured workflows, typed retrieval, topic guardrails, proof, and shared state.\n\nAI Constraint Breakthrough.\n\nThat is what the build taught us.",
            ],
        )

        self.assertFalse(gate["passed"])
        self.assertIn("opening_variety_low", gate["failed_reasons"])
        self.assertTrue(any("label_paragraph" in reason for reason in gate["failed_reasons"]))
        self.assertTrue(any("stock_template_scaffold" in reason for reason in gate["failed_reasons"]))
        self.assertTrue(any("persona_bio_opening" in reason for reason in gate["failed_reasons"]))

    def test_local_template_options_rewrite_internal_operator_catalog_to_public_macro_copy(self) -> None:
        context_packet = {
            "planned_option_briefs": [
                {
                    "option_number": 1,
                    "framing_mode": "contrarian_reframe",
                    "public_lane": "market_insight",
                    "primary_claim": "Unified Brain, Ops, daily briefs, planner, persona review, and long-form routing around one routed workspace snapshot so operator context travels across the system instead of living in isolated tools.",
                    "proof_packet": "AI Clone / Brain System -> Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot; content generation reads canon through typed lanes; before the current rebuild, malformed JSON, extra explanations, and weak schema discipline kept breaking downstream behavior.",
                    "story_beat": "Quiet Inefficiency Cleanup.",
                }
            ],
            "grounding_mode": "proof_ready",
        }

        options = local_content_generation_execution_service.compose_local_template_options(context_packet)

        self.assertEqual(len(options), 1)
        lowered = options[0].lower()
        self.assertIn("clear operating context", lowered)
        self.assertNotIn("brain, ops, daily briefs", lowered)
        self.assertNotIn("typed lanes", lowered)
        self.assertNotIn("routed workspace snapshot", lowered)

    def test_local_codex_result_payload_finalizes_internal_public_leaks(self) -> None:
        job = {
            "request_payload": {
                "topic": "workflow clarity",
                "audience": "tech_ai",
                "source_mode": "persona_only",
            },
            "context_packet": {
                "grounding_mode": "proof_ready",
                "persona_context_summary": "Workflow clarity beats prompting alone.",
                "examples_used": [],
                "primary_claims": [
                    "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone."
                ],
                "proof_packets": [
                    "AI Clone / Brain System -> Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot; content generation reads canon through typed lanes."
                ],
                "story_beats": ["Quiet Inefficiency Cleanup."],
                "approved_references": [],
                "voice_directives": [],
                "planned_option_briefs": [
                    {
                        "option_number": 1,
                        "framing_mode": "operator_lesson",
                        "public_lane": "operator_lesson",
                        "primary_claim": "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
                        "proof_packet": "AI Clone / Brain System -> Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot; content generation reads canon through typed lanes.",
                        "story_beat": "Quiet Inefficiency Cleanup.",
                    }
                ],
            },
        }

        result_payload = content_generation._build_local_codex_result_payload(
            job=job,
            options=[
                "Prompting alone stalled every tech_ai workflow I touched.\n\nDuring the AI Clone / Brain System rebuild we forced Brain, Ops, daily briefs, planner, persona review, and long-form routing to execute from one routed workspace snapshot.\n\nQuiet Inefficiency Cleanup.\n\nAgent orchestration or bust."
            ],
            model="gpt-5.4-mini",
            raw_output='{"options":[]}',
            command_stdout="",
            command_stderr="",
        )

        lowered = result_payload["options"][0].lower()
        self.assertNotIn("daily briefs", lowered)
        self.assertNotIn("routed workspace snapshot", lowered)
        self.assertNotIn("ai clone / brain system", lowered)

    def test_local_execution_result_payload_finalizes_internal_public_leaks(self) -> None:
        context_packet = {
            "grounding_mode": "proof_ready",
            "persona_context_summary": "Workflow clarity beats prompting alone.",
            "examples_used": [],
            "primary_claims": [
                "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone."
            ],
            "proof_packets": [
                "AI Clone / Brain System -> Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot; content generation reads canon through typed lanes."
            ],
            "story_beats": ["Quiet Inefficiency Cleanup."],
            "approved_references": [],
            "voice_directives": [],
            "planned_option_briefs": [
                {
                    "option_number": 1,
                    "framing_mode": "operator_lesson",
                    "public_lane": "operator_lesson",
                    "primary_claim": "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
                    "proof_packet": "AI Clone / Brain System -> Brain, Ops, daily briefs, planner, persona review, and long-form routing now run against one routed workspace snapshot; content generation reads canon through typed lanes.",
                    "story_beat": "Quiet Inefficiency Cleanup.",
                }
            ],
        }

        result_payload = local_content_generation_execution_service.build_result_payload(
            request_payload={"topic": "workflow clarity", "audience": "tech_ai", "source_mode": "persona_only"},
            context_packet=context_packet,
            options=[
                "Prompting alone stalled every tech_ai workflow I touched.\n\nDuring the AI Clone / Brain System rebuild we forced Brain, Ops, daily briefs, planner, persona review, and long-form routing to execute from one routed workspace snapshot.\n\nQuiet Inefficiency Cleanup.\n\nAgent orchestration or bust."
            ],
            provider="codex_terminal",
            model="gpt-5.4-mini",
            quality_gate={"passed": False},
            raw_output='{"options":[]}',
            command_stdout="",
            command_stderr="",
        )

        lowered = result_payload["options"][0].lower()
        self.assertNotIn("daily briefs", lowered)
        self.assertNotIn("routed workspace snapshot", lowered)
        self.assertNotIn("ai clone / brain system", lowered)
        self.assertNotIn("tech_ai", lowered)

    def test_local_codex_writer_prompt_humanizes_audience_label(self) -> None:
        brief = content_generation.ContentOptionBrief(
            option_number=1,
            framing_mode="operator_lesson",
            primary_claim="Workflow clarity beats prompting alone.",
            proof_packet="Fusion Academy Dashboard Transformation -> territory coordination improved once outreach became clearer.",
            story_beat="",
            public_lane="operator_lesson",
        )

        prompt = content_generation.build_local_codex_writer_prompt(
            topic="workflow clarity",
            context="Use the operator angle.",
            audience="tech_ai",
            grounding_mode="proof_ready",
            grounding_reason="Proof is available.",
            topic_anchor_chunks=[{"chunk": "Workflow clarity beats prompting alone."}],
            proof_anchor_chunks=[{"chunk": "Territory coordination improved once outreach became clearer."}],
            story_anchor_chunks=[],
            briefs=[brief],
            voice_directives=["Lead with clarity, not hype."],
            approved_references=["Fusion Academy Dashboard Transformation"],
        )

        self.assertIn("Audience: Tech and AI builders, founders, and operators", prompt)
        self.assertNotIn("Audience: tech_ai", prompt)

    def test_local_codex_result_payload_rewrites_persona_bio_opening(self) -> None:
        job = {
            "request_payload": {
                "topic": "ai is not making every market meaner",
                "audience": "tech_ai",
                "source_mode": "persona_only",
            },
            "context_packet": {
                "grounding_mode": "proof_ready",
                "persona_context_summary": "AI is not making every market meaner.",
                "examples_used": [],
                "primary_claims": [
                    "AI is not making every market meaner."
                ],
                "proof_packets": [
                    "Fusion Academy Dashboard Transformation -> territory coordination improved once outreach became clearer."
                ],
                "story_beats": [],
                "approved_references": [],
                "voice_directives": [],
                "planned_option_briefs": [
                    {
                        "option_number": 1,
                        "framing_mode": "contrarian_reframe",
                        "public_lane": "market_insight",
                        "primary_claim": "AI is not making every market meaner.",
                        "proof_packet": "Fusion Academy Dashboard Transformation -> territory coordination improved once outreach became clearer.",
                        "story_beat": "",
                    }
                ],
            },
        }

        result_payload = content_generation._build_local_codex_result_payload(
            job=job,
            options=[
                "Johnnie is building at the intersection of education, AI systems, entrepreneurship, and style.\n\nThe same tooling lands very differently when the operating playbook is clear."
            ],
            model="gpt-5.4-mini",
            raw_output='{\"options\":[]}',
            command_stdout="",
            command_stderr="",
        )

        lowered = result_payload["options"][0].lower()
        self.assertFalse(lowered.startswith("johnnie is"))
        self.assertIn("ai is not making every market meaner.", lowered)

    def test_local_codex_result_payload_strips_market_lane_house_lines(self) -> None:
        job = {
            "request_payload": {
                "topic": "ai is not making every market meaner",
                "audience": "tech_ai",
                "source_mode": "persona_only",
            },
            "context_packet": {
                "grounding_mode": "proof_ready",
                "persona_context_summary": "AI is not making every market meaner.",
                "examples_used": [],
                "primary_claims": [
                    "AI is not making every market meaner."
                ],
                "proof_packets": [
                    "Fusion Academy Dashboard Transformation -> territory coordination improved once outreach became clearer."
                ],
                "story_beats": [],
                "approved_references": [],
                "voice_directives": [],
                "planned_option_briefs": [
                    {
                        "option_number": 1,
                        "framing_mode": "contrarian_reframe",
                        "public_lane": "market_insight",
                        "primary_claim": "AI is not making every market meaner.",
                        "proof_packet": "Fusion Academy Dashboard Transformation -> territory coordination improved once outreach became clearer.",
                        "story_beat": "",
                    }
                ],
            },
        }

        result_payload = content_generation._build_local_codex_result_payload(
            job=job,
            options=[
                "ai is not making every market meaner.\n\nNot more reporting.\n\nClearer action.\n\nThe same tooling lands differently when buyer ownership is clear.\n\nThat is the operating model."
            ],
            model="gpt-5.4-mini",
            raw_output='{\"options\":[]}',
            command_stdout="",
            command_stderr="",
        )

        lowered = result_payload["options"][0].lower()
        self.assertNotIn("not more reporting.", lowered)
        self.assertNotIn("clearer action.", lowered)
        self.assertNotIn("that is the operating model.", lowered)
        self.assertTrue(result_payload["options"][0].startswith("AI is not making every market meaner."))

    def test_local_codex_result_payload_rewrites_audience_slug_and_house_scaffold(self) -> None:
        job = {
            "request_payload": {
                "topic": "workflow clarity",
                "audience": "tech_ai",
                "source_mode": "persona_only",
            },
            "context_packet": {
                "grounding_mode": "proof_ready",
                "persona_context_summary": "Workflow clarity gets stronger when one shared source of truth replaces scattered context.",
                "examples_used": [],
                "primary_claims": [
                    "Workflow clarity gets stronger when one shared source of truth replaces scattered context."
                ],
                "proof_packets": [
                    "Fusion Academy Dashboard Transformation -> territory coordination improved once outreach became clearer."
                ],
                "story_beats": [],
                "approved_references": [
                    "Fusion Academy Dashboard Transformation",
                    "territory coordination improved once outreach became clearer",
                ],
                "voice_directives": [],
                "planned_option_briefs": [
                    {
                        "option_number": 1,
                        "framing_mode": "operator_lesson",
                        "public_lane": "operator_lesson",
                        "primary_claim": "Workflow clarity gets stronger when one shared source of truth replaces scattered context.",
                        "proof_packet": "Fusion Academy Dashboard Transformation -> territory coordination improved once outreach became clearer.",
                        "story_beat": "",
                    }
                ],
            },
        }

        result_payload = content_generation._build_local_codex_result_payload(
            job=job,
            options=[
                "Operator lesson: workflow clarity stays fragile until tech_ai leads replace scattered context with one shared source of truth.\n\nThat is the operating model.\n\nFusion Academy Dashboard Transformation made territory coordination easier to trust.\n\nQuiet Inefficiency Cleanup is usually the real drag.\n\nOtherwise it's just another tab."
            ],
            model="gpt-5.4-mini",
            raw_output='{\"options\":[]}',
            command_stdout="",
            command_stderr="",
        )

        lowered = result_payload["options"][0].lower()
        self.assertNotIn("tech_ai", lowered)
        self.assertFalse(lowered.startswith("operator lesson:"))
        self.assertNotIn("that is the operating model.", lowered)
        self.assertNotIn("otherwise it's just another tab.", lowered)
        self.assertNotIn("quiet inefficiency cleanup", lowered)

    def test_local_codex_result_payload_strips_combined_house_paragraph_and_build_log_opener(self) -> None:
        job = {
            "request_payload": {
                "topic": "workflow clarity",
                "audience": "tech_ai",
                "source_mode": "persona_only",
            },
            "context_packet": {
                "grounding_mode": "proof_ready",
                "persona_context_summary": "Operator clarity gets stronger when one shared source of truth replaces scattered context.",
                "examples_used": [],
                "primary_claims": [
                    "Operator clarity gets stronger when one shared source of truth replaces scattered context.",
                    "If the workflow is unclear, AI just scales confusion.",
                ],
                "proof_packets": [
                    "Fusion Academy Dashboard Transformation -> Daily, weekly, monthly, quarterly, and yearly metrics were unified in one Salesforce dashboard; leadership engagement increased because execution was easier to see.",
                    "One shared source of truth made planning, execution, and follow-through easier to trust.",
                ],
                "story_beats": ["The real problem is usually quiet inefficiency, not obvious chaos."],
                "approved_references": [
                    "Fusion Academy Dashboard Transformation",
                    "One shared source of truth made planning, execution, and follow-through easier to trust.",
                ],
                "voice_directives": [],
                "planned_option_briefs": [
                    {
                        "option_number": 1,
                        "framing_mode": "warning",
                        "public_lane": "build_in_public",
                        "primary_claim": "If the workflow is unclear, AI just scales confusion.",
                        "proof_packet": "One shared source of truth made planning, execution, and follow-through easier to trust.",
                        "story_beat": "The real problem is usually quiet inefficiency, not obvious chaos.",
                    }
                ],
            },
        }

        result_payload = content_generation._build_local_codex_result_payload(
            job=job,
            options=[
                "Warning from the build log: if the workflow is unclear, AI just scales confusion.\n\nNot more reporting. Clearer action.\n\nOne shared source of truth made planning, execution, and follow-through easier to trust."
            ],
            model="gpt-5.4-mini",
            raw_output='{\"options\":[]}',
            command_stdout="",
            command_stderr="",
        )

        lowered = result_payload["options"][0].lower()
        self.assertNotIn("not more reporting.", lowered)
        self.assertNotIn("clearer action.", lowered)
        self.assertNotIn("warning from the build log", lowered)
        self.assertIn("One shared source of truth made planning, execution, and follow-through easier to trust.", result_payload["options"][0])

    def test_local_codex_result_payload_rewrites_systemy_public_phrases(self) -> None:
        job = {
            "request_payload": {
                "topic": "workflow clarity",
                "audience": "tech_ai",
                "source_mode": "persona_only",
            },
            "context_packet": {
                "grounding_mode": "proof_ready",
                "persona_context_summary": "AI helps when the workflow is coordinated, not improvised.",
                "examples_used": [],
                "primary_claims": [
                    "AI helps when the workflow is coordinated, not improvised."
                ],
                "proof_packets": [
                    "Fusion Academy Dashboard Transformation -> One shared operating view made priorities clearer, improved coordination, and made follow-through easier to trust."
                ],
                "story_beats": [],
                "approved_references": ["Fusion Academy Dashboard Transformation"],
                "voice_directives": [],
                "planned_option_briefs": [
                    {
                        "option_number": 1,
                        "framing_mode": "operator_lesson",
                        "public_lane": "operator_lesson",
                        "primary_claim": "AI helps when the workflow is coordinated, not improvised.",
                        "proof_packet": "Fusion Academy Dashboard Transformation -> One shared operating view made priorities clearer, improved coordination, and made follow-through easier to trust.",
                        "story_beat": "",
                    }
                ],
            },
        }

        result_payload = content_generation._build_local_codex_result_payload(
            job=job,
            options=[
                "Prompting without agent orchestration just recreates the mess you already have.\n\nThe Fusion Academy Dashboard Transformation worked because prompts were aimed into one Salesforce command center, not a dozen ad hoc outputs.\n\nThe operator lesson: map the system, then let automation run.\n\nThat is when the work slips."
            ],
            model="gpt-5.4-mini",
            raw_output='{\"options\":[]}',
            command_stdout="",
            command_stderr="",
        )

        lowered = result_payload["options"][0].lower()
        self.assertNotIn("agent orchestration", lowered)
        self.assertNotIn("salesforce command center", lowered)
        self.assertNotIn("the operator lesson:", lowered)
        self.assertNotIn("that is when the work slips.", lowered)
        self.assertIn("shared operating view", lowered)
        self.assertIn("fusion academy dashboard transformation makes this concrete.", lowered)

    def test_local_codex_result_payload_strips_stock_house_lines_for_market_claim_even_off_market_lane(self) -> None:
        job = {
            "request_payload": {
                "topic": "ai is not making every market meaner",
                "audience": "tech_ai",
                "source_mode": "persona_only",
            },
            "context_packet": {
                "grounding_mode": "proof_ready",
                "persona_context_summary": "AI is not making every market meaner.",
                "examples_used": [],
                "primary_claims": [
                    "AI is not making every market meaner."
                ],
                "proof_packets": [
                    "Fusion Academy Dashboard Transformation -> territory coordination improved once outreach became clearer."
                ],
                "story_beats": [],
                "approved_references": [],
                "voice_directives": [],
                "planned_option_briefs": [
                    {
                        "option_number": 2,
                        "framing_mode": "warning",
                        "public_lane": "build_in_public",
                        "primary_claim": "AI is not making every market meaner.",
                        "proof_packet": "Fusion Academy Dashboard Transformation -> territory coordination improved once outreach became clearer.",
                        "story_beat": "",
                    }
                ],
            },
        }

        result_payload = content_generation._build_local_codex_result_payload(
            job=job,
            options=[
                "AI is not making every market meaner.\n\nNot more reporting.\n\nClearer action.\n\nTeams that can see the field move faster.\n\nThat is the operating model."
            ],
            model="gpt-5.4-mini",
            raw_output='{\"options\":[]}',
            command_stdout="",
            command_stderr="",
        )

        lowered = result_payload["options"][0].lower()
        self.assertNotIn("not more reporting.", lowered)
        self.assertNotIn("clearer action.", lowered)
        self.assertNotIn("that is the operating model.", lowered)

    def test_local_codex_result_payload_drops_unapproved_named_reference_sentences(self) -> None:
        job = {
            "request_payload": {
                "topic": "ai is not making every market meaner",
                "audience": "tech_ai",
                "source_mode": "persona_only",
            },
            "context_packet": {
                "grounding_mode": "proof_ready",
                "persona_context_summary": "AI is not making every market meaner.",
                "examples_used": [],
                "primary_claims": [
                    "AI is not making every market meaner."
                ],
                "proof_packets": [
                    "Fusion Academy Dashboard Transformation -> territory coordination improved once outreach became clearer."
                ],
                "story_beats": [],
                "approved_references": [
                    "Fusion Academy Dashboard Transformation",
                    "territory coordination improved once outreach became clearer",
                ],
                "voice_directives": [],
                "planned_option_briefs": [
                    {
                        "option_number": 2,
                        "framing_mode": "operator_lesson",
                        "public_lane": "operator_lesson",
                        "primary_claim": "AI is not making every market meaner.",
                        "proof_packet": "Fusion Academy Dashboard Transformation -> territory coordination improved once outreach became clearer.",
                        "story_beat": "",
                    }
                ],
            },
        }

        result_payload = content_generation._build_local_codex_result_payload(
            job=job,
            options=[
                "AI is not making every market meaner.\n\nThat discipline came while Easy Outfit and the AI Clone were still learning on weaker, cheaper models.\n\nFusion Academy Dashboard Transformation kept territory coordination clear."
            ],
            model="gpt-5.4-mini",
            raw_output='{\"options\":[]}',
            command_stdout="",
            command_stderr="",
        )

        lowered = result_payload["options"][0].lower()
        self.assertNotIn("easy outfit", lowered)
        self.assertNotIn("ai clone", lowered)
        self.assertIn("territory coordination improved once outreach became clearer.", result_payload["options"][0])

    def test_local_codex_context_packet_prefers_topic_aligned_public_claims(self) -> None:
        fake_context = _fake_context()
        fake_context.primary_claims = [
            "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
            "Prompting alone is not an AI strategy.",
            "Johnnie is building at the intersection of education, AI systems, entrepreneurship, and style.",
        ]
        fake_context.raw_primary_claims = [
            "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
            "Johnnie is building at the intersection of education, AI systems, entrepreneurship, and style.",
        ]
        fake_context.public_safe_primary_claims = [
            {
                "raw_claim": "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone.",
                "public_claim": "Prompting plus agent orchestration is a stronger AI operating pattern than prompting alone.",
                "approval_status": "auto",
            }
        ]
        fake_context.proof_packets = [
            "Fusion Academy Dashboard Transformation -> territory coordination improved once outreach became clearer.",
            "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone -> Brain, Ops, daily briefs, planner, long-form routing, and content generation now depend on explicit handoffs, shared workspace state, and proof-aware prompts instead of isolated prompting.",
        ]
        fake_context.raw_story_beats = ["Quiet Inefficiency Cleanup."]
        fake_context.public_safe_story_beats = [
            {
                "raw_story_beat": "Quiet Inefficiency Cleanup.",
                "public_story_beat": "The real problem is usually quiet inefficiency, not obvious chaos.",
                "approval_status": "auto",
            }
        ]
        fake_context.topic_anchor_chunks = [
            {
                "chunk": "Johnnie is an AI practitioner, not just a passive user.",
                "metadata": {},
            },
            {
                "chunk": "AI is not making every market meaner.",
                "metadata": {},
            },
        ]
        fake_context.proof_anchor_chunks = [
            {
                "chunk": "Fusion Academy Dashboard Transformation -> territory coordination improved once outreach became clearer.",
                "metadata": {},
            },
            {
                "chunk": "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone. Evidence: Brain, Ops, daily briefs, planner, long-form routing, and content generation now depend on explicit handoffs, shared workspace state, and proof-aware prompts instead of isolated prompting.",
                "metadata": {},
            },
        ]
        request = content_generation.LocalCodexJobCreateRequest(
            user_id="johnnie_fields",
            topic="ai is not making every market meaner",
            context="Use the operator systems angle.",
            content_type="linkedin_post",
            category="value",
            tone="expert_direct",
            audience="tech_ai",
            source_mode="persona_only",
            workspace_slug="linkedin-content-os",
        )

        packet = content_generation._build_local_codex_context_packet(req=request, content_context=fake_context)

        self.assertEqual(packet["primary_claims"][0], "ai is not making every market meaner.")
        self.assertNotIn("Johnnie is building", " ".join(packet["primary_claims"]))
        self.assertEqual(packet["raw_primary_claims"][0], fake_context.raw_primary_claims[0])
        self.assertEqual(packet["public_safe_primary_claims"][0]["public_claim"], "Prompting plus agent orchestration is a stronger AI operating pattern than prompting alone.")
        self.assertTrue(all("daily briefs" not in item.lower() for item in packet["proof_packets"]))
        self.assertTrue(all("ai clone" not in item.lower() for item in packet["proof_packets"]))
        self.assertTrue(all("Johnnie is an AI practitioner" not in item for item in packet["topic_anchor_preview"]))
        self.assertEqual(packet["story_beats"], [])
        self.assertEqual(packet["raw_story_beats"][0], "Quiet Inefficiency Cleanup.")
        self.assertEqual(packet["public_safe_story_beats"][0]["public_story_beat"], "The real problem is usually quiet inefficiency, not obvious chaos.")

    def test_local_codex_primary_claims_drops_flat_topic_labels(self) -> None:
        claims = content_generation._local_codex_primary_claims(
            topic="workflow clarity",
            audience="tech_ai",
            primary_claims=[
                "workflow clarity.",
                "Operator clarity gets stronger when one shared source of truth replaces scattered context.",
                "Prompting plus agent orchestration is a stronger AI operating pattern than prompting alone.",
            ],
        )

        lowered = [claim.lower() for claim in claims]
        self.assertNotIn("workflow clarity.", lowered)
        self.assertIn(
            "operator clarity gets stronger when one shared source of truth replaces scattered context.",
            lowered,
        )

    def test_content_release_policy_generalizes_systemy_claims_and_tool_heavy_proof(self) -> None:
        claims = build_public_safe_primary_claims(
            raw_primary_claims=[
                "Johnnie treats prompting plus agent orchestration as a stronger AI operating pattern than prompting alone."
            ],
            content_type="linkedin_post",
            topic="workflow clarity",
            audience="tech_ai",
        )
        proofs = build_public_safe_proof_packets(
            proof_anchor_chunks=[{"metadata": {"artifact_backed": True}}],
            raw_proof_packets=[
                "Fusion Academy Dashboard Transformation -> Daily, weekly, monthly, quarterly, and yearly metrics were unified in one Salesforce dashboard; high-priority, active-pipeline, and gray-area outreach became clearer; territory coordination improved; meetings rose by more than 20%; referrals rose by more than 50%."
            ],
            content_type="linkedin_post",
            topic="workflow clarity",
            audience="tech_ai",
        )

        self.assertEqual(
            claims[0]["public_claim"],
            "AI helps when the workflow is coordinated, not improvised.",
        )
        self.assertEqual(
            proofs[0]["public_packet"],
            "Fusion Academy Dashboard Transformation -> One shared operating view made priorities clearer, improved coordination, and made follow-through easier to trust.",
        )

    def test_public_safe_proof_packets_drop_partial_source_fragment_labels(self) -> None:
        proofs = build_public_safe_proof_packets(
            proof_anchor_chunks=[{"metadata": {}}],
            raw_proof_packets=[
                "From surviving the. com crash to managing a gradual desktop to cloud transition -> Discipline and customer trust matter more than chasing every technology cycle."
            ],
            content_type="linkedin_post",
            topic="workflow clarity",
            audience="tech_ai",
        )

        self.assertEqual(len(proofs), 1)
        self.assertEqual(
            proofs[0]["public_packet"],
            "Discipline and customer trust matter more than chasing every technology cycle.",
        )

    def test_public_safe_proof_packets_strip_noisy_source_artifact_prefixes(self) -> None:
        proofs = build_public_safe_proof_packets(
            proof_anchor_chunks=[{"metadata": {}}],
            raw_proof_packets=[
                "From Pilot To Payoff 7 Pattern Matched Traits Of AI Systems That Actually Work P5Yznr8Duj4 · canon_bridge · 2 times more likely to be successful with AI because they're talking about it"
            ],
            content_type="linkedin_post",
            topic="workflow clarity",
            audience="tech_ai",
        )

        self.assertEqual(len(proofs), 1)
        self.assertEqual(
            proofs[0]["public_packet"],
            "2 times more likely to be successful with AI because they're talking about it.",
        )
        self.assertNotIn("p5yznr8duj4", proofs[0]["public_packet"].lower())
        self.assertNotIn("canon_bridge", proofs[0]["public_packet"].lower())

    def test_student_topic_anchor_gate_blocks_generic_business_proof(self) -> None:
        self.assertFalse(
            content_generation._passes_audience_anchor_gate(
                "Discipline and customer trust matter more than chasing every technology cycle.",
                "general",
                "twice exceptional prospective students",
            )
        )
        self.assertTrue(
            content_generation._passes_audience_anchor_gate(
                "Families trust the process more when reviewers can see both strengths and support needs.",
                "general",
                "twice exceptional prospective students",
            )
        )

    def test_public_safe_student_topic_rewrites_generic_business_claim_and_proof(self) -> None:
        claims = build_public_safe_primary_claims(
            raw_primary_claims=[
                "Discipline and customer trust matter more than chasing every technology cycle."
            ],
            content_type="linkedin_post",
            topic="twice exceptional prospective students",
            audience="general",
        )
        proofs = build_public_safe_proof_packets(
            proof_anchor_chunks=[{"metadata": {}}],
            raw_proof_packets=[
                "AJ -> Discipline and customer trust matter more than chasing every technology cycle."
            ],
            content_type="linkedin_post",
            topic="twice exceptional prospective students",
            audience="general",
        )

        self.assertEqual(
            claims[0]["public_claim"],
            "The right admissions system has to hold both a student's potential and their support needs at the same time.",
        )
        self.assertIn("family trust", proofs[0]["public_packet"].lower())
        self.assertNotIn("customer trust", proofs[0]["public_packet"].lower())

    def test_repair_weak_ranked_options_rebuilds_claim_led_option(self) -> None:
        brief = content_generation.ContentOptionBrief(
            option_number=3,
            framing_mode="contrarian_reframe",
            primary_claim="Operator clarity gets stronger when one shared source of truth replaces scattered context.",
            proof_packet="One shared source of truth made planning, execution, and follow-through easier to trust.",
            story_beat="The real problem is usually quiet inefficiency, not obvious chaos.",
            public_lane="market_insight",
        )

        weak_option = (
            "Fusion Academy Dashboard Transformation proved it: daily, weekly, monthly, quarterly, and yearly metrics "
            "collapsed into one Salesforce operating surface.\n\n"
            "Clarity has to come first."
        )
        weak_taste = content_generation.score_option_taste(
            weak_option,
            brief=brief,
            primary_claims=[brief.primary_claim],
            proof_packets=[brief.proof_packet],
            story_beats=[brief.story_beat],
        )

        repaired_options, repaired_tastes = content_generation._repair_weak_ranked_options(
            options=[weak_option],
            briefs=[brief],
            taste_scores=[weak_taste],
            topic="workflow clarity",
            audience="tech_ai",
            grounding_mode="proof_ready",
            primary_claims=[brief.primary_claim],
            proof_packets=[brief.proof_packet],
            story_beats=[brief.story_beat],
            approved_reference_terms=[],
        )

        lowered = repaired_options[0].lower()
        self.assertIn("operator clarity gets stronger", lowered)
        self.assertNotIn("salesforce operating surface", lowered)
        self.assertGreaterEqual(int(repaired_tastes[0]["overall"]), int(weak_taste["overall"]))

    def test_plan_content_option_briefs_prefers_labeled_proof_for_build_in_public_lane(self) -> None:
        briefs = content_generation.plan_content_option_briefs(
            primary_claims=[
                "Operator clarity gets stronger when one shared source of truth replaces scattered context.",
                "AI helps when the workflow is coordinated, not improvised.",
                "If the workflow is unclear, AI just scales confusion.",
            ],
            proof_packets=[
                "One shared source of truth made planning, execution, and follow-through easier to trust.",
                "Fusion Academy Dashboard Transformation -> One shared operating view made priorities clearer, improved coordination, and made follow-through easier to trust.",
            ],
            story_beats=["The real problem is usually quiet inefficiency, not obvious chaos."],
            framing_modes=["contrarian_reframe", "operator_lesson", "warning"],
            option_count=3,
        )

        self.assertEqual(briefs[0].public_lane, "market_insight")
        self.assertEqual(
            briefs[0].proof_packet,
            "One shared source of truth made planning, execution, and follow-through easier to trust.",
        )
        self.assertEqual(briefs[2].public_lane, "build_in_public")
        self.assertIn("Fusion Academy Dashboard Transformation ->", briefs[2].proof_packet)

    def test_repair_weak_ranked_options_repairs_mediocre_weakest_slot(self) -> None:
        brief = content_generation.ContentOptionBrief(
            option_number=3,
            framing_mode="warning",
            primary_claim="If the workflow is unclear, AI just scales confusion.",
            proof_packet="Fusion Academy Dashboard Transformation -> One shared operating view made priorities clearer, improved coordination, and made follow-through easier to trust.",
            story_beat="The real problem is usually quiet inefficiency, not obvious chaos.",
            public_lane="build_in_public",
        )
        weak_option = (
            "If the workflow is unclear, AI just scales confusion.\n\n"
            "So I build in public: hunt subtle friction and refuse to ship models until operator clarity is obvious.\n\n"
            "Clarity has to come first."
        )
        weak_taste = content_generation.score_option_taste(
            weak_option,
            brief=brief,
            primary_claims=[brief.primary_claim],
            proof_packets=[brief.proof_packet],
            story_beats=[brief.story_beat],
        )

        repaired_options, repaired_tastes = content_generation._repair_weak_ranked_options(
            options=["strong option", "solid option", weak_option],
            briefs=[
                content_generation.ContentOptionBrief(
                    option_number=1,
                    framing_mode="contrarian_reframe",
                    primary_claim="The edge comes from clarity, not from piling on more tools.",
                    proof_packet="One shared source of truth made planning, execution, and follow-through easier to trust.",
                    story_beat="",
                    public_lane="market_insight",
                ),
                content_generation.ContentOptionBrief(
                    option_number=2,
                    framing_mode="operator_lesson",
                    primary_claim="AI helps when the workflow is coordinated, not improvised.",
                    proof_packet="Fusion Academy Dashboard Transformation -> One shared operating view made priorities clearer, improved coordination, and made follow-through easier to trust.",
                    story_beat="",
                    public_lane="operator_lesson",
                ),
                brief,
            ],
            taste_scores=[
                {"overall": 95, "warnings": [], "strengths": []},
                {"overall": 88, "warnings": [], "strengths": []},
                weak_taste,
            ],
            topic="workflow clarity",
            audience="tech_ai",
            grounding_mode="proof_ready",
            primary_claims=[
                "The edge comes from clarity, not from piling on more tools.",
                "AI helps when the workflow is coordinated, not improvised.",
                brief.primary_claim,
            ],
            proof_packets=[
                "One shared source of truth made planning, execution, and follow-through easier to trust.",
                "Fusion Academy Dashboard Transformation -> One shared operating view made priorities clearer, improved coordination, and made follow-through easier to trust.",
                brief.proof_packet,
            ],
            story_beats=["", "", brief.story_beat],
            approved_reference_terms=["Fusion Academy Dashboard Transformation"],
        )

        self.assertNotIn("So I build in public", repaired_options[2])
        self.assertIn("Fusion Academy Dashboard Transformation", repaired_options[2])
        self.assertGreaterEqual(int(repaired_tastes[2]["overall"]), int(weak_taste["overall"]))

    def test_finalize_planned_options_reorders_existing_bridge_without_inventing_copy(self) -> None:
        brief = content_generation.ContentOptionBrief(
            option_number=3,
            framing_mode="warning",
            primary_claim="If the workflow is unclear, AI just scales confusion.",
            proof_packet="Fusion Academy Dashboard Transformation -> One shared operating view made priorities clearer, improved coordination, and made follow-through easier to trust.",
            story_beat="The real problem is usually quiet inefficiency, not obvious chaos.",
            public_lane="build_in_public",
        )
        option = (
            "If the workflow is unclear, AI just scales confusion.\n\n"
            "That is why workflow clarity has to be the gate.\n\n"
            "Fusion Academy Dashboard Transformation showed why: one shared operating view made priorities clearer, improved coordination, and made follow-through easier to trust.\n\n"
            "Clarity has to come first."
        )

        finalized = content_generation.finalize_planned_options(
            options=[option],
            briefs=[brief],
            grounding_mode="proof_ready",
        )[0]

        paragraphs = [segment.strip() for segment in finalized.split("\n\n") if segment.strip()]
        self.assertGreaterEqual(len(paragraphs), 3)
        self.assertIn("If the workflow is unclear, AI just scales confusion.", paragraphs[0])
        self.assertIn("Fusion Academy Dashboard Transformation", paragraphs[1])
        self.assertIn("workflow clarity has to be the gate", paragraphs[2].lower())
        self.assertGreaterEqual(len(paragraphs), 4)

    def test_finalize_planned_options_removes_malformed_reference_bridge_and_identity_scaffold(self) -> None:
        brief = content_generation.ContentOptionBrief(
            option_number=2,
            framing_mode="operator_lesson",
            primary_claim="AI should strengthen workflows without coming at the expense of customer trust.",
            proof_packet="AJ -> Discipline and customer trust matter more than chasing every technology cycle.",
            story_beat="Trust rises when people feel processed honestly instead of pushed through a script.",
            public_lane="operator_lesson",
        )
        option = (
            "I’m all-in on AI that strengthens workflows without bending the admissions trust contract because frontline credibility is the real moat.\n\n"
            "From surviving the makes this concrete.\n\n"
            "Education changed my own trajectory, so my education voice stays rooted in transformation and honest guidance rather than institutional worship.\n\n"
            "AJ’s guidance—use AI to enhance workflows but never at the expense of customer trust—became our checklist."
        )

        finalized = content_generation.finalize_planned_options(
            options=[option],
            briefs=[brief],
            grounding_mode="proof_ready",
        )[0]

        lowered = finalized.lower()
        self.assertNotIn("from surviving the makes this concrete", lowered)
        self.assertNotIn("institutional worship", lowered)

    def test_sanitize_public_output_drops_repeated_key_insight_scaffold_and_rewrites_ritual(self) -> None:
        brief = content_generation.ContentOptionBrief(
            option_number=3,
            framing_mode="build_in_public",
            primary_claim="AI is not making every market meaner.",
            proof_packet="Fusion Academy Dashboard Transformation -> One shared operating view made priorities clearer, improved coordination, and made follow-through easier to trust.",
            story_beat="The real problem is usually quiet inefficiency, not obvious chaos.",
            public_lane="build_in_public",
        )
        option = (
            "The key insight is that AI is not uniformly intensifying competition everywhere.\n\n"
            "AI isn't turning every market into a knife fight; it's widening the gap between teams with operator clarity and those still improvising.\n\n"
            "Fusion Academy Dashboard Transformation gave leadership one shared operating view, so priorities landed in the same order and coordination actually tightened.\n\n"
            "Operator clarity is still my primary build-in-public ritual because it’s the only thing I’ve seen AI reward consistently."
        )

        finalized = content_generation.finalize_planned_options(
            options=[option],
            briefs=[brief],
            grounding_mode="proof_ready",
        )[0]

        lowered = finalized.lower()
        self.assertNotIn("the key insight is that", lowered)
        self.assertIn("build-in-public habit", lowered)


class DirectContentGenerationGuardRouteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_runtime = os.environ.get("CONTENT_GENERATION_RUNTIME")
        self.previous_direct_enabled = os.environ.get("CONTENT_GENERATION_DIRECT_ROUTES_ENABLED")
        self.previous_direct_override = os.environ.get("CONTENT_GENERATION_DIRECT_OVERRIDE_TOKEN")
        os.environ["CONTENT_GENERATION_RUNTIME"] = "production"
        os.environ.pop("CONTENT_GENERATION_DIRECT_ROUTES_ENABLED", None)
        os.environ.pop("CONTENT_GENERATION_DIRECT_OVERRIDE_TOKEN", None)
        app = FastAPI()
        app.include_router(content_generation.router, prefix="/api/content-generation")
        self.client = TestClient(app)
        self.payload = {
            "user_id": "johnnie_fields",
            "topic": "workflow clarity",
            "context": "Use the operator angle.",
            "content_type": "linkedin_post",
            "category": "value",
            "tone": "expert_direct",
            "audience": "tech_ai",
            "source_mode": "persona_only",
        }

    def tearDown(self) -> None:
        if self.previous_runtime is None:
            os.environ.pop("CONTENT_GENERATION_RUNTIME", None)
        else:
            os.environ["CONTENT_GENERATION_RUNTIME"] = self.previous_runtime
        if self.previous_direct_enabled is None:
            os.environ.pop("CONTENT_GENERATION_DIRECT_ROUTES_ENABLED", None)
        else:
            os.environ["CONTENT_GENERATION_DIRECT_ROUTES_ENABLED"] = self.previous_direct_enabled
        if self.previous_direct_override is None:
            os.environ.pop("CONTENT_GENERATION_DIRECT_OVERRIDE_TOKEN", None)
        else:
            os.environ["CONTENT_GENERATION_DIRECT_OVERRIDE_TOKEN"] = self.previous_direct_override

    def test_generate_blocks_direct_route_in_production_by_default(self) -> None:
        response = self.client.post("/api/content-generation/generate", json=self.payload)

        self.assertEqual(response.status_code, 403)
        self.assertIn("/api/content-generation/codex-jobs", response.json()["detail"])

    def test_quick_generate_uses_same_production_guard(self) -> None:
        response = self.client.post(
            "/api/content-generation/quick-generate",
            params={"topic": "workflow clarity", "user_id": "johnnie_fields"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("/api/content-generation/codex-jobs", response.json()["detail"])

    def test_generate_allows_override_header_when_token_matches(self) -> None:
        os.environ["CONTENT_GENERATION_DIRECT_OVERRIDE_TOKEN"] = "allow-direct"
        expected = content_generation.ContentGenerationResponse(
            success=True,
            options=["Direct override path is enabled for this request."],
            persona_context="Workflow clarity beats prompting alone.",
            examples_used=[],
            diagnostics={"llm_provider_trace": [{"provider": "test", "actual_model": "test-model", "status": "success"}]},
        )

        with patch.object(content_generation, "run_content_generation", new=AsyncMock(return_value=expected)) as runner:
            response = self.client.post(
                "/api/content-generation/generate",
                headers={"X-Content-Generation-Direct-Override": "allow-direct"},
                json=self.payload,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["options"], ["Direct override path is enabled for this request."])
        runner.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
