from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.services.brain_response_privacy_service import sanitize_brain_text
from app.services.execution_artifact_reference_service import (
    contains_private_filesystem_reference,
    validate_remote_execution_artifact_reference,
)
from app.services.workspace_registry_service import (
    ACTIVE_PORTFOLIO_WORKSPACE_STATUSES,
    REPO_ROOT,
    workspace_registry_entries,
    workspace_root_path,
)
from app.utils.ai_clone_clock import CLOCK_AUTHORITY, CLOCK_SCHEMA_VERSION


PROJECTION_SCHEMA = "ops_workspace_context_projection/v1"
SNAPSHOT_TYPE = "ops_workspace_cycle_context"
WORKSPACE_KEY = "shared_ops"
MAX_BYTES = 128 * 1024
MAX_WORKSPACES = 25
MAX_ARTIFACTS_PER_WORKSPACE = 4
MAX_SOURCE_BYTES = 512 * 1024
MAX_PREP_BYTES = 2 * 1024 * 1024

_PROJECTION_FIELDS = frozenset(
    {
        "schema_version",
        "generated_at",
        "observed_at",
        "clock",
        "state",
        "reason_codes",
        "cycle_id",
        "workspaces",
        "data_policy",
    }
)
_WORKSPACE_FIELDS = frozenset(
    {
        "workspace_key",
        "display_name",
        "state",
        "reason_codes",
        "current_focus",
        "artifacts",
    }
)
_FOCUS_FIELDS = frozenset({"title", "status", "source_kind"})
_ARTIFACT_FIELDS = frozenset(
    {
        "kind",
        "title",
        "summary",
        "reference",
        "source_updated_at",
        "source_sha256",
        "consumption_role",
        "source_state",
    }
)
_DATA_POLICY = {
    "canonical_authority": "private_cycle_prep_and_workspace_state",
    "railway_role": "authenticated_bounded_workspace_context_projection",
    "private_bodies_included": False,
    "absolute_paths_included": False,
    "projection_is_write_authority": False,
}
_ARTIFACT_FIELDS_BY_KIND = (
    ("analytics", "latest_analytics_path"),
    ("execution_log", "execution_log_path"),
    ("briefing", "latest_briefing_path"),
    ("dispatch", "latest_sop_path"),
)
_SUMMARY_HEADINGS = {
    "analytics": (
        "exact next move",
        "current next experiment",
        "current state",
        "observed evidence",
        "bounded opportunity",
        "decision gate",
        "completion path",
        "purpose",
        "summary",
    ),
    "execution_log": (
        "outcome",
        "what changed",
        "follow-ups",
        "next",
        "summary",
    ),
    "briefing": (
        "outcome",
        "what changed",
        "next",
        "objective",
        "summary",
    ),
}
_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    flags=re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", flags=re.IGNORECASE)
_URL_RE = re.compile(r"https?://[^\s)>]+", flags=re.IGNORECASE)
_WORKSPACE_RECORD_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,12}-[A-Z][A-Z0-9]{1,12}-\d+\b")
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_WORKSPACE_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class OpsWorkspaceContextProjectionError(ValueError):
    pass


def _state_root() -> Path:
    return Path(
        os.getenv("AI_CLONE_STATE_ROOT")
        or (Path.home() / ".codex" / "ai-clone" / "state")
    ).expanduser()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_utc(value: Any, *, field: str) -> datetime:
    raw = str(value or "").strip()
    if not raw or len(raw) > 100:
        raise OpsWorkspaceContextProjectionError(f"{field} is missing or invalid")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OpsWorkspaceContextProjectionError(
            f"{field} is missing or invalid"
        ) from exc
    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
        or parsed.utcoffset() != timezone.utc.utcoffset(parsed)
    ):
        raise OpsWorkspaceContextProjectionError(f"{field} must use ai_clone_utc")
    return parsed.astimezone(timezone.utc)


def _active_project_entries() -> tuple[dict[str, Any], ...]:
    entries = tuple(
        dict(entry)
        for entry in workspace_registry_entries()
        if entry.get("kind") == "workspace"
        and entry.get("portfolio_visible") is True
        and str(entry.get("status") or "")
        in ACTIVE_PORTFOLIO_WORKSPACE_STATUSES
        and str(entry.get("key") or "").strip()
        and str(entry.get("key") or "").strip() != WORKSPACE_KEY
    )
    keys = [str(entry["key"]) for entry in entries]
    if not entries or len(entries) > MAX_WORKSPACES or len(keys) != len(set(keys)):
        raise OpsWorkspaceContextProjectionError(
            "The canonical active workspace registry is unavailable or malformed."
        )
    return entries


