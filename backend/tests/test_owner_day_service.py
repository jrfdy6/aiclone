from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.services.integrated_system_store import IntegratedSystemStore
from app.services.integrated_memory_readiness_service import IntegratedMemoryReadinessService
from app.services.owner_day_service import OwnerDayService


BRIEFING = {
    'plain_language_title': 'Review a current executive scheduling question',
    'what_it_means': 'The underlying work needs an owner decision before any external change.',
    'why_now': 'The current executive standup carried the unresolved source card forward.',
    'workspace_goal': 'Keep the executive queue current and prevent obsolete work from recurring.',
    'recommended_next_action': 'Verify the current provider evidence before choosing a disposition.',
    'classification': 'owner decision',
    'current_evidence': ['The current standup references the exact PM card.'],
    'unknowns': ['Whether the old scheduling request is still relevant.'],
    'decision_options': ['Investigate', 'Defer', 'Close'],
}


def test_owner_day_is_idempotent_and_emits_dream_durable_event(tmp_path: Path) -> None:
    service = OwnerDayService(IntegratedSystemStore(tmp_path / 'system.sqlite3'))
    session = service.upsert_session(
        owner_calendar_date='2026-09-05',
        overview={'executive_first': True, 'sources': {'executive': {'status': 'healthy'}}},
    )
    resumed = service.upsert_session(
        owner_calendar_date='2026-09-05',
        overview={'sources': {'calendar': {'status': 'unavailable'}}},
    )
    assert resumed['session_id'] == session['session_id']
    assert resumed['overview']['sources']['executive']['status'] == 'healthy'
    action = service.add_action(
        session_id=session['session_id'], action_id='exec:real-item-1',
        workspace_key='shared_ops', title='Recognizable executive item',
        description='Bounded owner follow-through.',
        source={'source_type': 'executive_standup', 'cycle_id': 'daily-2026-09-03'},
        briefing=BRIEFING,
        next_step='Review the evidence.',
    )
    updated = service.update_action(
        action['action_id'], status='Completed', next_step=None,
        idempotency_key='owner-day-transition:exec:real-item-1:1',
        outcome={'what_happened': 'Reviewed evidence', 'involved': 'Owner and AI Clone', 'result': 'Accepted', 'next_step': 'Feed next Dream', 'evidence_basis': 'owner_attested'},
    )
    replay = service.update_action(
        action['action_id'], status='Completed', next_step=None,
        idempotency_key='owner-day-transition:exec:real-item-1:1',
        outcome={'what_happened': 'Reviewed evidence', 'involved': 'Owner and AI Clone', 'result': 'Accepted', 'next_step': 'Feed next Dream', 'evidence_basis': 'owner_attested'},
    )
    assert updated['status'] == replay['status'] == 'Completed'
    assert updated['briefing']['plain_language_title'] == BRIEFING['plain_language_title']
    with service.store.connection() as connection:
        row = connection.execute("SELECT event_id,event_type,payload_json FROM system_events WHERE idempotency_key=?", ('owner-day-transition:exec:real-item-1:1',)).fetchone()
    assert row['event_type'] == 'owner.day_action_updated'
    assert json.loads(row['payload_json'])['briefing'] == BRIEFING

    dream_now = datetime.now(timezone.utc) + timedelta(minutes=1)
    memory = IntegratedMemoryReadinessService(service.store)
    readiness = memory.run_readiness(
        cycle_id='next-dream-owner-day-test',
        retrieval_refresh=lambda: {
            'schema_version': 'codex_memory_index/v1',
            'status': 'ok',
            'files': 1,
            'last_sync_at': dream_now.isoformat(),
        },
        recall_search=lambda query: [{'path': 'SOURCE_OF_TRUTH.md', 'query': query}],
        now=dream_now,
    )
    assert readiness['status'] == 'ready'
    owner_memory = next(
        item for item in memory.list_retrievable_memory_entries()
        if item['source_event_id'] == row['event_id']
    )
    assert owner_memory['fact']['payload']['action_id'] == action['action_id']
    assert owner_memory['fact']['payload']['briefing'] == BRIEFING


def test_legacy_action_can_be_enriched_without_creating_owner_evidence(tmp_path: Path) -> None:
    service = OwnerDayService(IntegratedSystemStore(tmp_path / 'system.sqlite3'))
    session = service.upsert_session(owner_calendar_date='2026-09-05', overview={})
    with service.store.connection() as connection:
        connection.execute(
            "INSERT INTO owner_day_actions(action_id,session_id,workspace_key,title,description,source_json,status,created_at,updated_at) VALUES(?,?,?,?,?,?,'Open / Not reviewed',?,?)",
            ('legacy', session['session_id'], 'shared_ops', 'Opaque title', 'Opaque description', '{}', '2026-09-05T00:00:00Z', '2026-09-05T00:00:00Z'),
        )
    enriched = service.update_briefing('legacy', BRIEFING)
    assert enriched['briefing'] == BRIEFING
    with service.store.connection() as connection:
        assert connection.execute('SELECT COUNT(*) FROM system_events').fetchone()[0] == 0


def test_action_rejects_an_incomplete_owner_briefing(tmp_path: Path) -> None:
    service = OwnerDayService(IntegratedSystemStore(tmp_path / 'system.sqlite3'))
    session = service.upsert_session(owner_calendar_date='2026-09-05', overview={})
    with pytest.raises(ValueError, match='complete owner-day briefing'):
        service.add_action(
            session_id=session['session_id'], action_id='opaque', workspace_key='shared_ops',
            title='Internal filename', description='No useful explanation.', source={},
            briefing={'plain_language_title': 'Still incomplete'}, next_step=None,
        )
