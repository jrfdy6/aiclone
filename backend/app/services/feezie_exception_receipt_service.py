from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any


SCHEMA_VERSION = "feezie_exception_receipts/v1"
RECEIPT_SCHEMA_VERSION = "feezie_exception_receipt/v1"
CANONICAL_WORKSPACE_KEY = "feezie-os"
MAX_RECEIPTS = 12

_SIGNAL_SECTION_NAMES = (
    "social_feed",
    "source_assets",
    "reaction_queue",
)
_SEVERITY_ORDER = {"red": 0, "yellow": 1, "info": 2}
_GENERATION_WORKSPACE_ALIASES = {
    "feezie-os",
    "linkedin-os",
    "linkedin-content-os",
}


def _clean_text(value: Any, *, limit: int = 240) -> str:
    cleaned = " ".join(str(value or "").replace("\xa0", " ").split()).strip()
    return cleaned[:limit]


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: Any) -> datetime | None:
    text = _clean_text(value, limit=80)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _string_list(value: Any, *, limit: int = 8, item_limit: int = 120) -> list[str]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, Mapping)):
        return []
    values: list[str] = []
    seen: set[str] = set()
    for item in value:
        cleaned = _clean_text(item, limit=item_limit)
        if not cleaned or cleaned.lower() in seen:
            continue
        seen.add(cleaned.lower())
        values.append(cleaned)
        if len(values) >= limit:
            break
    return values


def _safe_source_ids(value: Iterable[Any]) -> list[str]:
    safe: list[str] = []
    for item in _string_list(value, limit=8, item_limit=300):
        if "/" in item or "\\" in item or item.startswith("~"):
            safe.append(f"opaque-ref-{_stable_hash(item)[:12]}")
        else:
            safe.append(item[:160])
    return safe


def _reason_codes(value: Any) -> list[str]:
    codes: list[str] = []
    for item in _string_list(value, limit=6, item_limit=160):
        code = re.sub(r"[^a-z0-9]+", "_", item.lower()).strip("_")
        if code:
            codes.append(code[:100])
    return codes


def _receipt(
    *,
    code: str,
    title: str,
    observed_at: Any,
    source_ids: Iterable[Any],
    agenda_tags: Iterable[str],
    severity: str,
    actionable: bool,
    next_action: str,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    safe_source_ids = _safe_source_ids(source_ids)
    safe_tags = _string_list(agenda_tags, limit=8, item_limit=80)
    safe_evidence = dict(evidence or {})
    identity = {
        "code": code,
        "source_ids": safe_source_ids,
        "agenda_tags": safe_tags,
        "severity": severity,
        "actionable": actionable,
        "evidence": safe_evidence,
    }
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "receipt_id": f"feezie-exception-{_stable_hash(identity)[:16]}",
        "workspace_key": CANONICAL_WORKSPACE_KEY,
        "code": _clean_text(code, limit=120),
        "title": _clean_text(title, limit=220),
        "status": "open" if actionable else "informational",
        # The receipt is a current observation that old or incomplete evidence
        # still needs attention.  The underlying source timestamp stays stable
        # so an unchanged exception retains the same relevance fingerprint.
        "active_exception": True,
        "observed_at": _clean_text(observed_at, limit=80) or None,
        "source_ids": safe_source_ids,
        "agenda_tags": safe_tags,
        "severity": severity if severity in _SEVERITY_ORDER else "yellow",
        "actionable": actionable,
        "action_required": actionable,
        "decision_required": actionable,
        "next_action": _clean_text(next_action, limit=300),
        "evidence": safe_evidence,
        "data_policy": {
            "bounded": True,
            "raw_draft_content_included": False,
            "private_notes_included": False,
            "absolute_paths_included": False,
        },
    }


def _signal_freshness_receipt(snapshot: Mapping[str, Any]) -> dict[str, Any] | None:
    status = snapshot.get("snapshot_status") if isinstance(snapshot.get("snapshot_status"), Mapping) else {}
    sections = status.get("sections") if isinstance(status.get("sections"), Mapping) else {}
    nonfresh: dict[str, str] = {}
    timestamps: list[datetime] = []
    for name in _SIGNAL_SECTION_NAMES:
        section = sections.get(name) if isinstance(sections.get(name), Mapping) else {}
        state = _clean_text(section.get("state"), limit=40).lower() or "missing"
        if state != "fresh":
            nonfresh[name] = state
            generated_at = _parse_timestamp(section.get("generated_at"))
            if generated_at is not None:
                timestamps.append(generated_at)
    if not nonfresh:
        return None
    red = any(state in {"corrupt", "degraded"} for state in nonfresh.values())
    observed_at = max(timestamps) if timestamps else _parse_timestamp(status.get("checked_at"))
    return _receipt(
        code="feezie_signal_freshness_exception",
        title="FEEZIE signal inputs are not current",
        observed_at=_iso(observed_at) if observed_at else status.get("checked_at"),
        source_ids=[f"workspace-snapshot:{name}" for name in sorted(nonfresh)],
        agenda_tags=["pipeline_health"],
        severity="red" if red else "yellow",
        actionable=True,
        next_action="Refresh or repair the named signal inputs before treating trend-sensitive recommendations as current.",
        evidence={"section_states": nonfresh},
    )


