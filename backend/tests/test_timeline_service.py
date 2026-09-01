from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from app.services import timeline_service as service


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


class _Cursor:
    def __init__(self, batches: list[list[dict]]) -> None:
        self._batches = batches
        self._index = -1

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, _query, _params) -> None:
        self._index += 1

    def fetchall(self):
        return self._batches[self._index]


class _Connection:
    def __init__(self, batches: list[list[dict]]) -> None:
        self._batches = batches

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self, **_kwargs):
        return _Cursor(self._batches)


class _Pool:
    def __init__(self, batches: list[list[dict]]) -> None:
        self._batches = batches

    def connection(self):
        return _Connection(self._batches)


def test_timeline_separates_meeting_evaluation_and_unverified_storage_time() -> None:
    meeting_payload = {
        "record_kind": "standup",
        "meeting_held": True,
        "evaluation_only": False,
        "observed_at": "2026-08-26T12:00:00Z",
        "meeting_evidence": {"schema_version": "standup_meeting_evidence/v1"},
    }
    evaluation_payload = {
        "record_kind": "workspace_cycle_plan",
        "meeting_held": False,
        "evaluation_only": True,
        "observed_at": "2026-08-26T13:00:00Z",
    }
    unverified_payload = {
        "record_kind": "standup",
        "meeting_held": True,
        "evaluation_only": False,
    }
    standups = [
        {
            "id": "late-meeting-write",
            "owner": "Jean-Claude",
            "workspace_key": "agc",
            "created_at": _utc("2026-08-27T12:00:00Z"),
            "status": "completed",
            "source": "standup_agent_meeting",
            "payload": meeting_payload,
        },
        {
            "id": "cycle-evaluation",
            "owner": "Jean-Claude",
            "workspace_key": "agc",
            "created_at": _utc("2026-08-26T13:01:00Z"),
            "status": "completed",
            "source": "standup_prep",
            "payload": evaluation_payload,
        },
        {
            "id": "unverified",
            "owner": "Legacy",
            "workspace_key": "agc",
            "created_at": _utc("2026-08-25T11:00:00Z"),
            "status": "completed",
            "source": "legacy_writer",
            "payload": unverified_payload,
        },
    ]
    pool = _Pool([[], standups, []])

    with patch.object(service, "get_pool", return_value=pool), patch.object(
        service,
        "is_verified_meeting_record",
        side_effect=lambda payload, **_kwargs: payload is meeting_payload,
    ):
        events = service.list_events(limit=10)

    by_id = {event.id: event for event in events}
    meeting = by_id["standup::late-meeting-write"]
    evaluation = by_id["cycle_evaluation::cycle-evaluation"]
    unverified = by_id["coordination_record::unverified"]
    assert meeting.type == "standup"
    assert meeting.occurred_at == _utc("2026-08-26T12:00:00Z")
    assert meeting.payload["persisted_at"] == "2026-08-27T12:00:00Z"
    assert evaluation.type == "workspace_cycle_evaluation"
    assert evaluation.payload["timestamp_meaning"] == "workspace_evaluation_observed_at"
    assert unverified.type == "unverified_standup_record"
    assert unverified.payload["timestamp_meaning"] == "persistence_created_at_reference_only"
