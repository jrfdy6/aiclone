from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes import content_generation
from app.services.content_generation_context_service import ContentGenerationContext


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
        content_reservoir_chunks=[],
    )


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
        with patch.object(content_generation, "build_content_generation_context", return_value=_fake_context()):
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
                "model": "gpt-5.1-codex",
                "options": [
                    "Workflow clarity is not a nice-to-have. It is the difference between prompting and operating.",
                    "Prompting alone sounds smart until the handoff breaks. That is where workflow clarity starts to matter.",
                    "Most AI advice stops at the prompt. Real operator work starts at the workflow.",
                ],
                "raw_output": "{\"options\":[]}",
            },
        )
        self.assertEqual(complete_response.status_code, 200)
        self.assertEqual(complete_response.json()["status"], "completed")
        self.assertEqual(len(complete_response.json()["result"]["options"]), 3)

        status_response = self.client.get(f"/api/content-generation/codex-jobs/{job_id}")
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], "completed")
        self.assertEqual(
            status_response.json()["result"]["diagnostics"]["llm_provider_trace"][0]["provider"],
            "codex_terminal",
        )


if __name__ == "__main__":
    unittest.main()
