from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from app.utils.runtime_workspace_root import resolve_runtime_workspace_root

_REPO_ROOT = resolve_runtime_workspace_root(__file__)
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from runtime_paths import (  # noqa: E402
    seed_workspace_state_file,
    workspace_state_path,
)


ARCHIVE_DIRNAME = "market_signal_archive"
WORKSPACE_STATE_KEY = "feezie-os"
WORKSPACE_ROOT_RELATIVE = Path("workspaces/linkedin-content-os")


def _configured_state_root() -> Path:
    configured = str(os.getenv("AI_CLONE_STATE_ROOT") or "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".codex" / "ai-clone" / "state").resolve()


def _canonical_workspace_root() -> Path:
    configured = str(os.getenv("AI_CLONE_ROOT") or "").strip()
    repo_root = Path(configured).expanduser().resolve() if configured else _REPO_ROOT
    return (repo_root / WORKSPACE_ROOT_RELATIVE).resolve()


def _uses_private_generated_state(workspace_root: Path) -> bool:
    if str(os.getenv("AI_CLONE_STATE_ROOT") or "").strip():
        return True
    return workspace_root.expanduser().resolve() == _canonical_workspace_root()


def archive_root(workspace_root: Path) -> Path:
    if not _uses_private_generated_state(workspace_root):
        return workspace_root / "research" / ARCHIVE_DIRNAME
    return workspace_state_path(
        WORKSPACE_STATE_KEY,
        Path("research") / ARCHIVE_DIRNAME,
        state_root=_configured_state_root(),
    )


def archive_read_roots(workspace_root: Path) -> tuple[Path, ...]:
    roots = [archive_root(workspace_root)]
    roots.append(workspace_root / "research" / ARCHIVE_DIRNAME)
    return tuple(dict.fromkeys(path.expanduser().resolve() for path in roots))


def _seed_archive_file(workspace_root: Path, relative_path: Path) -> Path:
    if not _uses_private_generated_state(workspace_root):
        return workspace_root / relative_path
    return seed_workspace_state_file(
        WORKSPACE_STATE_KEY,
        relative_path,
        source_root=workspace_root,
        project_root=_REPO_ROOT,
        state_root=_configured_state_root(),
    )


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def _clean_multiline_text(value: Any) -> str:
    if value is None:
        return ""
    return "\n".join(line.rstrip() for line in str(value).strip().splitlines()).strip()


def _list_text(value: Any) -> list[str]:
    if isinstance(value, list):
        items = value
    elif value in (None, ""):
        items = []
    else:
        items = [value]

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _clean_text(item)
        lowered = text.lower()
        if not text or lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(text)
    return cleaned


def _split_markdown_frontmatter(text: str) -> tuple[str | None, str]:
    """Split only on exact Markdown frontmatter delimiter lines."""

    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return None, text
    closing_index = next(
        (
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.rstrip("\r\n") == "---"
        ),
        None,
    )
    if closing_index is None:
        raise ValueError("unterminated Markdown frontmatter")
    return "".join(lines[1:closing_index]), "".join(lines[closing_index + 1 :])


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    frontmatter, body = _split_markdown_frontmatter(text)
    if frontmatter is None:
        return {}, text.strip()
    meta = yaml.safe_load(frontmatter) or {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, body.strip()


def _relative_path(path: Path, workspace_root: Path) -> str:
    try:
        return path.relative_to(workspace_root).as_posix()
    except ValueError:
        return path.as_posix()


def _month_key(record: dict[str, Any]) -> str:
    for key in ("published_at", "created_at"):
        value = _clean_text(record.get(key))
        if len(value) >= 7:
            return value[:7]
    signal_id = _clean_text(record.get("id"))
    if len(signal_id) >= 7:
        return signal_id[:7]
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _month_manifest_path(workspace_root: Path, month_key: str) -> Path:
    return archive_root(workspace_root) / f"{month_key}.jsonl"


def _month_markdown_path(workspace_root: Path, month_key: str) -> Path:
    return archive_root(workspace_root) / f"{month_key}.md"


def _record_sort_key(record: dict[str, Any]) -> tuple[str, str]:
    timestamp = _clean_text(record.get("published_at") or record.get("created_at"))
    return timestamp, _clean_text(record.get("id"))


def _record_identity(record: dict[str, Any]) -> str:
    return _clean_text(record.get("id") or record.get("source_url") or record.get("title"))


def _load_month_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _write_month_records(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(records, key=_record_sort_key)
    lines = [json.dumps(record, ensure_ascii=False, sort_keys=False) for record in ordered]
    rendered = "\n".join(lines) + ("\n" if lines else "")
    if path.exists() and path.read_text(encoding="utf-8") == rendered:
        return
    path.write_text(rendered, encoding="utf-8")


def _render_month_markdown(month_key: str, records: list[dict[str, Any]]) -> str:
    lines = [
        f"# Market Signal Archive — {month_key}",
        "",
        "Local generated archive of normalized LinkedIn research signals. Source files remain under `research/market_signals/`.",
        "",
    ]
    for record in sorted(records, key=_record_sort_key):
        title = _clean_text(record.get("title")) or _clean_text(record.get("id")) or "Untitled signal"
        lines.extend(
            [
                f"## {title}",
                f"- Signal ID: `{_clean_text(record.get('id'))}`",
                f"- Runtime source: `{_clean_text(record.get('source_path'))}`",
                f"- Source platform: `{_clean_text(record.get('source_platform'))}`",
                f"- Source type: `{_clean_text(record.get('source_type'))}`",
                f"- Source URL: `{_clean_text(record.get('source_url'))}`" if _clean_text(record.get("source_url")) else "",
                f"- Author: `{_clean_text(record.get('author'))}`" if _clean_text(record.get("author")) else "",
                f"- Priority lane: `{_clean_text(record.get('priority_lane'))}`" if _clean_text(record.get("priority_lane")) else "",
                f"- Created at: `{_clean_text(record.get('created_at'))}`" if _clean_text(record.get("created_at")) else "",
                f"- Published at: `{_clean_text(record.get('published_at'))}`" if _clean_text(record.get("published_at")) else "",
                "",
            ]
        )
        summary = _clean_text(record.get("summary"))
        if summary:
            lines.extend(["### Summary", "", summary, ""])
        why_it_matters = _clean_text(record.get("why_it_matters"))
        if why_it_matters:
            lines.extend(["### Why It Matters", "", why_it_matters, ""])
        topics = _list_text(record.get("topics"))
        if topics:
            lines.append("### Topics")
            lines.extend([f"- {item}" for item in topics])
            lines.append("")
        claims = _list_text(record.get("supporting_claims"))
        if claims:
            lines.append("### Supporting Claims")
            lines.extend([f"- {item}" for item in claims])
            lines.append("")
        body_text = _clean_multiline_text(record.get("body_text"))
        if body_text:
            lines.extend(["### Source", "", body_text, ""])
    return "\n".join(lines).strip()


def _write_month_markdown(path: Path, month_key: str, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = _render_month_markdown(month_key, records) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == rendered:
        return
    path.write_text(rendered, encoding="utf-8")


def _preserve_existing_archive_fields(record: dict[str, Any], existing: dict[str, Any] | None) -> dict[str, Any]:
    if not existing:
        return record
    merged = dict(record)
    for key in ("created_at", "archived_at"):
        value = _clean_text(existing.get(key))
        if value:
            merged[key] = value
    return merged


def build_market_signal_archive_record(signal_path: Path, workspace_root: Path) -> dict[str, Any]:
    text = signal_path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(text)
    signal_id = signal_path.stem
    record: dict[str, Any] = {
        "id": signal_id,
        "kind": _clean_text(meta.get("kind")) or "market_signal",
        "title": _clean_text(meta.get("title")) or signal_id,
        "source_path": _relative_path(signal_path, workspace_root),
        "source_platform": _clean_text(meta.get("source_platform")),
        "source_type": _clean_text(meta.get("source_type")),
        "source_url": _clean_text(meta.get("source_url")),
        "author": _clean_text(meta.get("author")),
        "priority_lane": _clean_text(meta.get("priority_lane")),
        "role_alignment": _clean_text(meta.get("role_alignment")),
        "risk_level": _clean_text(meta.get("risk_level")),
        "publish_posture": _clean_text(meta.get("publish_posture")),
        "capture_method": _clean_text(meta.get("capture_method")),
        "ingest_mode": _clean_text(meta.get("ingest_mode")),
        "created_at": _clean_text(meta.get("created_at")),
        "published_at": _clean_text(meta.get("published_at")),
        "summary": _clean_text(meta.get("summary")),
        "why_it_matters": _clean_text(meta.get("why_it_matters")),
        "core_claim": _clean_text(meta.get("core_claim")),
        "headline_candidates": _list_text(meta.get("headline_candidates")),
        "supporting_claims": _list_text(meta.get("supporting_claims")),
        "topics": _list_text(meta.get("topics")),
        "trust_notes": _list_text(meta.get("trust_notes")),
        "watchlist_matches": _list_text(meta.get("watchlist_matches")),
        "body_text": body,
        "source_metadata": meta.get("source_metadata") or {},
        "engagement": meta.get("engagement") or {},
        "archived_at": datetime.now(timezone.utc).isoformat(),
    }
    month_key = _month_key(record)
    archive_relative = Path("research") / ARCHIVE_DIRNAME
    record["archive_month"] = month_key
    record["archive_manifest_path"] = (archive_relative / f"{month_key}.jsonl").as_posix()
    record["archive_markdown_path"] = (archive_relative / f"{month_key}.md").as_posix()
    return record


def sync_market_signal_archive_entry(signal_path: Path, workspace_root: Path) -> dict[str, Any]:
    record = build_market_signal_archive_record(signal_path, workspace_root)
    month_key = str(record["archive_month"])
    archive_relative = Path("research") / ARCHIVE_DIRNAME
    manifest_path = _seed_archive_file(
        workspace_root,
        archive_relative / f"{month_key}.jsonl",
    )
    markdown_path = _seed_archive_file(
        workspace_root,
        archive_relative / f"{month_key}.md",
    )
    records: dict[str, dict[str, Any]] = {}
    legacy_manifest = workspace_root / archive_relative / f"{month_key}.jsonl"
    for path in dict.fromkeys((legacy_manifest, manifest_path)):
        for item in _load_month_records(path):
            identity = _record_identity(item)
            if identity:
                records[identity] = item
    identity = _record_identity(record)
    record = _preserve_existing_archive_fields(record, records.get(identity))
    records[identity] = record
    ordered = [item for _, item in sorted(records.items(), key=lambda pair: _record_sort_key(pair[1]))]
    _write_month_records(manifest_path, ordered)
    _write_month_markdown(markdown_path, month_key, ordered)
    return record


def sync_market_signal_archive(workspace_root: Path) -> dict[str, Any]:
    signals_root = workspace_root / "research" / "market_signals"
    if not signals_root.exists():
        return {"count": 0, "months": []}
    archived = 0
    months: set[str] = set()
    for signal_path in sorted(signals_root.glob("*.md")):
        if signal_path.name.upper() == "README.MD":
            continue
        record = sync_market_signal_archive_entry(signal_path, workspace_root)
        archived += 1
        months.add(str(record["archive_month"]))
    return {"count": archived, "months": sorted(months)}


def load_market_signal_archive_records(workspace_root: Path) -> list[dict[str, Any]]:
    records_by_identity: dict[str, dict[str, Any]] = {}
    # Legacy first, then state: a state record may refine the same durable
    # signal, but a partial state month must never hide legacy-only records.
    for root in reversed(archive_read_roots(workspace_root)):
        if not root.exists():
            continue
        for path in sorted(root.glob("*.jsonl")):
            if not path.is_file():
                continue
            for record in _load_month_records(path):
                identity = _record_identity(record)
                if identity:
                    records_by_identity[identity] = record
    return sorted(records_by_identity.values(), key=_record_sort_key)