def _read_json(path: Path, *, maximum_bytes: int) -> dict[str, Any]:
    if (
        not path.exists()
        or not path.is_file()
        or path.is_symlink()
        or path.stat().st_size > maximum_bytes
    ):
        raise OpsWorkspaceContextProjectionError("A required cycle receipt is unavailable or oversized.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OpsWorkspaceContextProjectionError("A required cycle receipt is malformed.") from exc
    if not isinstance(value, dict):
        raise OpsWorkspaceContextProjectionError("A required cycle receipt is malformed.")
    return value


def _within(path: Path, root: Path) -> Path | None:
    try:
        return path.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, RuntimeError, ValueError):
        return None


def _prep_path(raw: Any, *, state_root: Path) -> Path | None:
    value = str(raw or "").strip()
    if not value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = state_root / path
    allowed_root = state_root / "memory" / "standup-prep"
    if _within(path, allowed_root) is None:
        return None
    if path.is_symlink() or path.stat().st_size > MAX_PREP_BYTES:
        return None
    return path


def _humanize_reference(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        return ""
    if "/" in candidate or re.search(r"\.(?:md|json|jsonl|csv|txt)$", candidate, flags=re.IGNORECASE):
        stem = Path(candidate.replace("\\", "/")).stem
        return re.sub(r"[_-]+", " ", stem).strip()
    return candidate


def _owner_text(value: Any, *, limit: int) -> str:
    text = _MARKDOWN_LINK_RE.sub(lambda match: match.group(1), str(value or ""))
    text = _BACKTICK_RE.sub(lambda match: _humanize_reference(match.group(1)), text)
    text = _URL_RE.sub("an external reference", text)
    text = _EMAIL_RE.sub("a private contact", text)
    text = _UUID_RE.sub("a prior record", text)
    text = _WORKSPACE_RECORD_RE.sub("the current workspace opportunity", text)
    text = sanitize_brain_text(text)
    text = " ".join(text.replace("\xa0", " ").split()).strip(" -")
    if not text or "[credential" in text.lower() or "[private-runtime]" in text.lower():
        return ""
    if len(text) <= limit:
        return text
    clipped = text[: max(0, limit - 1)].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return f"{clipped or text[: max(0, limit - 1)]}…"


def _markdown_title(text: str, path: Path) -> str:
    for line in text.splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line.strip())
        if match:
            title = _owner_text(match.group(1), limit=180)
            if title:
                return title
    return _owner_text(path.stem.replace("_", " ").replace("-", " "), limit=180)


