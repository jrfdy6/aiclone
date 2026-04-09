from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def resolve_workspace_root() -> Path:
    current = Path(__file__).resolve()
    candidates = list(current.parents) + [Path.cwd(), *Path.cwd().parents, Path("/app"), Path("/")]
    seen: set[Path] = set()
    for parent in candidates:
        if parent in seen:
            continue
        seen.add(parent)
        if (parent / "memory").exists() and (parent / "workspaces").exists():
            return parent
    return current.parents[3]


ROOT = resolve_workspace_root()
MEMORY_ROOT = ROOT / "memory"
REPORT_ROOT = MEMORY_ROOT / "reports"
DEFAULT_WORKSPACE_KEY = "linkedin-content-os"
DEFAULT_SOURCE_FILE_NAMES = (
    "codex_session_handoff.jsonl",
    "persistent_state.md",
    "daily-briefs.md",
    "dream_cycle_log.md",
    "cron-prune.md",
)
MAX_SIGNALS = 12
SOURCE_LIMITS = {
    "chronicle": 6,
    "persistent_state": 2,
    "daily_brief": 2,
    "dream_cycle": 2,
    "cron_prune": 2,
}

_WHITESPACE_RE = re.compile(r"\s+")
_MARKDOWN_PREFIX_RE = re.compile(r"^[#>*`\-\d.\s]+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_ARTIFACT_TOKEN_RE = re.compile(r"(/Users/neo/[^\s,)\]]+)")
_BUILD_PROOF_TERMS = {
    "accepted",
    "artifact",
    "automation",
    "briefing",
    "bridge",
    "built",
    "cache",
    "codex",
    "completed",
    "dispatch",
    "draft",
    "execution",
    "fixed",
    "improved",
    "launched",
    "lane",
    "packet",
    "proof",
    "queue",
    "refresh",
    "reroute",
    "rewired",
    "runner",
    "routed",
    "shipped",
    "snapshot",
    "sop",
    "synced",
    "workflow",
    "write-back",
}
_IDENTITY_TERMS = {
    "belief",
    "brand",
    "identity",
    "persona",
    "phrase",
    "principle",
    "story",
    "taste",
    "voice",
    "worldview",
}
_TOPIC_TERMS = {
    "automation",
    "brain",
    "brief",
    "codex",
    "content",
    "execution",
    "fusion-os",
    "linkedin-content-os",
    "memory",
    "openclaw",
    "operator",
    "persona",
    "pm",
    "railway",
    "workflow",
    "workspace",
}
_KNOWN_WORKSPACES = {
    "agc",
    "ai-swag-store",
    "easyoutfitapp",
    "fusion-os",
    "linkedin-content-os",
    "shared_ops",
}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_text(value: Any) -> str:
    text = str(value or "").replace("\u2014", "-").replace("\u2019", "'")
    text = text.strip()
    if not text:
        return ""
    text = _MARKDOWN_PREFIX_RE.sub("", text).strip()
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip(" -")


def _truncate(text: str, limit: int = 180) -> str:
    normalized = _normalize_text(text)
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def _first_sentence(text: str) -> str:
    normalized = _normalize_text(text)
    if not normalized:
        return ""
    parts = _SENTENCE_SPLIT_RE.split(normalized, maxsplit=1)
    return parts[0].strip() if parts else normalized


def _as_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        normalized = _normalize_text(item)
        if normalized:
            items.append(normalized)
    return items


def _tail_lines(path: Path, limit: int) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-limit:]


def _extract_artifact_paths(*values: str) -> list[str]:
    seen: set[str] = set()
    artifacts: list[str] = []
    for value in values:
        for match in _ARTIFACT_TOKEN_RE.findall(value or ""):
            if match in seen:
                continue
            seen.add(match)
            artifacts.append(match)
    return artifacts


def _section_map(markdown: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = "root"
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            heading = _normalize_text(line.lstrip("#").strip()).lower()
            current = heading or "root"
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line.strip())
    return sections


def _latest_markdown_entry(markdown: str) -> str:
    matches = list(re.finditer(r"(?m)^#\s+", markdown))
    if not matches:
        return markdown
    return markdown[matches[-1].start() :]