def _performance_receipts(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    summary = (
        snapshot.get("publication_performance_summary")
        if isinstance(snapshot.get("publication_performance_summary"), Mapping)
        else {}
    )
    if not summary:
        return []
    generated_at = summary.get("generated_at")
    receipts: list[dict[str, Any]] = []
    gaps = summary.get("actionable_gaps") if isinstance(summary.get("actionable_gaps"), list) else []
    for gap in gaps[:8]:
        if not isinstance(gap, Mapping):
            continue
        code = _clean_text(gap.get("code"), limit=120)
        if not code or code == "feezie_portfolio_mix_sourcing_warning":
            continue
        actionable = gap.get("actionable") is True
        tags = _string_list(gap.get("agenda_tags"), limit=6, item_limit=80)
        if not actionable and "informational_only" not in tags:
            tags.append("informational_only")
        receipts.append(
            _receipt(
                code=code,
                title=_clean_text(gap.get("next_action"), limit=220) or "FEEZIE performance follow-up is due",
                observed_at=generated_at,
                source_ids=[f"publication-performance:{code}"],
                agenda_tags=tags or ["feedback_learning", "execution_or_lifecycle"],
                severity=_clean_text(gap.get("severity"), limit=20).lower() or "yellow",
                actionable=actionable,
                next_action=_clean_text(gap.get("next_action"), limit=300),
                evidence={"gap_code": code},
            )
        )

    due_counts: Counter[str] = Counter()
    publications = summary.get("recent_publications") if isinstance(summary.get("recent_publications"), list) else []
    for publication in publications[:10]:
        if not isinstance(publication, Mapping):
            continue
        for due_action in _string_list(publication.get("due_actions"), limit=6, item_limit=80):
            due_counts[due_action] += 1
    if due_counts.get("record_owner_assessment"):
        count = due_counts["record_owner_assessment"]
        receipts.append(
            _receipt(
                code="feezie_owner_assessment_due",
                title=f"Owner assessment is due for {count} confirmed publication(s)",
                observed_at=generated_at,
                source_ids=["publication-performance:owner-assessment-due"],
                agenda_tags=["feedback_learning", "execution_or_lifecycle"],
                severity="yellow",
                actionable=True,
                next_action="Record the owner quality and outcome assessment before drawing a new editorial lesson.",
                evidence={"due_count": count},
            )
        )

    topic_mix = summary.get("rolling_topic_mix") if isinstance(summary.get("rolling_topic_mix"), Mapping) else {}
    intent_mix = summary.get("rolling_intent_mix") if isinstance(summary.get("rolling_intent_mix"), Mapping) else {}
    topic_deficits = {
        _clean_text(key, limit=80): int(value or 0)
        for key, value in (topic_mix.get("deficits") or {}).items()
        if _clean_text(key, limit=80) and int(value or 0) > 0
    } if isinstance(topic_mix.get("deficits"), Mapping) else {}
    intent_deficits = {
        _clean_text(key, limit=80): int(value or 0)
        for key, value in (intent_mix.get("deficits") or {}).items()
        if _clean_text(key, limit=80) and int(value or 0) > 0
    } if isinstance(intent_mix.get("deficits"), Mapping) else {}
    if topic_deficits or intent_deficits:
        receipts.append(
            _receipt(
                code="feezie_portfolio_mix_drift",
                title="The measured FEEZIE portfolio mix is short of one or more targets",
                observed_at=generated_at,
                source_ids=["publication-performance:portfolio-mix"],
                agenda_tags=["informational_only"],
                severity="info",
                actionable=False,
                next_action="Use the deficits only to sequence qualified evidence; never create filler or bypass admission gates.",
                evidence={
                    "topic_deficits": topic_deficits,
                    "intent_deficits": intent_deficits,
                    "topic_sample_size": int(topic_mix.get("sample_size") or 0),
                    "intent_sample_size": int(intent_mix.get("sample_size") or 0),
                },
            )
        )
    return receipts


def _generation_receipts(generation_jobs: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for job in list(generation_jobs)[:8]:
        workspace_slug = _clean_text(job.get("workspace_slug"), limit=80).lower()
        if workspace_slug and workspace_slug not in _GENERATION_WORKSPACE_ALIASES:
            continue
        job_id = _clean_text(job.get("id"), limit=160)
        status = _clean_text(job.get("status"), limit=40).lower()
        result = job.get("result_payload") if isinstance(job.get("result_payload"), Mapping) else {}
        diagnostics = result.get("diagnostics") if isinstance(result.get("diagnostics"), Mapping) else {}
        readiness = (
            diagnostics.get("editorial_readiness")
            if isinstance(diagnostics.get("editorial_readiness"), Mapping)
            else {}
        )
        classification = (
            diagnostics.get("candidate_classification")
            if isinstance(diagnostics.get("candidate_classification"), Mapping)
            else {}
        )
        if not classification:
            context = job.get("context_packet") if isinstance(job.get("context_packet"), Mapping) else {}
            classification = (
                context.get("candidate_classification")
                if isinstance(context.get("candidate_classification"), Mapping)
                else {}
            )
        updated_at = job.get("updated_at") or job.get("completed_at") or job.get("created_at")
        critic_status = _clean_text(readiness.get("critic_status"), limit=80).lower()
        readiness_status = _clean_text(readiness.get("status"), limit=80).lower()
        critic_failed = status == "failed" or critic_status in {
            "failed",
            "error",
            "critic_unavailable",
            "critic_not_run",
            "unavailable",
        } or readiness_status in {"critic_unavailable", "critic_not_run"}
        if critic_failed:
            blocking_reasons = _reason_codes(readiness.get("blocking_reasons"))
            receipts.append(
                _receipt(
                    code="feezie_critic_failure",
                    title="A FEEZIE draft lacks a completed independent critic receipt",
                    observed_at=updated_at,
                    source_ids=[job_id or "content-generation-job"],
                    agenda_tags=["content_quality", "pipeline_health"],
                    severity="yellow",
                    actionable=True,
                    next_action="Repair or rerun the independent critic before any option advances to owner review.",
                    evidence={
                        "job_status": status or "unknown",
                        "critic_status": critic_status or readiness_status or "missing",
                        "blocking_reason_codes": blocking_reasons,
                    },
                )
            )

        employer_safety = _clean_text(classification.get("employer_safety"), limit=80).lower()
        if employer_safety == "blocked":
            receipts.append(
                _receipt(
                    code="feezie_employer_safety_blocked",
                    title="A FEEZIE candidate is blocked by the employer-safety boundary",
                    observed_at=updated_at,
                    source_ids=[job_id or "content-generation-job"],
                    agenda_tags=["content_quality", "owner_intent_or_approval", "privacy_or_public_claim"],
                    severity="red",
                    actionable=True,
                    next_action="Keep the candidate out of owner review until the exact claim, proof treatment, and employer boundary are resolved.",
                    evidence={
                        "employer_safety": employer_safety,
                        "proof_posture": _clean_text(classification.get("proof_posture"), limit=80),
                    },
                )
            )
        elif employer_safety == "owner_review_required":
            receipts.append(
                _receipt(
                    code="feezie_employer_safety_owner_review",
                    title="Employer-sensitive copy remains behind the normal owner-review gate",
                    observed_at=updated_at,
                    source_ids=[job_id or "content-generation-job"],
                    agenda_tags=["informational_only"],
                    severity="info",
                    actionable=False,
                    next_action="Use the existing item-level owner-review gate; do not convene a standup unless a boundary conflict appears.",
                    evidence={"employer_safety": employer_safety},
                )
            )
    return receipts


def build_feezie_exception_receipts(
    *,
    workspace_snapshot: Mapping[str, Any] | None = None,
    generation_jobs: Iterable[Mapping[str, Any]] = (),
    now: datetime | None = None,
    limit: int = MAX_RECEIPTS,
) -> dict[str, Any]:
    """Build content-minimized exceptions for Dream Cycle and standup routing.

    The result deliberately carries counts, state codes, opaque job IDs, and
    next actions only.  It never projects draft copy, prompts, private notes,
    comments, DMs, or machine-local paths.
    """

    evaluated_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    snapshot = workspace_snapshot if isinstance(workspace_snapshot, Mapping) else {}
    receipts: list[dict[str, Any]] = []
    signal_receipt = _signal_freshness_receipt(snapshot)
    if signal_receipt is not None:
        receipts.append(signal_receipt)
    receipts.extend(_performance_receipts(snapshot))
    receipts.extend(_generation_receipts(generation_jobs))

    deduped: dict[str, dict[str, Any]] = {}
    for receipt in receipts:
        deduped.setdefault(str(receipt.get("receipt_id") or ""), receipt)
    ordered = sorted(
        deduped.values(),
        key=lambda item: (
            0 if item.get("actionable") is True else 1,
            _SEVERITY_ORDER.get(str(item.get("severity") or "info"), 9),
            str(item.get("code") or ""),
            str(item.get("receipt_id") or ""),
        ),
    )[: max(1, min(int(limit or MAX_RECEIPTS), MAX_RECEIPTS))]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso(evaluated_at),
        "workspace_key": CANONICAL_WORKSPACE_KEY,
        "counts": {
            "total": len(ordered),
            "actionable": sum(1 for item in ordered if item.get("actionable") is True),
            "informational": sum(1 for item in ordered if item.get("actionable") is not True),
            "red": sum(1 for item in ordered if item.get("severity") == "red"),
            "yellow": sum(1 for item in ordered if item.get("severity") == "yellow"),
        },
        "receipts": ordered,
        "data_policy": {
            "bounded_receipt_count": MAX_RECEIPTS,
            "raw_draft_content_included": False,
            "private_notes_included": False,
            "absolute_paths_included": False,
        },
    }


def merge_feezie_exception_receipt_payloads(
    payloads: Iterable[Mapping[str, Any]],
    *,
    now: datetime | None = None,
    limit: int = MAX_RECEIPTS,
) -> dict[str, Any]:
    """Merge already-sanitized local and Railway receipt projections."""

    evaluated_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    deduped: dict[str, dict[str, Any]] = {}
    for payload in payloads:
        if not isinstance(payload, Mapping):
            continue
        for item in payload.get("receipts") or []:
            if not isinstance(item, Mapping):
                continue
            receipt_id = _clean_text(item.get("receipt_id"), limit=160)
            if not receipt_id or item.get("schema_version") != RECEIPT_SCHEMA_VERSION:
                continue
            # Rebuild the public shape instead of trusting arbitrary additional
            # fields from either transport boundary.
            projected = {
                key: item.get(key)
                for key in (
                    "schema_version",
                    "receipt_id",
                    "workspace_key",
                    "code",
                    "title",
                    "status",
                    "active_exception",
                    "observed_at",
                    "source_ids",
                    "agenda_tags",
                    "severity",
                    "actionable",
                    "action_required",
                    "decision_required",
                    "next_action",
                    "evidence",
                    "data_policy",
                )
            }
            deduped.setdefault(receipt_id, projected)
    ordered = sorted(
        deduped.values(),
        key=lambda item: (
            0 if item.get("actionable") is True else 1,
            _SEVERITY_ORDER.get(str(item.get("severity") or "info"), 9),
            str(item.get("code") or ""),
            str(item.get("receipt_id") or ""),
        ),
    )[: max(1, min(int(limit or MAX_RECEIPTS), MAX_RECEIPTS))]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso(evaluated_at),
        "workspace_key": CANONICAL_WORKSPACE_KEY,
        "counts": {
            "total": len(ordered),
            "actionable": sum(1 for item in ordered if item.get("actionable") is True),
            "informational": sum(1 for item in ordered if item.get("actionable") is not True),
            "red": sum(1 for item in ordered if item.get("severity") == "red"),
            "yellow": sum(1 for item in ordered if item.get("severity") == "yellow"),
        },
        "receipts": ordered,
        "data_policy": {
            "bounded_receipt_count": MAX_RECEIPTS,
            "raw_draft_content_included": False,
            "private_notes_included": False,
            "absolute_paths_included": False,
        },
    }


