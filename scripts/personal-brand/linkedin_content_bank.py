from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKSPACE_RELATIVE = "workspaces/linkedin-content-os"
POST_SCHEMA_VERSION = "linkedin_content_bank_post/v1"
EVENT_SCHEMA_VERSION = "linkedin_content_bank_event/v1"
REJECTION_SCHEMA_VERSION = "linkedin_content_bank_rejection/v1"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def content_bank_root(workspace_dir: Path) -> Path:
    return workspace_dir / "content_bank"


def reports_root(workspace_dir: Path) -> Path:
    return workspace_dir / "reports"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _append_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def _hash_key(*parts: str) -> str:
    payload = "\n".join(clean_text(part).lower() for part in parts if clean_text(part))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _workspace_path(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if text.startswith(WORKSPACE_RELATIVE):
        return text
    if text.startswith(("drafts/", "plans/", "research/", "docs/", "reports/", "content_bank/")):
        return f"{WORKSPACE_RELATIVE}/{text}"
    return text


def _resolve_workspace_path(repo_root: Path, workspace_dir: Path, value: Any) -> Path | None:
    text = clean_text(value)
    if not text:
        return None
    path = Path(text)
    if path.is_absolute():
        return path
    if text.startswith(WORKSPACE_RELATIVE):
        return repo_root / text
    return workspace_dir / text


def _source_refs(item: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for value in (item.get("source_path"), item.get("source_url")):
        text = _workspace_path(value) if value == item.get("source_path") else clean_text(value)
        if text and text not in refs:
            refs.append(text)
    return refs


def _canon_refs(repo_root: Path) -> list[str]:
    candidates = [
        "memory/runtime/LEARNINGS.md",
        "memory/runtime/persistent_state.md",
        "knowledge/persona/feeze/identity/VOICE_PATTERNS.md",
        "knowledge/persona/feeze/history/story_bank.md",
        "knowledge/source-intelligence/index.json",
    ]
    return [path for path in candidates if (repo_root / path).exists()]


def _candidate_fingerprint(item: dict[str, Any]) -> str:
    return _hash_key(
        clean_text(item.get("idea_id")),
        _workspace_path(item.get("draft_path")),
        _workspace_path(item.get("source_path")),
        clean_text(item.get("source_url")),
        clean_text(item.get("title")),
    )


def _existing_fingerprints(records: list[dict[str, Any]]) -> set[str]:
    fingerprints: set[str] = set()
    for record in records:
        fingerprint = clean_text(record.get("fingerprint"))
        if fingerprint:
            fingerprints.add(fingerprint)
            continue
        metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        fingerprints.add(
            _hash_key(
                clean_text(metadata.get("idea_id")),
                clean_text(record.get("draft_path")),
                " ".join(str(ref) for ref in record.get("source_refs") or []),
                clean_text(record.get("title")),
            )
        )
    return {item for item in fingerprints if item}


def _load_latent_items(workspace_dir: Path) -> list[dict[str, Any]]:
    payload = _read_json(workspace_dir / "plans" / "latent_ideas.json")
    items = payload.get("items")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _drafted_latent_items(workspace_dir: Path, repo_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    bankable: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for item in _load_latent_items(workspace_dir):
        transform_status = clean_text(item.get("transform_status")).lower()
        draft_path = _workspace_path(item.get("draft_path"))
        if transform_status != "drafted" and not draft_path:
            continue
        if not draft_path:
            rejected.append({"item": item, "reason": "drafted_candidate_missing_draft_path"})
            continue
        resolved = _resolve_workspace_path(repo_root, workspace_dir, draft_path)
        if resolved is None or not resolved.exists():
            rejected.append({"item": item, "reason": "drafted_candidate_missing_draft_file"})
            continue
        bankable.append(item)
    return bankable, rejected


def _post_record(item: dict[str, Any], *, repo_root: Path, created_at: str) -> dict[str, Any]:
    transform_plan = item.get("transform_plan") if isinstance(item.get("transform_plan"), dict) else {}
    draft_path = _workspace_path(item.get("draft_path"))
    source_refs = _source_refs(item)
    fingerprint = _candidate_fingerprint(item)
    return {
        "schema_version": POST_SCHEMA_VERSION,
        "id": f"feezie-bank-{fingerprint}",
        "fingerprint": fingerprint,
        "created_at": created_at,
        "workspace": WORKSPACE_RELATIVE,
        "status": "banked",
        "terminal_state": "banked",
        "lane": clean_text(item.get("content_lane")) or "linkedin",
        "content_type": clean_text(item.get("content_type")) or "post",
        "title": clean_text(item.get("title")) or "Untitled banked post",
        "draft_path": draft_path,
        "source_refs": source_refs,
        "brain_signal_ids": [],
        "canon_refs": _canon_refs(repo_root),
        "quality_gate": {
            "source_grounded": bool(source_refs),
            "draft_exists": bool(draft_path),
            "voice_posture": "owner_review_required",
            "promotion_rule": clean_text(transform_plan.get("promotion_rule")),
        },
        "why_this_exists": clean_text(transform_plan.get("proposed_angle"))
        or clean_text(item.get("suggested_fix"))
        or clean_text(item.get("latent_reason")),
        "next_action": "owner_review",
        "metadata": {
            "idea_id": clean_text(item.get("idea_id")),
            "source_kind": clean_text(item.get("source_kind")),
            "latent_reason": clean_text(item.get("latent_reason")),
            "transform_type": clean_text(transform_plan.get("transform_type")),
            "proof_prompt": clean_text(transform_plan.get("proof_prompt")),
            "score": item.get("score"),
        },
    }


def _rejection_record(item: dict[str, Any], *, reason: str, created_at: str) -> dict[str, Any]:
    fingerprint = _candidate_fingerprint(item) or _hash_key(clean_text(item.get("title")), reason)
    return {
        "schema_version": REJECTION_SCHEMA_VERSION,
        "id": f"feezie-reject-{fingerprint}",
        "fingerprint": fingerprint,
        "created_at": created_at,
        "workspace": WORKSPACE_RELATIVE,
        "status": "rejected_with_reason",
        "reason": reason,
        "title": clean_text(item.get("title")) or "Untitled rejected candidate",
        "draft_path": _workspace_path(item.get("draft_path")),
        "source_refs": _source_refs(item),
        "metadata": {
            "idea_id": clean_text(item.get("idea_id")),
            "transform_status": clean_text(item.get("transform_status")),
        },
    }


def _run_event(
    *,
    run_id: str,
    created_at: str,
    candidate_count: int,
    banked_count: int,
    duplicate_count: int,
    rejected_count: int,
    no_op_reason: str | None,
    new_post_ids: list[str],
    duplicate_ids: list[str],
    rejection_ids: list[str],
) -> dict[str, Any]:
    if banked_count:
        terminal_state = "banked"
    elif rejected_count:
        terminal_state = "rejected_with_reason"
    elif duplicate_count:
        terminal_state = "duplicate"
    else:
        terminal_state = "no_qualified_signal"
    return {
        "schema_version": EVENT_SCHEMA_VERSION,
        "id": f"feezie-bank-event-{_hash_key(run_id, created_at, terminal_state)}",
        "run_id": run_id,
        "created_at": created_at,
        "workspace": WORKSPACE_RELATIVE,
        "terminal_state": terminal_state,
        "event_type": terminal_state,
        "candidate_count": candidate_count,
        "banked_count": banked_count,
        "duplicate_count": duplicate_count,
        "rejected_count": rejected_count,
        "no_op_reason": no_op_reason,
        "new_post_ids": new_post_ids,
        "duplicate_ids": duplicate_ids,
        "rejection_ids": rejection_ids,
    }


def _append_backlog_projection(backlog_path: Path, posts: list[dict[str, Any]], *, run_id: str) -> list[str]:
    if not posts:
        return []
    existing = backlog_path.read_text(encoding="utf-8") if backlog_path.exists() else "# LinkedIn Content Backlog\n"
    lines: list[str] = []
    if "<!-- autonomous-content-bank -->" not in existing:
        lines.extend(["", "## Autonomous Content Bank", "<!-- autonomous-content-bank -->"])
    appended_ids: list[str] = []
    for post in posts:
        post_id = clean_text(post.get("id"))
        marker = f"<!-- {post_id} -->"
        if not post_id or marker in existing:
            continue
        title = clean_text(post.get("title")) or post_id
        draft_path = clean_text(post.get("draft_path"))
        source_refs = [clean_text(ref) for ref in post.get("source_refs") or [] if clean_text(ref)]
        source_line = source_refs[0] if source_refs else "source recorded in content bank"
        lines.extend(
            [
                "",
                f"### {post_id} - {title}",
                marker,
                "- Status: `banked`",
                f"- Draft: `{draft_path}`",
                f"- Source: {source_line}",
                f"- Why it exists: {clean_text(post.get('why_this_exists')) or 'Generated from the autonomous content loop.'}",
                "- Review action: owner review",
                f"- Bank run: `{run_id}`",
            ]
        )
        appended_ids.append(post_id)
    if appended_ids:
        _write_text(backlog_path, existing.rstrip() + "\n" + "\n".join(lines))
    return appended_ids


def _status_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    lines = [
        "# Autonomous Content Loop Status",
        "",
        f"- Generated at: `{clean_text(report.get('generated_at'))}`",
        f"- Run id: `{clean_text(report.get('run_id'))}`",
        f"- Terminal state: `{clean_text(summary.get('terminal_state'))}`",
        f"- Candidates: `{summary.get('candidate_count', 0)}`",
        f"- Banked: `{summary.get('banked_count', 0)}`",
        f"- Duplicates: `{summary.get('duplicate_count', 0)}`",
        f"- Rejected: `{summary.get('rejected_count', 0)}`",
    ]
    no_op_reason = clean_text(summary.get("no_op_reason"))
    if no_op_reason:
        lines.append(f"- No-op reason: {no_op_reason}")
    posts = report.get("new_posts") if isinstance(report.get("new_posts"), list) else []
    if posts:
        lines.extend(["", "## New Banked Posts"])
        for post in posts:
            if not isinstance(post, dict):
                continue
            lines.append(f"- `{clean_text(post.get('id'))}` - {clean_text(post.get('title'))}")
    return "\n".join(lines)


def run_autonomous_content_bank(
    *,
    workspace_dir: Path,
    repo_root: Path,
    now: datetime | None = None,
    write: bool = True,
    project_backlog: bool = True,
) -> dict[str, Any]:
    created = isoformat_z(now or utc_now())
    run_id = f"feezie-content-bank-{created.replace(':', '').replace('-', '')}"
    bank_root = content_bank_root(workspace_dir)
    posts_path = bank_root / "posts.jsonl"
    events_path = bank_root / "events.jsonl"
    rejections_path = bank_root / "rejections.jsonl"

    existing_posts = _read_jsonl(posts_path)
    existing_rejections = _read_jsonl(rejections_path)
    existing_post_fingerprints = _existing_fingerprints(existing_posts)
    existing_rejection_fingerprints = _existing_fingerprints(existing_rejections)
    bankable_items, rejected_items = _drafted_latent_items(workspace_dir, repo_root)

    new_posts: list[dict[str, Any]] = []
    duplicate_ids: list[str] = []
    for item in bankable_items:
        post = _post_record(item, repo_root=repo_root, created_at=created)
        if post["fingerprint"] in existing_post_fingerprints:
            duplicate_ids.append(post["id"])
            continue
        existing_post_fingerprints.add(post["fingerprint"])
        new_posts.append(post)

    new_rejections: list[dict[str, Any]] = []
    for rejected in rejected_items:
        item = rejected.get("item") if isinstance(rejected.get("item"), dict) else {}
        rejection = _rejection_record(item, reason=clean_text(rejected.get("reason")), created_at=created)
        if rejection["fingerprint"] in existing_rejection_fingerprints:
            continue
        existing_rejection_fingerprints.add(rejection["fingerprint"])
        new_rejections.append(rejection)

    candidate_count = len(bankable_items) + len(rejected_items)
    no_op_reason = None
    if not candidate_count:
        no_op_reason = "No drafted latent-transform candidates were available to bank."
    elif not new_posts and duplicate_ids:
        no_op_reason = "All drafted latent-transform candidates were already banked."
    elif not new_posts and new_rejections:
        no_op_reason = "Drafted candidates were rejected before banking; see content_bank/rejections.jsonl."

    event = _run_event(
        run_id=run_id,
        created_at=created,
        candidate_count=candidate_count,
        banked_count=len(new_posts),
        duplicate_count=len(duplicate_ids),
        rejected_count=len(new_rejections),
        no_op_reason=no_op_reason,
        new_post_ids=[post["id"] for post in new_posts],
        duplicate_ids=duplicate_ids,
        rejection_ids=[rejection["id"] for rejection in new_rejections],
    )
    appended_backlog_ids: list[str] = []
    if write:
        _append_jsonl(posts_path, new_posts)
        _append_jsonl(rejections_path, new_rejections)
        _append_jsonl(events_path, [event])
        if project_backlog:
            appended_backlog_ids = _append_backlog_projection(workspace_dir / "backlog.md", new_posts, run_id=run_id)

    report = {
        "schema_version": "linkedin_autonomous_content_loop_status/v1",
        "generated_at": created,
        "run_id": run_id,
        "workspace": WORKSPACE_RELATIVE,
        "summary": {
            "terminal_state": event["terminal_state"],
            "candidate_count": candidate_count,
            "banked_count": len(new_posts),
            "duplicate_count": len(duplicate_ids),
            "rejected_count": len(new_rejections),
            "no_op_reason": no_op_reason,
        },
        "new_posts": new_posts,
        "duplicates": duplicate_ids,
        "rejections": new_rejections,
        "backlog_projection": {
            "enabled": project_backlog,
            "appended_ids": appended_backlog_ids,
            "path": f"{WORKSPACE_RELATIVE}/backlog.md",
        },
        "source_paths": [
            f"{WORKSPACE_RELATIVE}/plans/latent_ideas.json",
            f"{WORKSPACE_RELATIVE}/content_bank/posts.jsonl",
            f"{WORKSPACE_RELATIVE}/content_bank/events.jsonl",
            f"{WORKSPACE_RELATIVE}/content_bank/rejections.jsonl",
        ],
    }
    if write:
        _write_json(reports_root(workspace_dir) / "autonomous_loop_status.json", report)
        _write_text(reports_root(workspace_dir) / "autonomous_loop_status.md", _status_markdown(report))
    return report
