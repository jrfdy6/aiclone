#!/usr/bin/env python3
"""Drain queued Brain canonical-memory routes into local memory files."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_API_URL = "https://aiclone-production-32dc.up.railway.app"
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from runtime_paths import PROJECT_ROOT, STATE_ROOT, memory_state_path, seed_memory_state_file


WORKSPACE_ROOT = PROJECT_ROOT
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
MEMORY_ROOT = memory_state_path(state_root=STATE_ROOT)
REPORT_ROOT = MEMORY_ROOT / "reports"
SCRIPT_DIR = WORKSPACE_ROOT / "scripts"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from brain_automation_context import (
    brain_signal_lines,
    build_brain_automation_context,
    portfolio_attention_lines,
    source_intelligence_lines,
)
from runtime_http import control_plane_headers


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _fetch_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers=control_plane_headers({"Accept": "application/json", "Content-Type": "application/json"}),
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    _atomic_write_text(path, json.dumps(payload, indent=2) + "\n")


def _write_markdown(path: Path, text: str) -> None:
    _atomic_write_text(path, text)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temporary = Path(temporary_raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


@contextmanager
def _sync_lock():
    lock_path = MEMORY_ROOT / "locks" / "brain_canonical_memory_sync.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _append_markdown(path: Path, heading: str, body: str) -> None:
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "append_markdown_block.py"),
        str(path),
        "--heading",
        heading,
        "--body",
        body,
    ]
    subprocess.run(cmd, check=True)


def _runtime_memory_path(relative_path: str) -> Path:
    return seed_memory_state_file(
        relative_path,
        project_root=WORKSPACE_ROOT,
        state_root=MEMORY_ROOT.parent,
    )


def _append_chronicle(item: dict[str, Any], marker: str) -> None:
    summary = item["summary"]
    workspace_key = item["workspace_key"]
    scope = "shared_ops" if workspace_key == "shared_ops" else "workspace"
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "append_codex_handoff.py"),
        "--path",
        str(_runtime_memory_path("memory/codex_session_handoff.jsonl")),
        "--summary",
        f"Brain triage promoted `{item['trait']}` into canonical memory for `{workspace_key}`.",
        "--workspace-key",
        workspace_key,
        "--scope",
        scope,
        "--source",
        "brain-canonical-memory-sync",
        "--author-agent",
        "brain",
        "--trigger",
        "brain_memory_sync",
        "--signal-type",
        "brain_triage",
        "--signal-type",
        "memory",
        "--project-update",
        summary,
        "--tag",
        "brain",
        "--tag",
        "canonical-memory-sync",
        "--tag",
        marker,
    ]
    for target in item["targets"]:
        cmd.extend(["--memory-promotion", f"{target}: {summary}"])
    subprocess.run(cmd, check=True)


def _build_summary(delta: dict[str, Any], route: dict[str, Any]) -> str:
    metadata = delta.get("metadata") or {}
    summary = str(route.get("summary") or "").strip()
    if summary:
        return summary
    owner_excerpt = str(metadata.get("owner_response_excerpt") or "").strip()
    if owner_excerpt:
        return owner_excerpt
    notes = str(delta.get("notes") or "").strip()
    if notes:
        return notes
    return str(delta.get("trait") or "Reviewed Brain signal").strip()


def _normalize_targets(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    allowed = {"persistent_state", "learnings", "chronicle"}
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        target = str(item or "").strip()
        if not target or target not in allowed or target in seen:
            continue
        seen.add(target)
        normalized.append(target)
    return normalized


def _workspace_key_for(delta: dict[str, Any], route: dict[str, Any]) -> str:
    route_workspace = str(route.get("workspace_key") or "").strip()
    if route_workspace:
        return route_workspace
    metadata = delta.get("metadata") or {}
    metadata_workspace = str(metadata.get("last_brain_route_workspace_key") or metadata.get("workspace_key") or "").strip()
    if metadata_workspace:
        return metadata_workspace
    target = str(delta.get("persona_target") or "").lower()
    trait = str(delta.get("trait") or "").lower()
    if "feeze" in target or "linkedin" in target or "feezie" in trait or "linkedin" in trait:
        return "linkedin-os"
    return "shared_ops"


def _route_key(route: dict[str, Any]) -> str:
    route_id = str(route.get("route_id") or "").strip()
    if route_id:
        return route_id
    return "|".join(
        [
            str(route.get("queued_at") or ""),
            str(route.get("workspace_key") or ""),
            ",".join(_normalize_targets(route.get("targets"))),
            str(route.get("summary") or "")[:200],
        ]
    )


def _route_id_for_pending(delta: dict[str, Any], route: dict[str, Any]) -> str:
    explicit = str(route.get("route_id") or "").strip()
    if explicit and len(explicit) <= 80 and all(character.isalnum() or character in {"-", "_"} for character in explicit):
        return explicit
    normalized = {
        "schema_version": "brain_canonical_memory_route/v1",
        "delta_id": str(delta.get("id") or "").strip(),
        "workspace_key": _workspace_key_for(delta, route),
        "targets": sorted(_normalize_targets(route.get("targets"))),
        "summary": " ".join(_build_summary(delta, route).split()),
        "selected_promotion_item_ids": sorted(
            str(value or "").strip()
            for value in (route.get("selected_promotion_item_ids") or [])
            if str(value or "").strip()
        ),
    }
    digest = hashlib.sha256(
        json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return f"brain-memory-route-v1-{digest[:32]}"


def _effect_marker(route_id: str, target: str) -> str:
    return f"brain-canonical-route:{route_id}:{target}"


def _path_contains_marker(path: Path, marker: str) -> bool:
    if not path.exists():
        return False
    try:
        return marker in path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False


def _memory_line(item: dict[str, Any]) -> str:
    return f"- `{item['workspace_key']}`: {item['summary']}"


def build_report(api_url: str, limit: int, sync_live: bool) -> dict[str, Any]:
    now = _now()
    brain_context = build_brain_automation_context(signal_limit=5)
    brain_context_lines = [
        *portfolio_attention_lines(brain_context, limit=2),
        *brain_signal_lines(brain_context, limit=3),
        *source_intelligence_lines(brain_context, limit=1),
    ]
    deltas = _fetch_json(f"{api_url.rstrip('/')}/api/persona/deltas?limit={limit}")
    rows = [item for item in deltas if isinstance(item, dict)]

    queued_items: list[dict[str, Any]] = []
    delta_updates: dict[str, dict[str, Any]] = {}
    seen_route_ids: set[str] = set()

    for delta in rows:
        metadata = delta.get("metadata") or {}
        pending_routes = metadata.get("pending_canonical_memory_routes") or []
        if not isinstance(pending_routes, list) or not pending_routes:
            continue

        queued_keys: set[str] = set()
        for route in pending_routes:
            if not isinstance(route, dict):
                continue
            if str(route.get("state") or "queued").strip().lower() != "queued":
                continue
            targets = _normalize_targets(route.get("targets"))
            if not targets:
                continue
            route_id = _route_id_for_pending(delta, route)
            queued_keys.add(route_id)
            if route_id in seen_route_ids:
                continue
            seen_route_ids.add(route_id)
            item = {
                "route_id": route_id,
                "delta_id": str(delta.get("id") or ""),
                "trait": str(delta.get("trait") or "Reviewed Brain signal"),
                "summary": _build_summary(delta, route),
                "workspace_key": _workspace_key_for(delta, route),
                "targets": targets,
                "queued_at": str(route.get("queued_at") or ""),
                "source_route": route,
            }
            queued_items.append(item)

        if queued_keys:
            delta_updates[str(delta.get("id") or "")] = {
                "delta": delta,
                "queued_keys": queued_keys,
            }

    processed_items: list[dict[str, Any]] = []
    artifact_paths: list[str] = []

    if sync_live and queued_items:
        with _sync_lock():
            local_now = now.astimezone()
            daily_log_path = seed_memory_state_file(
                f"{local_now:%Y-%m-%d}.md",
                project_root=WORKSPACE_ROOT,
                state_root=MEMORY_ROOT.parent,
            )
            target_paths = {
                "persistent_state": _runtime_memory_path("memory/persistent_state.md"),
                "learnings": _runtime_memory_path("memory/LEARNINGS.md"),
                "chronicle": _runtime_memory_path("memory/codex_session_handoff.jsonl"),
            }
            processed_by_route_id: dict[str, dict[str, Any]] = {}

            for item in queued_items:
                route_id = item["route_id"]
                effect_artifacts: list[str] = []
                effects: list[dict[str, Any]] = []
                for target in item["targets"]:
                    path = target_paths[target]
                    marker = _effect_marker(route_id, target)
                    reused = _path_contains_marker(path, marker)
                    if not reused and target == "chronicle":
                        _append_chronicle(item, marker)
                    elif not reused:
                        _append_markdown(
                            path,
                            f"## Brain Triage {target.replace('_', ' ').title()} — {route_id}",
                            f"<!-- {marker} -->\n{_memory_line(item)}",
                        )
                    effect_artifacts.append(str(path))
                    effects.append({"target": target, "marker": marker, "artifact_path": str(path), "reused": reused})

                daily_marker = _effect_marker(route_id, "daily_log")
                daily_reused = _path_contains_marker(daily_log_path, daily_marker)
                if not daily_reused:
                    _append_markdown(
                        daily_log_path,
                        f"## Brain Canonical Memory Sync — {route_id}",
                        (
                            f"<!-- {daily_marker} -->\n"
                            f"{_memory_line(item)} -> `{', '.join(item['targets'])}`"
                        ),
                    )
                effect_artifacts.append(str(daily_log_path))
                effects.append(
                    {
                        "target": "daily_log",
                        "marker": daily_marker,
                        "artifact_path": str(daily_log_path),
                        "reused": daily_reused,
                    }
                )
                artifact_paths.extend(effect_artifacts)
                processed_by_route_id[route_id] = {
                    **item,
                    "artifact_paths": list(dict.fromkeys(effect_artifacts)),
                    "effects": effects,
                }

            artifact_paths = list(dict.fromkeys(artifact_paths))
            processed_at = _iso(now)
            for delta_id, update in delta_updates.items():
                delta = update["delta"]
                metadata = delta.get("metadata") or {}
                pending_routes = metadata.get("pending_canonical_memory_routes") or []
                remaining_routes: list[dict[str, Any]] = []
                history = [item for item in (metadata.get("brain_memory_sync_history") or []) if isinstance(item, dict)]
                history_route_ids = {
                    str(item.get("route_id") or "").strip()
                    for item in history
                    if str(item.get("route_id") or "").strip()
                }
                delta_processed: list[dict[str, Any]] = []
                for route in pending_routes:
                    if not isinstance(route, dict):
                        continue
                    route_id = _route_id_for_pending(delta, route)
                    if route_id not in update["queued_keys"]:
                        remaining_routes.append(route)
                        continue
                    processed = processed_by_route_id.get(route_id)
                    if processed is None:
                        remaining_routes.append(route)
                        continue
                    route_workspace = _workspace_key_for(delta, route)
                    targets = _normalize_targets(route.get("targets"))
                    summary = _build_summary(delta, route)
                    if route_id not in history_route_ids:
                        history.append(
                            {
                                "route_id": route_id,
                                "processed_at": processed_at,
                                "workspace_key": route_workspace,
                                "targets": targets,
                                "summary": summary[:500],
                                "source_delta_id": delta_id,
                                "queued_at": route.get("queued_at"),
                                "artifact_paths": processed["artifact_paths"],
                                "effects": processed["effects"],
                            }
                        )
                        history_route_ids.add(route_id)
                    if not any(item.get("route_id") == route_id for item in delta_processed):
                        delta_processed.append(
                            {
                                "route_id": route_id,
                                "delta_id": delta_id,
                                "trait": str(delta.get("trait") or ""),
                                "workspace_key": route_workspace,
                                "targets": targets,
                                "summary": summary,
                                "effects": processed["effects"],
                            }
                        )

                _fetch_json(
                    f"{api_url.rstrip('/')}/api/persona/deltas/{delta_id}",
                    method="PATCH",
                    payload={
                        "metadata": {
                            "pending_canonical_memory_routes": remaining_routes,
                            "brain_memory_sync_history": history,
                            "last_brain_memory_sync_at": processed_at,
                        }
                    },
                )
                processed_items.extend(delta_processed)

    return {
        "generated_at": _iso(now),
        "source": "brain_canonical_memory_sync",
        "sync_live": sync_live,
        "queued_route_count": len(queued_items),
        "processed_count": len(processed_items),
        "artifact_paths": artifact_paths,
        "processed_items": processed_items,
        "brain_context": brain_context,
        "brain_context_lines": brain_context_lines,
        "source_paths": list(
            dict.fromkeys(
                [
                    f"{api_url.rstrip('/')}/api/persona/deltas?limit={limit}",
                    *(brain_context.get("source_paths") or []),
                    *artifact_paths,
                ]
            )
        ),
    }


def _publish_status(api_url: str, report: dict[str, Any]) -> None:
    _fetch_json(
        f"{api_url.rstrip('/')}/api/brain/memory-sync-status",
        method="POST",
        payload=report,
    )


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Brain Canonical Memory Sync Report",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Live sync: `{report['sync_live']}`",
        f"- Queued routes seen: `{report['queued_route_count']}`",
        f"- Routes processed: `{report['processed_count']}`",
        "",
        "## Artifacts",
    ]
    if not report.get("artifact_paths"):
        lines.append("- None.")
    else:
        for path in report["artifact_paths"]:
            lines.append(f"- `{path}`")
    lines.extend(["", "## Brain Context"])
    brain_context_lines = report.get("brain_context_lines") or ["No active Brain Signal or portfolio blocker changed this sync run."]
    for item in brain_context_lines:
        lines.append(f"- {item}")
    lines.extend(["", "## Processed Items"])
    if not report.get("processed_items"):
        lines.append("- None.")
    else:
        for item in report["processed_items"]:
            lines.append(
                f"- `{item['workspace_key']}` · `{', '.join(item['targets'])}` · {item['summary']}"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-json", default=str(REPORT_ROOT / "brain_canonical_memory_sync_latest.json"))
    parser.add_argument("--output-md", default=str(REPORT_ROOT / "brain_canonical_memory_sync_latest.md"))
    args = parser.parse_args()

    report = build_report(args.api_url, limit=args.limit, sync_live=not args.dry_run)
    _write_json(Path(args.output_json).expanduser(), report)
    _write_markdown(Path(args.output_md).expanduser(), _markdown_report(report))
    if not args.dry_run:
        _publish_status(args.api_url, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
