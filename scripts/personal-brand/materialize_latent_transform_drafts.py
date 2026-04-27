#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

HELPER_DIR = Path(__file__).resolve().parent
if str(HELPER_DIR) not in sys.path:
    sys.path.insert(0, str(HELPER_DIR))

from linkedin_idea_qualification import (  # noqa: E402
    active_draft_indexes,
    build_latent_idea_payload,
    load_or_build_latent_idea_payload,
    write_latent_idea_artifacts,
)
from linkedin_strategy_utils import (  # noqa: E402
    clean_text,
    drafts_root,
    load_social_feed_items,
    now_iso,
    priority_lane_label,
    role_alignment_for_lane,
    slugify,
    workspace_root,
    workspace_source_path,
    write_text,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize worker-ready latent transform drafts.")
    parser.add_argument("--workspace", help="Override workspace root.")
    return parser.parse_args()


def _workspace_dir_from_arg(path: str | None) -> Path:
    return Path(path).resolve() if path else workspace_root()


def _social_feed_lookup(workspace_dir: Path) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for item in load_social_feed_items(workspace_dir):
        if not isinstance(item, dict):
            continue
        source_path = workspace_source_path(item.get("source_path"))
        if source_path:
            lookup[source_path] = item
    return lookup


def _draft_path_for_title(workspace_dir: Path, title: str) -> Path:
    date_prefix = now_iso()[:10]
    base = drafts_root(workspace_dir) / f"{date_prefix}_{slugify(title)}-latent-transform.md"
    if not base.exists():
        return base
    stem = base.stem
    suffix = base.suffix or ".md"
    index = 2
    while True:
        candidate = drafts_root(workspace_dir) / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _first_non_empty(*values: Any) -> str:
    for value in values:
        text = clean_text(value)
        if text:
            return text
    return ""


def _first_list_entry(values: Any) -> str:
    if not isinstance(values, list):
        return ""
    for value in values:
        text = clean_text(value)
        if text:
            return text
    return ""


def _source_signal(item: dict[str, Any], source_item: dict[str, Any] | None, transform_plan: dict[str, Any]) -> str:
    return _first_non_empty(
        transform_plan.get("source_signal"),
        (source_item or {}).get("summary"),
        _first_list_entry((source_item or {}).get("supporting_claims")),
        item.get("source_summary"),
        item.get("source_supporting_claim"),
        item.get("title"),
    )


def _draft_body(item: dict[str, Any], source_item: dict[str, Any] | None) -> str:
    transform_plan = item.get("transform_plan") if isinstance(item.get("transform_plan"), dict) else {}
    lane = clean_text(item.get("content_lane"))
    priority_lane = priority_lane_label(lane)
    title = clean_text(item.get("title"))
    source_path = clean_text(item.get("source_path"))
    source_url = clean_text(item.get("source_url"))
    proposed_angle = clean_text(transform_plan.get("proposed_angle"))
    owner_question = clean_text(transform_plan.get("owner_question"))
    proof_prompt = clean_text(transform_plan.get("proof_prompt"))
    promotion_rule = clean_text(transform_plan.get("promotion_rule"))
    owner_prompt = owner_question.rstrip("?").strip()
    summary = _first_non_empty((source_item or {}).get("summary"), item.get("source_summary"))
    source_signal = _source_signal(item, source_item, transform_plan)
    why_it_matters = clean_text((source_item or {}).get("why_it_matters")) or clean_text(item.get("suggested_fix"))
    revision_goals = [clean_text(entry) for entry in (transform_plan.get("revision_goals") or []) if clean_text(entry)]
    revision_lines = "\n".join(f"- {goal}" for goal in revision_goals) or "- Tighten the angle before promotion."
    first_pass_lines = [
        f'"{title}" is useful because the source signal is {source_signal.rstrip(".")}.'
        if source_signal
        else "",
        proposed_angle or title,
        (
            f"The operator consequence still needs to answer this clearly: {owner_prompt}."
            if owner_prompt
            else "The operator consequence still needs to become unmistakably concrete."
        ),
        f"The proof line I would want in the next pass is: {proof_prompt or 'add one lived example or artifact before promotion.'}",
        (
            f"The next pass only deserves promotion if it can satisfy this rule: {promotion_rule}"
            if promotion_rule
            else "The next pass only deserves promotion if it can satisfy one clear audience consequence plus one defendable proof line."
        ),
    ]
    first_pass = "\n\n".join(line for line in first_pass_lines if line)
    return "\n".join(
        [
            "---",
            f'title: "{title}"',
            "draft_kind: owner_review",
            "source_kind: latent_transform",
            f"idea_id: {clean_text(item.get('idea_id'))}",
            f"lane: {lane}",
            f"priority_lane: {priority_lane}",
            "publish_posture: owner_review_required",
            "risk_level: low",
            f"role_alignment: {role_alignment_for_lane(lane)}",
            "score: 12",
            f"source_url: {source_url}",
            f"source_path: {source_path}",
            f"latent_reason: {clean_text(item.get('latent_reason'))}",
            f"transform_type: {clean_text(transform_plan.get('transform_type'))}",
            "generated_by: latent_transform_worker",
            f"created_at: {now_iso()}",
            "---",
            "",
            f"# {title}",
            "",
            "## Why this draft exists",
            f"- This source was preserved as `{clean_text(item.get('latent_reason'))}` instead of discarded.",
            f"- The transform worker picked it up because `autotransform_ready={bool(transform_plan.get('autotransform_ready'))}`.",
            f"- Priority lane: `{priority_lane}`",
            "",
            "## Source signal",
            f"- Source file: `{source_path}`",
            (f"- Source URL: {source_url}" if source_url else ""),
            (f"- Source summary: {summary}" if summary else ""),
            (f"- Why it matters: {why_it_matters}" if why_it_matters else ""),
            "",
            "## Transform brief",
            f"- Proposed angle: {proposed_angle}",
            f"- Owner question: {owner_question}",
            f"- Proof prompt: {proof_prompt}",
            f"- Promotion rule: {promotion_rule}",
            "",
            "## Revision goals",
            revision_lines,
            "",
            "## First-pass transformed draft",
            "",
            first_pass,
            "",
            "## Owner notes",
            "- Keep or revise the proposed angle.",
            "- Add the exact lived proof line before approval.",
            "- Do not publish without explicit owner approval.",
        ]
    )


def materialize_latent_transform_drafts(workspace_dir: Path) -> dict[str, Any]:
    payload = load_or_build_latent_idea_payload(workspace_dir)
    _, draft_by_source_path = active_draft_indexes(workspace_dir)
    social_lookup = _social_feed_lookup(workspace_dir)
    created: list[str] = []
    updated: list[str] = []

    for item in payload.get("items", []):
        if not isinstance(item, dict):
            continue
        transform_plan = item.get("transform_plan") if isinstance(item.get("transform_plan"), dict) else {}
        if not bool(transform_plan.get("autotransform_ready")):
            continue
        source_path = clean_text(item.get("source_path"))
        active_draft = draft_by_source_path.get(source_path) if source_path else None
        if active_draft and clean_text(active_draft.get("source_kind")) != "latent_transform":
            continue
        if active_draft and clean_text(active_draft.get("source_kind")) == "latent_transform":
            draft_path = Path(str(active_draft.get("draft_fs_path")))
        else:
            draft_path = _draft_path_for_title(workspace_dir, clean_text(item.get("title")))
        source_item = social_lookup.get(source_path) if source_path else None
        write_text(draft_path, _draft_body(item, source_item))
        if active_draft:
            updated.append(draft_path.name)
        else:
            created.append(draft_path.name)

    refreshed_payload = build_latent_idea_payload(workspace_dir)
    write_latent_idea_artifacts(workspace_dir, refreshed_payload)
    return {
        "workspace": "workspaces/linkedin-content-os",
        "created": created,
        "created_count": len(created),
        "updated": updated,
        "updated_count": len(updated),
    }


def main() -> None:
    args = parse_args()
    workspace_dir = _workspace_dir_from_arg(args.workspace)
    result = materialize_latent_transform_drafts(workspace_dir)
    print(result)


if __name__ == "__main__":
    main()
