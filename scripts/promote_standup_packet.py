#!/usr/bin/env python3
"""Promote a standup prep packet into a live standup and PM cards."""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_API_URL = "https://aiclone-production-32dc.up.railway.app"
WORKSPACE_AGENT_NAMES = {
    "fusion-os": "Fusion Systems Operator",
    "easyoutfitapp": "Easy Outfit Product Agent",
    "ai-swag-store": "Commerce Growth Agent",
    "agc": "AGC Strategy Agent",
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_json(root: Path) -> Path | None:
    matches = sorted(root.glob("*.json"))
    return matches[-1] if matches else None


def _fetch_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _summarize(text: str, max_len: int = 110) -> str:
    normalized = " ".join(text.split()).strip()
    if len(normalized) <= max_len:
        return normalized
    return normalized[: max_len - 1].rstrip() + "…"


def _should_include_yoda(standup_kind: str, workspace_key: str) -> bool:
    if workspace_key == "linkedin-os":
        return True
    return standup_kind in {"executive_ops", "operations", "weekly_review", "saturday_vision"}


def _workspace_agent_name(workspace_key: str) -> str:
    return WORKSPACE_AGENT_NAMES.get(workspace_key, "Workspace Agent")


def _participants_for(standup_kind: str, workspace_key: str, *, include_yoda: bool) -> list[str]:
    if workspace_key not in {"shared_ops", "linkedin-os"}:
        participants = ["Jean-Claude", _workspace_agent_name(workspace_key)]
    elif standup_kind == "operations":
        participants = ["Jean-Claude", "Neo"]
    else:
        participants = ["Jean-Claude", "Neo"]
    if include_yoda and "Yoda" not in participants:
        participants.append("Yoda")
    return participants


def _pm_updates_from(recommendation: dict[str, Any] | None, prep: dict[str, Any]) -> list[dict[str, Any]]:
    source = (recommendation or {}).get("pm_updates")
    if not isinstance(source, list) or not source:
        source = prep.get("pm_updates") or []
    updates: list[dict[str, Any]] = []
    for item in source:
        if not isinstance(item, dict):
            continue
        updates.append(item)
    return updates


def _build_decisions(prep: dict[str, Any], pm_updates: list[dict[str, Any]]) -> list[str]:
    workspace_key = str(prep.get("workspace_key") or "shared_ops")
    snapshot = dict(prep.get("pm_snapshot") or {})
    cards = snapshot.get("cards") or []
    decisions: list[str] = []

    blocked = [card for card in cards if isinstance(card, dict) and str(card.get("status") or "") == "blocked"]
    review = [card for card in cards if isinstance(card, dict) and str(card.get("status") or "") == "review"]
    active = [card for card in cards if isinstance(card, dict) and str(card.get("status") or "") in {"queued", "in_progress", "ready"}]

    for card in blocked[:2]:
        decisions.append(f"Unblock `{card.get('title')}` before additional work enters `{workspace_key}`.")
    for card in review[:1]:
        decisions.append(f"Review `{card.get('title')}` and either close it or return it to execution.")
    for item in pm_updates[:2]:
        title = str(item.get("title") or "").strip()
        if title:
            decisions.append(f"Create or queue `{title}` on the PM board.")
    if not decisions:
        for card in active[:1]:
            decisions.append(f"Keep `{card.get('title')}` moving and revisit it in the next standup.")
    if not decisions:
        decisions.append("Nothing to report. Leave the board unchanged and wait for the next real signal.")
    return decisions[:5]


def _build_owners(prep: dict[str, Any], include_yoda: bool) -> list[str]:
    workspace_key = str(prep.get("workspace_key") or "shared_ops")
    owners = ["Jean-Claude — update the PM board, open the next SOP, and carry the lane summary back to leadership."]
    if workspace_key not in {"shared_ops", "linkedin-os"}:
        workspace_agent = WORKSPACE_AGENT_NAMES.get(workspace_key, "Workspace Agent")
        owners.append(
            f"{workspace_agent} — execute inside `{workspace_key}` only and report back through workspace memory plus the PM card."
        )
    if include_yoda:
        owners.append("Yoda — challenge whether the next move still aligns with the North Star before scope expands.")
    return owners


def _jean_claude_note(prep: dict[str, Any]) -> str:
    agenda = [str(item).strip() for item in (prep.get("agenda") or []) if str(item).strip()]
    pm_lines = [str(item).strip() for item in ((prep.get("pm_snapshot") or {}).get("lines") or []) if str(item).strip()]
    artifact = [str(item).strip() for item in (prep.get("artifact_deltas") or []) if str(item).strip()]
    strategy_lines = [str(item).strip() for item in (prep.get("strategy_context_lines") or []) if str(item).strip()]
    summary_bits = []
    if pm_lines:
        summary_bits.append(pm_lines[0])
    if agenda:
        summary_bits.append(f"Agenda starts with {agenda[0]}")
    if artifact:
        summary_bits.append(f"Latest delta: {artifact[0]}")
    if strategy_lines:
        summary_bits.append(strategy_lines[0])
    return " ".join(summary_bits) or (prep.get("summary") or "PM-first standup is ready.")


def _neo_note(prep: dict[str, Any], decisions: list[str]) -> str:
    strategy_context = dict(prep.get("strategy_context") or {})
    display_name = str(strategy_context.get("display_name") or prep.get("workspace_key") or "this lane")
    routing = str(strategy_context.get("default_routing") or "").strip()
    if decisions:
        note = f"Keep the board as the source of truth. Pressure-test {decisions[0]} and only expand scope if `{display_name}` is actually clear."
        if routing:
            note += f" {routing}"
        return note
    note = "Keep the PM board ahead of narrative. If there is no clear board move, say nothing is ready and leave the lane alone."
    if routing:
        note += f" {routing}"
    return note


def _workspace_agent_note(prep: dict[str, Any], decisions: list[str]) -> str:
    workspace_key = str(prep.get("workspace_key") or "shared_ops")
    workspace_agent = _workspace_agent_name(workspace_key)
    strategy_context = dict(prep.get("strategy_context") or {})
    display_name = str(strategy_context.get("display_name") or workspace_key)
    if decisions:
        return (
            f"{workspace_agent} should execute inside `{workspace_key}` only. Start from {decisions[0]}, keep `{display_name}` inside its charter, and report back through workspace artifacts plus the PM card."
        )
    return f"{workspace_agent} should keep `{workspace_key}` clean, local, execution-focused, and inside `{display_name}` strategy until the next real board move appears."


def _yoda_note(prep: dict[str, Any], chronicle_entry: dict[str, Any] | None) -> str:
    chronicle_context = (
        f"Current Chronicle signal: {_summarize(str(chronicle_entry.get('summary') or ''))}"
        if chronicle_entry and chronicle_entry.get("summary")
        else "Current Chronicle signal is still consolidating."
    )
    workspace_key = str(prep.get("workspace_key") or "shared_ops")
    strategy_context = dict(prep.get("strategy_context") or {})
    inferred_excerpt = str(strategy_context.get("inferred_excerpt") or "").strip()
    if workspace_key == "linkedin-os":
        note = f"Protect the North Star: FEEZIE OS should keep strengthening Johnnie's brand, career, and long-term public positioning. {chronicle_context}"
    else:
        note = f"Protect the why behind the system: this move should deepen the second-brain, preserve Johnnie's voice, and stay pointed at durable leverage instead of generic automation. {chronicle_context}"
    if inferred_excerpt:
        note += f" Grounding brief: {_summarize(inferred_excerpt, max_len=180)}"
    return note


def _build_discussion_rounds(
    prep: dict[str, Any],
    decisions: list[str],
    owners: list[str],
    chronicle_entry: dict[str, Any] | None,
    *,
    include_yoda: bool,
    participants: list[str],
) -> list[dict[str, Any]]:
    agenda = [str(item).strip() for item in (prep.get("agenda") or []) if str(item).strip()]
    artifact_deltas = [str(item).strip() for item in (prep.get("artifact_deltas") or []) if str(item).strip()]
    workspace_key = str(prep.get("workspace_key") or "shared_ops")
    second_speaker = participants[1] if len(participants) > 1 else "Neo"
    if second_speaker == "Neo":
        second_role = "system-operator"
        second_note = _neo_note(prep, decisions)
        second_focus = "priority_and_scope"
    else:
        second_role = "workspace-operator"
        second_note = _workspace_agent_note(prep, decisions)
        second_focus = "workspace_execution"
    rounds = [
        {
            "round": 1,
            "speaker": "Jean-Claude",
            "role": "workspace-president",
            "note": _jean_claude_note(prep),
            "focus": "pm_board_first",
        },
        {
            "round": 2,
            "speaker": second_speaker,
            "role": second_role,
            "note": second_note,
            "focus": second_focus,
        },
    ]
    if include_yoda:
        rounds.append(
            {
                "round": 3,
                "speaker": "Yoda",
                "role": "strategic-overlay",
                "note": _yoda_note(prep, chronicle_entry),
                "focus": "north_star",
            }
        )
    close_round = {
        "round": 4 if include_yoda else 3,
        "speaker": "Jean-Claude",
        "role": "workspace-president",
        "note": "Decision set: "
        + "; ".join(decisions[:2])
        + (" Owners: " + " ".join(owners[:2]) if owners else ""),
        "focus": "decision_and_handoff",
    }
    if agenda:
        close_round["agenda"] = agenda[:3]
    if artifact_deltas:
        close_round["artifacts"] = artifact_deltas[:2]
    rounds.append(close_round)
    return rounds


def _build_payload(prep: dict[str, Any], recommendation: dict[str, Any] | None, chronicle_entry: dict[str, Any] | None) -> dict[str, Any]:
    standup_kind = str(prep.get("standup_kind") or "executive_ops")
    workspace_key = str(prep.get("workspace_key") or "shared_ops")
    include_yoda = _should_include_yoda(standup_kind, workspace_key)
    participants = _participants_for(standup_kind, workspace_key, include_yoda=include_yoda)
    pm_updates = []
    source_updates = _pm_updates_from(recommendation, prep)
    for item in source_updates:
        if not isinstance(item, dict):
            continue
        pm_updates.append(
            {
                "workspace_key": item.get("workspace_key") or workspace_key,
                "scope": item.get("scope") or ("workspace" if workspace_key != "shared_ops" else "shared_ops"),
                "owner_agent": item.get("owner_agent") or prep.get("owner_agent") or "jean-claude",
                "title": item.get("title") or "Untitled PM update",
                "status": item.get("status") or "todo",
                "reason": item.get("reason") or "Derived from standup prep.",
                "payload": dict(item.get("payload") or {}),
            }
        )
    decisions = _build_decisions(prep, pm_updates)
    owners = _build_owners(prep, include_yoda)
    discussion_rounds = _build_discussion_rounds(
        prep,
        decisions,
        owners,
        chronicle_entry if isinstance(chronicle_entry, dict) else None,
        include_yoda=include_yoda,
        participants=participants,
    )
    return {
        "standup_kind": standup_kind or workspace_key,
        "owner": "Jean-Claude",
        "workspace_key": workspace_key,
        "summary": prep.get("summary") or "Standup prep ready.",
        "agenda": list(prep.get("agenda") or []),
        "blockers": list((prep.get("standup_payload") or {}).get("blockers") or prep.get("blockers") or []),
        "commitments": list((prep.get("standup_payload") or {}).get("commitments") or prep.get("commitments") or []),
        "needs": list((prep.get("standup_payload") or {}).get("needs") or prep.get("needs") or []),
        "decisions": decisions,
        "owners": owners,
        "artifact_deltas": list(prep.get("artifact_deltas") or []),
        "source": "standup_prep",
        "conversation_path": str(prep.get("standup_payload", {}).get("conversation_path") or ""),
        "source_paths": list(prep.get("source_paths") or []),
        "memory_promotions": [str(item.get("content") or "") for item in (prep.get("memory_promotions") or []) if isinstance(item, dict)],
        "pm_snapshot": dict(prep.get("pm_snapshot") or {}),
        "strategy_context": dict(prep.get("strategy_context") or {}),
        "strategy_context_lines": list(prep.get("strategy_context_lines") or []),
        "participants": participants,
        "discussion_rounds": discussion_rounds,
        "jean_claude_note": _jean_claude_note(prep),
        "neo_note": _neo_note(prep, decisions),
        "yoda_note": _yoda_note(prep, chronicle_entry) if include_yoda else None,
        "prep_id": prep.get("prep_id"),
        "recommendation_path": recommendation.get("path") if isinstance(recommendation, dict) else None,
        "pm_updates": pm_updates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prep-json", required=True)
    parser.add_argument("--recommendation-json")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    prep_path = Path(args.prep_json).expanduser()
    prep = _read_json(prep_path)
    recommendation = _read_json(Path(args.recommendation_json).expanduser()) if args.recommendation_json else None
    if recommendation is not None and args.recommendation_json:
        recommendation = {**recommendation, "path": str(Path(args.recommendation_json).expanduser())}

    chronicle_entries = prep.get("chronicle_entries") or []
    chronicle_entry = chronicle_entries[-1] if chronicle_entries else None
    payload = _build_payload(prep, recommendation, chronicle_entry if isinstance(chronicle_entry, dict) else None)

    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return 0

    result = _fetch_json(f"{args.api_url.rstrip('/')}/api/standups/promote", method="POST", payload=payload)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.URLError as exc:
        raise SystemExit(f"Failed to reach standup API at {DEFAULT_API_URL}: {exc}") from exc
