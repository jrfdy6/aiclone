from __future__ import annotations

import os
import tempfile
import unittest

from app.services.local_codex_generation_service import (
    claim_next_codex_job,
    complete_codex_job,
    create_codex_job,
    fail_codex_job,
    get_codex_job,
)


class LocalCodexGenerationServiceTest(unittest.TestCase):
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
