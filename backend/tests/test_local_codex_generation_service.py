from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from app.services.local_codex_generation_service import (
    _load_jobs,
    claim_next_codex_job,
    complete_codex_job,
    create_codex_job,
    fail_codex_job,
    get_codex_job,
    read_job_artifact_content,
    write_job_artifact,
)


class LocalCodexGenerationServiceTest(unittest.TestCase):
    def test_load_jobs_prefers_db_store_when_available(self) -> None:
        expected = [{"id": "job-db-1", "status": "pending"}]
        with patch("app.services.local_codex_generation_service._maybe_pool", return_value=object()), patch(
            "app.services.local_codex_generation_service._load_jobs_from_db",
            return_value=expected,
        ) as loader:
            jobs = _load_jobs()

        self.assertEqual(jobs, expected)
        loader.assert_called_once()

    def test_write_job_artifact_persists_db_content_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            previous = os.environ.get("LOCAL_CODEX_JOB_STORE_DIR")
            os.environ["LOCAL_CODEX_JOB_STORE_DIR"] = tmp_dir
            try:
                with patch("app.services.local_codex_generation_service._maybe_pool", return_value=object()), patch(
                    "app.services.local_codex_generation_service._write_artifact_content_to_db"
                ) as writer:
                    artifact = write_job_artifact(
                        job_id="job-1",
                        kind="context_packet",
                        label="context-packet.json",
                        content='{"hello":"world"}\n',
                        filename="context-packet.json",
                        mime_type="application/json",
                    )
            finally:
                if previous is None:
                    os.environ.pop("LOCAL_CODEX_JOB_STORE_DIR", None)
                else:
                    os.environ["LOCAL_CODEX_JOB_STORE_DIR"] = previous

        writer.assert_called_once()
        self.assertEqual(artifact["job_id"], "job-1")
        self.assertEqual(artifact["kind"], "context_packet")

    def test_read_job_artifact_content_uses_db_store_before_file(self) -> None:
        with patch("app.services.local_codex_generation_service.list_job_artifacts", return_value=[{"artifact_id": "artifact-1"}]), patch(
            "app.services.local_codex_generation_service._maybe_pool",
            return_value=object(),
        ), patch(
            "app.services.local_codex_generation_service._read_artifact_content_from_db",
            return_value="persisted artifact content",
        ) as reader:
            content = read_job_artifact_content(job_id="job-1", artifact_id="artifact-1")

        self.assertEqual(content, "persisted artifact content")
        reader.assert_called_once()

    def test_create_claim_complete_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            previous = os.environ.get("LOCAL_CODEX_JOB_STORE_DIR")
            os.environ["LOCAL_CODEX_JOB_STORE_DIR"] = tmp_dir
            try:
                created = create_codex_job(
                    workspace_slug="linkedin-content-os",
                    requested_by="johnnie_fields",
                    request_payload={"topic": "workflow clarity"},
                    context_packet={"prompt": "write 3 options", "planned_option_briefs": []},
                    idempotency_key="abc123",
                )
                self.assertEqual(created["status"], "pending")

                fetched = get_codex_job(created["id"])
                self.assertIsNotNone(fetched)
                self.assertEqual(fetched["requested_by"], "johnnie_fields")

                claimed = claim_next_codex_job(worker_id="worker-1", workspace_slug="linkedin-content-os")
                self.assertIsNotNone(claimed)
                self.assertEqual(claimed["status"], "running")

                completed = complete_codex_job(
                    job_id=created["id"],
                    worker_id="worker-1",
                    result_payload={"success": True, "options": ["one", "two", "three"], "diagnostics": {}},
                )
                self.assertEqual(completed["status"], "completed")
                self.assertEqual(completed["claimed_by"], "worker-1")

                none_left = claim_next_codex_job(worker_id="worker-2", workspace_slug="linkedin-content-os")
                self.assertIsNone(none_left)
            finally:
                if previous is None:
                    os.environ.pop("LOCAL_CODEX_JOB_STORE_DIR", None)
                else:
                    os.environ["LOCAL_CODEX_JOB_STORE_DIR"] = previous

    def test_fail_job_records_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            previous = os.environ.get("LOCAL_CODEX_JOB_STORE_DIR")
            os.environ["LOCAL_CODEX_JOB_STORE_DIR"] = tmp_dir
            try:
                created = create_codex_job(
                    workspace_slug="linkedin-content-os",
                    requested_by="johnnie_fields",
                    request_payload={"topic": "operator insight"},
                    context_packet={"prompt": "write 3 options", "planned_option_briefs": []},
                    idempotency_key="def456",
                )
                failed = fail_codex_job(
                    job_id=created["id"],
                    worker_id="worker-1",
                    error_message="codex exec timed out",
                )
                self.assertEqual(failed["status"], "failed")
                self.assertIn("timed out", failed["error_message"])
            finally:
                if previous is None:
                    os.environ.pop("LOCAL_CODEX_JOB_STORE_DIR", None)
                else:
                    os.environ["LOCAL_CODEX_JOB_STORE_DIR"] = previous


if __name__ == "__main__":
    unittest.main()