def _parse_cron_sections(markdown: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"root": []}
    current = "root"
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.endswith(":"):
            current = _normalize_text(line[:-1]).lower() or "root"
            sections.setdefault(current, [])
            continue
        if ":" in line and current == "root":
            key, value = line.split(":", 1)
            current = _normalize_text(key).lower() or "root"
            sections.setdefault(current, [])
            normalized_value = _normalize_text(value)
            if normalized_value:
                sections[current].append(normalized_value)
            continue
        sections.setdefault(current, []).append(line)
    return sections


def _topic_tags(*values: str) -> list[str]:
    text = " ".join(_normalize_text(value).lower() for value in values if _normalize_text(value))
    seen: set[str] = set()
    tags: list[str] = []
    for term in sorted(_TOPIC_TERMS):
        if term in text and term not in seen:
            seen.add(term)
            tags.append(term)
    return tags


def _workspace_keys(*values: str) -> list[str]:
    text = " ".join(_normalize_text(value).lower() for value in values if _normalize_text(value))
    keys: list[str] = []
    for key in sorted(_KNOWN_WORKSPACES):
        if key in text and key not in keys:
            keys.append(key)
    return keys


def _recommend_route(*, claim: str, proof: str, lesson: str, source_kind: str, identity_bias: bool, artifact_paths: list[str]) -> str:
    combined = " ".join(part.lower() for part in (claim, proof, lesson) if part)
    if identity_bias or any(term in combined for term in _IDENTITY_TERMS):
        return "persona_candidate"
    if artifact_paths or any(term in combined for term in _BUILD_PROOF_TERMS):
        return "content_reservoir"
    if source_kind in {"dream_cycle", "chronicle"} and proof:
        return "content_reservoir"
    return "keep_in_ops"


def _durability_for(route: str, *, proof: str, artifact_paths: list[str]) -> str:
    if route == "persona_candidate":
        return "durable"
    if route == "content_reservoir":
        return "durable" if artifact_paths or proof else "working"
    return "ephemeral"


def _score_signal(*, claim: str, proof: str, lesson: str, artifact_paths: list[str], workspace_keys: list[str], route: str) -> int:
    score = 0
    if claim:
        score += 4
    if proof:
        score += 3
    if lesson:
        score += 2
    if artifact_paths:
        score += min(3, len(artifact_paths))
    if workspace_keys:
        score += 1
    if route != "keep_in_ops":
        score += 1
    return score


def _signal_id(source_kind: str, source_ref: str, claim: str) -> str:
    basis = f"{source_kind}|{source_ref}|{claim.lower()}"
    return re.sub(r"[^a-z0-9]+", "-", basis.lower()).strip("-")[:80]


