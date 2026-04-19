#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_INTELLIGENCE_ROOT = REPO_ROOT / "knowledge" / "source-intelligence"
INDEX_PATH = SOURCE_INTELLIGENCE_ROOT / "index.json"
TRANSCRIPTS_ROOT = REPO_ROOT / "knowledge" / "aiclone" / "transcripts"
INGESTIONS_ROOT = REPO_ROOT / "knowledge" / "ingestions"
SCAFFOLD_DIRS = ("raw", "normalized", "digests", "promotions")


def main() -> int:
    parser = argparse.ArgumentParser(description="Register existing transcript and ingestion assets in the source-intelligence index.")
    parser.add_argument("--check", action="store_true", help="Build the index without writing it.")
    args = parser.parse_args()
    payload = build_source_intelligence_index(REPO_ROOT)
    if args.check:
        print(json.dumps({"sources": len(payload["sources"]), "counts": payload["counts"]}, sort_keys=True))
        return 0
    write_source_intelligence_index(payload)
    print(f"Registered {len(payload['sources'])} source-intelligence assets at {INDEX_PATH.relative_to(REPO_ROOT)}")
    return 0


def build_source_intelligence_index(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    source_root = repo_root / "knowledge" / "source-intelligence"
    transcript_root = repo_root / "knowledge" / "aiclone" / "transcripts"
    ingestion_root = repo_root / "knowledge" / "ingestions"
    entries = [
        *_transcript_entries(repo_root, transcript_root, source_root),
        *_ingestion_entries(repo_root, ingestion_root, source_root),
    ]
    entries = sorted(entries, key=lambda item: (str(item.get("captured_at") or ""), str(item.get("source_id") or "")))
    return {
        "schema_version": "source_intelligence_index/v1",
        "generated_at": _now_iso(),
        "roots": {
            "source_intelligence": _rel(source_root, repo_root),
            "transcripts": _rel(transcript_root, repo_root),
            "ingestions": _rel(ingestion_root, repo_root),
        },
        "states": ["raw", "digested", "reviewed", "routed", "promoted", "ignored"],
        "counts": _counts(entries),
        "sources": entries,
    }


def write_source_intelligence_index(payload: dict[str, Any], repo_root: Path = REPO_ROOT) -> None:
    source_root = repo_root / "knowledge" / "source-intelligence"
    for dirname in SCAFFOLD_DIRS:
        (source_root / dirname).mkdir(parents=True, exist_ok=True)
    index_path = source_root / "index.json"
    index_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _transcript_entries(repo_root: Path, transcript_root: Path, source_root: Path) -> list[dict[str, Any]]:
    if not transcript_root.exists():
        return []
    entries: list[dict[str, Any]] = []
    for transcript_path in sorted(transcript_root.glob("*.md")):
        if transcript_path.name.upper() in {"INDEX.MD", "README.MD", "TEMPLATE.MD"}:
            continue
        packet_path = transcript_path.with_suffix(".shared_source_packet.json")
        packet = _read_json(packet_path)
        identity = _dict(packet.get("source_identity")) if packet else {}
        understanding = _dict(packet.get("source_understanding")) if packet else {}
        route_affordances = _dict(packet.get("route_affordances")) if packet else {}
        source_id = _clean_id(identity.get("id") or transcript_path.stem)
        promotions = _promotion_paths(source_root, source_id, repo_root)
        entry = {
            "source_id": source_id,
            "source_kind": "transcript_library",
            "source_class": identity.get("source_class") or "long_form_media",
            "source_channel": identity.get("source_channel") or _infer_channel(transcript_path),
            "source_type": identity.get("source_type") or "transcript_note",
            "source_url": identity.get("source_url"),
            "title": understanding.get("title") or _first_heading(transcript_path) or _title_from_slug(transcript_path.stem),
            "summary": understanding.get("summary") or _first_meaningful_line(transcript_path),
            "raw_path": _rel(transcript_path, repo_root),
            "raw_paths": [_rel(transcript_path, repo_root)],
            "metadata_path": _rel(packet_path, repo_root) if packet_path.exists() else None,
            "normalized_path": _rel(packet_path, repo_root) if packet_path.exists() else None,
            "digest_path": _rel(packet_path, repo_root) if packet_path.exists() else None,
            "route_decision": {
                "path": _rel(packet_path, repo_root) if packet_path.exists() else None,
                "route_affordances": route_affordances,
            },
            "promotions": promotions,
            "status": _status(
                has_raw=True,
                has_digest=packet_path.exists(),
                has_review=bool(route_affordances.get("brain_review")),
                has_route=any(bool(value) for value in route_affordances.values()),
                has_promotions=bool(promotions),
            ),
            "published_at": identity.get("published_at"),
            "captured_at": identity.get("captured_at"),
        }
        entries.append(_strip_none(entry))
    return entries


def _ingestion_entries(repo_root: Path, ingestion_root: Path, source_root: Path) -> list[dict[str, Any]]:
    if not ingestion_root.exists():
        return []
    entries: list[dict[str, Any]] = []
    for normalized_path in sorted(ingestion_root.glob("**/normalized.md")):
        source_dir = normalized_path.parent
        packet_path = _first_existing(
            source_dir / "shared_source_packet.json",
            source_dir / "review_packets.json",
        )
        routing_path = source_dir / "routing_status.json"
        build_review_path = source_dir / "build_review.md"
        persona_review_path = source_dir / "persona_review.md"
        linkedin_review_path = source_dir / "linkedin_review.md"
        raw_paths = sorted(path for path in (source_dir / "raw").glob("*") if path.is_file()) if (source_dir / "raw").exists() else []
        packet = _read_json(packet_path) if packet_path else {}
        routing = _read_json(routing_path)
        packet_identity = _dict(packet.get("source_identity"))
        packet_understanding = _dict(packet.get("source_understanding"))
        source_id = _clean_id(packet_identity.get("id") or f"ingestion-{source_dir.relative_to(ingestion_root).as_posix()}")
        digest_path = _first_existing(source_dir / "shared_source_packet.json", build_review_path, persona_review_path, linkedin_review_path, normalized_path)
        promotions = _promotion_paths(source_root, source_id, repo_root)
        has_review = any(path.exists() for path in (persona_review_path, linkedin_review_path)) or bool(packet)
        routing_status_value = str(routing.get("status") or "").strip().lower()
        has_route = routing_status_value in {"ok", "routed", "completed"} or bool(_dict(packet.get("route_affordances")))
        ignored = routing_status_value in {"ignore", "ignored", "skipped"}
        entry = {
            "source_id": source_id,
            "source_kind": "machine_ingestion",
            "source_class": packet_identity.get("source_class") or "long_form_media",
            "source_channel": packet_identity.get("source_channel") or _infer_channel_from_raw(raw_paths),
            "source_type": packet_identity.get("source_type") or "transcript",
            "source_url": packet_identity.get("source_url") or _source_url_from_raw(raw_paths),
            "title": packet_understanding.get("title") or _first_heading(normalized_path) or _title_from_slug(source_dir.name),
            "summary": packet_understanding.get("summary") or _first_meaningful_line(normalized_path),
            "raw_path": _rel(raw_paths[0], repo_root) if raw_paths else None,
            "raw_paths": [_rel(path, repo_root) for path in raw_paths],
            "metadata_path": _rel(packet_path, repo_root) if packet_path else None,
            "normalized_path": _rel(normalized_path, repo_root),
            "digest_path": _rel(digest_path, repo_root) if digest_path else None,
            "route_decision": {
                "path": _rel(routing_path, repo_root) if routing_path.exists() else None,
                "routing_status": routing,
                "route_affordances": _dict(packet.get("route_affordances")),
            },
            "promotions": promotions,
            "status": _status(
                has_raw=bool(raw_paths),
                has_digest=normalized_path.exists() or bool(digest_path),
                has_review=has_review,
                has_route=has_route,
                has_promotions=bool(promotions),
                ignored=ignored,
            ),
            "published_at": packet_identity.get("published_at"),
            "captured_at": _captured_at_from_path(source_dir, ingestion_root),
        }
        entries.append(_strip_none(entry))
    return entries


def _status(
    *,
    has_raw: bool,
    has_digest: bool,
    has_review: bool,
    has_route: bool,
    has_promotions: bool,
    ignored: bool = False,
) -> str:
    if ignored:
        return "ignored"
    if has_promotions:
        return "promoted"
    if has_route:
        return "routed"
    if has_review:
        return "reviewed"
    if has_digest:
        return "digested"
    if has_raw:
        return "raw"
    return "raw"


def _counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"total": len(entries), "raw": 0, "digested": 0, "reviewed": 0, "routed": 0, "promoted": 0, "ignored": 0}
    for entry in entries:
        status = str(entry.get("status") or "raw")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_existing(*paths: Path) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _promotion_paths(source_root: Path, source_id: str, repo_root: Path) -> list[str]:
    promotions_root = source_root / "promotions"
    if not promotions_root.exists():
        return []
    needle = _clean_id(source_id)
    return [
        _rel(path, repo_root)
        for path in sorted(promotions_root.glob("**/*"))
        if path.is_file() and needle in _clean_id(path.stem)
    ]


