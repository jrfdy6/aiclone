from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models import EmailMessage, EmailThread, EmailThreadDraftRequest
from app.services.email_drafting_bridge_service import build_email_drafting_packet
from app.services.email_ops_service import (
    _classify_thread,
    _default_draft_type,
    _hydrate_codex_job_result,
    _merge_live_thread_state,
    _read_threads,
    _write_threads,
    generate_draft,
    restore_auto_route,
    save_thread_draft,
    update_thread_draft_lifecycle,
)
from app.routes.content_generation import ContentGenerationResponse
from app.services.local_codex_generation_service import complete_codex_job, get_codex_job


def _sample_thread(*, subject: str, body_text: str, from_address: str, to_addresses: list[str], provider_labels: list[str] | None = None) -> EmailThread:
    now = datetime.now(timezone.utc)
    return EmailThread(
        id="thread-1",
        provider="gmail",
        provider_thread_id="thread-1",
        provider_labels=provider_labels or [],
        subject=subject,
        from_address=from_address,
        from_name=None,
        organization=None,
        to_addresses=to_addresses,
        messages=[
            EmailMessage(
                id="msg-1",
                direction="inbound",
                from_address=from_address,
                from_name=None,
                to_addresses=to_addresses,
                cc_addresses=[],
                subject=subject,
                body_text=body_text,
                received_at=now,
            )
        ],
        last_message_at=now,
        created_at=now,
        updated_at=now,
    )


