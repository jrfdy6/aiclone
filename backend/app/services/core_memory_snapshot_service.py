from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CORE_MEMORY_RELATIVE_PATHS: tuple[str, ...] = (
    "memory/persistent_state.md",
    "memory/LEARNINGS.md",
    "memory/daily-briefs.md",
    "memory/cron-prune.md",
    "memory/dream_cycle_log.md",
    "memory/codex_session_handoff.jsonl",
    "memory/2026-04-08.md",
    "memory/2026-04-09.md",
    "memory/doc-updates.md",
    "memory/self-improvement.md",
    "memory/audit_log_day_1.md",
)

UNTRACKED_CORE_MEMORY_RELATIVE_PATHS: tuple[str, ...] = (
    "memory/LEARNINGS.md",
    "memory/daily-briefs.md",
    "memory/cron-prune.md",
    "memory/dream_cycle_log.md",
    "memory/20??-??-??.md",
    "memory/doc-updates.md",
    "memory/self-improvement.md",
    "memory/audit_log_day_1.md",
)

RUNTIME_MEMORY_RELATIVE_PATHS: dict[str, str] = {
    "memory/persistent_state.md": "memory/runtime/persistent_state.md",
    "memory/LEARNINGS.md": "memory/runtime/LEARNINGS.md",
    "memory/codex_session_handoff.jsonl": "memory/runtime/codex_session_handoff.jsonl",
}

SNAPSHOT_RELATIVE_ROOT = Path("docs/runtime_snapshots/core_memory")
LATEST_POINTER_NAME = "LATEST.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def snapshot_root(workspace_root: Path) -> Path:
    return workspace_root / SNAPSHOT_RELATIVE_ROOT


def latest_pointer_path(workspace_root: Path) -> Path:
    return snapshot_root(workspace_root) / LATEST_POINTER_NAME


def snapshot_dir(workspace_root: Path, snapshot_id: str) -> Path:
    return snapshot_root(workspace_root) / snapshot_id


def manifest_path(workspace_root: Path, snapshot_id: str) -> Path:
    return snapshot_dir(workspace_root, snapshot_id) / "manifest.json"


def overview_path(workspace_root: Path, snapshot_id: str) -> Path:
    return snapshot_dir(workspace_root, snapshot_id) / "README.md"


