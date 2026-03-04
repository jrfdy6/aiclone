from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from app.models import KnowledgeDoc, LogEntry, Playbook, Prospect

BASE_DIR = Path(__file__).resolve().parents[2]
KNOWLEDGE_ROOT = Path(__file__).resolve().parents[5] / "knowledge" / "aiclone"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

PROSPECT_CACHE = DATA_DIR / "prospects.json"
LOG_CACHE = DATA_DIR / "system_logs.json"


@dataclass
class _FileDoc:
    id: str
    title: str
    path: Path
    summary: str
    tags: List[str]
    updated_at: datetime


def _summarize_file(path: Path, max_lines: int = 5) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()][:max_lines]
    return " ".join(lines)


def _iter_markdown_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return root.rglob("*.md")


def load_local_knowledge() -> List[KnowledgeDoc]:
    docs: List[KnowledgeDoc] = []
    for file_path in _iter_markdown_files(KNOWLEDGE_ROOT):
        rel = file_path.relative_to(KNOWLEDGE_ROOT)
        doc_id = rel.as_posix().replace("/", "-").replace(".md", "")
        parents = list(rel.parents)
        doc = KnowledgeDoc(
            id=doc_id,
            title=file_path.stem.replace("_", " ").title(),
            summary=_summarize_file(file_path),
            tags=[parent.name for parent in parents[:-1]],
            source_path=str(rel),
            updated_at=datetime.fromtimestamp(file_path.stat().st_mtime),
        )
        docs.append(doc)
    return docs


def load_local_playbooks() -> List[Playbook]:
    playbooks: List[Playbook] = []
    for file_path in _iter_markdown_files(KNOWLEDGE_ROOT):
        rel = file_path.relative_to(KNOWLEDGE_ROOT)
        category = rel.parts[0] if rel.parts else "general"
        playbooks.append(
            Playbook(
                id=rel.as_posix().replace("/", "-")
                .replace(".md", ""),
                name=file_path.stem.replace("_", " ").title(),
                category=category,
                steps=[],
                sop_path=str(rel),
                linked_docs=[str(rel)],
            )
        )
    return playbooks


def _read_json_list(path: Path) -> list:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return []


def _write_json_list(path: Path, payload: list) -> None:
    path.write_text(json.dumps(payload, indent=2, default=str))


def load_cached_prospects() -> List[Prospect]:
    payload = _read_json_list(PROSPECT_CACHE)
    return [Prospect(**item) for item in payload]


def save_prospect(prospect: Prospect) -> None:
    prospects = _read_json_list(PROSPECT_CACHE)
    prospects.append(json.loads(prospect.model_dump_json()))
    _write_json_list(PROSPECT_CACHE, prospects)


def append_log(entry: LogEntry) -> None:
    logs = _read_json_list(LOG_CACHE)
    logs.append(json.loads(entry.model_dump_json()))
    _write_json_list(LOG_CACHE, logs)


def load_logs(limit: int = 100) -> List[LogEntry]:
    payload = _read_json_list(LOG_CACHE)
    entries = [LogEntry(**item) for item in payload]
    return sorted(entries, key=lambda e: e.timestamp, reverse=True)[:limit]
