from __future__ import annotations

import os
from datetime import datetime, time
from pathlib import Path
from typing import List

try:
    from psycopg.errors import UndefinedTable
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - local fallback when DB deps are absent
    UndefinedTable = Exception  # type: ignore[assignment]
    dict_row = None

from app.models import DailyBrief
from app.services.daily_brief_parser import ParsedBrief, parse_briefs_markdown

_WORKSPACE_CANDIDATES = (
    Path(os.getenv("OPENCLAW_WORKSPACE", "")),
    Path("/Users/neo/.openclaw/workspace"),
    Path(__file__).resolve().parents[3],
)


def list_daily_briefs(limit: int = 50) -> List[DailyBrief]:
    rows = _load_from_db(limit)
    if rows:
        return rows
    return _load_from_local_files(limit)


def _load_from_db(limit: int) -> List[DailyBrief]:
    try:
        from app.services.open_brain_db import get_pool

        pool = get_pool()
        with pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT id, brief_date, title, summary, content_markdown, source, source_ref, metadata, created_at, updated_at
                    FROM daily_briefs
                    ORDER BY brief_date DESC, updated_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall() or []
        return [_row_to_brief(row) for row in rows]
    except UndefinedTable:
        return []
    except Exception:
        return []


def _load_from_local_files(limit: int) -> List[DailyBrief]:
    entries: List[DailyBrief] = []
    for workspace in _WORKSPACE_CANDIDATES:
        if not workspace:
            continue
        current_file = workspace / "memory" / "daily-briefs.md"
        if current_file.exists():
            parsed = parse_briefs_markdown(current_file.read_text(), source_ref=str(current_file))
            entries.extend(_parsed_to_models(parsed, source="workspace_markdown"))
            break
    entries.sort(key=lambda item: (item.brief_date, item.updated_at), reverse=True)
    return entries[:limit]


def _parsed_to_models(parsed_entries: List[ParsedBrief], *, source: str) -> List[DailyBrief]:
    models: List[DailyBrief] = []
    for entry in parsed_entries:
        models.append(
            DailyBrief(
                id=f"local-{entry.brief_date.isoformat()}",
                brief_date=entry.brief_date,
                title=entry.title,
                summary=entry.summary,
                content_markdown=entry.content_markdown,
                source=source,
                source_ref=entry.metadata.get("source_ref"),
                metadata=entry.metadata,
                created_at=datetime.combine(entry.brief_date, time.min),
                updated_at=datetime.combine(entry.brief_date, time.min),
            )
        )
    return models


def _row_to_brief(row: dict) -> DailyBrief:
    return DailyBrief(
        id=str(row["id"]),
        brief_date=row["brief_date"],
        title=row["title"],
        summary=row.get("summary"),
        content_markdown=row.get("content_markdown") or "",
        source=row.get("source") or "unknown",
        source_ref=row.get("source_ref"),
        metadata=row.get("metadata") or {},
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