def _source_url_from_raw(raw_paths: list[Path]) -> str | None:
    for path in raw_paths:
        if path.suffix.lower() == ".url":
            return _first_meaningful_line(path)
    return None


def _infer_channel_from_raw(raw_paths: list[Path]) -> str:
    source_url = _source_url_from_raw(raw_paths) or ""
    if "youtube.com" in source_url or "youtu.be" in source_url:
        return "youtube"
    if "linkedin.com" in source_url:
        return "linkedin"
    if "reddit.com" in source_url:
        return "reddit"
    return "manual"


def _infer_channel(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")[:2000].lower()
    if "youtube.com" in text or "youtu.be" in text:
        return "youtube"
    return "manual"


def _captured_at_from_path(source_dir: Path, ingestion_root: Path) -> str | None:
    try:
        relative = source_dir.relative_to(ingestion_root)
    except ValueError:
        return None
    parts = relative.parts
    if len(parts) >= 2 and re.fullmatch(r"\d{4}", parts[0]) and re.fullmatch(r"\d{2}", parts[1]):
        return f"{parts[0]}-{parts[1]}"
    return None


def _first_heading(path: Path) -> str:
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return ""


def _first_meaningful_line(path: Path) -> str:
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("-"):
            stripped = stripped[1:].strip()
        return stripped[:280]
    return ""


def _title_from_slug(value: str) -> str:
    return " ".join(part.capitalize() for part in re.split(r"[_-]+", value) if part)


def _clean_id(value: Any) -> str:
    text = str(value or "").strip().lower().replace("/", "-")
    text = re.sub(r"[^a-z0-9_.:-]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "source"


def _strip_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
