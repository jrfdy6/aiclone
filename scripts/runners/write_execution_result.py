#!/usr/bin/env python3
"""Write execution results back into PM state, Chronicle, and durable memory."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import stat
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(os.getenv("AI_CLONE_ROOT") or Path(__file__).resolve().parents[2]).expanduser().resolve()
BACKEND_ROOT = WORKSPACE_ROOT / "backend"
MEMORY_ROOT = WORKSPACE_ROOT / "memory"
SCRIPT_DIR = WORKSPACE_ROOT / "scripts"
RUNNERS_DIR = SCRIPT_DIR / "runners"
DEFAULT_API_URL = "https://aiclone-production-32dc.up.railway.app"

if str(RUNNERS_DIR) not in sys.path:
    sys.path.insert(0, str(RUNNERS_DIR))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.core_memory_snapshot_service import resolve_live_memory_write_path
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from app.models import PMExecutionResultCommitRequest
from execution_result_outbox import (
    OUTBOX_PENDING_EXIT,
    ExecutionResultOutboxConflict,
    ExecutionResultOutboxSecurityError,
    ExecutionResultOutboxUnavailable,
    flush_pending_outbox,
    mark_outbox_materialized,
    prepare_outbox_entry,
    reconcile_outbox_entry,
)
from runtime_http import control_plane_headers, open_control_plane_request, validate_control_plane_url
from runtime_paths import STATE_ROOT


CODEX_HANDOFF_PATH = resolve_live_memory_write_path(WORKSPACE_ROOT, "memory/codex_session_handoff.jsonl")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _read_list(values: list[str] | None, file_path: str | None) -> list[str]:
    items = [value.strip() for value in (values or []) if value and value.strip()]
    if file_path:
        text = Path(file_path).read_text(encoding="utf-8")
        items.extend(line.strip() for line in text.splitlines() if line.strip())
    return items


def _read_summary(args: argparse.Namespace) -> str:
    if args.summary is not None:
        return args.summary.strip()
    if args.summary_file is not None:
        return Path(args.summary_file).read_text(encoding="utf-8").strip()
    return sys.stdin.read().strip()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temp_path = Path(temp_raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _write_text_once(path: Path, text: str) -> bool:
    if path.is_symlink():
        raise RuntimeError(f"Stable execution-result artifact must not be a symlink: {path}")
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise RuntimeError(f"Stable execution-result artifact conflicts with existing content: {path}")
        return False
    _atomic_write_text(path, text)
    return True


def _write_json_once(path: Path, payload: Any) -> bool:
    return _write_text_once(path, json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n")


def _append_text(path: Path, text: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as exc:
        raise RuntimeError(f"Could not safely append execution-result memory: {path}") from exc
    try:
        file_stat = os.fstat(fd)
        if not stat.S_ISREG(file_stat.st_mode):
            raise RuntimeError(f"Execution-result memory target is not a regular file: {path}")
        encoded = text.encode("utf-8")
        offset = 0
        while offset < len(encoded):
            written = os.write(fd, encoded[offset:])
            if written <= 0:
                raise RuntimeError(f"Execution-result memory append did not complete: {path}")
            offset += written
        os.fsync(fd)
    finally:
        os.close(fd)


def _append_jsonl_once(path: Path, payload: dict[str, Any], *, result_id: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError(f"Execution-result Chronicle target must not be a symlink: {path}")
    existing = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    for line in existing.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and str(item.get("result_id") or "") == result_id:
            if item != payload:
                raise RuntimeError(f"Chronicle result id conflicts with existing content: {result_id}")
            return False
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    _append_text(path, prefix + json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")
    return True


def _append_markdown_once(path: Path, heading: str, body: str, *, result_id: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError(f"Execution-result memory target must not be a symlink: {path}")
    marker = f"<!-- execution-result:{result_id} -->"
    existing = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    if marker in existing:
        return False
    block = f"{heading.strip()}\n\n{body.strip()}\n\n{marker}\n"
    prefix = "" if not existing else ("" if existing.endswith("\n\n") else "\n" if existing.endswith("\n") else "\n\n")
    _append_text(path, prefix + block)
    return True


def _runtime_memory_path(relative_path: str) -> Path:
    return resolve_live_memory_write_path(WORKSPACE_ROOT, relative_path)


def _require_contained_path(raw_path: str, root: Path, *, label: str) -> Path:
    path = Path(raw_path).expanduser().resolve()
    resolved_root = root.resolve()
    if path != resolved_root and resolved_root not in path.parents:
        raise RuntimeError(f"{label} is outside the AI Clone workspace: {path}")
    return path


def _expected_result_paths(operation: PMExecutionResultCommitRequest) -> tuple[Path, Path]:
    result_id = str(operation.result_id)
    result_path = (MEMORY_ROOT / "runner-results" / operation.runner_id / f"{result_id}.json").resolve()
    memo_path = (MEMORY_ROOT / "runner-memos" / operation.runner_id / f"{result_id}_execution_result.md").resolve()
    _require_contained_path(str(result_path), WORKSPACE_ROOT, label="Execution-result JSON")
    _require_contained_path(str(memo_path), WORKSPACE_ROOT, label="Execution-result memo")
    if Path(operation.result_path).expanduser().resolve() != result_path:
        raise RuntimeError("Execution-result JSON path does not match its stable result id.")
    if Path(operation.memo_path).expanduser().resolve() != memo_path:
        raise RuntimeError("Execution-result memo path does not match its stable result id.")
    return result_path, memo_path


def _materialization_lock_path() -> Path:
    return STATE_ROOT / "locks" / "execution-result-materialization.lock"


def _materialization_lock():
    class _Lock:
        def __enter__(self):
            path = _materialization_lock_path()
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.parent.chmod(0o700)
            flags = os.O_RDWR | os.O_CREAT
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            try:
                fd = os.open(path, flags, 0o600)
            except OSError as exc:
                raise RuntimeError("Execution-result materialization lock could not be opened safely.") from exc
            try:
                lock_stat = os.fstat(fd)
                if not stat.S_ISREG(lock_stat.st_mode):
                    raise RuntimeError("Execution-result materialization lock must be a regular file.")
                os.fchmod(fd, 0o600)
                self.handle = os.fdopen(fd, "a+", encoding="utf-8")
            except Exception:
                os.close(fd)
                raise
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
            return self

        def __exit__(self, exc_type, exc, tb):
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()
            return False

    return _Lock()


def _materialize_execution_result(operation: PMExecutionResultCommitRequest) -> None:
    """Write all local result artifacts exactly once for one stable result id."""

    result_id = str(operation.result_id)
    result_path, memo_path = _expected_result_paths(operation)
    work_order_path = _require_contained_path(operation.work_order_path, WORKSPACE_ROOT, label="Work order")
    workspace_memory_path = (
        _require_contained_path(operation.workspace_result_path, WORKSPACE_ROOT, label="Workspace result path")
        if operation.workspace_result_path
        else None
    )
    created_at = operation.created_at.astimezone(timezone.utc)
    local_created_at = operation.created_at.astimezone()
    daily_path = MEMORY_ROOT / f"{local_created_at.date().isoformat()}.md"
    result_payload = {
        "schema_version": "execution_result/v1",
        "result_id": result_id,
        "claim_id": str(operation.claim_id),
        "runner_id": operation.runner_id,
        "author_agent": operation.author_agent,
        "created_at": _iso(created_at),
        "workspace_key": operation.workspace_key,
        "card_id": str(operation.card_id),
        "title": operation.title,
        "status": operation.status,
        "summary": operation.summary,
        "blockers": operation.blockers,
        "decisions": operation.decisions,
        "learnings": operation.learnings,
        "outcomes": operation.outcomes,
        "follow_ups": operation.follow_ups,
        "host_actions": operation.host_actions,
        "host_action_proof": operation.host_action_proof,
        "project_updates": operation.project_updates,
        "memory_promotions": operation.memory_promotions,
        "persistent_state_updates": operation.persistent_state_updates,
        "artifacts": operation.artifacts,
    }

    memo_lines = [
        f"# Execution Result - {operation.title}",
        "",
        f"- Result: `{result_id}`",
        f"- Claim: `{operation.claim_id}`",
        f"- Card: `{operation.card_id}`",
        f"- Workspace: `{operation.workspace_key}`",
        f"- Status: `{operation.status}`",
        "",
        "## Summary",
        operation.summary,
        "",
        "## Blockers",
        *[f"- {item}" for item in (operation.blockers or ["None."])],
        "",
        "## Decisions",
        *[f"- {item}" for item in (operation.decisions or ["None."])],
        "",
        "## Learnings",
        *[f"- {item}" for item in (operation.learnings or ["None."])],
        "",
        "## Outcomes",
        *[f"- {item}" for item in (operation.outcomes or ["None."])],
        "",
        "## Follow-ups",
        *[f"- {item}" for item in (operation.follow_ups or ["None."])],
        "",
        "## Host Actions",
        *[f"- {item}" for item in (operation.host_actions or ["None."])],
        "",
        "## Host Action Proof",
        *[f"- {item}" for item in (operation.host_action_proof or ["None."])],
    ]
    memo_text = "\n".join(memo_lines).rstrip() + "\n"

    chronicle_entry = {
        "schema_version": "codex_chronicle/v1",
        "entry_id": result_id,
        "result_id": result_id,
        "claim_id": str(operation.claim_id),
        "created_at": _iso(created_at),
        "source": f"{operation.runner_id}-execution-result",
        "author_agent": operation.author_agent,
        "workspace_key": operation.workspace_key,
        "scope": "workspace" if operation.workspace_key != "shared_ops" else "shared_ops",
        "trigger": "execution_result",
        "importance": "high",
        "summary": operation.summary,
        "signal_types": ["execution", "learning", "outcome", "pm"],
        "decisions": operation.decisions,
        "blockers": operation.blockers,
        "project_updates": operation.project_updates or [f"Execution result recorded for `{operation.title}`."],
        "learning_updates": operation.learnings,
        "identity_signals": [],
        "mindset_signals": [
            "Execution results should feed the same durable memory loop used by standups and the Codex control plane."
        ],
        "phrase_signals": [],
        "outcomes": operation.outcomes or [f"Execution result file written to {result_path}"],
        "follow_ups": [*operation.follow_ups, *[f"Host: {item}" for item in operation.host_actions]],
        "memory_promotions": [*operation.memory_promotions, *operation.persistent_state_updates],
        "pm_candidates": [*operation.follow_ups, *[f"Host: {item}" for item in operation.host_actions]],
        "artifacts": operation.artifacts,
        "tags": [operation.runner_id, "execution-result", operation.workspace_key],
    }

    daily_lines = [
        f"- Result ID: `{result_id}`",
        f"- Card: `{operation.card_id}`",
        f"- Workspace: `{operation.workspace_key}`",
        f"- Result: {operation.summary}",
    ]
    for heading, values in (
        ("Outcomes", operation.outcomes),
        ("Blockers", operation.blockers),
        ("Follow-ups", operation.follow_ups),
        ("Host Actions", operation.host_actions),
        ("Host Action Proof", operation.host_action_proof),
    ):
        if values:
            daily_lines.extend(["", f"### {heading}", *[f"- {item}" for item in values]])

    with _materialization_lock():
        _write_json_once(result_path, result_payload)
        _write_text_once(memo_path, memo_text)
        _append_jsonl_once(CODEX_HANDOFF_PATH, chronicle_entry, result_id=result_id)
        _append_markdown_once(
            daily_path,
            f"## {operation.runner_id.capitalize()} Execution Result — {local_created_at:%Y-%m-%d %H:%M %Z}",
            "\n".join(daily_lines),
            result_id=result_id,
        )
        if workspace_memory_path is not None:
            _append_markdown_once(
                workspace_memory_path,
                f"## {operation.author_agent} Workspace Result — {local_created_at:%Y-%m-%d %H:%M %Z}",
                "\n".join(daily_lines),
                result_id=result_id,
            )
        if operation.learnings:
            _append_markdown_once(
                _runtime_memory_path("memory/LEARNINGS.md"),
                f"## {operation.runner_id.capitalize()} Execution Learnings — {local_created_at:%Y-%m-%d}",
                "\n".join(f"- {item}" for item in operation.learnings),
                result_id=result_id,
            )
        if operation.memory_promotions or operation.persistent_state_updates:
            _append_markdown_once(
                _runtime_memory_path("memory/persistent_state.md"),
                f"## {operation.runner_id.capitalize()} Execution State — {local_created_at:%Y-%m-%d %H:%M %Z}",
                "\n".join(
                    f"- {item}" for item in [*operation.memory_promotions, *operation.persistent_state_updates]
                ),
                result_id=result_id,
            )


def _parse_work_order_context(work_order: dict[str, Any], work_order_path: Path) -> dict[str, Any]:
    brief = work_order.get("execution_brief")
    if isinstance(brief, dict):
        card_id = str(brief.get("card_id") or "")
        workspace_key = str(brief.get("workspace_key") or "shared_ops")
        title = str(brief.get("title") or "Untitled execution")
        workspace_root = None
    else:
        card_id = str(work_order.get("pm_card_id") or work_order.get("card_id") or "")
        workspace_key = str(work_order.get("workspace_key") or "shared_ops")
        title = str(work_order.get("title") or "Untitled execution")
        workspace_root = work_order_path.parent.parent if work_order_path.parent.name == "dispatch" else None
    if not card_id:
        raise SystemExit("Work order is missing a PM card id.")
    return {
        "card_id": card_id,
        "workspace_key": workspace_key,
        "title": title,
        "workspace_root": workspace_root,
        "preferred_target_agent": work_order.get("workspace_agent") or work_order.get("owner_agent"),
    }


def _fetch_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    validated_url = validate_control_plane_url(url)
    data = None
    headers = control_plane_headers({"Content-Type": "application/json"})
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(validated_url, data=data, headers=headers, method=method)
    with open_control_plane_request(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _optional_backend_imports() -> dict[str, Any]:
    if not any(os.getenv(name) for name in ("OPEN_BRAIN_DATABASE_URL", "BRAIN_VECTOR_DATABASE_URL", "DATABASE_URL")):
        return {"mode": "api"}
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    loaded: dict[str, Any] = {}
    try:
        from app.models import PMCardUpdate  # type: ignore
        from app.services.pm_card_service import auto_progress_card, get_card, update_card  # type: ignore

        loaded["PMCardUpdate"] = PMCardUpdate
        loaded["auto_progress_card"] = auto_progress_card
        loaded["get_card"] = get_card
        loaded["update_card"] = update_card
        loaded["mode"] = "service"
    except Exception as exc:  # pragma: no cover - runtime dependent
        loaded["mode"] = "api"
        loaded["error"] = str(exc)
    return loaded


def _load_card(imports: dict[str, Any], api_url: str, card_id: str) -> dict[str, Any]:
    if imports.get("mode") == "service":
        card = imports["get_card"](card_id)
        if card is None:
            raise SystemExit(f"PM card not found: {card_id}")
        return card.model_dump(mode="json")
    payload = _fetch_json(f"{api_url}/api/pm/cards?limit=200")
    if not isinstance(payload, list):
        raise SystemExit("PM card list response was not a list.")
    for card in payload:
        if str(card.get("id")) == card_id:
            return card
    raise SystemExit(f"PM card not found: {card_id}")


def _update_card(imports: dict[str, Any], api_url: str, card_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if imports.get("mode") == "service":
        updated = imports["update_card"](
            card_id,
            imports["PMCardUpdate"](
                status=payload["status"],
                payload=payload["payload"],
            ),
        )
        if updated is None:
            raise SystemExit(f"Failed to update PM card {card_id}")
        return updated.model_dump(mode="json")
    return _fetch_json(f"{api_url}/api/pm/cards/{card_id}", method="PATCH", payload=payload)


def _auto_progress_review_card(imports: dict[str, Any], api_url: str, card_id: str) -> dict[str, Any] | None:
    try:
        if imports.get("mode") == "service" and callable(imports.get("auto_progress_card")):
            return imports["auto_progress_card"](card_id, record_audit=False)
        return _fetch_json(f"{api_url}/api/pm/cards/{card_id}/auto-progress", method="POST")
    except Exception as exc:  # pragma: no cover - runtime dependent
        print(
            f"[write_execution_result] Warning: automatic PM review progression failed for {card_id}: {exc}. "
            "Leaving the card in review."
        )
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-order", help="Path to a runner or workspace-agent work order JSON.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--force-api", action="store_true", help="Skip backend service imports and write back through the API only.")
    parser.add_argument("--runner-id", default="neo")
    parser.add_argument("--author-agent", default="neo")
    parser.add_argument("--claim-id", help="UUID claim written atomically when the PM card entered running state.")
    parser.add_argument("--worker-id", help="Worker id that owns the active PM execution claim.")
    parser.add_argument("--result-id", help="Stable UUID for an explicit replay; defaults deterministically from card + claim.")
    parser.add_argument(
        "--reconcile-outbox",
        action="store_true",
        help="Materialize and commit all private pending execution-result operations, then exit.",
    )
    parser.add_argument("--status", default="review", choices=["review", "done", "blocked"])
    parser.add_argument("--summary", help="Short summary of what the execution produced.")
    parser.add_argument("--summary-file")
    parser.add_argument("--blocker", action="append", dest="blockers")
    parser.add_argument("--blocker-file")
    parser.add_argument("--decision", action="append", dest="decisions")
    parser.add_argument("--decision-file")
    parser.add_argument("--learning", action="append", dest="learnings")
    parser.add_argument("--learning-file")
    parser.add_argument("--outcome", action="append", dest="outcomes")
    parser.add_argument("--outcome-file")
    parser.add_argument("--follow-up", action="append", dest="follow_ups")
    parser.add_argument("--follow-up-file")
    parser.add_argument("--host-action", action="append", dest="host_actions")
    parser.add_argument("--host-action-file")
    parser.add_argument("--host-action-proof", action="append", dest="host_action_proof")
    parser.add_argument("--host-action-proof-file")
    parser.add_argument("--project-update", action="append", dest="project_updates")
    parser.add_argument("--project-update-file")
    parser.add_argument("--memory-promotion", action="append", dest="memory_promotions")
    parser.add_argument("--memory-promotion-file")
    parser.add_argument("--persistent-state", action="append", dest="persistent_state")
    parser.add_argument("--persistent-state-file")
    parser.add_argument("--artifact", action="append", dest="artifacts")
    parser.add_argument("--artifact-file")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.reconcile_outbox:
        missing = [
            flag
            for flag, value in (
                ("--work-order", args.work_order),
                ("--claim-id", args.claim_id),
                ("--worker-id", args.worker_id),
            )
            if not str(value or "").strip()
        ]
        if missing:
            parser.error(f"the following arguments are required for a result write: {', '.join(missing)}")
    return args


def _stable_result_id(card_id: str, claim_id: str, supplied: str | None) -> str:
    if supplied:
        return str(uuid.UUID(str(supplied)))
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:pm-execution-result:{card_id}:{claim_id}"))


def _reconcile_pending(api_url: str) -> int:
    report = flush_pending_outbox(api_url=api_url, materialize=_materialize_execution_result)
    print(json.dumps(report, indent=2, ensure_ascii=True, sort_keys=True))
    return 0 if report["pending"] == 0 and report["conflicts"] == 0 else OUTBOX_PENDING_EXIT


def main() -> int:
    args = parse_args()
    if args.reconcile_outbox:
        return _reconcile_pending(args.api_url.rstrip("/"))

    summary = _read_summary(args)
    if not summary:
        raise SystemExit("A non-empty summary is required.")

    work_order_path = Path(args.work_order).expanduser()
    if not work_order_path.exists():
        raise SystemExit(f"Work order not found: {work_order_path}")
    work_order = json.loads(work_order_path.read_text(encoding="utf-8"))
    context = _parse_work_order_context(work_order, work_order_path)
    card_id = str(context["card_id"])
    workspace_key = str(context["workspace_key"])
    title = str(context["title"])
    workspace_root = context.get("workspace_root")
    now = _now()
    try:
        claim_id = str(uuid.UUID(str(args.claim_id)))
        result_id = _stable_result_id(card_id, claim_id, args.result_id)
    except ValueError as exc:
        raise SystemExit("claim-id and result-id must be UUIDs.") from exc

    decisions = _read_list(args.decisions, args.decision_file)
    blockers = _read_list(args.blockers, args.blocker_file)
    learnings = _read_list(args.learnings, args.learning_file)
    outcomes = _read_list(args.outcomes, args.outcome_file)
    follow_ups = _read_list(args.follow_ups, args.follow_up_file)
    host_actions = _read_list(args.host_actions, args.host_action_file)
    host_action_proof = _read_list(args.host_action_proof, args.host_action_proof_file)
    project_updates = _read_list(args.project_updates, args.project_update_file)
    memory_promotions = _read_list(args.memory_promotions, args.memory_promotion_file)
    persistent_state = _read_list(args.persistent_state, args.persistent_state_file)
    artifacts = _read_list(args.artifacts, args.artifact_file)

    result_path = (MEMORY_ROOT / "runner-results" / args.runner_id / f"{result_id}.json").resolve()
    memo_path = (MEMORY_ROOT / "runner-memos" / args.runner_id / f"{result_id}_execution_result.md").resolve()
    workspace_memory_path = (
        workspace_root.resolve() / "memory" / "execution_log.md"
        if isinstance(workspace_root, Path)
        else None
    )
    all_artifacts = list(
        dict.fromkeys([str(result_path), str(memo_path), str(work_order_path.resolve()), *artifacts])
    )
    try:
        operation = PMExecutionResultCommitRequest(
            card_id=card_id,
            claim_id=claim_id,
            worker_id=str(args.worker_id),
            result_id=result_id,
            runner_id=args.runner_id,
            author_agent=args.author_agent,
            created_at=now,
            workspace_key=workspace_key,
            title=title,
            status=args.status,
            summary=summary,
            decisions=decisions,
            blockers=blockers,
            learnings=learnings,
            outcomes=outcomes,
            follow_ups=follow_ups,
            host_actions=host_actions,
            host_action_proof=host_action_proof,
            project_updates=project_updates,
            memory_promotions=memory_promotions,
            persistent_state_updates=persistent_state,
            artifacts=all_artifacts,
            result_path=str(result_path),
            memo_path=str(memo_path),
            work_order_path=str(work_order_path.resolve()),
            workspace_result_path=str(workspace_memory_path.resolve()) if workspace_memory_path is not None else None,
        )
    except Exception as exc:
        raise SystemExit(f"Execution result failed bounded validation: {exc}") from exc

    if args.dry_run:
        print(operation.model_dump_json(indent=2))
        print("Dry run: private outbox, durable memory, and PM state were not changed.")
        return 0

    outbox_path: Path | None = None
    try:
        # This must happen before any non-idempotent local memory operation.
        outbox_path = prepare_outbox_entry(operation)
        _materialize_execution_result(operation)
        mark_outbox_materialized(outbox_path)
        committed = reconcile_outbox_entry(outbox_path, api_url=args.api_url.rstrip("/"))
    except (ExecutionResultOutboxUnavailable, ExecutionResultOutboxConflict, ExecutionResultOutboxSecurityError) as exc:
        print(f"[write_execution_result] PM write-back pending reconciliation: {exc}")
        if outbox_path is not None:
            print(f"Pending outbox entry: {outbox_path}")
        return OUTBOX_PENDING_EXIT
    except Exception as exc:
        print(f"[write_execution_result] Local materialization pending replay: {exc}")
        if outbox_path is not None:
            print(f"Pending outbox entry: {outbox_path}")
        return OUTBOX_PENDING_EXIT

    print(f"Execution result committed for {title}")
    print(f"Result JSON: {result_path}")
    print(f"Result memo: {memo_path}")
    print(f"Updated PM card: {committed.card.id} -> {committed.card.status}")
    print(f"Commit disposition: {committed.disposition}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
