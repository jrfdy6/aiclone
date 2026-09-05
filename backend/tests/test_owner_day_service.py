from __future__ import annotations

from pathlib import Path

from app.services.integrated_system_store import IntegratedSystemStore
from app.services.owner_day_service import OwnerDayService


def test_owner_day_is_idempotent_and_emits_dream_durable_event(tmp_path: Path) -> None:
    service = OwnerDayService(IntegratedSystemStore(tmp_path / 'system.sqlite3'))
    session = service.upsert_session(owner_calendar_date='2026-09-05', overview={'executive_first': True})
    action = service.add_action(
        session_id=session['session_id'], action_id='exec:real-item-1',
        workspace_key='shared_ops', title='Recognizable executive item',
        description='Bounded owner follow-through.',
        source={'source_type': 'executive_standup', 'cycle_id': 'daily-2026-09-03'},
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
    with service.store.connection() as connection:
        row = connection.execute("SELECT event_type,payload_json FROM system_events WHERE idempotency_key=?", ('owner-day-transition:exec:real-item-1:1',)).fetchone()
    assert row['event_type'] == 'owner.day_action_updated'
