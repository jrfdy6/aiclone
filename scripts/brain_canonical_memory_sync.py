#!/usr/bin/env python3
"""Drain queued Brain canonical-memory routes into local memory files."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_API_URL = "https://aiclone-production-32dc.up.railway.app"
WORKSPACE_ROOT = Path("/Users/neo/.openclaw/workspace")
MEMORY_ROOT = WORKSPACE_ROOT / "memory"
REPORT_ROOT = MEMORY_ROOT / "reports"
SCRIPT_DIR = WORKSPACE_ROOT / "scripts"


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
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def _append_chronicle(item: dict[str, Any]) -> None:
    summary = item["summary"]
    workspace_key = item["workspace_key"]
    scope = "shared_ops" if workspace_key == "shared_ops" else "workspace"
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "append_codex_handoff.py"),
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
    return "|".join(
        [
            str(route.get("queued_at") or ""),
            str(route.get("workspace_key") or ""),
            ",".join(_normalize_targets(route.get("targets"))),
            str(route.get("summary") or "")[:200],
        ]
    )


def _memory_line(item: dict[str, Any]) -> str:
    return f"- `{item['workspace_key']}`: {item['summary']}"


def build_report(api_url: str, limit: int, sync_live: bool) -> dict[str, Any]:
    now = _now()
    deltas = _fetch_json(f"{api_url.rstrip('/')}/api/persona/deltas?limit={limit}")
    rows = [item for item in deltas if isinstance(item, dict)]

    queued_items: list[dict[str, Any]] = []
    delta_updates: dict[str, dict[str, Any]] = {}

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
            item = {
                "delta_id": str(delta.get("id") or ""),
                "trait": str(delta.get("trait") or "Reviewed Brain signal"),
                "summary": _build_summary(delta, route),
                "workspace_key": _workspace_key_for(delta, route),
                "targets": targets,
                "queued_at": str(route.get("queued_at") or ""),
                "source_route": route,
            }
            queued_items.append(item)
            queued_keys.add(_route_key(route))

        if queued_keys:
            delta_updates[str(delta.get("id") or "")] = {
                "delta": delta,
                "queued_keys": queued_keys,
            }

    processed_items: list[dict[str, Any]] = []
    artifact_paths: list[str] = []

    if sync_live and queued_items:
        local_now = now.astimezone()
        daily_log_path = MEMORY_ROOT / f"{local_now:%Y-%m-%d}.md"

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in queued_items:
            for target in item["targets"]:
                grouped[target].append(item)

        if grouped.get("persistent_state"):
            path = MEMORY_ROOT / "persistent_state.md"
            _append_markdown(
                path,
                f"## Brain Triage Memory Sync — {local_now:%Y-%m-%d %H:%M %Z}",
                "\n".join(_memory_line(item) for item in grouped["persistent_state"]),
            )
            artifact_paths.append(str(path))

        if grouped.get("learnings"):
            path = MEMORY_ROOT / "LEARNINGS.md"
            _append_markdown(
                path,
                f"## Brain Triage Learnings — {local_now:%Y-%m-%d}",
                "\n".join(_memory_line(item) for item in grouped["learnings"]),
            )
            artifact_paths.append(str(path))

        if grouped.get("chronicle"):
            for item in grouped["chronicle"]:
                _append_chronicle(item)
            artifact_paths.append(str(MEMORY_ROOT / "codex_session_handoff.jsonl"))

        _append_markdown(
            daily_log_path,
            f"## Brain Canonical Memory Sync — {local_now:%Y-%m-%d %H:%M %Z}",
            "\n".join(
                [
                    f"- Processed reviewed Brain routes: `{len(queued_items)}`",
                    *[_memory_line(item) + f" -> `{', '.join(item['targets'])}`" for item in queued_items],
                ]
            ),
        )
        artifact_paths.append(str(daily_log_path))

        processed_at = _iso(now)
        for delta_id, update in delta_updates.items():
            delta = update["delta"]
            metadata = delta.get("metadata") or {}
            pending_routes = metadata.get("pending_canonical_memory_routes") or []
            remaining_routes: list[dict[str, Any]] = []
            history = list(metadata.get("brain_memory_sync_history") or [])
            for route in pending_routes:
                if not isinstance(route, dict):
                    continue
                key = _route_key(route)
                if key not in update["queued_keys"]:
                    remaining_routes.append(route)
                    continue
                route_workspace = _workspace_key_for(delta, route)
                targets = _normalize_targets(route.get("targets"))
                summary = _build_summary(delta, route)
                history.append(
                    {
                        "processed_at": processed_at,
                        "workspace_key": route_workspace,
                        "targets": targets,
                        "summary": summary[:500],
                        "source_delta_id": delta_id,
                        "queued_at": route.get("queued_at"),
                        "artifact_paths": artifact_paths,
                    }
                )
                processed_items.append(
                    {
                        "delta_id": delta_id,
                        "trait": str(delta.get("trait") or ""),
                        "workspace_key": route_workspace,
                        "targets": targets,
                        "summary": summary,
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

    return {
        "generated_at": _iso(now),
        "source": "brain_canonical_memory_sync",
        "sync_live": sync_live,
        "queued_route_count": len(queued_items),
        "processed_count": len(processed_items),
        "artifact_paths": artifact_paths,
        "processed_items": processed_items,
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
