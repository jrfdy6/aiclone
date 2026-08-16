from __future__ import annotations

import json
from typing import Optional

try:
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
except Exception:  # pragma: no cover
    dict_row = None  # type: ignore
    Jsonb = None  # type: ignore

try:
    from app.models import EmailThread
    from app.services.open_brain_db import get_pool
except Exception:  # pragma: no cover
    EmailThread = None  # type: ignore
    get_pool = None  # type: ignore


def _maybe_pool():
    if get_pool is None or dict_row is None or Jsonb is None:
        return None
    try:
        return get_pool()
    except Exception:
        return None


def _provider_key(thread: EmailThread) -> str:
    if thread.provider == "gmail" and thread.provider_thread_id:
        return f"gmail:{thread.provider_thread_id}"
    return f"{thread.provider}:{thread.id}"


def _serialize_thread(thread: EmailThread) -> dict:
    return json.loads(thread.model_dump_json())


def _deserialize_thread(payload: object) -> Optional[EmailThread]:
    if EmailThread is None or not isinstance(payload, dict):
        return None
    try:
        return EmailThread(**payload)
    except Exception:
        return None


def load_persisted_threads() -> Optional[list[EmailThread]]:
    pool = _maybe_pool()
    if pool is None:
        return None
    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT provider_key, state
                FROM email_thread_state
                ORDER BY updated_at DESC
                """
            )
            rows = cur.fetchall() or []
    threads: list[EmailThread] = []
    for row in rows:
        thread = _deserialize_thread(row.get("state"))
        if thread is not None:
            threads.append(thread)
    return threads


def replace_persisted_threads(threads: list[EmailThread]) -> bool:
    pool = _maybe_pool()
    if pool is None:
        return False

    serialized = [
        (
            _provider_key(thread),
            thread.provider,
            thread.provider_thread_id,
            Jsonb(_serialize_thread(thread)),
        )
        for thread in threads
    ]
    keys = [item[0] for item in serialized]

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM email_thread_state")
            if serialized:
                cur.executemany(
                    """
                    INSERT INTO email_thread_state (provider_key, provider, provider_thread_id, state)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (provider_key) DO UPDATE
                    SET provider = EXCLUDED.provider,
                        provider_thread_id = EXCLUDED.provider_thread_id,
                        state = EXCLUDED.state,
                        updated_at = NOW()
                    """,
                    serialized,
                )
        conn.commit()
    return True