class EmailOpsServiceTests(unittest.TestCase):
    def test_agc_requires_explicit_workspace_label(self) -> None:
        thread = _sample_thread(
            subject="Need help improving procurement workflow visibility",
            body_text="We want operational clarity and workflow modernization support for procurement operations.",
            from_address="operations@statecollege.edu",
            to_addresses=["neo512235@gmail.com"],
        )

        classified = _classify_thread(thread)

        self.assertEqual(classified.workspace_key, "shared_ops")
        self.assertEqual(classified.lane, "manual_review")
        self.assertIn("label_required:workspace/agc", classified.routing_reasons)

    def test_agc_routes_when_workspace_label_is_present(self) -> None:
        thread = _sample_thread(
            subject="Vendor onboarding package",
            body_text="Please review the reseller onboarding packet and next supplier steps.",
            from_address="partnerrelations@quantabio.com",
            to_addresses=["neo512235+agc-vendors@gmail.com"],
            provider_labels=["workspace/agc"],
        )

        classified = _classify_thread(thread)

        self.assertEqual(classified.workspace_key, "agc")
        self.assertEqual(classified.lane, "supplier_partner")
        self.assertIn("label:workspace/agc", classified.routing_reasons)

    def test_build_email_drafting_packet_is_thread_grounded(self) -> None:
        thread = _classify_thread(
            _sample_thread(
                subject="Family intake question for school placement support",
                body_text="We were referred for help finding the right school environment. What does your intake process look like?",
                from_address="parent.intake@example.org",
                to_addresses=["neo512235+fusion@gmail.com"],
            )
        )

        payload = EmailThreadDraftRequest()
        packet = build_email_drafting_packet(
            thread,
            payload=payload,
            draft_type=_default_draft_type(thread),
            generated_at=datetime.now(timezone.utc),
            signature_block="Fusion Team",
        )

        self.assertEqual(packet.get("draft_mode"), "email_reply")
        self.assertEqual(packet.get("draft_engine"), "template")
        self.assertEqual(packet.get("source_mode"), "email_thread_grounded")
        self.assertEqual(packet.get("workspace_key"), "fusion-os")
        self.assertEqual(packet.get("lane"), "primary")
        self.assertTrue(packet.get("latest_inbound_message"))
        self.assertTrue(packet.get("recent_thread_history"))
        self.assertIn("signature_block", packet)

    def test_generate_draft_persists_bridge_metadata_without_changing_template_flow(self) -> None:
        thread = _classify_thread(
            _sample_thread(
                subject="Vendor onboarding package",
                body_text="Please review the reseller onboarding packet and next supplier steps.",
                from_address="partnerrelations@quantabio.com",
                to_addresses=["neo512235+agc-vendors@gmail.com"],
                provider_labels=["workspace/agc"],
            )
        )

        from app.services import email_ops_service

        original_loader = email_ops_service._load_or_seed_threads
        original_writer = email_ops_service._write_threads
        try:
            email_ops_service._load_or_seed_threads = lambda: ([thread.model_copy(deep=True)], False)
            email_ops_service._write_threads = lambda threads: None
            response = asyncio.run(generate_draft(thread.id, EmailThreadDraftRequest()))
        finally:
            email_ops_service._load_or_seed_threads = original_loader
            email_ops_service._write_threads = original_writer

        self.assertEqual(response.draft_type, "qualify")
        self.assertEqual(response.draft_mode, "email_reply")
        self.assertEqual(response.draft_engine, "template")
        self.assertEqual(response.source_mode, "email_thread_grounded")
        self.assertEqual(response.thread.draft_engine, "template")
        self.assertEqual(response.thread.draft_source_mode, "email_thread_grounded")
        self.assertIsNone(response.thread.draft_job_id)
        self.assertEqual((response.thread.draft_audit or {}).get("selected_path"), "template")
        packet = (response.thread.draft_audit or {}).get("packet") or {}
        self.assertEqual(packet.get("thread_id"), thread.id)
        self.assertEqual(packet.get("workspace_key"), "agc")
        self.assertEqual(packet.get("draft_type"), "qualify")
        self.assertTrue(response.draft_body.startswith("Thank you for following up."))

    def test_restore_auto_route_clears_manual_override_and_reclassifies_thread(self) -> None:
        thread = _classify_thread(
            _sample_thread(
                subject="Family intake question for school placement support",
                body_text="We were referred for help finding the right school environment. What does your intake process look like?",
                from_address="parent.intake@example.org",
                to_addresses=["neo512235+fusion@gmail.com"],
            )
        )
        thread.manual_workspace_key = "feezie-os"
        thread.manual_lane = "primary"
        thread.manual_notes = "Temporary smoke override"
        thread = _classify_thread(thread)

        from app.services import email_ops_service

        original_loader = email_ops_service._load_or_seed_threads
        original_writer = email_ops_service._write_threads
        try:
            email_ops_service._load_or_seed_threads = lambda: ([thread.model_copy(deep=True)], False)
            email_ops_service._write_threads = lambda threads: None
            restored = restore_auto_route(thread.id)
        finally:
            email_ops_service._load_or_seed_threads = original_loader
            email_ops_service._write_threads = original_writer

        self.assertEqual(restored.workspace_key, "fusion-os")
        self.assertEqual(restored.lane, "primary")
        self.assertEqual(restored.last_route_source, "auto")
        self.assertIsNone(restored.manual_workspace_key)
        self.assertIsNone(restored.manual_lane)
        self.assertIsNone(restored.manual_notes)
        self.assertNotIn("manual_override", restored.routing_reasons)

    def test_read_threads_prefers_persisted_store_when_available(self) -> None:
        thread = _classify_thread(
            _sample_thread(
                subject="Family intake question for school placement support",
                body_text="We were referred for help finding the right school environment. What does your intake process look like?",
                from_address="parent.intake@example.org",
                to_addresses=["neo512235+fusion@gmail.com"],
            )
        )

        from app.services import email_ops_service

        original_loader = email_ops_service.load_persisted_threads
        with tempfile.TemporaryDirectory() as tmp_dir:
            original_cache = email_ops_service.EMAIL_THREADS_CACHE
            try:
                email_ops_service.load_persisted_threads = lambda: [thread.model_copy(deep=True)]
                email_ops_service.EMAIL_THREADS_CACHE = Path(tmp_dir) / "email_threads.json"
                email_ops_service.EMAIL_THREADS_CACHE.write_text("[]")
                loaded = _read_threads()
            finally:
                email_ops_service.load_persisted_threads = original_loader
                email_ops_service.EMAIL_THREADS_CACHE = original_cache

        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].workspace_key, "fusion-os")

    def test_write_threads_keeps_json_cache_and_updates_persisted_store(self) -> None:
        thread = _classify_thread(
            _sample_thread(
                subject="Family intake question for school placement support",
                body_text="We were referred for help finding the right school environment. What does your intake process look like?",
                from_address="parent.intake@example.org",
                to_addresses=["neo512235+fusion@gmail.com"],
            )
        )

        from app.services import email_ops_service

        captured: list[EmailThread] = []
        original_writer = email_ops_service.replace_persisted_threads
        with tempfile.TemporaryDirectory() as tmp_dir:
            original_cache = email_ops_service.EMAIL_THREADS_CACHE
            try:
                email_ops_service.replace_persisted_threads = lambda threads: captured.extend([item.model_copy(deep=True) for item in threads]) or True
                email_ops_service.EMAIL_THREADS_CACHE = Path(tmp_dir) / "email_threads.json"
                _write_threads([thread])
                payload = json.loads(email_ops_service.EMAIL_THREADS_CACHE.read_text())
            finally:
                email_ops_service.replace_persisted_threads = original_writer
                email_ops_service.EMAIL_THREADS_CACHE = original_cache

        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0].workspace_key, "fusion-os")
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["workspace_key"], "fusion-os")

    def test_generate_draft_uses_content_generation_for_eligible_feezie_thread(self) -> None:
        thread = _classify_thread(
            _sample_thread(
                subject="Podcast invitation and speaking collaboration",
                body_text="Would Johnnie be open to a podcast conversation about creator systems and visibility?",
                from_address="host@growthoperator.fm",
                to_addresses=["neo512235+feezie@gmail.com"],
            )
        )
        thread.needs_human = False
        thread.high_value = False
        thread.high_risk = False

        from app.services import email_ops_service

        original_loader = email_ops_service._load_or_seed_threads
        original_writer = email_ops_service._write_threads
        try:
            email_ops_service._load_or_seed_threads = lambda: ([thread.model_copy(deep=True)], False)
            email_ops_service._write_threads = lambda threads: None
            with patch.object(
                email_ops_service,
                "_run_content_generation_for_thread",
                return_value=(
                    ContentGenerationResponse(
                        success=True,
                        options=["Happy to continue the conversation and learn more about the format you have in mind."],
                        diagnostics={"source_mode": "email_thread_grounded"},
                    ),
                    {"content_type": "email_reply", "source_mode": "email_thread_grounded"},
                ),
            ):
                response = asyncio.run(
                    generate_draft(
                        thread.id,
                        EmailThreadDraftRequest(draft_engine="content_generation", source_mode="email_thread_grounded"),
                    )
                )
        finally:
            email_ops_service._load_or_seed_threads = original_loader
            email_ops_service._write_threads = original_writer

        self.assertEqual(response.draft_engine, "content_generation")
        self.assertEqual(response.source_mode, "email_thread_grounded")
        self.assertEqual((response.thread.draft_audit or {}).get("selected_path"), "content_generation")
        self.assertIn("Happy to continue the conversation", response.draft_body)
        self.assertIn("Johnnie", response.draft_body)

    def test_generate_draft_falls_back_when_content_generation_is_ineligible(self) -> None:
        thread = _classify_thread(
            _sample_thread(
                subject="Invoice overdue for shared tool subscription",
                body_text="Your April invoice is overdue. Please confirm remittance timing.",
                from_address="billing@saasvendor.io",
                to_addresses=["neo512235+ops@gmail.com"],
            )
        )

        from app.services import email_ops_service

        original_loader = email_ops_service._load_or_seed_threads
        original_writer = email_ops_service._write_threads
        try:
            email_ops_service._load_or_seed_threads = lambda: ([thread.model_copy(deep=True)], False)
            email_ops_service._write_threads = lambda threads: None
            response = asyncio.run(
                generate_draft(
                    thread.id,
                    EmailThreadDraftRequest(draft_engine="content_generation", source_mode="email_thread_grounded"),
                )
            )
        finally:
            email_ops_service._load_or_seed_threads = original_loader
            email_ops_service._write_threads = original_writer

        self.assertEqual(response.draft_engine, "content_generation")
        self.assertEqual((response.thread.draft_audit or {}).get("selected_path"), "template")
        self.assertEqual((response.thread.draft_audit or {}).get("generation_reason"), "workspace_not_enabled")
        self.assertTrue(response.draft_body.startswith("Thanks for reaching out."))

    def test_generate_draft_records_generation_error_when_provider_flow_fails(self) -> None:
        thread = _classify_thread(
            _sample_thread(
                subject="Podcast invitation and speaking collaboration",
                body_text="Would Johnnie be open to a podcast conversation about creator systems and visibility?",
                from_address="host@growthoperator.fm",
                to_addresses=["neo512235+feezie@gmail.com"],
            )
        )
        thread.needs_human = False
        thread.high_value = False
        thread.high_risk = False

        from app.services import email_ops_service

        original_loader = email_ops_service._load_or_seed_threads
        original_writer = email_ops_service._write_threads
        try:
            email_ops_service._load_or_seed_threads = lambda: ([thread.model_copy(deep=True)], False)
            email_ops_service._write_threads = lambda threads: None
            with patch.object(
                email_ops_service,
                "_run_content_generation_for_thread",
                side_effect=RuntimeError("Incorrect API key provided"),
            ):
                response = asyncio.run(
                    generate_draft(
                        thread.id,
                        EmailThreadDraftRequest(draft_engine="content_generation", source_mode="email_thread_grounded"),
                    )
                )
        finally:
            email_ops_service._load_or_seed_threads = original_loader
            email_ops_service._write_threads = original_writer

        self.assertEqual((response.thread.draft_audit or {}).get("selected_path"), "template_fallback")
        self.assertEqual((response.thread.draft_audit or {}).get("generation_reason"), "content_generation_error:RuntimeError")
        diagnostics = (response.thread.draft_audit or {}).get("generation_diagnostics") or {}
        self.assertIn("Incorrect API key provided", diagnostics.get("error", ""))
        self.assertTrue(diagnostics.get("fallback_triggered"))
        self.assertTrue(response.draft_body.startswith("Thanks for reaching out."))

    def test_generate_draft_queues_codex_job_for_eligible_thread(self) -> None:
        thread = _classify_thread(
            _sample_thread(
                subject="Podcast invitation and speaking collaboration",
                body_text="Would Johnnie be open to a podcast conversation about creator systems and visibility?",
                from_address="host@growthoperator.fm",
                to_addresses=["neo512235+feezie@gmail.com"],
            )
        )
        thread.needs_human = False
        thread.high_value = False
        thread.high_risk = False

        from app.services import email_ops_service

        original_loader = email_ops_service._load_or_seed_threads
        original_writer = email_ops_service._write_threads
        previous_store = os.environ.get("LOCAL_CODEX_JOB_STORE_DIR")
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.environ["LOCAL_CODEX_JOB_STORE_DIR"] = tmp_dir
            try:
                email_ops_service._load_or_seed_threads = lambda: ([thread.model_copy(deep=True)], False)
                email_ops_service._write_threads = lambda threads: None
                response = asyncio.run(
                    generate_draft(
                        thread.id,
                        EmailThreadDraftRequest(draft_engine="codex_job", source_mode="email_thread_grounded"),
                    )
                )
                self.assertEqual(response.draft_engine, "codex_job")
                self.assertEqual(response.thread.draft_engine, "codex_job")
                self.assertEqual((response.thread.draft_audit or {}).get("selected_path"), "codex_job_pending")
                self.assertTrue(response.thread.draft_job_id)
                self.assertEqual(response.draft_body, "")
                queued_job = get_codex_job(str(response.thread.draft_job_id))
                self.assertIsNotNone(queued_job)
                self.assertEqual(queued_job["status"], "pending")
                self.assertEqual(queued_job["workspace_slug"], "email-drafts")
                self.assertEqual((queued_job.get("request_payload") or {}).get("content_type"), "email_reply")
                self.assertEqual((queued_job.get("context_packet") or {}).get("expected_option_count"), 1)
            finally:
                email_ops_service._load_or_seed_threads = original_loader
                email_ops_service._write_threads = original_writer
                if previous_store is None:
                    os.environ.pop("LOCAL_CODEX_JOB_STORE_DIR", None)
                else:
                    os.environ["LOCAL_CODEX_JOB_STORE_DIR"] = previous_store

    def test_hydrate_codex_job_result_applies_completed_email_draft(self) -> None:
        now = datetime.now(timezone.utc)
        thread = _classify_thread(
            _sample_thread(
                subject="Podcast invitation and speaking collaboration",
                body_text="Would Johnnie be open to a podcast conversation about creator systems and visibility?",
                from_address="host@growthoperator.fm",
                to_addresses=["neo512235+feezie@gmail.com"],
            )
        )
        thread.needs_human = False
        thread.high_value = False
        thread.high_risk = False
        thread.draft_engine = "codex_job"
        thread.draft_mode = "email_reply"
        thread.draft_type = "acknowledge"
        thread.draft_subject = f"Re: {thread.subject}"
        thread.draft_job_id = None
        thread.draft_audit = {"selected_path": "codex_job_pending"}

        previous_store = os.environ.get("LOCAL_CODEX_JOB_STORE_DIR")
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.environ["LOCAL_CODEX_JOB_STORE_DIR"] = tmp_dir
            try:
                from app.services.local_codex_generation_service import create_codex_job

                job = create_codex_job(
                    workspace_slug="email-drafts",
                    requested_by="johnnie_fields",
                    request_payload={"content_type": "email_reply", "source_mode": "email_thread_grounded"},
                    context_packet={
                        "job_kind": "email_draft",
                        "thread_id": thread.id,
                        "requested_model": "gpt-5.4-mini",
                        "signature_block": "Johnnie",
                    },
                    idempotency_key="email-codex-job",
                )
                thread.draft_job_id = str(job["id"])
                completed = complete_codex_job(
                    job_id=str(job["id"]),
                    worker_id="local-bridge",
                    result_payload={
                        "success": True,
                        "options": ["Happy to continue the conversation and learn more about the format you have in mind."],
                        "diagnostics": {
                            "grounding_mode": "email_thread_grounded",
                            "generation_strategy": "codex_terminal",
                        },
                    },
                )
                self.assertEqual(completed["status"], "completed")
                hydrated, changed = _hydrate_codex_job_result(thread)
                self.assertTrue(changed)
                self.assertIsNone(hydrated.draft_job_id)
                self.assertEqual((hydrated.draft_audit or {}).get("selected_path"), "codex_job")
                self.assertIn("Happy to continue the conversation", hydrated.draft_body or "")
                self.assertIn("Johnnie", hydrated.draft_body or "")
                self.assertIsNotNone(hydrated.draft_generated_at)
            finally:
                if previous_store is None:
                    os.environ.pop("LOCAL_CODEX_JOB_STORE_DIR", None)
                else:
                    os.environ["LOCAL_CODEX_JOB_STORE_DIR"] = previous_store

    def test_save_thread_draft_persists_provider_draft_metadata(self) -> None:
        thread = _classify_thread(
            _sample_thread(
                subject="Family intake question for school placement support",
                body_text="What does your intake process look like?",
                from_address="parent.intake@example.org",
                to_addresses=["neo512235+fusion@gmail.com"],
            )
        )
        thread.provider = "gmail"
        thread.provider_thread_id = "gmail-thread-1"
        thread.draft_subject = "Re: Family intake question for school placement support"
        thread.draft_body = "Happy to explain the intake process and next steps."
        thread.draft_engine = "content_generation"
        thread.draft_audit = {"selected_path": "content_generation"}

        from app.services import email_ops_service

        original_loader = email_ops_service._load_or_seed_threads
        original_writer = email_ops_service._write_threads
        try:
            email_ops_service._load_or_seed_threads = lambda: ([thread.model_copy(deep=True)], False)
            email_ops_service._write_threads = lambda threads: None
            with patch.object(
                email_ops_service,
                "save_gmail_draft",
                return_value={"action": "created", "draft_id": "gmail-draft-1", "thread_id": "gmail-thread-1", "message_id": "gmail-msg-1"},
            ):
                response = save_thread_draft(thread.id)
        finally:
            email_ops_service._load_or_seed_threads = original_loader
            email_ops_service._write_threads = original_writer

        self.assertEqual(response.provider_draft_id, "gmail-draft-1")
        self.assertEqual(response.provider_draft_status, "saved")
        self.assertEqual(response.thread.provider_draft_status, "saved")
        self.assertEqual(response.thread.provider_draft_id, "gmail-draft-1")
        provider_persist = (response.thread.draft_audit or {}).get("provider_persist") or {}
        self.assertEqual(provider_persist.get("provider"), "gmail")
        self.assertEqual(provider_persist.get("action"), "created")

    def test_clear_local_draft_cancels_pending_codex_job_and_preserves_provider_link(self) -> None:
        thread = _classify_thread(
            _sample_thread(
                subject="Podcast invitation and speaking collaboration",
                body_text="Would Johnnie be open to a podcast conversation about creator systems?",
                from_address="host@growthoperator.fm",
                to_addresses=["neo512235+feezie@gmail.com"],
            )
        )
        thread.workspace_key = "feezie-os"
        thread.lane = "primary"
        thread.needs_human = False
        thread.status = "waiting"
        thread.provider_draft_id = "gmail-draft-queued"
        thread.provider_draft_status = "saved"
        thread.draft_engine = "codex_job"
        thread.draft_subject = f"Re: {thread.subject}"
        thread.draft_audit = {"selected_path": "codex_job_pending"}

        from app.services import email_ops_service

        original_loader = email_ops_service._load_or_seed_threads
        original_writer = email_ops_service._write_threads
        previous_store = os.environ.get("LOCAL_CODEX_JOB_STORE_DIR")
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.environ["LOCAL_CODEX_JOB_STORE_DIR"] = tmp_dir
            try:
                from app.services.local_codex_generation_service import create_codex_job

                job = create_codex_job(
                    workspace_slug="email-drafts",
                    requested_by="johnnie_fields",
                    request_payload={"content_type": "email_reply", "source_mode": "email_thread_grounded"},
                    context_packet={"job_kind": "email_draft", "thread_id": thread.id},
                    idempotency_key="email-lifecycle-clear-local",
                )
                thread.draft_job_id = str(job["id"])
                email_ops_service._load_or_seed_threads = lambda: ([thread.model_copy(deep=True)], False)
                email_ops_service._write_threads = lambda threads: None

                updated, message = update_thread_draft_lifecycle(thread.id, action="clear_local_draft")
                canceled_job = get_codex_job(str(job["id"]))
            finally:
                email_ops_service._load_or_seed_threads = original_loader
                email_ops_service._write_threads = original_writer
                if previous_store is None:
                    os.environ.pop("LOCAL_CODEX_JOB_STORE_DIR", None)
                else:
                    os.environ["LOCAL_CODEX_JOB_STORE_DIR"] = previous_store

        self.assertEqual(message, "Local draft cleared.")
        self.assertIsNone(updated.draft_body)
        self.assertIsNone(updated.draft_job_id)
        self.assertIsNone(updated.draft_subject)
        self.assertEqual(updated.provider_draft_id, "gmail-draft-queued")
        self.assertEqual(updated.provider_draft_status, "saved")
        self.assertEqual(updated.status, "drafted")
        lifecycle = ((updated.draft_audit or {}).get("lifecycle") or {})
        self.assertEqual(lifecycle.get("last_action"), "clear_local_draft")
        details = lifecycle.get("details") or {}
        self.assertEqual(details.get("job_status"), "canceled")
        self.assertEqual((canceled_job or {}).get("status"), "canceled")

    def test_unlink_provider_draft_preserves_local_draft(self) -> None:
        thread = _classify_thread(
            _sample_thread(
                subject="Family intake question for school placement support",
                body_text="What does your intake process look like?",
                from_address="parent.intake@example.org",
                to_addresses=["neo512235+fusion@gmail.com"],
            )
        )
        thread.provider = "gmail"
        thread.provider_thread_id = "gmail-thread-1"
        thread.draft_subject = "Re: Family intake question for school placement support"
        thread.draft_body = "Happy to explain the intake process and next steps."
        thread.draft_engine = "content_generation"
        thread.draft_audit = {
            "selected_path": "content_generation",
            "provider_persist": {"provider": "gmail", "draft_id": "gmail-draft-1"},
        }
        thread.provider_draft_id = "gmail-draft-1"
        thread.provider_draft_status = "saved"

        from app.services import email_ops_service

        original_loader = email_ops_service._load_or_seed_threads
        original_writer = email_ops_service._write_threads
        try:
            email_ops_service._load_or_seed_threads = lambda: ([thread.model_copy(deep=True)], False)
            email_ops_service._write_threads = lambda threads: None
            updated, message = update_thread_draft_lifecycle(thread.id, action="unlink_provider_draft")
        finally:
            email_ops_service._load_or_seed_threads = original_loader
            email_ops_service._write_threads = original_writer

        self.assertEqual(message, "Gmail draft link cleared.")
        self.assertEqual(updated.draft_body, "Happy to explain the intake process and next steps.")
        self.assertIsNone(updated.provider_draft_id)
        self.assertIsNone(updated.provider_draft_status)
        self.assertEqual(updated.status, "drafted")
        self.assertNotIn("provider_persist", updated.draft_audit or {})
        self.assertEqual((((updated.draft_audit or {}).get("lifecycle") or {}).get("last_action")), "unlink_provider_draft")

    def test_clear_all_draft_state_removes_local_and_provider_state(self) -> None:
        thread = _classify_thread(
            _sample_thread(
                subject="Family intake question for school placement support",
                body_text="What does your intake process look like?",
                from_address="parent.intake@example.org",
                to_addresses=["neo512235+fusion@gmail.com"],
            )
        )
        thread.provider = "gmail"
        thread.provider_thread_id = "gmail-thread-1"
        thread.draft_subject = "Re: Family intake question for school placement support"
        thread.draft_body = "Happy to explain the intake process and next steps."
        thread.draft_engine = "template"
        thread.draft_audit = {"selected_path": "template", "provider_persist": {"provider": "gmail"}}
        thread.provider_draft_id = "gmail-draft-1"
        thread.provider_draft_status = "saved"
        thread.status = "drafted"

        from app.services import email_ops_service

        original_loader = email_ops_service._load_or_seed_threads
        original_writer = email_ops_service._write_threads
        try:
            email_ops_service._load_or_seed_threads = lambda: ([thread.model_copy(deep=True)], False)
            email_ops_service._write_threads = lambda threads: None
            updated, message = update_thread_draft_lifecycle(thread.id, action="clear_all_draft_state")
        finally:
            email_ops_service._load_or_seed_threads = original_loader
            email_ops_service._write_threads = original_writer

        self.assertEqual(message, "Local draft and Gmail draft link cleared.")
        self.assertIsNone(updated.draft_body)
        self.assertIsNone(updated.provider_draft_id)
        self.assertEqual(updated.status, "routed")
        lifecycle = ((updated.draft_audit or {}).get("lifecycle") or {})
        self.assertEqual(lifecycle.get("last_action"), "clear_all_draft_state")

    def test_merge_live_thread_state_preserves_local_draft_metadata(self) -> None:
        now = datetime.now(timezone.utc)
        existing = EmailThread(
            id="gmail-thread-1",
            provider="gmail",
            provider_thread_id="gmail-thread-1",
            workspace_key="fusion-os",
            lane="primary",
            status="drafted",
            subject="Family intake question",
            from_address="parent.intake@example.org",
            to_addresses=["neo512235+fusion@gmail.com"],
            confidence_score=0.92,
            needs_human=False,
            high_value=False,
            high_risk=False,
            sla_at_risk=False,
            routing_reasons=["alias:fusion"],
            messages=[
                EmailMessage(
                    id="msg-1",
                    direction="inbound",
                    from_address="parent.intake@example.org",
                    to_addresses=["neo512235+fusion@gmail.com"],
                    cc_addresses=[],
                    subject="Family intake question",
                    body_text="What does your intake process look like?",
                    received_at=now,
                )
            ],
            draft_subject="Re: Family intake question",
            draft_body="Saved local draft",
            draft_engine="content_generation",
            draft_generated_at=now,
            provider_draft_id="gmail-draft-1",
            provider_draft_status="saved",
            provider_draft_saved_at=now,
            last_message_at=now,
            created_at=now,
            updated_at=now,
        )
        live = existing.model_copy(
            deep=True,
            update={
                "draft_subject": None,
                "draft_body": None,
                "draft_engine": None,
                "provider_draft_id": None,
                "provider_draft_status": None,
            },
        )

        merged = _merge_live_thread_state([existing], [live])

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].draft_body, "Saved local draft")
        self.assertEqual(merged[0].provider_draft_id, "gmail-draft-1")
        self.assertEqual(merged[0].provider_draft_status, "saved")


if __name__ == "__main__":
    unittest.main()
