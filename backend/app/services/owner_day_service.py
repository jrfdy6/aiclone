from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.models.owner_day import OWNER_DAY_STATUSES
from app.services.integrated_system_store import IntegratedSystemStore, _canonical_json


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OwnerDayService:
    """Durable owner-day read/write model over the existing event ledger."""

    def __init__(self, store: IntegratedSystemStore | None = None) -> None:
        self.store = store or IntegratedSystemStore()
        self.store.migrate()

    def upsert_session(self, *, owner_calendar_date: str, overview: dict[str, Any]) -> dict[str, Any]:
        date = str(owner_calendar_date or '').strip()
        if len(date) != 10:
            raise ValueError('owner_calendar_date must be YYYY-MM-DD')
        now = _now()
        session_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f'ai-clone:owner-day:{date}'))
        overview_json = _canonical_json(overview)
        with self.store.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            c.execute(
                "INSERT INTO owner_day_sessions(session_id,owner_calendar_date,status,overview_json,created_at,updated_at) VALUES(?,?, 'open',?,?,?) ON CONFLICT(owner_calendar_date) DO UPDATE SET overview_json=excluded.overview_json,updated_at=excluded.updated_at",
                (session_id, date, overview_json, now, now),
            )
            row = c.execute('SELECT * FROM owner_day_sessions WHERE owner_calendar_date=?', (date,)).fetchone()
            c.execute('COMMIT')
        return self._session(row)

    def get_session(self, owner_calendar_date: str) -> dict[str, Any] | None:
        with self.store.connection() as c:
            row = c.execute('SELECT * FROM owner_day_sessions WHERE owner_calendar_date=?', (owner_calendar_date,)).fetchone()
        return self._session(row) if row else None

    def add_action(self, **values: Any) -> dict[str, Any]:
        if values['action_id'].strip() == '' or values['workspace_key'].strip() == '':
            raise ValueError('action_id and workspace_key are required')
        now = _now()
        source_json = _canonical_json(values['source'])
        action_id = values['action_id'].strip()
        with self.store.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            c.execute(
                "INSERT INTO owner_day_actions(action_id,session_id,workspace_key,title,description,source_json,status,next_step,outcome_json,created_at,updated_at) VALUES(?,?,?,?,?,?,'Open / Not reviewed',?,NULL,?,?) ON CONFLICT(action_id) DO NOTHING",
                (action_id, values['session_id'], values['workspace_key'].strip(), values['title'][:300], values['description'][:2000], source_json, values.get('next_step'), now, now),
            )
            row = c.execute('SELECT * FROM owner_day_actions WHERE action_id=?', (action_id,)).fetchone()
            if not row:
                raise RuntimeError('owner-day action persistence failed')
            if row['session_id'] != values['session_id'] or row['source_json'] != source_json:
                raise ValueError('owner-day action idempotency conflict')
            c.execute('COMMIT')
        return self._action(row)

    def update_action(self, action_id: str, *, status: str, next_step: str | None, outcome: dict[str, Any] | None, idempotency_key: str) -> dict[str, Any]:
        if status not in OWNER_DAY_STATUSES:
            raise ValueError('unknown owner-day status')
        if status == 'Completed':
            required = {'what_happened', 'involved', 'result', 'evidence_basis'}
            if not outcome or not required.issubset(outcome) or outcome.get('evidence_basis') not in {'provider_verified','system_verified','owner_attested'}:
                raise ValueError('Completed requires a bounded outcome and evidence_basis')
        now = _now()
        # One transition gets one stable event identity. The read model and
        # append-only ledger commit together so a partial lifecycle write is
        # impossible.
        event_key = str(idempotency_key or '').strip()
        if not event_key or len(event_key) > 200:
            raise ValueError('idempotency_key is required')
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f'ai-clone:event:{event_key}'))
        event_payload = {
            'action_id': action_id, 'session_id': None, 'workspace_key': None,
            'status': status, 'next_step': next_step, 'outcome': outcome,
        }
        with self.store.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT * FROM owner_day_actions WHERE action_id=?', (action_id,)).fetchone()
            if not row:
                raise KeyError('unknown owner-day action')
            event_payload['session_id'] = row['session_id']
            event_payload['workspace_key'] = row['workspace_key']
            existing_event = c.execute('SELECT payload_json FROM system_events WHERE idempotency_key=?', (event_key,)).fetchone()
            if existing_event:
                existing_payload = json.loads(existing_event['payload_json'])
                if existing_payload.get('action_id') != action_id or existing_payload.get('status') != status:
                    raise ValueError('owner-day transition idempotency conflict')
                c.execute('COMMIT')
                return self._action(row)
            c.execute('UPDATE owner_day_actions SET status=?,next_step=?,outcome_json=?,updated_at=? WHERE action_id=?', (status, next_step, _canonical_json(outcome) if outcome else None, now, action_id))
            c.execute(
                "INSERT INTO system_events(event_id,event_type,aggregate_type,aggregate_id,occurred_at,actor_type,payload_json,provenance_json,artifact_refs_json,idempotency_key) VALUES (?,?,?,?,?,'owner_day',?,?, '[]',?) ON CONFLICT(idempotency_key) DO NOTHING",
                (event_id, 'owner.day_action_updated', 'owner_day_action', action_id, now,
                 _canonical_json(event_payload), _canonical_json({'source': 'start-my-day', 'source_action_id': action_id, 'prior_status': row['status']}), event_key),
            )
            c.execute('COMMIT')
        with self.store.connection() as c:
            updated = c.execute('SELECT * FROM owner_day_actions WHERE action_id=?', (action_id,)).fetchone()
        return self._action(updated)

    def list_actions(self, session_id: str) -> list[dict[str, Any]]:
        with self.store.connection() as c:
            rows = c.execute('SELECT * FROM owner_day_actions WHERE session_id=? ORDER BY CASE WHEN status=\'Open / Not reviewed\' THEN 0 ELSE 1 END, updated_at, action_id', (session_id,)).fetchall()
        return [self._action(row) for row in rows]

    @staticmethod
    def _session(row: Any) -> dict[str, Any]:
        return {**dict(row), 'overview': json.loads(row['overview_json'])}

    @staticmethod
    def _action(row: Any) -> dict[str, Any]:
        result = dict(row)
        result['source'] = json.loads(result.pop('source_json'))
        result['outcome'] = json.loads(result.pop('outcome_json')) if result.get('outcome_json') else None
        result.pop('outcome_json', None)
        return result