def _workspace_relative(path: Path, workspace_root: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_runtime_pointer_file(path: Path, runtime_relative: Path) -> bool:
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    normalized = " ".join(text.split()).lower()
    runtime_ref = runtime_relative.as_posix().lower()
    return (
        runtime_ref in normalized
        and "runtime" in normalized
        and ("resolver" in normalized or "canonical logical path" in normalized)
    )


def _is_runtime_placeholder_file(path: Path, relative_path: Path) -> bool:
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != 1:
        return False
    heading = lines[0].lstrip("#").strip().lower()
    expected_heading = relative_path.stem.replace("-", " ").replace("_", " ").lower()
    return bool(lines[0].startswith("#") and heading == expected_heading)


def _is_non_material_learning_note(path: Path, relative_path: Path) -> bool:
    if relative_path.as_posix() != "memory/LEARNINGS.md" or not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != 3:
        return False
    heading, section_heading, note = lines
    if heading.lower() != "# learnings":
        return False
    if section_heading.lstrip("#").strip().lower() != "daily memory flush learnings":
        return False
    normalized_note = " ".join(note.split()).lower()
    if not normalized_note.startswith("-"):
        return False
    return any(
        phrase in normalized_note
        for phrase in (
            "no immediate durable lessons identified",
            "no durable lessons identified",
            "no new durable lessons identified",
        )
    )


def _is_stale_runtime_mirror(
    live_hash: str | None,
    runtime_hash: str | None,
    live_path: Path,
    runtime_path: Path,
) -> bool:
    if not live_hash or not runtime_hash or live_hash == runtime_hash:
        return False
    if not live_path.exists() or not runtime_path.exists():
        return False
    try:
        live_text = live_path.read_text(encoding="utf-8", errors="replace").strip()
        runtime_text = runtime_path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return False
    return bool(live_text and runtime_text.startswith(live_text))


def _line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return sum(1 for _ in handle)


def _preview_lines(path: Path, *, head: int = 3, tail: int = 3) -> dict[str, list[str]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return {
        "head": lines[:head],
        "tail": lines[-tail:] if tail else [],
    }


def latest_snapshot_id(workspace_root: Path) -> str | None:
    pointer = latest_pointer_path(workspace_root)
    if not pointer.exists():
        return None
    try:
        payload = json.loads(pointer.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    snapshot_id = payload.get("snapshot_id")
    if isinstance(snapshot_id, str) and snapshot_id.strip():
        return snapshot_id.strip()
    return None


def runtime_relative_path(relative_path: str | Path) -> Path:
    relative = Path(relative_path)
    mapped = RUNTIME_MEMORY_RELATIVE_PATHS.get(relative.as_posix())
    return Path(mapped) if mapped else relative


def resolve_live_memory_write_path(workspace_root: Path, relative_path: str | Path) -> Path:
    return workspace_root / runtime_relative_path(relative_path)


def expected_memory_read_mode(relative_path: str | Path) -> str:
    relative = Path(relative_path)
    runtime_relative = runtime_relative_path(relative)
    return "runtime" if runtime_relative != relative else "live"


def resolve_memory_read_target(workspace_root: Path, relative_path: str | Path) -> dict[str, Any]:
    relative = Path(relative_path)
    live_path = workspace_root / relative
    runtime_path = resolve_live_memory_write_path(workspace_root, relative)
    expected_mode = expected_memory_read_mode(relative)
    expected_path = runtime_path if expected_mode == "runtime" else live_path
    snapshot_id = latest_snapshot_id(workspace_root)
    snapshot_path = snapshot_dir(workspace_root, snapshot_id) / relative if snapshot_id else None

    if expected_path.exists():
        resolved_mode = expected_mode
        resolved_path = expected_path
    elif expected_mode == "runtime" and live_path.exists():
        resolved_mode = "live"
        resolved_path = live_path
    elif snapshot_path is not None and snapshot_path.exists():
        resolved_mode = "snapshot"
        resolved_path = snapshot_path
    else:
        resolved_mode = "missing"
        resolved_path = expected_path

    runtime_exists = runtime_path.exists()
    live_exists = live_path.exists()
    runtime_mtime = runtime_path.stat().st_mtime if runtime_exists else None
    live_mtime = live_path.stat().st_mtime if live_exists else None
    runtime_hash = _sha256(runtime_path) if runtime_exists else None
    live_hash = _sha256(live_path) if live_exists else None
    live_is_runtime_pointer = bool(
        expected_mode == "runtime" and _is_runtime_pointer_file(live_path, runtime_relative_path(relative))
    )
    live_is_runtime_placeholder = bool(
        expected_mode == "runtime" and _is_runtime_placeholder_file(live_path, relative)
    )
    live_is_non_material_learning_note = bool(
        expected_mode == "runtime" and _is_non_material_learning_note(live_path, relative)
    )
    live_is_stale_runtime_mirror = bool(
        expected_mode == "runtime" and _is_stale_runtime_mirror(live_hash, runtime_hash, live_path, runtime_path)
    )
    runtime_out_of_sync = bool(
        expected_mode == "runtime"
        and runtime_exists
        and live_exists
        and live_mtime is not None
        and runtime_mtime is not None
        and live_mtime > runtime_mtime + 1
        and not live_is_runtime_pointer
        and not live_is_runtime_placeholder
        and not live_is_non_material_learning_note
        and not live_is_stale_runtime_mirror
        and live_hash != runtime_hash
    )
    live_newer_by_hours = None
    if runtime_out_of_sync and live_mtime is not None and runtime_mtime is not None:
        live_newer_by_hours = round((live_mtime - runtime_mtime) / 3600, 2)

    return {
        "relative_path": relative.as_posix(),
        "expected_mode": expected_mode,
        "expected_path": expected_path,
        "resolved_mode": resolved_mode,
        "resolved_path": resolved_path,
        "fallback_active": resolved_mode != expected_mode,
        "missing": resolved_mode == "missing",
        "runtime_path": runtime_path,
        "live_path": live_path,
        "snapshot_path": snapshot_path,
        "snapshot_id": snapshot_id,
        "runtime_out_of_sync": runtime_out_of_sync,
        "live_newer_by_hours": live_newer_by_hours,
        "runtime_sha256": runtime_hash,
        "live_sha256": live_hash,
        "live_is_runtime_pointer": live_is_runtime_pointer,
        "live_is_runtime_placeholder": live_is_runtime_placeholder,
        "live_is_non_material_learning_note": live_is_non_material_learning_note,
        "live_is_stale_runtime_mirror": live_is_stale_runtime_mirror,
    }


def resolve_snapshot_fallback_path(workspace_root: Path, relative_path: str | Path) -> Path:
    return resolve_memory_read_target(workspace_root, relative_path)["resolved_path"]


def build_core_memory_snapshot(
    workspace_root: Path,
    *,
    snapshot_id: str,
    relative_paths: tuple[str, ...] = DEFAULT_CORE_MEMORY_RELATIVE_PATHS,
) -> dict[str, Any]:
    root = workspace_root.resolve()
    target_dir = snapshot_dir(root, snapshot_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    entries: list[dict[str, Any]] = []
    for relative_str in relative_paths:
        relative = Path(relative_str)
        source = resolve_live_memory_write_path(root, relative)
        destination = target_dir / relative
        entry: dict[str, Any] = {
            "relative_path": relative.as_posix(),
            "live_path": _workspace_relative(root / relative, root),
            "source_path": _workspace_relative(source, root),
            "snapshot_path": _workspace_relative(destination, root),
            "exists": source.exists(),
        }
        if source.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            entry.update(
                {
                    "sha256": _sha256(source),
                    "bytes": source.stat().st_size,
                    "lines": _line_count(source),
                    "preview": _preview_lines(source),
                }
            )
        entries.append(entry)

    manifest = {
        "snapshot_id": snapshot_id,
        "captured_at_utc": _now_iso(),
        "workspace_root": str(root),
        "snapshot_root": _workspace_relative(target_dir, root),
        "relative_paths": list(relative_paths),
        "files": entries,
        "untracked_runtime_globs": list(UNTRACKED_CORE_MEMORY_RELATIVE_PATHS),
    }
    manifest_target = manifest_path(root, snapshot_id)
    manifest_target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# Core Memory Snapshot — {snapshot_id}",
        "",
        f"- Captured at: `{manifest['captured_at_utc']}`",
        f"- Snapshot root: `{manifest['snapshot_root']}`",
        "",
        "## Files",
        "",
    ]
    for entry in entries:
        lines.append(f"### `{entry['relative_path']}`")
        lines.append(f"- Exists: `{entry['exists']}`")
        if entry["exists"]:
            lines.append(f"- SHA-256: `{entry['sha256']}`")
            lines.append(f"- Size: `{entry['bytes']}` bytes")
            lines.append(f"- Lines: `{entry['lines']}`")
            preview = entry.get("preview") or {}
            head_lines = preview.get("head") or []
            tail_lines = preview.get("tail") or []
            if head_lines:
                lines.append("- Head:")
                lines.append("```text")
                lines.extend(head_lines)
                lines.append("```")
            if tail_lines:
                lines.append("- Tail:")
                lines.append("```text")
                lines.extend(tail_lines)
                lines.append("```")
        lines.append("")
    overview_path(root, snapshot_id).write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    pointer = {
        "snapshot_id": snapshot_id,
        "captured_at_utc": manifest["captured_at_utc"],
        "manifest_path": _workspace_relative(manifest_target, root),
    }
    latest_pointer_path(root).write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")
    return manifest


def restore_core_memory_snapshot(workspace_root: Path, *, snapshot_id: str | None = None) -> dict[str, Any]:
    root = workspace_root.resolve()
    chosen_snapshot_id = snapshot_id or latest_snapshot_id(root)
    if not chosen_snapshot_id:
        raise FileNotFoundError("No core memory snapshot is available.")
    manifest_target = manifest_path(root, chosen_snapshot_id)
    if not manifest_target.exists():
        raise FileNotFoundError(f"Missing manifest: {manifest_target}")
    manifest = json.loads(manifest_target.read_text(encoding="utf-8"))
    restored: list[str] = []
    for entry in manifest.get("files") or []:
        if not isinstance(entry, dict) or not entry.get("exists"):
            continue
        relative = Path(str(entry.get("relative_path") or ""))
        snapshot_copy = snapshot_dir(root, chosen_snapshot_id) / relative
        live_target = resolve_live_memory_write_path(root, relative)
        if not snapshot_copy.exists():
            continue
        live_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(snapshot_copy, live_target)
        restored.append(relative.as_posix())
    return {
        "snapshot_id": chosen_snapshot_id,
        "restored": restored,
        "count": len(restored),
    }