def _section_lines(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = ""
    for raw_line in text.splitlines():
        heading = re.match(r"^#{2,4}\s+(.+?)\s*$", raw_line.strip())
        if heading:
            current = " ".join(heading.group(1).lower().split())
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(raw_line)
    return sections


def _meaningful_section_text(lines: list[str]) -> str:
    fragments: list[str] = []
    skipped_prefixes = (
        "date:",
        "workspace:",
        "source card:",
        "pm card:",
        "opportunity owner:",
        "source:",
    )
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("|"):
            continue
        line = re.sub(r"^(?:[-*]|\d+[.)])\s+", "", line)
        if (
            not line
            or line.lower().startswith(skipped_prefixes)
            or re.search(r"_{3,}", line)
        ):
            continue
        cleaned = _owner_text(line, limit=320)
        if not cleaned:
            continue
        fragments.append(cleaned)
        if len(" ".join(fragments)) >= 260 or len(fragments) >= 2:
            break
    return _owner_text(" ".join(fragments), limit=480)


def _markdown_summary(text: str, *, kind: str) -> str:
    sections = _section_lines(text)
    for heading in _SUMMARY_HEADINGS.get(kind, ()):
        summary = _meaningful_section_text(sections.get(heading, []))
        if summary:
            return summary
    for lines in sections.values():
        summary = _meaningful_section_text(lines)
        if summary:
            return summary
    return ""


def _latest_execution_result(text: str) -> tuple[str, str]:
    entry_matches = list(re.finditer(r"(?m)^##\s+.+?\s*$", text))
    if not entry_matches:
        return "", ""
    latest = text[entry_matches[-1].start() :]
    result = ""
    for raw_line in latest.splitlines():
        match = re.match(
            r"^\s*(?:[-*]\s*)?result:\s*(.+?)\s*$",
            raw_line,
            flags=re.IGNORECASE,
        )
        if match:
            result = _owner_text(match.group(1), limit=180)
            break
    sections = _section_lines(latest)
    summary_parts = [
        _meaningful_section_text(sections.get("outcomes", [])),
        _meaningful_section_text(sections.get("follow-ups", [])),
    ]
    summary = _owner_text(
        " ".join(part for part in summary_parts if part),
        limit=480,
    )
    return result, summary


def _json_title_and_summary(text: str, path: Path) -> tuple[str, str]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = {}
    title = ""
    summary = ""
    if isinstance(value, dict):
        for key in ("title", "name", "objective"):
            title = _owner_text(value.get(key), limit=180)
            if title:
                break
        for key in ("objective", "summary", "reason", "next_step"):
            summary = _owner_text(value.get(key), limit=480)
            if summary and summary != title:
                break
    if not title:
        title = _owner_text(path.stem.replace("_", " ").replace("-", " "), limit=180)
    return title, summary


def _artifact_path(
    raw: Any,
    *,
    workspace_key: str,
    state_root: Path,
) -> tuple[Path, str] | None:
    value = str(raw or "").strip()
    if not value:
        return None
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = state_root / candidate
    roots = (
        state_root / "workspaces" / workspace_key,
        workspace_root_path(workspace_key),
    )
    for root in roots:
        relative = _within(candidate, root)
        if relative is None:
            continue
        if candidate.is_symlink() or candidate.stat().st_size > MAX_SOURCE_BYTES:
            return None
        reference = f"workspace://{workspace_key}/{relative.as_posix()}"
        try:
            validate_remote_execution_artifact_reference(reference)
        except ValueError:
            return None
        return candidate, reference
    return None


def _artifact_projection(
    *,
    kind: str,
    raw_path: Any,
    workspace_key: str,
    state_root: Path,
    observed_at: datetime,
) -> dict[str, Any] | None:
    resolved = _artifact_path(
        raw_path,
        workspace_key=workspace_key,
        state_root=state_root,
    )
    if resolved is None:
        return None
    path, reference = resolved
    try:
        raw_bytes = path.read_bytes()
        text = raw_bytes.decode("utf-8", errors="ignore")
    except OSError:
        return None
    if path.suffix.lower() == ".json":
        title, summary = _json_title_and_summary(text, path)
    elif kind == "execution_log":
        title, summary = _latest_execution_result(text)
        title = title or _markdown_title(text, path)
        summary = summary or _markdown_summary(text, kind=kind)
    else:
        title = _markdown_title(text, path)
        summary = _markdown_summary(text, kind=kind)
    if not title:
        return None
    source_updated = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return {
        "kind": kind,
        "title": title,
        "summary": summary,
        "reference": reference,
        "source_updated_at": source_updated.isoformat().replace("+00:00", "Z"),
        "source_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "consumption_role": "reference_only",
        "source_state": (
            "verified_preexisting"
            if source_updated <= observed_at
            else "changed_since_cycle"
        ),
    }


def _current_focus(prep: Mapping[str, Any]) -> dict[str, str] | None:
    snapshot = prep.get("pm_snapshot")
    if not isinstance(snapshot, Mapping):
        return None
    cards = snapshot.get("cards")
    if not isinstance(cards, list):
        return None
    for raw_card in cards:
        if not isinstance(raw_card, Mapping):
            continue
        title = _owner_text(raw_card.get("title"), limit=220)
        if not title:
            continue
        truth = raw_card.get("effective_truth")
        effective = truth if isinstance(truth, Mapping) else {}
        status = _owner_text(
            effective.get("effective_state")
            or raw_card.get("status")
            or raw_card.get("top_status")
            or "unknown",
            limit=80,
        ).lower().replace(" ", "_")
        if status not in {
            "todo",
            "queued",
            "running",
            "in_progress",
            "review",
            "blocked",
            "failed",
            "done",
            "complete",
        }:
            status = "unknown"
        return {
            "title": title,
            "status": status,
            "source_kind": "canonical_pm_snapshot",
        }
    return None


def _workspace_projection(
    entry: Mapping[str, Any],
    result: Mapping[str, Any] | None,
    *,
    state_root: Path,
    cycle_id: str,
    observed_at: datetime,
) -> dict[str, Any]:
    workspace_key = str(entry["key"])
    display_name = _owner_text(
        entry.get("portfolio_label") or entry.get("display_name") or workspace_key,
        limit=120,
    )
    reason_codes: list[str] = []
    prep: dict[str, Any] | None = None
    if result is None:
        reason_codes.append("workspace_cycle_result_missing")
    else:
        path = _prep_path(result.get("prep_json_path"), state_root=state_root)
        if path is None:
            reason_codes.append("workspace_cycle_prep_unavailable")
        else:
            try:
                candidate = _read_json(path, maximum_bytes=MAX_PREP_BYTES)
                if (
                    candidate.get("schema_version") != "standup_prep/v2"
                    or candidate.get("workspace_key") != workspace_key
                    or candidate.get("cycle_id") != cycle_id
                    or _parse_utc(candidate.get("observed_at"), field="prep observed_at")
                    != observed_at
                ):
                    raise OpsWorkspaceContextProjectionError(
                        "Workspace prep identity does not match the portfolio cycle."
                    )
                prep = candidate
            except OpsWorkspaceContextProjectionError:
                reason_codes.append("workspace_cycle_prep_invalid")

    artifacts: list[dict[str, Any]] = []
    focus = _current_focus(prep or {})
    context = prep.get("workspace_context") if isinstance(prep, Mapping) else None
    if isinstance(context, Mapping) and context.get("available") is True:
        seen_refs: set[str] = set()
        for kind, field in _ARTIFACT_FIELDS_BY_KIND:
            artifact = _artifact_projection(
                kind=kind,
                raw_path=context.get(field),
                workspace_key=workspace_key,
                state_root=state_root,
                observed_at=observed_at,
            )
            if artifact is None or artifact["reference"] in seen_refs:
                continue
            seen_refs.add(str(artifact["reference"]))
            artifacts.append(artifact)
            if len(artifacts) >= MAX_ARTIFACTS_PER_WORKSPACE:
                break
    elif prep is not None:
        reason_codes.append("workspace_context_unavailable")

    verified_artifacts = [
        artifact
        for artifact in artifacts
        if artifact["source_state"] == "verified_preexisting"
    ]
    if prep is not None and not artifacts:
        reason_codes.append("no_bounded_consumed_artifacts")
    elif prep is not None and not verified_artifacts:
        reason_codes.append("consumed_sources_changed_since_cycle")
    state = (
        "consumed"
        if prep is not None and verified_artifacts
        else "partial"
        if prep is not None or focus
        else "unavailable"
    )
    return {
        "workspace_key": workspace_key,
        "display_name": display_name,
        "state": state,
        "reason_codes": list(dict.fromkeys(reason_codes))[:10],
        "current_focus": focus,
        "artifacts": artifacts,
    }


def build_ops_workspace_context_projection(
    *,
    state_root: Path | None = None,
    report_path: Path | None = None,
) -> dict[str, Any]:
    resolved_state_root = Path(state_root or _state_root()).expanduser()
    resolved_report = Path(
        report_path
        or resolved_state_root
        / "memory"
        / "reports"
        / "portfolio_standup_prep_latest.json"
    ).expanduser()
    report = _read_json(resolved_report, maximum_bytes=MAX_PREP_BYTES)
    if report.get("schema_version") != "portfolio_standup_prep/v1":
        raise OpsWorkspaceContextProjectionError("The portfolio prep receipt has an invalid schema.")
    cycle_id = str(report.get("cycle_id") or "").strip()
    if not cycle_id or len(cycle_id) > 200:
        raise OpsWorkspaceContextProjectionError("The portfolio prep receipt has no bounded cycle identity.")
    observed_at_raw = str(report.get("observed_at") or "").strip()
    observed_at = _parse_utc(observed_at_raw, field="observed_at")
    raw_results = report.get("results")
    if not isinstance(raw_results, list):
        raise OpsWorkspaceContextProjectionError("The portfolio prep receipt has no workspace results.")
    results_by_workspace: dict[str, Mapping[str, Any]] = {}
    for item in raw_results:
        if not isinstance(item, Mapping):
            continue
        key = str(item.get("workspace_key") or "").strip()
        if key and key not in results_by_workspace:
            results_by_workspace[key] = item

    workspaces = [
        _workspace_projection(
            entry,
            results_by_workspace.get(str(entry["key"])),
            state_root=resolved_state_root,
            cycle_id=cycle_id,
            observed_at=observed_at,
        )
        for entry in _active_project_entries()
    ]
    degraded = [item for item in workspaces if item["state"] != "consumed"]
    projection = {
        "schema_version": PROJECTION_SCHEMA,
        "generated_at": _now_iso(),
        "observed_at": observed_at_raw,
        "clock": {
            "schema_version": CLOCK_SCHEMA_VERSION,
            "authority": CLOCK_AUTHORITY,
            "timezone": "UTC",
            "observed_at": observed_at_raw,
        },
        "state": "degraded" if degraded else "ready",
        "reason_codes": (
            ["workspace_context_projection_incomplete"] if degraded else []
        ),
        "cycle_id": cycle_id,
        "workspaces": workspaces,
        "data_policy": dict(_DATA_POLICY),
    }
    return validate_ops_workspace_context_projection(projection)


def unavailable_ops_workspace_context_projection(reason: str) -> dict[str, Any]:
    return {
        "schema_version": PROJECTION_SCHEMA,
        "generated_at": _now_iso(),
        "observed_at": None,
        "clock": None,
        "state": "unavailable",
        "reason_codes": [str(reason or "projection_unavailable")[:200]],
        "cycle_id": None,
        "workspaces": [],
        "data_policy": dict(_DATA_POLICY),
    }


def validate_ops_workspace_context_projection(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("schema_version") != PROJECTION_SCHEMA:
        raise OpsWorkspaceContextProjectionError("invalid workspace-context projection schema")
    if set(payload) != _PROJECTION_FIELDS:
        raise OpsWorkspaceContextProjectionError("invalid workspace-context projection envelope")
    _parse_utc(payload.get("generated_at"), field="generated_at")
    state = payload.get("state")
    reason_codes = payload.get("reason_codes")
    if (
        state not in {"ready", "degraded", "unavailable"}
        or not isinstance(reason_codes, list)
        or len(reason_codes) > 20
        or any(not isinstance(item, str) or not item.strip() or len(item) > 200 for item in reason_codes)
        or (state == "ready" and reason_codes)
        or (state != "ready" and not reason_codes)
        or payload.get("data_policy") != _DATA_POLICY
    ):
        raise OpsWorkspaceContextProjectionError("invalid workspace-context projection state")

    workspaces = payload.get("workspaces")
    if not isinstance(workspaces, list) or len(workspaces) > MAX_WORKSPACES:
        raise OpsWorkspaceContextProjectionError("invalid workspace-context projection workspaces")
    if state == "unavailable":
        if (
            payload.get("observed_at") is not None
            or payload.get("clock") is not None
            or payload.get("cycle_id") is not None
            or workspaces
        ):
            raise OpsWorkspaceContextProjectionError("unavailable projection cannot claim cycle context")
    else:
        observed_at_raw = str(payload.get("observed_at") or "")
        observed_at = _parse_utc(observed_at_raw, field="observed_at")
        clock = payload.get("clock")
        if not isinstance(clock, dict) or clock != {
            "schema_version": CLOCK_SCHEMA_VERSION,
            "authority": CLOCK_AUTHORITY,
            "timezone": "UTC",
            "observed_at": observed_at_raw,
        }:
            raise OpsWorkspaceContextProjectionError("invalid workspace-context projection clock")
        cycle_id = payload.get("cycle_id")
        if not isinstance(cycle_id, str) or not cycle_id.strip() or len(cycle_id) > 200:
            raise OpsWorkspaceContextProjectionError("invalid workspace-context cycle identity")
        expected_keys = [str(entry["key"]) for entry in _active_project_entries()]
        projected_keys: list[str] = []
        for item in workspaces:
            if not isinstance(item, dict) or set(item) != _WORKSPACE_FIELDS:
                raise OpsWorkspaceContextProjectionError("invalid workspace-context item")
            workspace_key = item.get("workspace_key")
            projected_keys.append(str(workspace_key or ""))
            if (
                not isinstance(workspace_key, str)
                or _WORKSPACE_KEY_RE.fullmatch(workspace_key) is None
                or not isinstance(item.get("display_name"), str)
                or not str(item["display_name"]).strip()
                or len(item["display_name"]) > 120
                or item.get("state") not in {"consumed", "partial", "unavailable"}
                or not isinstance(item.get("reason_codes"), list)
                or len(item["reason_codes"]) > 10
                or any(not isinstance(reason, str) or not reason.strip() or len(reason) > 200 for reason in item["reason_codes"])
                or (item.get("state") == "consumed" and item["reason_codes"])
            ):
                raise OpsWorkspaceContextProjectionError("invalid workspace-context item")
            focus = item.get("current_focus")
            if focus is not None and (
                not isinstance(focus, dict)
                or set(focus) != _FOCUS_FIELDS
                or not isinstance(focus.get("title"), str)
                or not focus["title"].strip()
                or len(focus["title"]) > 220
                or focus.get("status") not in {"todo", "queued", "running", "in_progress", "review", "blocked", "failed", "done", "complete", "unknown"}
                or focus.get("source_kind") != "canonical_pm_snapshot"
            ):
                raise OpsWorkspaceContextProjectionError("invalid workspace-context focus")
            artifacts = item.get("artifacts")
            if not isinstance(artifacts, list) or len(artifacts) > MAX_ARTIFACTS_PER_WORKSPACE:
                raise OpsWorkspaceContextProjectionError("invalid workspace-context artifacts")
            if item.get("state") != "consumed" and not item["reason_codes"]:
                raise OpsWorkspaceContextProjectionError(
                    "incomplete workspace context requires a reason"
                )
            seen_refs: set[str] = set()
            verified_artifact_count = 0
            for artifact in artifacts:
                if not isinstance(artifact, dict) or set(artifact) != _ARTIFACT_FIELDS:
                    raise OpsWorkspaceContextProjectionError("invalid workspace-context artifact")
                reference = artifact.get("reference")
                if (
                    artifact.get("kind") not in {"analytics", "execution_log", "briefing", "dispatch"}
                    or not isinstance(artifact.get("title"), str)
                    or not artifact["title"].strip()
                    or len(artifact["title"]) > 180
                    or not isinstance(artifact.get("summary"), str)
                    or len(artifact["summary"]) > 480
                    or not isinstance(reference, str)
                    or not reference.startswith(f"workspace://{workspace_key}/")
                    or reference in seen_refs
                    or artifact.get("consumption_role") != "reference_only"
                    or artifact.get("source_state") not in {"verified_preexisting", "changed_since_cycle"}
                    or not isinstance(artifact.get("source_sha256"), str)
                    or _SHA256_RE.fullmatch(artifact["source_sha256"]) is None
                ):
                    raise OpsWorkspaceContextProjectionError("invalid workspace-context artifact")
                try:
                    validate_remote_execution_artifact_reference(reference)
                    source_updated_at = _parse_utc(
                        artifact.get("source_updated_at"),
                        field="source_updated_at",
                    )
                except (ValueError, OpsWorkspaceContextProjectionError) as exc:
                    raise OpsWorkspaceContextProjectionError("invalid workspace-context artifact") from exc
                if artifact["source_state"] == "verified_preexisting":
                    if source_updated_at > observed_at:
                        raise OpsWorkspaceContextProjectionError(
                            "verified workspace source postdates the governed cycle"
                        )
                    verified_artifact_count += 1
                elif source_updated_at <= observed_at:
                    raise OpsWorkspaceContextProjectionError(
                        "changed workspace source does not postdate the governed cycle"
                    )
                seen_refs.add(reference)
            if item.get("state") == "consumed" and verified_artifact_count == 0:
                raise OpsWorkspaceContextProjectionError(
                    "consumed workspace requires a verified preexisting artifact receipt"
                )
        if projected_keys != expected_keys or len(projected_keys) != len(set(projected_keys)):
            raise OpsWorkspaceContextProjectionError(
                "workspace-context projection must cover the exact active project portfolio"
            )
        if state == "ready" and any(item.get("state") != "consumed" for item in workspaces):
            raise OpsWorkspaceContextProjectionError("ready projection contains incomplete workspace context")
        if state == "degraded" and all(item.get("state") == "consumed" for item in workspaces):
            raise OpsWorkspaceContextProjectionError("degraded projection has no incomplete workspace context")

    try:
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise OpsWorkspaceContextProjectionError("workspace-context projection is not bounded JSON") from exc
    if (
        len(serialized.encode("utf-8")) > MAX_BYTES
        or contains_private_filesystem_reference(serialized)
        or sanitize_brain_text(serialized) != serialized
        or _EMAIL_RE.search(serialized)
    ):
        raise OpsWorkspaceContextProjectionError("workspace-context projection contains private or oversized material")
    return payload


def ops_workspace_context_projection_semantic_sha256(payload: dict[str, Any]) -> str:
    semantic = json.loads(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    semantic.pop("generated_at", None)
    return hashlib.sha256(
        json.dumps(semantic, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
