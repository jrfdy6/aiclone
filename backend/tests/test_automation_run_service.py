from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from app.models.automations import AutomationRun
from app.services import automation_run_service


def _participant_run(*, report_sha256: str = "a" * 64) -> AutomationRun:
    observed = datetime(2026, 8, 26, 20, 0, tzinfo=timezone.utc)
    return AutomationRun(
        id="participant-report-1",
        automation_id="standup_participant_report",
        automation_name="Standup Participant Report",
        source="local_launchd_registry",
        runtime="codex_exec",
        status="completed",
        delivered=False,
        delivery_channel="standup_transcript",
        run_at=observed,
        finished_at=observed,
        owner_agent="Jean-Claude",
        scope="workspace",
        workspace_key="fusion-os",
        action_required=False,
        metadata={"report_sha256": report_sha256},
    )


def _stored_tuple(run: AutomationRun) -> tuple:
    return (
        run.automation_id,
        run.automation_name,
        run.source,
        run.runtime,
        run.status,
        run.delivered,
        run.delivery_channel,
        run.delivery_target,
        run.run_at,
        run.finished_at,
        run.duration_ms,
        run.error,
        run.owner_agent,
        run.session_target,
        run.scope,
        run.workspace_key,
        run.action_required,
        run.metadata,
    )


class _Cursor:
    def __init__(self, existing: tuple) -> None:
        self.existing = existing
        self._next = None
        self.insert_attempted = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query: str, _params=()) -> None:
        normalized = " ".join(query.split())
        if normalized.startswith("SELECT pg_advisory_xact_lock"):
            self._next = None
        elif "FROM automation_run_daily_receipts" in normalized:
            self._next = None
        elif "FROM automation_runs" in normalized and "FOR UPDATE" in normalized:
            self._next = self.existing
        elif normalized.startswith("INSERT INTO automation_runs"):
            self.insert_attempted = True
            raise AssertionError("immutable replay must not update or insert")
        else:
            raise AssertionError(normalized)

    def fetchone(self):
        value = self._next
        self._next = None
        return value


class _Connection:
    def __init__(self, cursor: _Cursor) -> None:
        self._cursor = cursor
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self._cursor

    def commit(self) -> None:
        self.committed = True


class _Pool:
    def __init__(self, connection: _Connection) -> None:
        self._connection = connection

    @contextmanager
    def connection(self):
        yield self._connection


def test_identical_participant_report_replay_is_acknowledged_without_overwrite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _participant_run()
    cursor = _Cursor(_stored_tuple(run))
    connection = _Connection(cursor)
    monkeypatch.setattr(automation_run_service, "_get_pool", lambda: _Pool(connection))

    assert automation_run_service.upsert_runs([run]) == 1
    assert connection.committed is True
    assert cursor.insert_attempted is False


def test_conflicting_participant_report_replay_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored = _participant_run(report_sha256="a" * 64)
    incoming = _participant_run(report_sha256="b" * 64)
    cursor = _Cursor(_stored_tuple(stored))
    connection = _Connection(cursor)
    monkeypatch.setattr(automation_run_service, "_get_pool", lambda: _Pool(connection))

    with pytest.raises(
        automation_run_service.AutomationRunMirrorError,
        match="immutable",
    ):
        automation_run_service.upsert_runs([incoming])

    assert connection.committed is False
    assert cursor.insert_attempted is False
