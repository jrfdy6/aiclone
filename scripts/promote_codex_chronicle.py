#!/usr/bin/env python3
"""Promote Chronicle/standup signal into durable memory and PM recommendation files."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from runtime_paths import (
    PROJECT_ROOT,
    STATE_ROOT,
    memory_state_path,
    resolve_memory_read_path,
    seed_memory_state_file,
)
from local_state_lock import exclusive_local_state_lock


WORKSPACE_ROOT = PROJECT_ROOT
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
MEMORY_ROOT = memory_state_path(state_root=STATE_ROOT)
SCRIPT_DIR = WORKSPACE_ROOT / "scripts"
DEFAULT_PREP_ROOT = resolve_memory_read_path(
    "standup-prep",
    project_root=WORKSPACE_ROOT,
    state_root=STATE_ROOT,
)

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary_raw = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temporary = Path(temporary_raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def _latest_prep(prep_root: Path, standup_kind: str) -> Path | None:
    matches = sorted((prep_root / standup_kind).glob("*.json"))
    return matches[-1] if matches else None


def _append_markdown_once(path: Path, heading: str, body: str, *, marker: str) -> bool:
    """Append a marked promotion block once under the process-wide promotion lock."""

    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_RDWR | os.O_CREAT | os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        file_stat = os.fstat(descriptor)
        if not stat.S_ISREG(file_stat.st_mode):
            raise RuntimeError(f"Promotion target must be a regular file: {path}")
        existing = b""
        offset = 0
        while offset < file_stat.st_size:
            chunk = os.pread(descriptor, min(1024 * 1024, file_stat.st_size - offset), offset)
            if not chunk:
                break
            existing += chunk
            offset += len(chunk)
        marker_bytes = marker.encode("utf-8")
        if marker_bytes in existing:
            return False

        prefix = b""
        if existing:
            prefix = b"\n" if existing.endswith(b"\n") else b"\n\n"
            if existing.endswith(b"\n\n"):
                prefix = b""
        block = "\n\n".join(piece for piece in [heading.strip(), body.strip()] if piece)
        encoded = prefix + f"{block}\n\n{marker}\n".encode("utf-8")
        view = memoryview(encoded)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("Promotion append made no forward progress.")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return True


def _promotion_identity(prep: dict[str, Any], *, workspace_key: str) -> tuple[str, str]:
    canonical = json.dumps(
        {
            "workspace_key": workspace_key,
            "prep": prep,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest, str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:chronicle-promotion:{digest}"))


def _promotion_marker_path(promotion_id: str) -> Path:
    return MEMORY_ROOT / "promotion-markers" / f"{promotion_id}.json"


def _load_or_create_promotion_marker(
    *,
    promotion_id: str,
    recommendation_id: str,
    workspace_key: str,
    prep_path: Path,
) -> tuple[Path, dict[str, Any]]:
    marker_path = _promotion_marker_path(promotion_id)
    if marker_path.exists():
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        if str(marker.get("promotion_id") or "") != promotion_id:
            raise RuntimeError(f"Promotion marker identity mismatch: {marker_path}")
        return marker_path, marker
    marker = {
        "schema_version": "chronicle_promotion_marker/v1",
        "promotion_id": promotion_id,
        "recommendation_id": recommendation_id,
        "created_at": _iso(_now()),
        "updated_at": _iso(_now()),
        "workspace_key": workspace_key,
        "prep_json": str(prep_path),
        "stages": {},
    }
    _write_json(marker_path, marker)
    return marker_path, marker


def _mark_promotion_stage(
    marker_path: Path,
    marker: dict[str, Any],
    stage: str,
    *,
    created: bool,
    status: str = "complete",
) -> None:
    stages = marker.setdefault("stages", {})
    stages[stage] = {
        "status": status,
        "created": bool(created),
        "completed_at": _iso(_now()),
    }
    marker["updated_at"] = _iso(_now())
    _write_json(marker_path, marker)


def _promotion_stage_complete(marker: dict[str, Any], stage: str) -> bool:
    stage_payload = (marker.get("stages") or {}).get(stage) or {}
    return str(stage_payload.get("status") or "") in {"complete", "skipped"}


def _runtime_memory_path(relative_path: str) -> Path:
    return seed_memory_state_file(
        relative_path,
        project_root=WORKSPACE_ROOT,
        state_root=MEMORY_ROOT.parent,
    )


def _main_unlocked() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prep-json", help="Path to a standup prep JSON file.")
    parser.add_argument("--prep-root", default=str(DEFAULT_PREP_ROOT))
    parser.add_argument("--standup-kind", default="executive_ops")
    parser.add_argument("--workspace-key", default="shared_ops")
    parser.add_argument("--write-learnings", action="store_true")
    parser.add_argument("--write-pm-recommendations", action="store_true")
    args = parser.parse_args()

    prep_path = Path(args.prep_json).expanduser() if args.prep_json else _latest_prep(Path(args.prep_root), args.standup_kind)
    if prep_path is None or not prep_path.exists():
        raise SystemExit("No standup prep JSON found to promote.")

    prep = json.loads(prep_path.read_text(encoding="utf-8"))
    promotions = prep.get("memory_promotions") or []
    pm_updates = prep.get("pm_updates") or []
    pm_updates_blocked_reason = prep.get("pm_updates_blocked_reason")
    promotion_id, recommendation_id = _promotion_identity(
        prep,
        workspace_key=args.workspace_key,
    )
    marker_path, promotion_marker = _load_or_create_promotion_marker(
        promotion_id=promotion_id,
        recommendation_id=recommendation_id,
        workspace_key=args.workspace_key,
        prep_path=prep_path,
    )
    try:
        timestamp = datetime.fromisoformat(
            str(promotion_marker["created_at"]).replace("Z", "+00:00")
        ).astimezone()
    except (KeyError, TypeError, ValueError):
        raise RuntimeError(f"Promotion marker has an invalid created_at value: {marker_path}")
    daily_path = seed_memory_state_file(
        f"{timestamp:%Y-%m-%d}.md",
        project_root=WORKSPACE_ROOT,
        state_root=MEMORY_ROOT.parent,
    )

    promotion_lines = [
        f"- Workspace: `{args.workspace_key}`",
        f"- Prep Source: `{prep_path}`",
        "",
        "### Durable Memory Candidates",
    ]
    if not promotions:
        promotion_lines.append("- None.")
    else:
        for item in promotions:
            promotion_lines.append(f"- `{item.get('target')}`: {item.get('content')}")

    promotion_lines.extend(["", "### PM Recommendation Candidates"])
    if not pm_updates:
        if pm_updates_blocked_reason:
            reason_label = {
                "pm_snapshot_unavailable": "Blocked: PM snapshot unavailable during prep.",
            }.get(pm_updates_blocked_reason, f"Blocked: {pm_updates_blocked_reason}")
            promotion_lines.append(f"- None. ({reason_label})")
        else:
            promotion_lines.append("- None.")
    else:
        for item in pm_updates:
            promotion_lines.append(f"- `{item.get('workspace_key')}`: {item.get('title')}")

    daily_created = False
    if not _promotion_stage_complete(promotion_marker, "daily_memory"):
        daily_created = _append_markdown_once(
            daily_path,
            f"## Codex Chronicle Promotion — {timestamp:%Y-%m-%d %H:%M %Z}",
            "\n".join(promotion_lines),
            marker=f"<!-- ai-clone:chronicle-promotion:{promotion_id}:daily-memory -->",
        )
        _mark_promotion_stage(
            marker_path,
            promotion_marker,
            "daily_memory",
            created=daily_created,
        )

    learnings_written = 0
    if args.write_learnings:
        learnings = [
            item.get("content")
            for item in promotions
            if item.get("target") == "learnings" and isinstance(item.get("content"), str)
        ]
        if learnings and not _promotion_stage_complete(promotion_marker, "learnings"):
            learnings_path = _runtime_memory_path("memory/LEARNINGS.md")
            learnings_created = _append_markdown_once(
                learnings_path,
                f"## Chronicle Promotions — {timestamp:%Y-%m-%d}",
                "\n".join(f"- {item}" for item in learnings),
                marker=f"<!-- ai-clone:chronicle-promotion:{promotion_id}:learnings -->",
            )
            _mark_promotion_stage(
                marker_path,
                promotion_marker,
                "learnings",
                created=learnings_created,
            )
            learnings_written = len(learnings) if learnings_created else 0
        elif not learnings and not _promotion_stage_complete(promotion_marker, "learnings"):
            _mark_promotion_stage(
                marker_path,
                promotion_marker,
                "learnings",
                created=False,
                status="skipped",
            )

    recommendation_path: Path | None = None
    if args.write_pm_recommendations and pm_updates and not pm_updates_blocked_reason:
        recommendation_path = MEMORY_ROOT / "pm-recommendations" / f"{promotion_id}.json"
        if not _promotion_stage_complete(promotion_marker, "pm_recommendations"):
            recommendation_created = not recommendation_path.exists()
            if recommendation_path.exists():
                existing_recommendation = json.loads(recommendation_path.read_text(encoding="utf-8"))
                if str(existing_recommendation.get("promotion_id") or "") != promotion_id:
                    raise RuntimeError(
                        f"PM recommendation identity mismatch: {recommendation_path}"
                    )
            else:
                _write_json(
                    recommendation_path,
                    {
                        "schema_version": "pm_recommendations/v1",
                        "recommendation_id": recommendation_id,
                        "promotion_id": promotion_id,
                        "created_at": promotion_marker["created_at"],
                        "workspace_key": args.workspace_key,
                        "source": "codex_chronicle_promotion",
                        "prep_json": str(prep_path),
                        "pm_updates": pm_updates,
                    },
                )
            _mark_promotion_stage(
                marker_path,
                promotion_marker,
                "pm_recommendations",
                created=recommendation_created,
            )
    elif args.write_pm_recommendations and not _promotion_stage_complete(
        promotion_marker,
        "pm_recommendations",
    ):
        _mark_promotion_stage(
            marker_path,
            promotion_marker,
            "pm_recommendations",
            created=False,
            status="skipped",
        )

    print(f"Promoted Chronicle prep into {daily_path}")
    if learnings_written:
        print(f"Appended {learnings_written} learning entries to {_runtime_memory_path('memory/LEARNINGS.md')}")
    if recommendation_path is not None:
        print(f"PM recommendations: {recommendation_path}")
    elif args.write_pm_recommendations and pm_updates_blocked_reason:
        print(f"Skipped PM recommendation write: {pm_updates_blocked_reason}")
    print(f"Promotion marker: {marker_path}")
    return 0


def main() -> int:
    lock_path = MEMORY_ROOT / "locks" / "chronicle-promotion.lock"
    with exclusive_local_state_lock(lock_path):
        return _main_unlocked()


if __name__ == "__main__":
    raise SystemExit(main())