def build_feezie_collection_failure_receipts(
    *,
    component: str,
    error_type: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Represent a missing exception source without leaking transport details."""

    evaluated_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    safe_component = re.sub(r"[^a-z0-9]+", "_", _clean_text(component).lower()).strip("_")[:80]
    error_match = re.search(r"\b([A-Za-z][A-Za-z0-9_]*(?:Error|Exception))\b", _clean_text(error_type))
    safe_error = error_match.group(1)[:80] if error_match else "unavailable"
    receipt = _receipt(
        code=f"feezie_{safe_component or 'exception'}_collection_unavailable",
        title="A FEEZIE exception source is unavailable",
        # This is the time the collection failure itself was observed, not a
        # fabricated source-publication time.  The receipt identity remains
        # stable because `_receipt` deliberately excludes observation time from
        # its identity hash; exact-cycle replay still receives the same value.
        observed_at=_iso(evaluated_at),
        source_ids=[f"exception-source:{safe_component or 'unknown'}"],
        agenda_tags=["pipeline_health"],
        severity="yellow",
        actionable=True,
        next_action="Restore the bounded exception-receipt source before declaring the feedback loop healthy.",
        evidence={
            "component": safe_component or "unknown",
            "error_type": safe_error or "unavailable",
        },
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _iso(evaluated_at),
        "workspace_key": CANONICAL_WORKSPACE_KEY,
        "counts": {"total": 1, "actionable": 1, "informational": 0, "red": 0, "yellow": 1},
        "receipts": [receipt],
        "data_policy": {
            "bounded_receipt_count": MAX_RECEIPTS,
            "raw_draft_content_included": False,
            "private_notes_included": False,
            "absolute_paths_included": False,
        },
    }
