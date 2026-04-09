from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ARCHIVE_DIRNAME = "market_signal_archive"


def archive_root(workspace_root: Path) -> Path:
    return workspace_root / "research" / ARCHIVE_DIRNAME


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


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text.strip()
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text.strip()
    meta = yaml.safe_load(parts[1]) or {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, parts[2].strip()


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
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _render_month_markdown(month_key: str, records: list[dict[str, Any]]) -> str:
    lines = [
        f"# Market Signal Archive — {month_key}",
        "",
        "Tracked archive of normalized LinkedIn research signals. Runtime files still live under `research/market_signals/`.",
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
    path.write_text(_render_month_markdown(month_key, records) + "\n", encoding="utf-8")


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
    record["archive_month"] = month_key
    record["archive_manifest_path"] = _relative_path(_month_manifest_path(workspace_root, month_key), workspace_root)
    record["archive_markdown_path"] = _relative_path(_month_markdown_path(workspace_root, month_key), workspace_root)
    return record


def sync_market_signal_archive_entry(signal_path: Path, workspace_root: Path) -> dict[str, Any]:
    record = build_market_signal_archive_record(signal_path, workspace_root)
    month_key = str(record["archive_month"])
    manifest_path = _month_manifest_path(workspace_root, month_key)
    records = {item.get("id"): item for item in _load_month_records(manifest_path) if isinstance(item, dict)}
    records[str(record["id"])] = record
    ordered = [item for _, item in sorted(records.items(), key=lambda pair: _record_sort_key(pair[1]))]
    _write_month_records(manifest_path, ordered)
    _write_month_markdown(_month_markdown_path(workspace_root, month_key), month_key, ordered)
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
    root = archive_root(workspace_root)
    if not root.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.jsonl")):
        records.extend(_load_month_records(path))
    return sorted(records, key=_record_sort_key)
