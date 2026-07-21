from __future__ import annotations

import importlib
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.models import BrainLongFormIngestRequest, BrainSignalCreateRequest, BrainYouTubeWatchlistIngestRequest, PMCard
from app.security.execution_authorization import sign_execution_payload, verify_execution_payload
from app.services import brain_local_action_queue_service as queue_service


brain_routes = importlib.import_module("app.routes.brain")


def _signed_card(payload: dict, *, card_id: str = "brain-card-1") -> PMCard:
    now = datetime.now(timezone.utc)
    return PMCard(
        id=card_id,
        title="Brain local action",
        owner="Jean-Claude",
        status="todo",
        source="brain_local_action:signal_create",
        link_type="brain_local_action",
        payload=sign_execution_payload(card_id, payload),
        created_at=now,
        updated_at=now,
    )


class BrainLocalActionQueueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.secret_patch = patch.dict(os.environ, {"CONTROL_PLANE_JOB_SIGNING_SECRET": "test-signing-secret"})
        self.secret_patch.start()

    def tearDown(self) -> None:
        self.secret_patch.stop()

    def test_queue_creates_signed_bounded_allowlisted_pm_card(self) -> None:
        captured = []

        def fake_create(payload):
            captured.append(payload)
            return _signed_card(payload.payload)

        signal = BrainSignalCreateRequest(
            source_kind="manual",
            source_ref="manual-test-1",
            raw_summary="A bounded signal should execute only on the local host.",
        )
        with (
            patch.object(queue_service.pm_card_service, "find_active_card_by_trigger_key", return_value=None),
            patch.object(queue_service.pm_card_service, "create_card", side_effect=fake_create),
        ):
            card, disposition = queue_service.enqueue_brain_local_action(
                "signal_create",
                {"signal": signal.model_dump(mode="json", exclude_none=True)},
            )

        self.assertEqual(disposition, "queued")
        self.assertTrue(verify_execution_payload(card.id, card.payload))
        action = queue_service.validate_brain_local_action(card.payload["brain_local_action"])
        self.assertEqual(action["action"], "signal_create")
        self.assertEqual(set(action["parameters"]), {"signal"})
        execution = captured[0].payload["execution"]
        self.assertEqual(execution["execution_mode"], "brain_local_action")
        self.assertEqual(execution["assigned_runner"], "codex_workspace_execution")

    def test_duplicate_click_returns_existing_signed_card_without_create(self) -> None:
        signal = BrainSignalCreateRequest(source_kind="manual", raw_summary="The same click must remain idempotent.")
        action = queue_service.build_brain_local_action(
            "signal_create",
            {"signal": signal.model_dump(mode="json", exclude_none=True)},
        )
        trigger_key = f"brain-local-action:signal_create:{action['idempotency_key']}"
        existing = _signed_card(
            {
                "workspace_key": "shared_ops",
                "trigger_key": trigger_key,
                "brain_local_action": action,
                "execution": {
                    "state": "queued",
                    "execution_mode": "brain_local_action",
                    "target_agent": "Brain Local Action",
                },
            },
            card_id="existing-brain-card",
        )

        with (
            patch.object(queue_service.pm_card_service, "find_active_card_by_trigger_key", return_value=existing),
            patch.object(queue_service.pm_card_service, "create_card") as create_card,
        ):
            card, disposition = queue_service.enqueue_brain_local_action(
                "signal_create",
                {"signal": signal.model_dump(mode="json", exclude_none=True)},
            )

        self.assertEqual(disposition, "already_active")
        self.assertEqual(card.id, existing.id)
        create_card.assert_not_called()

    def test_retry_requeues_failed_active_card_instead_of_dead_ending(self) -> None:
        signal = BrainSignalCreateRequest(source_kind="manual", raw_summary="Retry this deterministic local action.")
        action = queue_service.build_brain_local_action(
            "signal_create",
            {"signal": signal.model_dump(mode="json", exclude_none=True)},
        )
        existing = _signed_card(
            {
                "workspace_key": "shared_ops",
                "trigger_key": f"brain-local-action:signal_create:{action['idempotency_key']}",
                "brain_local_action": action,
                "execution": {
                    "state": "failed",
                    "executor_status": "failed",
                    "executor_last_error": "temporary mirror failure",
                    "execution_mode": "brain_local_action",
                    "target_agent": "Brain Local Action",
                },
            },
            card_id="failed-brain-card",
        )

        def fake_update(card_id, update):
            self.assertEqual(card_id, existing.id)
            self.assertEqual(update.status, "todo")
            return existing.model_copy(update={"status": update.status, "payload": sign_execution_payload(card_id, update.payload)})

        with (
            patch.object(queue_service.pm_card_service, "find_active_card_by_trigger_key", return_value=existing),
            patch.object(queue_service.pm_card_service, "update_card", side_effect=fake_update) as update_card,
            patch.object(queue_service.pm_card_service, "create_card") as create_card,
        ):
            card, disposition = queue_service.enqueue_brain_local_action(
                "signal_create",
                {"signal": signal.model_dump(mode="json", exclude_none=True)},
            )

        self.assertEqual(disposition, "requeued")
        self.assertEqual(card.payload["execution"]["executor_status"], "queued")
        update_card.assert_called_once()
        create_card.assert_not_called()

    def test_rejects_unallowlisted_action_and_oversized_payload(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported Brain local action"):
            queue_service.build_brain_local_action("shell", {})

        with self.assertRaises(ValueError):
            queue_service.build_brain_local_action(
                "signal_create",
                {
                    "signal": {
                        "source_kind": "manual",
                        "raw_summary": "x" * (queue_service.BRAIN_LOCAL_ACTION_MAX_BYTES + 1),
                    }
                },
            )

    def test_youtube_job_read_reports_executor_failure_truthfully(self) -> None:
        request = BrainYouTubeWatchlistIngestRequest(url="https://www.youtube.com/watch?v=failed")
        action = queue_service.build_brain_local_action(
            "youtube_watchlist_ingest",
            {"request": request.model_dump(mode="json", exclude_none=True)},
        )
        failed = _signed_card(
            {
                "brain_local_action": action,
                "execution": {"state": "failed", "executor_status": "failed", "executor_last_error": "network"},
            },
            card_id="failed-youtube-card",
        ).model_copy(update={"status": "in_progress"})
        with patch.object(queue_service.pm_card_service, "list_cards", return_value=[failed]):
            jobs = queue_service.list_youtube_ingest_jobs()

        self.assertEqual(jobs[0]["status"], "failed")
        self.assertEqual(jobs[0]["error"], "network")

    def test_filesystem_heavy_routes_only_enqueue_signed_local_work(self) -> None:
        queued = _signed_card({"brain_local_action": queue_service.build_brain_local_action("refresh_persona_review", {})})
        with (
            patch.object(brain_routes, "enqueue_brain_local_action", return_value=(queued, "queued")) as enqueue,
            patch("app.services.brain_long_form_ingest_service.BrainLongFormIngestService.register_source") as direct_long_form,
            patch("app.services.youtube_watchlist_service._ingest_watchlist_video") as direct_youtube,
            patch("app.services.brain_signal_service.create_signal") as direct_signal,
        ):
            long_form = brain_routes.ingest_long_form(BrainLongFormIngestRequest(notes="A local source note."))
            youtube = brain_routes.queue_youtube_watchlist_ingest(
                BrainYouTubeWatchlistIngestRequest(url="https://www.youtube.com/watch?v=abc")
            )
            signal = brain_routes.post_brain_signal(
                BrainSignalCreateRequest(source_kind="manual", raw_summary="A local signal mutation.")
            )
            refresh = brain_routes.refresh_brain_persona_review()

        self.assertTrue(long_form["queued"])
        self.assertEqual(youtube["job_id"], queued.id)
        self.assertTrue(signal["queued"])
        self.assertTrue(refresh["queued"])
        self.assertEqual([call.args[0] for call in enqueue.call_args_list], [
            "long_form_ingest",
            "youtube_watchlist_ingest",
            "signal_create",
            "refresh_persona_review",
        ])
        direct_long_form.assert_not_called()
        direct_youtube.assert_not_called()
        direct_signal.assert_not_called()


if __name__ == "__main__":
    unittest.main()
