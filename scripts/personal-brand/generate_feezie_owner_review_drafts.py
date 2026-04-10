#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

HELPER_DIR = Path(__file__).resolve().parent
if str(HELPER_DIR) not in sys.path:
    sys.path.insert(0, str(HELPER_DIR))

from linkedin_strategy_utils import (  # noqa: E402
    clean_text,
    drafts_root,
    load_queue_items,
    now_iso,
    read_json,
    slugify,
    workspace_root,
    write_text,
)
from linkedin_idea_qualification import load_or_build_idea_qualification_payload, qualification_indexes  # noqa: E402


def _workspace_dir_from_arg(path: str | None) -> Path:
    return Path(path).resolve() if path else workspace_root()


def _existing_source_paths(workspace_dir: Path) -> set[str]:
    source_paths: set[str] = set()
    for path in drafts_root(workspace_dir).glob("*.md"):
        if path.name == "README.md" or path.name.startswith("queue_") or path.name.startswith("feezie_owner_review_packet_"):
            continue
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("source_path:"):
                source_paths.add(clean_text(line.split(":", 1)[1]))
    return source_paths


def _queue_body(item: dict[str, Any]) -> str:
    proof_lines = "\n".join(f"- `{anchor}`" for anchor in item.get("proof_anchors") or [])
    title = clean_text(item.get("title"))
    core_angle = clean_text(item.get("core_angle"))
    why_now = clean_text(item.get("why_now"))
    lane = clean_text(item.get("lane"))
    return "\n".join(
        [
            "---",
            f'title: "{title}"',
            "draft_kind: owner_review",
            "source_kind: feezie_queue",
            f"lane: {lane}",
            f"priority_lane: {lane}",
            f"publish_posture: {clean_text(item.get('approval_status')) or 'owner_review_required'}",
            "risk_level: low",
            "role_alignment: role_anchored",
            f"source_path: {clean_text(item.get('source_path'))}",
            f"created_at: {now_iso()}",
            "---",
            "",
            f"# {title}",
            "",
            "## Why this draft exists",
            f"- Queue item: `{clean_text(item.get('id'))}`",
            f"- Lane: `{lane}`",
            f"- Why now: {why_now}",
            "",
            "## Proof anchors",
            proof_lines or "- _Add proof anchors before approval._",
            "",
            "## First-pass draft",
            "",
            f"{core_angle}.",
            "",
            "That is the part I would want to make clear publicly before the conversation gets flattened into generic posting.",
            "",
            f"What keeps making this worth saying now is {why_now.lower()}.",
            "",
            "The owner-review question is not whether this sounds smart. It is whether this stays true to lived work, proof, and the kind of signal FEEZIE should actually reinforce.",
            "",
            "## Owner notes",
            "- Tighten the hook if needed.",
            "- Keep this grounded in real proof, not abstraction.",
            "- Do not publish without explicit owner approval.",
        ]
    )


def _reaction_body(item: dict[str, Any]) -> str:
    title = clean_text(item.get("title"))
    hook = clean_text(item.get("hook"))
    post_angle = clean_text(item.get("post_angle"))
    why_it_matters = clean_text(item.get("why_it_matters"))
    summary = clean_text(item.get("summary"))
    source_url = clean_text(item.get("source_url"))
    source_path = clean_text(item.get("source_path"))
    lane = clean_text(item.get("priority_lane"))
    qualification_route = clean_text(item.get("qualification_route")) or "pass"
    qualification_id = clean_text(item.get("qualification_id"))
    qualification_reason = clean_text(item.get("qualification_reason"))
    return "\n".join(
        [
            "---",
            f'title: "{title}"',
            "draft_kind: owner_review",
            "source_kind: reaction_seed",
            f'author: "{clean_text(item.get("author"))}"',
            f"lane: {lane}",
            f"priority_lane: {lane}",
            f"publish_posture: {clean_text(item.get('publish_posture')) or 'owner_review_required'}",
            f"risk_level: {clean_text(item.get('risk_level')) or 'low'}",
            f"role_alignment: {clean_text(item.get('role_alignment')) or 'role_anchored'}",
            f"source_url: {source_url}",
            f"source_path: {source_path}",
            f"qualification_route: {qualification_route}",
            f"qualification_id: {qualification_id}",
            f"created_at: {now_iso()}",
            "---",
            "",
            f"# {title}",
            "",
            "## Source signal",
            f"- Source URL: {source_url}",
            f"- Source file: `{source_path}`",
            f"- Why it matters: {why_it_matters}",
            f"- Qualification: `{qualification_route}`",
            (f"- Qualification notes: {qualification_reason}" if qualification_reason else ""),
            "",
            "## First-pass draft",
            "",
            hook or title,
            "",
            summary or post_angle,
            "",
            why_it_matters or "This matters because it sharpens the operator view instead of just echoing the source.",
            "",
            post_angle or "The owner-review move is to turn this signal into a clearer standalone point of view.",
            "",
            "## Owner notes",
            "- Confirm this should become a standalone post rather than stay a reaction.",
            "- Tighten the second paragraph to sound more recognizably Feeze.",
            "- Publish only after owner approval.",
        ]
    )


def _reaction_slug(item: dict[str, Any]) -> str:
    return slugify(clean_text(item.get("title")))


def _queue_slug(item: dict[str, Any]) -> str:
    return slugify(clean_text(item.get("title")))


def materialize_owner_review_drafts(workspace_dir: Path) -> dict[str, Any]:
    drafts_dir = drafts_root(workspace_dir)
    drafts_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    existing_sources = _existing_source_paths(workspace_dir)
    qualification_payload = load_or_build_idea_qualification_payload(workspace_dir)
    _, qualification_by_source_path = qualification_indexes(qualification_payload)

    for item in load_queue_items(workspace_dir)[:3]:
        draft_path = drafts_dir / f"{clean_text(item.get('id')).lower()}_{_queue_slug(item)}.md"
        if draft_path.exists():
            continue
        write_text(draft_path, _queue_body(item))
        created.append(draft_path.name)

    reaction_queue = read_json(workspace_dir / "plans" / "reaction_queue.json") or {}
    for item in (reaction_queue.get("post_seeds") or [])[:5]:
        if not isinstance(item, dict):
            continue
        source_path = clean_text(item.get("source_path"))
        report = qualification_by_source_path.get(source_path) if source_path else None
        route = clean_text((report or {}).get("route")) or clean_text(item.get("qualification_route")) or "discard"
        if route != "pass":
            continue
        if source_path and source_path in existing_sources:
            continue
        if report:
            item = dict(item)
            item["qualification_route"] = route
            item["qualification_id"] = clean_text(report.get("idea_id")) or clean_text(item.get("title"))
            item["qualification_reason"] = clean_text(report.get("suggested_fix"))
        draft_path = drafts_dir / f"{Path(now_iso()).name[:10]}_{_reaction_slug(item)}.md"
        if draft_path.exists():
            continue
        write_text(draft_path, _reaction_body(item))
        created.append(draft_path.name)
        if source_path:
            existing_sources.add(source_path)

    return {"created": created, "created_count": len(created), "workspace": "workspaces/linkedin-content-os"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize owner-review FEEZIE drafts.")
    parser.add_argument("--workspace", help="Override workspace root.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workspace_dir = _workspace_dir_from_arg(args.workspace)
    result = materialize_owner_review_drafts(workspace_dir)
    print(result)


if __name__ == "__main__":
    main()
