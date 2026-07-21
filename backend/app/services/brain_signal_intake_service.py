from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models import BrainSignal, BrainSignalCreateRequest, PersonaDelta
from app.services import brain_signal_service
from app.services.brain_workspace_contract_service import recommend_brain_workspaces
from app.services.portfolio_workspace_snapshot_service import build_portfolio_workspace_snapshot
from app.services.workspace_registry_service import REPO_ROOT, canonicalize_workspace_key


ROOT = REPO_ROOT
SOURCE_INDEX_FILENAMES = ("index.json", "index.json.txt")
SOURCE_SIGNAL_STATUSES = {"digested", "reviewed", "routed", "promoted"}
AUTOMATION_REPORT_SPECS: tuple[dict[str, Any], ...] = (
    {
        "automation_id": "brain_canonical_memory_sync",
        "label": "Brain canonical memory sync",
        "workspace_key": "shared_ops",
        "path": ROOT / "memory" / "reports" / "brain_canonical_memory_sync_latest.json",
    },
    {
        "automation_id": "accountability_sweep",
        "label": "Accountability sweep",
        "workspace_key": "shared_ops",
        "path": ROOT / "memory" / "reports" / "accountability_sweep_latest.json",
    },
    {
        "automation_id": "fallback_watchdog",
        "label": "Fallback watchdog",
        "workspace_key": "shared_ops",
        "path": ROOT / "memory" / "reports" / "fallback_watchdog_latest.json",
    },
    {
        "automation_id": "pulse_standup_autoroute",
        "label": "Pulse standup autoroute",
        "workspace_key": "feezie-os",
        "path": ROOT / "memory" / "reports" / "pulse_standup_autoroute_latest.json",
    },
    {
        "automation_id": "operator_story_signals",
        "label": "Operator story signals",
        "workspace_key": "feezie-os",
        "path": ROOT / "memory" / "reports" / "operator_story_signals_latest.json",
    },
    {
        "automation_id": "content_safe_operator_lessons",
        "label": "Content-safe operator lessons",
        "workspace_key": "feezie-os",
        "path": ROOT / "memory" / "reports" / "content_safe_operator_lessons_latest.json",
    },
    {
        "automation_id": "post_sync_dispatch",
        "label": "Post-sync dispatch",
        "workspace_key": "shared_ops",
        "path": ROOT / "memory" / "reports" / "post_sync_dispatch_latest.json",
    },
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def _trim(value: Any, *, limit: int = 360) -> str:
    text = _clean_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _source_index_candidates() -> list[Path]:
    roots = [
        ROOT,
        ROOT / "app",
        ROOT / "backend",
        ROOT / "backend" / "app",
        Path.cwd(),
        Path.cwd().parent,
        Path("/app"),
        Path("/app/app"),
        Path("/app/backend"),
        Path("/app/backend/app"),
        Path("/"),
    ]
    for parent in Path(__file__).resolve().parents:
        roots.extend([parent, parent / "app", parent / "backend", parent / "backend" / "app"])
    return list(
        dict.fromkeys(root / "knowledge" / "source-intelligence" / filename for root in roots for filename in SOURCE_INDEX_FILENAMES)
    )


def load_source_intelligence_index() -> dict[str, Any]:
    index_path = next((path for path in _source_index_candidates() if path.exists()), None)
    if index_path is None:
        return {"available": False, "sources": [], "counts": {}, "source_ref": None}
    payload = _read_json(index_path)
    sources = [item for item in payload.get("sources") or [] if isinstance(item, dict)]
    return {
        **payload,
        "available": bool(payload),
        "source_ref": str(index_path),
        "sources": sources,
        "counts": payload.get("counts") if isinstance(payload.get("counts"), dict) else {},
    }


def run_brain_signal_intake(
    *,
    include_source_intelligence: bool = True,
    include_workspace_attention: bool = True,
    include_automation_outputs: bool = True,
    source_limit: int | None = None,
    include_quiet_automation: bool = False,
) -> dict[str, Any]:
    existing_ids = _existing_signal_ids()
    result: dict[str, Any] = {
        "schema_version": "brain_signal_intake_result/v1",
        "generated_at": _now_iso(),
        "counts": {"processed": 0, "created": 0, "updated": 0},
        "buckets": {
            "source_intelligence": _bucket_counts(),
            "workspace_attention": _bucket_counts(),
            "automation_outputs": _bucket_counts(),
        },
        "signals": [],
        "source_refs": [],
        "errors": [],
    }

    if include_source_intelligence:
        try:
            _ingest_source_intelligence(result=result, existing_ids=existing_ids, source_limit=source_limit)
        except Exception as exc:
            result["errors"].append(f"source_intelligence: {exc}")

    if include_workspace_attention:
        try:
            _ingest_workspace_attention(result=result, existing_ids=existing_ids)
        except Exception as exc:
            result["errors"].append(f"workspace_attention: {exc}")

    if include_automation_outputs:
        try:
            _ingest_automation_outputs(result=result, existing_ids=existing_ids, include_quiet=include_quiet_automation)
        except Exception as exc:
            result["errors"].append(f"automation_outputs: {exc}")

    return result


def _bucket_counts() -> dict[str, int]:
    return {"processed": 0, "created": 0, "updated": 0}


def _existing_signal_ids() -> dict[tuple[str, str], str]:
    existing: dict[tuple[str, str], str] = {}
    for signal in brain_signal_service.list_signals(limit=500):
        signature = _signature(signal.source_kind, signal.source_ref)
        if signature is not None:
            existing[signature] = signal.id
    return existing


def _signature(source_kind: str, source_ref: str | None) -> tuple[str, str] | None:
    ref = _clean_text(source_ref)
    if not ref:
        return None
    return (_clean_text(source_kind).lower(), ref)


def _record_signal(
    *,
    request: BrainSignalCreateRequest,
    bucket: str,
    result: dict[str, Any],
    existing_ids: dict[tuple[str, str], str],
) -> BrainSignal:
    signature = _signature(request.source_kind, request.source_ref)
    existing_id = existing_ids.get(signature) if signature is not None else None
    signal = brain_signal_service.create_signal(request)
    created = existing_id is None or existing_id != signal.id
    bucket_counts = result["buckets"][bucket]
    bucket_counts["processed"] += 1
    bucket_counts["created" if created else "updated"] += 1
    result["counts"]["processed"] += 1
    result["counts"]["created" if created else "updated"] += 1
    if signature is not None:
        existing_ids[signature] = signal.id
    result["signals"].append(
        {
            "id": signal.id,
            "source_kind": signal.source_kind,
            "source_ref": signal.source_ref,
            "source_workspace_key": signal.source_workspace_key,
            "workspace_candidates": signal.workspace_candidates,
            "review_status": signal.review_status,
            "bucket": bucket,
            "created": created,
        }
    )
    return signal


def _ingest_source_intelligence(
    *,
    result: dict[str, Any],
    existing_ids: dict[tuple[str, str], str],
    source_limit: int | None,
) -> None:
    index = load_source_intelligence_index()
    source_ref = index.get("source_ref")
    if source_ref:
        result["source_refs"].append(str(source_ref))
    sources = [source for source in (index.get("sources") or []) if _source_status(source) in SOURCE_SIGNAL_STATUSES]
    if source_limit is not None:
        sources = sources[: max(0, int(source_limit))]

    for source in sources:
        request = _source_signal_request(source, source_index=index)
        _record_signal(request=request, bucket="source_intelligence", result=result, existing_ids=existing_ids)


def _source_status(source: dict[str, Any]) -> str:
    return _clean_text(source.get("status")).lower() or "raw"


def _source_signal_request(source: dict[str, Any], *, source_index: dict[str, Any]) -> BrainSignalCreateRequest:
    source_id = _clean_text(source.get("source_id")) or _clean_text(source.get("source_url")) or _clean_text(source.get("raw_path"))
    status = _source_status(source)
    title = _clean_text(source.get("title")) or source_id
    summary = _clean_text(source.get("summary"))
    source_ref = source_id
    routing = _source_workspace_routing(source)
    workspace_candidates = routing["workspace_keys"]
    source_paths = [
        _clean_text(source.get(key))
        for key in ("raw_path", "normalized_path", "digest_path", "metadata_path")
        if _clean_text(source.get(key))
    ]
    route_decision = source.get("route_decision") if isinstance(source.get("route_decision"), dict) else {}
    digest = _trim(summary or title, limit=500)
    raw_summary = _trim(f"Source intelligence `{status}`: {title}. {summary}" if summary else f"Source intelligence `{status}`: {title}.", limit=900)
    return BrainSignalCreateRequest(
        source_kind="source_intelligence",
        source_ref=source_ref,
        source_workspace_key="shared_ops",
        raw_summary=raw_summary,
        digest=digest,
        signal_types=_clean_list(
            [
                "source_intelligence",
                f"source_status:{status}",
                _clean_text(source.get("source_kind")),
                _clean_text(source.get("source_channel")),
                _clean_text(source.get("source_type")),
            ]
        ),
        durability=_source_durability(status),
        confidence=_source_confidence(status),
        actionability=_source_actionability(status),
        identity_relevance="medium" if "feezie-os" in workspace_candidates else "unknown",
        workspace_candidates=workspace_candidates,
        executive_interpretation={
            "yoda_meaning": "Hold this as Brain signal before turning source intelligence into downstream work.",
            "neo_system_impact": "Source intelligence is now a first-class BrainSignal with workspace routing evidence attached.",
            "jean_claude_operational_translation": "Review the digest, then choose source-only, memory, standup, PM, persona canon, workspace-local, or ignore.",
        },
        route_decision={
            "intake": {
                "source": "brain_signal_intake_service",
                "source_index_ref": source_index.get("source_ref"),
                "source_index_generated_at": source_index.get("generated_at"),
                "source_status": status,
                "source_paths": list(dict.fromkeys(source_paths)),
                "original_route_decision": route_decision,
                "workspace_routing": routing,
                "raw_global_source_rule": "Raw global source intelligence must not flow directly into child workspaces.",
                "recommended_initial_route": "source_only" if status == "digested" else "review",
            }
        },
    )


def _source_workspace_routing(source: dict[str, Any]) -> dict[str, Any]:
    title = _clean_text(source.get("title"))
    summary = _clean_text(source.get("summary"))
    notes = " ".join(
        part
        for part in (
            summary,
            _clean_text(source.get("source_url")),
            _clean_text(source.get("source_channel")),
            _clean_text(source.get("source_type")),
        )
        if part
    )
    metadata = {
        "lane_hint": "source_intelligence",
        "evidence_source": _clean_text(source.get("source_url") or source.get("raw_path") or source.get("digest_path")),
        "route_decision": source.get("route_decision") if isinstance(source.get("route_decision"), dict) else {},
    }
    try:
        recommendation = recommend_brain_workspaces(
            PersonaDelta(
                id=f"source-intelligence::{_clean_text(source.get('source_id')) or 'source'}",
                capture_id=None,
                persona_target="feeze.core",
                trait=title or summary or "Source intelligence signal",
                notes=notes,
                status="draft",
                metadata=metadata,
                created_at=_now(),
                committed_at=None,
            )
        )
        keys = _canonical_workspace_keys(["shared_ops", *(recommendation.get("workspace_keys") or [])])
    except Exception as exc:
        recommendation = {"error": str(exc), "workspace_keys": ["shared_ops", "feezie-os"]}
        keys = ["shared_ops", "feezie-os"]

    if "feezie-os" not in keys:
        keys.append("feezie-os")
    return {
        "workspace_keys": keys,
        "policy": "source_intelligence_defaults_to_shared_ops_and_feezie_domain_evidence_required_for_project_workspaces",
        "recommendation": recommendation,
    }


def _source_durability(status: str) -> str:
    if status in {"promoted", "routed", "reviewed"}:
        return "durable"
    if status == "digested":
        return "medium"
    return "unknown"


def _source_confidence(status: str) -> str:
    if status in {"promoted", "routed", "reviewed"}:
        return "high"
    if status == "digested":
        return "medium"
    return "unknown"


def _source_actionability(status: str) -> str:
    if status in {"promoted", "routed"}:
        return "high"
    if status == "reviewed":
        return "medium"
    if status == "digested":
        return "low"
    return "unknown"


def _ingest_workspace_attention(*, result: dict[str, Any], existing_ids: dict[tuple[str, str], str]) -> None:
    snapshot = build_portfolio_workspace_snapshot()
    result["source_refs"].append("portfolio_workspace_snapshot_service")
    for workspace in snapshot.get("workspaces") or []:
        if not isinstance(workspace, dict):
            continue
        request = _workspace_attention_signal_request(workspace, snapshot=snapshot)
        if request is None:
            continue
        _record_signal(request=request, bucket="workspace_attention", result=result, existing_ids=existing_ids)


def _workspace_attention_signal_request(workspace: dict[str, Any], *, snapshot: dict[str, Any]) -> BrainSignalCreateRequest | None:
    workspace_key = canonicalize_workspace_key(workspace.get("workspace_key"), default="shared_ops")
    display_name = _clean_text(workspace.get("display_name") or workspace_key)
    counts = workspace.get("counts") if isinstance(workspace.get("counts"), dict) else {}
    attention_pm_cards = _int(counts.get("attention_pm_cards"))
    standup_blockers = _int(counts.get("standup_blockers"))
    active_pm_cards = _int(counts.get("active_pm_cards"))
    missing_writeback = active_pm_cards > 0 and not bool(workspace.get("execution_log"))
    if not (attention_pm_cards or standup_blockers or missing_writeback):
        return None

    blockers: list[str] = []
    for standup in workspace.get("latest_standups") or []:
        if isinstance(standup, dict):
            blockers.extend(_trim(item, limit=160) for item in standup.get("blockers") or [] if _clean_text(item))
    attention_titles = [
        _trim(card.get("title"), limit=160)
        for card in workspace.get("active_pm_cards") or []
        if isinstance(card, dict) and _clean_text(card.get("status")).lower() in {"review", "blocked", "failed"}
    ]
    signal_types = ["workspace_attention"]
    if attention_pm_cards:
        signal_types.append("pm_attention")
    if standup_blockers:
        signal_types.append("standup_blocker")
    if missing_writeback:
        signal_types.append("missing_writeback")
    summary = (
        f"{display_name} needs Brain attention: {attention_pm_cards} attention PM card(s), "
        f"{standup_blockers} standup blocker(s), {active_pm_cards} active PM card(s)."
    )
    if missing_writeback:
        summary += " Active work has no latest execution-log write-back visible in the portfolio snapshot."
    digest_parts = [summary, *blockers[:2], *attention_titles[:2]]
    return BrainSignalCreateRequest(
        source_kind="workspace_snapshot",
        source_ref=f"portfolio-workspace:{workspace_key}:attention",
        source_workspace_key=workspace_key,
        raw_summary=_trim(" ".join(part for part in digest_parts if part), limit=900),
        digest=_trim(summary, limit=500),
        signal_types=signal_types,
        durability="operational",
        confidence="high",
        actionability="high" if attention_pm_cards or standup_blockers else "medium",
        identity_relevance="workspace_scoped",
        workspace_candidates=_canonical_workspace_keys([workspace_key, "shared_ops"]),
        executive_interpretation={
            "yoda_meaning": "This is workspace state, not global source intelligence.",
            "neo_system_impact": "Brain has a portfolio-visible attention signal tied to PM, blocker, or write-back state.",
            "jean_claude_operational_translation": "Inspect the workspace before routing to standup or PM.",
        },
        route_decision={
            "intake": {
                "source": "brain_signal_intake_service",
                "portfolio_snapshot_generated_at": snapshot.get("generated_at"),
                "workspace_key": workspace_key,
                "counts": counts,
                "blockers": blockers[:4],
                "attention_pm_titles": attention_titles[:4],
                "source_paths": workspace.get("source_paths") or [],
                "recommended_initial_route": "standup",
                "writeback_required_before_pm_completion": True,
            }
        },
    )


def _ingest_automation_outputs(
    *,
    result: dict[str, Any],
    existing_ids: dict[tuple[str, str], str],
    include_quiet: bool,
) -> None:
    for spec in AUTOMATION_REPORT_SPECS:
        path = Path(spec["path"])
        if not path.exists():
            continue
        result["source_refs"].append(_relative_path(path))
        report = _read_json(path)
        request = _automation_signal_request(spec, report, include_quiet=include_quiet)
        if request is None:
            continue
        _record_signal(request=request, bucket="automation_outputs", result=result, existing_ids=existing_ids)


def _automation_signal_request(spec: dict[str, Any], report: dict[str, Any], *, include_quiet: bool) -> BrainSignalCreateRequest | None:
    markers = _automation_markers(report)
    if not markers and not include_quiet:
        return None
    automation_id = _clean_text(spec.get("automation_id"))
    label = _clean_text(spec.get("label")) or automation_id
    path = Path(spec["path"])
    workspace_key = canonicalize_workspace_key(spec.get("workspace_key"), default="shared_ops")
    generated_at = _clean_text(report.get("generated_at"))
    summary = f"{label} produced Brain-reviewable output"
    if markers:
        summary += f": {'; '.join(markers[:5])}."
    elif include_quiet:
        summary += " with no active alert markers."
    signal_types = ["automation_output", automation_id]
    if any("error" in marker.lower() for marker in markers):
        signal_types.append("automation_error")
    if any("stale" in marker.lower() or "followup" in marker.lower() for marker in markers):
        signal_types.append("pm_attention")
    return BrainSignalCreateRequest(
        source_kind="automation_output",
        source_ref=_relative_path(path),
        source_workspace_key=workspace_key,
        raw_summary=_trim(summary, limit=900),
        digest=_trim(summary, limit=500),
        signal_types=_clean_list(signal_types),
        durability="operational",
        confidence="high" if markers else "medium",
        actionability="high" if markers else "low",
        identity_relevance="operational",
        workspace_candidates=_canonical_workspace_keys([workspace_key, "shared_ops"]),
        executive_interpretation={
            "yoda_meaning": "Automation output should inform Brain without becoming its own planning layer.",
            "neo_system_impact": "Cron output is registered as a BrainSignal and remains traceable to its report.",
            "jean_claude_operational_translation": "Review the report markers, then route only if there is bounded follow-up work.",
        },
        route_decision={
            "intake": {
                "source": "brain_signal_intake_service",
                "automation_id": automation_id,
                "report_path": _relative_path(path),
                "report_generated_at": generated_at,
                "markers": markers,
                "recommended_initial_route": "standup" if markers else "source_only",
            }
        },
    )


def _automation_markers(report: dict[str, Any]) -> list[str]:
    markers: list[str] = []
    for key in (
        "active_count",
        "memory_alert_count",
        "durable_retrieval_alert_count",
        "delivery_alert_count",
        "runtime_alert_count",
        "queued_route_count",
        "processed_count",
        "ready_count",
        "dispatched_count",
        "stale_review_count",
        "stale_running_count",
        "rerouted_count",
        "route_count",
        "autorouted_count",
        "created_count",
        "lesson_count",
        "signal_count",
    ):
        count = _int(report.get(key))
        if count > 0:
            markers.append(f"{key}={count}")
    status = _clean_text(report.get("status")).lower()
    if status and status not in {"ok", "success", "completed"}:
        markers.append(f"status={status}")
    if report.get("active") is True:
        markers.append("active=true")
    followup = report.get("executive_followup_card")
    if isinstance(followup, dict) and followup.get("pending_card_ids"):
        markers.append(f"executive_followup_pending={len(followup.get('pending_card_ids') or [])}")
    brain_context = report.get("brain_context")
    if isinstance(brain_context, dict):
        errors = [_clean_text(error) for error in brain_context.get("errors") or [] if _clean_text(error)]
        if errors:
            markers.append(f"brain_context_errors={len(errors)}")
    counts = report.get("counts")
    if isinstance(counts, dict):
        total = _int(counts.get("total"))
        if total > 0:
            markers.append(f"counts.total={total}")
    return list(dict.fromkeys(markers))


def _canonical_workspace_keys(values: list[Any]) -> list[str]:
    keys: list[str] = []
    for value in values:
        key = canonicalize_workspace_key(value, default="")
        if key and key not in keys:
            keys.append(key)
    return keys


def _clean_list(values: list[Any]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        text = _clean_text(value)
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned
