from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping

from app.services.portfolio_cycle_service import PortfolioCycleService


def _parse_time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def adapt_daily_workspace_standups(
    rows: list[Mapping[str, Any]],
    *,
    cycle_date: date,
    observed_at: datetime,
    expected_workspaces: list[str],
    healthy_no_change_max_age_hours: int = 72,
) -> dict[str, dict[str, Any]]:
    """Adapt daily conclusions, including explicit fresh-state no-change receipts."""

    latest: dict[str, tuple[datetime, dict[str, Any]]] = {}
    prior: dict[str, tuple[datetime, Mapping[str, Any]]] = {}
    expected = set(expected_workspaces)
    freshness_reference = observed_at.replace(tzinfo=timezone.utc) if observed_at.tzinfo is None else observed_at.astimezone(timezone.utc)
    freshness_cutoff = freshness_reference - timedelta(hours=healthy_no_change_max_age_hours)
    for raw in rows:
        workspace = str(raw.get("workspace_key") or "").strip()
        if workspace not in expected or str(raw.get("status") or "").strip().lower() != "completed":
            continue
        created = _parse_time(raw.get("created_at"))
        if created is None or created.date() > cycle_date:
            continue
        if created.date() < cycle_date:
            if created >= freshness_cutoff and (workspace not in prior or created > prior[workspace][0]):
                prior[workspace] = (created, raw)
            continue
        payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else {}
        sections = payload.get("standup_sections") if isinstance(payload.get("standup_sections"), dict) else {}
        summary = " ".join(str(payload.get("summary") or raw.get("summary") or "Completed workspace standup.").split())
        adapted = {
            "summary": summary,
            "work_underway": sections.get("work_underway") or sections.get("next_focus") or [],
            "completed_work": sections.get("completed_work") or sections.get("content_produced") or [],
            "blockers": sections.get("blockers") or [],
            "urgent_escalations": sections.get("urgent_escalations") or [],
            "decisions": sections.get("decisions") or [],
            "evidence_links": [{"ref": f"standup:{raw.get('id')}"}] if raw.get("id") else [],
            "recommended_next_actions": sections.get("recommended_next_actions") or sections.get("next_focus") or [],
            "_conclusion_kind": "conclusion",
        }
        if workspace not in latest or created > latest[workspace][0]:
            latest[workspace] = (created, adapted)
    adapted_rows = {workspace: payload for workspace, (_created, payload) in latest.items()}
    for workspace, (created, raw) in prior.items():
        if workspace in adapted_rows:
            continue
        raw_payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else {}
        prior_summary = " ".join(str(raw_payload.get("summary") or raw.get("summary") or "Healthy; no material change.").split())
        adapted_rows[workspace] = {
            "summary": f"Healthy no-change receipt; latest completed workspace state remains fresh. {prior_summary}"[:1000],
            "work_underway": [],
            "completed_work": [],
            "blockers": [],
            "urgent_escalations": [],
            "decisions": [],
            "evidence_links": [{"ref": f"standup:{raw.get('id')}", "basis_created_at": created.isoformat()}] if raw.get("id") else [],
            "recommended_next_actions": [],
            "_conclusion_kind": "healthy_no_change",
        }
    return adapted_rows


def run_portfolio_coordination(
    *,
    service: PortfolioCycleService,
    portfolio_cycle_id: str,
    cycle_date: date,
    observed_at: datetime,
    expected_workspaces: list[str],
    readiness_id: str,
    standup_rows: list[Mapping[str, Any]],
    system_health: Mapping[str, Any],
    morning_brief_ref: str | None = None,
    owner_calls: list[Mapping[str, Any]] | None = None,
    recommended_next_actions: list[str] | None = None,
) -> dict[str, Any]:
    service.start_cycle(portfolio_cycle_id=portfolio_cycle_id, cycle_date=cycle_date, expected_workspaces=expected_workspaces, readiness_id=readiness_id, morning_brief_ref=morning_brief_ref)
    adapted = adapt_daily_workspace_standups(
        standup_rows,
        cycle_date=cycle_date,
        observed_at=observed_at,
        expected_workspaces=expected_workspaces,
    )
    for workspace, payload in adapted.items():
        normalized_payload = dict(payload)
        conclusion_kind = str(normalized_payload.pop("_conclusion_kind", "conclusion"))
        service.record_workspace_conclusion(
            portfolio_cycle_id=portfolio_cycle_id,
            workspace_key=workspace,
            conclusion_kind=conclusion_kind,
            provenance_kind="deterministic_policy",
            payload=normalized_payload,
            idempotency_key=f"daily-standup-adapter:{portfolio_cycle_id}:{workspace}",
        )
    return service.conclude_ops(
        portfolio_cycle_id=portfolio_cycle_id,
        system_health=system_health,
        owner_calls=list(owner_calls or []),
        recommended_next_actions=recommended_next_actions,
    )