def _chronicle_signals(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    signals: list[dict[str, Any]] = []
    raw_lines = [line for line in _tail_lines(path, 80) if line.strip()]
    for raw_line in reversed(raw_lines):
        try:
            entry = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        source = _normalize_text(entry.get("source"))
        summary = _normalize_text(entry.get("summary"))
        decisions = _as_list(entry.get("decisions"))
        learnings = _as_list(entry.get("learning_updates"))
        identity_signals = _as_list(entry.get("identity_signals"))
        mindset_signals = _as_list(entry.get("mindset_signals"))
        project_updates = _as_list(entry.get("project_updates"))
        outcomes = _as_list(entry.get("outcomes"))
        follow_ups = _as_list(entry.get("follow_ups"))
        artifacts = [str(item).strip() for item in entry.get("artifacts") or [] if str(item).strip()]
        has_story_value = any([decisions, learnings, identity_signals, mindset_signals, project_updates, outcomes, artifacts])
        if not has_story_value:
            continue
        claim = decisions[0] if decisions else project_updates[0] if project_updates else identity_signals[0] if identity_signals else summary
        proof_parts = project_updates[:1] + outcomes[:1]
        proof = " ".join(part for part in proof_parts if part)
        lesson = learnings[0] if learnings else mindset_signals[0] if mindset_signals else follow_ups[0] if follow_ups else ""
        if source == "codex-history" and not proof and not lesson and len(identity_signals) <= 1:
            continue
        workspace_keys = _workspace_keys(
            str(entry.get("workspace_key") or ""),
            " ".join(str(tag) for tag in entry.get("tags") or []),
            claim,
            proof,
            lesson,
        )
        if not workspace_keys and str(entry.get("workspace_key") or "").strip():
            workspace_keys = [str(entry.get("workspace_key") or "").strip()]
        artifact_paths = list(dict.fromkeys(artifacts + _extract_artifact_paths(claim, proof, lesson)))
        route = _recommend_route(
            claim=claim,
            proof=proof,
            lesson=lesson,
            source_kind="chronicle",
            identity_bias=bool(identity_signals),
            artifact_paths=artifact_paths,
        )
        signals.append(
            {
                "id": _signal_id("chronicle", str(entry.get("entry_id") or entry.get("handoff_id") or summary), claim),
                "title": _truncate(summary or claim, 110),
                "claim": _truncate(claim, 280),
                "proof": _truncate(proof, 280),
                "lesson": _truncate(lesson, 220),
                "artifact_paths": artifact_paths[:5],
                "workspace_keys": workspace_keys[:5],
                "topic_tags": _topic_tags(source, claim, proof, lesson, " ".join(str(tag) for tag in entry.get("tags") or [])),
                "durability": _durability_for(route, proof=proof, artifact_paths=artifact_paths),
                "route": route,
                "source_kind": "chronicle",
                "source_ref": str(path),
                "created_at": str(entry.get("created_at") or _utcnow_iso()),
                "score": _score_signal(
                    claim=claim,
                    proof=proof,
                    lesson=lesson,
                    artifact_paths=artifact_paths,
                    workspace_keys=workspace_keys,
                    route=route,
                ),
            }
        )
    return signals


def _persistent_state_signal(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    sections = _section_map(path.read_text(encoding="utf-8", errors="replace"))
    snapshot = _normalize_text(" ".join(sections.get("snapshot", [])[:2]))
    findings = _normalize_text(" ".join(sections.get("findings", [])[:2]))
    actions = _normalize_text(" ".join(sections.get("actions", [])[:2]))
    automation = _normalize_text(" ".join(sections.get("automation health", [])[:2]))
    claim = findings or snapshot
    if not claim:
        return []
    route = "keep_in_ops"
    return [
        {
            "id": _signal_id("persistent_state", str(path), claim),
            "title": "Persistent state signal",
            "claim": _truncate(claim, 280),
            "proof": _truncate(automation, 240),
            "lesson": _truncate(actions, 220),
            "artifact_paths": [],
            "workspace_keys": _workspace_keys(claim, automation, actions) or ["shared_ops"],
            "topic_tags": _topic_tags(claim, automation, actions, "persistent_state"),
            "durability": _durability_for(route, proof=automation, artifact_paths=[]),
            "route": route,
            "source_kind": "persistent_state",
            "source_ref": str(path),
            "created_at": _utcnow_iso(),
            "score": _score_signal(
                claim=claim,
                proof=automation,
                lesson=actions,
                artifact_paths=[],
                workspace_keys=_workspace_keys(claim, automation, actions) or ["shared_ops"],
                route=route,
            ),
        }
    ]


def _daily_brief_signal(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    latest = _latest_markdown_entry(path.read_text(encoding="utf-8", errors="replace"))
    sections = _section_map(latest)
    summary = _normalize_text(" ".join(sections.get("summary", [])[:3] or sections.get("key highlights:", [])[:3]))
    blockers = _normalize_text(" ".join(sections.get("blockers/alerts", [])[:2] or sections.get("alerts & follow-ups:", [])[:2]))
    follow_ups = _normalize_text(" ".join(sections.get("follow-ups", [])[:2] or sections.get("additional notes:", [])[:2]))
    claim = summary or blockers
    if not claim:
        return []
    route = "keep_in_ops"
    return [
        {
            "id": _signal_id("daily_brief", str(path), claim),
            "title": "Daily brief signal",
            "claim": _truncate(claim, 280),
            "proof": _truncate(blockers, 220),
            "lesson": _truncate(follow_ups, 220),
            "artifact_paths": [],
            "workspace_keys": _workspace_keys(claim, blockers, follow_ups) or ["shared_ops"],
            "topic_tags": _topic_tags(claim, blockers, follow_ups, "daily_brief"),
            "durability": _durability_for(route, proof=blockers, artifact_paths=[]),
            "route": route,
            "source_kind": "daily_brief",
            "source_ref": str(path),
            "created_at": _utcnow_iso(),
            "score": _score_signal(
                claim=claim,
                proof=blockers,
                lesson=follow_ups,
                artifact_paths=[],
                workspace_keys=_workspace_keys(claim, blockers, follow_ups) or ["shared_ops"],
                route=route,
            ),
        }
    ]


def _dream_cycle_signal(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    sections = _section_map(path.read_text(encoding="utf-8", errors="replace"))
    highlights = sections.get("latest codex handoff highlights", [])
    learning_lines = sections.get("learning and action items", [])
    follow_up_lines = sections.get("follow-up actions", [])
    claim = _first_sentence(" ".join(highlights[:2])) or _first_sentence(" ".join(sections.get("overview", [])[:2]))
    proof = _normalize_text(" ".join(highlights[:3]))
    lesson = _normalize_text(" ".join(learning_lines[:2] + follow_up_lines[:1]))
    if not claim:
        return []
    artifact_paths = _extract_artifact_paths(proof, lesson)
    route = _recommend_route(
        claim=claim,
        proof=proof,
        lesson=lesson,
        source_kind="dream_cycle",
        identity_bias=False,
        artifact_paths=artifact_paths,
    )
    workspace_keys = _workspace_keys(claim, proof, lesson) or ["shared_ops"]
    return [
        {
            "id": _signal_id("dream_cycle", str(path), claim),
            "title": "Dream cycle signal",
            "claim": _truncate(claim, 280),
            "proof": _truncate(proof, 260),
            "lesson": _truncate(lesson, 220),
            "artifact_paths": artifact_paths[:5],
            "workspace_keys": workspace_keys,
            "topic_tags": _topic_tags(claim, proof, lesson, "dream_cycle"),
            "durability": _durability_for(route, proof=proof, artifact_paths=artifact_paths),
            "route": route,
            "source_kind": "dream_cycle",
            "source_ref": str(path),
            "created_at": _utcnow_iso(),
            "score": _score_signal(
                claim=claim,
                proof=proof,
                lesson=lesson,
                artifact_paths=artifact_paths,
                workspace_keys=workspace_keys,
                route=route,
            ),
        }
    ]


def _cron_prune_signal(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    sections = _parse_cron_sections(path.read_text(encoding="utf-8", errors="replace"))
    highlights = [_normalize_text(line) for line in sections.get("highlights", []) if _normalize_text(line)]
    blockers = _normalize_text(" ".join(sections.get("blockers", [])[:2]))
    follow_up = _normalize_text(" ".join(sections.get("follow-up", [])[:2]))
    claim = highlights[0] if highlights else blockers
    proof = " ".join(highlights[1:3])
    if not claim:
        return []
    route = _recommend_route(
        claim=claim,
        proof=proof,
        lesson=follow_up or blockers,
        source_kind="cron_prune",
        identity_bias=False,
        artifact_paths=[],
    )
    workspace_keys = _workspace_keys(claim, proof, follow_up, blockers) or ["shared_ops"]
    return [
        {
            "id": _signal_id("cron_prune", str(path), claim),
            "title": "Progress pulse signal",
            "claim": _truncate(claim, 280),
            "proof": _truncate(proof or blockers, 220),
            "lesson": _truncate(follow_up, 180),
            "artifact_paths": [],
            "workspace_keys": workspace_keys,
            "topic_tags": _topic_tags(claim, proof, follow_up, blockers, "progress_pulse"),
            "durability": _durability_for(route, proof=proof or blockers, artifact_paths=[]),
            "route": route,
            "source_kind": "cron_prune",
            "source_ref": str(path),
            "created_at": _utcnow_iso(),
            "score": _score_signal(
                claim=claim,
                proof=proof or blockers,
                lesson=follow_up,
                artifact_paths=[],
                workspace_keys=workspace_keys,
                route=route,
            ),
        }
    ]


def _dedupe_and_rank(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(signals, key=lambda item: (int(item.get("score") or 0), str(item.get("created_at") or "")), reverse=True)
    deduped: list[dict[str, Any]] = []
    overflow: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    per_source_counts: dict[str, int] = {}
    for signal in ranked:
        claim = _normalize_text(signal.get("claim"))
        route = str(signal.get("route") or "")
        source_kind = str(signal.get("source_kind") or "unknown")
        key = (claim.lower(), route)
        if not claim or key in seen:
            continue
        seen.add(key)
        limit = SOURCE_LIMITS.get(source_kind, 1)
        if per_source_counts.get(source_kind, 0) < limit:
            deduped.append(signal)
            per_source_counts[source_kind] = per_source_counts.get(source_kind, 0) + 1
        else:
            overflow.append(signal)
        if len(deduped) >= MAX_SIGNALS:
            break
    if len(deduped) < MAX_SIGNALS:
        for signal in overflow:
            deduped.append(signal)
            if len(deduped) >= MAX_SIGNALS:
                break
    return deduped


def build_operator_story_signals_payload(
    *,
    workspace_key: str = DEFAULT_WORKSPACE_KEY,
    memory_root: Path | None = None,
) -> dict[str, Any]:
    resolved_memory_root = (memory_root or MEMORY_ROOT).resolve()
    source_paths = {name: str((resolved_memory_root / name).resolve()) for name in DEFAULT_SOURCE_FILE_NAMES}
    collected: list[dict[str, Any]] = []
    collected.extend(_chronicle_signals(Path(source_paths["codex_session_handoff.jsonl"])))
    collected.extend(_persistent_state_signal(Path(source_paths["persistent_state.md"])))
    collected.extend(_daily_brief_signal(Path(source_paths["daily-briefs.md"])))
    collected.extend(_dream_cycle_signal(Path(source_paths["dream_cycle_log.md"])))
    collected.extend(_cron_prune_signal(Path(source_paths["cron-prune.md"])))
    signals = _dedupe_and_rank(collected)

    route_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    workspace_counts: dict[str, int] = {}
    for signal in signals:
        route = str(signal.get("route") or "keep_in_ops")
        source_kind = str(signal.get("source_kind") or "unknown")
        route_counts[route] = route_counts.get(route, 0) + 1
        source_counts[source_kind] = source_counts.get(source_kind, 0) + 1
        for workspace in signal.get("workspace_keys") or []:
            workspace_key_name = str(workspace or "").strip()
            if workspace_key_name:
                workspace_counts[workspace_key_name] = workspace_counts.get(workspace_key_name, 0) + 1

    return {
        "generated_at": _utcnow_iso(),
        "workspace": workspace_key,
        "source_paths": source_paths,
        "signals": signals,
        "counts": {
            "total": len(signals),
            "by_route": route_counts,
            "by_source_kind": source_counts,
            "by_workspace": workspace_counts,
        },
        "notes": {
            "design_rule": "Distill raw OpenClaw memory into bounded operator-story signals before routing into persona or content lanes.",
            "routes": ["keep_in_ops", "persona_candidate", "content_reservoir"],
        },
    }


def render_operator_story_signals_markdown(payload: dict[str, Any]) -> str:
    counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
    by_route = counts.get("by_route") if isinstance(counts.get("by_route"), dict) else {}
    lines = [
        "# Operator Story Signals",
        "",
        f"- Generated at: `{payload.get('generated_at')}`",
        f"- Workspace: `{payload.get('workspace')}`",
        f"- Signal count: `{counts.get('total', 0)}`",
        f"- Routes: `{json.dumps(by_route, sort_keys=True)}`",
        "",
    ]
    for signal in payload.get("signals") or []:
        if not isinstance(signal, dict):
            continue
        lines.extend(
            [
                f"## {signal.get('title') or 'Signal'}",
                f"- Route: `{signal.get('route')}`",
                f"- Durability: `{signal.get('durability')}`",
                f"- Source: `{signal.get('source_kind')}`",
                f"- Workspaces: `{', '.join(signal.get('workspace_keys') or []) or 'shared_ops'}`",
                f"- Claim: {signal.get('claim') or ''}",
                f"- Proof: {signal.get('proof') or 'None'}",
                f"- Lesson: {signal.get('lesson') or 'None'}",
            ]
        )
        artifact_paths = signal.get("artifact_paths") or []
        if artifact_paths:
            lines.append(f"- Artifacts: `{', '.join(artifact_paths)}`")
        topic_tags = signal.get("topic_tags") or []
        if topic_tags:
            lines.append(f"- Topic tags: `{', '.join(topic_tags)}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
