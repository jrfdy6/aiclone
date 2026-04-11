from __future__ import annotations

from typing import Any, Iterable


def build_execution_contract(
    *,
    title: str,
    workspace_key: str,
    source: str,
    reason: str | None = None,
    instructions: Iterable[object] | None = None,
    acceptance_criteria: Iterable[object] | None = None,
    artifacts_expected: Iterable[object] | None = None,
) -> dict[str, Any]:
    normalized_title = " ".join(str(title or "").split()).strip() or "Untitled PM task"
    normalized_workspace = str(workspace_key or "shared_ops").strip() or "shared_ops"
    normalized_reason = " ".join(str(reason or "").split()).strip()

    instruction_list = _clean_string_list(instructions)
    if not instruction_list:
        instruction_list = [
            f"Advance `{normalized_title}` inside `{normalized_workspace}` without expanding scope beyond the PM card.",
            "Use the PM card and linked standup context as the source of truth while executing.",
            "Write back a concrete result with outcomes, blockers, and follow-up actions through the execution-result writer.",
        ]

    acceptance_list = _clean_string_list(acceptance_criteria)
    if not acceptance_list:
        acceptance_list = [
            f"`{normalized_title}` advances to a concrete next state instead of remaining a placeholder.",
            "PM write-back includes a bounded summary, concrete outcomes, and any blockers or follow-up actions.",
        ]

    artifact_list = _clean_string_list(artifacts_expected)
    if not artifact_list:
        artifact_list = [
            "updated PM execution result",
            "bounded workspace artifact or execution memo when work produces one",
        ]

    completion_contract = {
        "source": source,
        "autostart": True,
        "writeback_required": True,
        "next_state_on_result": "review",
        "auto_return_limit": 2,
        "result_requirements": {
            "summary_min_length": 20,
            "require_outcome_or_artifact": True,
            "require_writeback": True,
            "allow_blockers": False,
        },
        "done_when": acceptance_list[:6],
    }
    if normalized_reason:
        completion_contract["why_this_exists"] = normalized_reason

    return {
        "instructions": instruction_list[:6],
        "acceptance_criteria": acceptance_list[:6],
        "artifacts_expected": artifact_list[:6],
        "completion_contract": completion_contract,
    }


def _clean_string_list(values: Iterable[object] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        normalized = " ".join(str(value or "").split()).strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(normalized)
    return cleaned
