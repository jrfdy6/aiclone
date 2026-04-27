from __future__ import annotations
import json
import re
import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from app.models import (
    EmailMessage,
    EmailSyncResponse,
    EmailThread,
    EmailThreadDraftRequest,
    EmailThreadDraftResponse,
    EmailThreadEscalateRequest,
    EmailThreadEscalateResponse,
    EmailThreadListResponse,
    EmailThreadRouteRequest,
    EmailThreadSaveDraftResponse,
    PMCardCreate,
)
from app.services.email_drafting_bridge_service import (
    build_local_codex_email_context_packet,
    build_local_codex_email_request_payload,
    build_content_generation_request_payload,
    build_email_drafting_packet,
    codex_job_eligibility,
    content_generation_eligibility,
    normalize_generated_email_body,
    resolve_draft_engine,
    resolve_draft_mode,
    resolve_source_mode,
)
from app.services.gmail_inbox_service import fetch_gmail_threads, gmail_account_email, gmail_connection_status, save_gmail_draft
from app.services.local_codex_generation_service import cancel_codex_job, create_codex_job, get_codex_job
from app.services.email_thread_state_store import load_persisted_threads, replace_persisted_threads
from app.services.trigger_identity_service import build_content_job_idempotency_key
from app.services import pm_card_service

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
EMAIL_THREADS_CACHE = DATA_DIR / "email_threads.json"

WORKSPACE_ALIAS_MAP: dict[str, tuple[str, Optional[str]]] = {
    "agc": ("agc", None),
    "agc-universities": ("agc", "consulting_opportunity"),
    "agc-vendors": ("agc", "supplier_partner"),
    "fusion": ("fusion-os", "primary"),
    "feezie": ("feezie-os", "primary"),
    "easyoutfit": ("easyoutfitapp", "primary"),
    "swag": ("ai-swag-store", "primary"),
    "ops": ("shared_ops", "ops_admin"),
}

WORKSPACE_LABEL_MAP: dict[str, tuple[str, Optional[str]]] = {
    "workspace/agc": ("agc", None),
    "workspace/fusion-os": ("fusion-os", "primary"),
    "workspace/feezie-os": ("feezie-os", "primary"),
    "workspace/shared-ops": ("shared_ops", "ops_admin"),
    "workspace/easyoutfitapp": ("easyoutfitapp", "primary"),
    "workspace/ai-swag-store": ("ai-swag-store", "primary"),
}

AGC_REQUIRED_LABEL = "workspace/agc"

WORKSPACE_KEYWORDS: dict[str, list[str]] = {
    "agc": [
        "procurement",
        "purchasing",
        "vendor",
        "supplier",
        "quote",
        "pricing",
        "rfq",
        "rfp",
        "proposal",
        "capability statement",
        "workflow modernization",
        "operational clarity",
        "process optimization",
        "university",
        "higher education",
        "scientific",
        "medical",
        "reseller",
        "teaming",
        "subcontracting",
        "prime",
    ],
    "fusion-os": [
        "student",
        "family",
        "admissions",
        "enrollment",
        "school placement",
        "therapeutic",
        "referral",
        "school fit",
    ],
    "feezie-os": [
        "linkedin",
        "podcast",
        "creator",
        "content collaboration",
        "speaking",
        "interview",
        "brand partnership",
        "audience",
    ],
    "easyoutfitapp": [
        "beta",
        "wardrobe",
        "outfit",
        "app feedback",
        "subscription",
        "mobile app",
        "bug report",
    ],
    "ai-swag-store": [
        "merch",
        "swag",
        "apparel",
        "bulk order",
        "print",
        "fulfillment",
    ],
    "shared_ops": [
        "invoice",
        "billing",
        "hosting",
        "domain",
        "operations",
        "infrastructure",
        "admin",
        "tooling",
    ],
}

AGC_LANE_KEYWORDS: dict[str, list[str]] = {
    "consulting_opportunity": [
        "operational clarity",
        "workflow modernization",
        "process optimization",
        "discovery",
        "implementation support",
        "audit",
        "assessment",
        "program management",
        "project management",
        "institutional operations",
        "higher education operations",
    ],
    "product_sourcing": [
        "product request",
        "catalog",
        "quote",
        "pricing",
        "laboratory",
        "scientific",
        "medical supplies",
        "medical equipment",
        "packaging",
        "availability",
        "lead time",
        "purchase order",
    ],
    "supplier_partner": [
        "manufacturer",
        "distributor",
        "reseller",
        "dealer",
        "supplier application",
        "teaming",
        "subcontracting",
        "prime partnership",
        "channel partner",
    ],
    "registrations_compliance": [
        "vendor portal",
        "onboarding",
        "w-9",
        "insurance",
        "uei",
        "cage",
        "sam",
        "capability statement",
        "certifications",
        "registration",
        "tax form",
        "coi",
    ],
    "finance_admin": [
        "invoice",
        "remittance",
        "payment",
        "calendar",
        "scheduling",
        "administrative",
    ],
}

AGC_WATCHLIST_DOMAINS: dict[str, tuple[str, Optional[str]]] = {
    "american.edu": ("agc", "consulting_opportunity"),
    "gwu.edu": ("agc", "consulting_opportunity"),
    "georgetown.edu": ("agc", "consulting_opportunity"),
    "gallaudet.edu": ("agc", "consulting_opportunity"),
    "udc.edu": ("agc", "consulting_opportunity"),
    "montgomerycollege.edu": ("agc", "consulting_opportunity"),
    "umd.edu": ("agc", "consulting_opportunity"),
    "umbc.edu": ("agc", "consulting_opportunity"),
    "pgcc.edu": ("agc", "consulting_opportunity"),
    "howard.edu": ("agc", "consulting_opportunity"),
    "vwr.com": ("agc", "supplier_partner"),
    "avantorsciences.com": ("agc", "supplier_partner"),
    "quantabio.com": ("agc", "supplier_partner"),
    "fishersci.com": ("agc", "supplier_partner"),
    "thermofisher.com": ("agc", "supplier_partner"),
    "uline.com": ("agc", "supplier_partner"),
    "gdit.com": ("agc", "consulting_opportunity"),
    "saic.com": ("agc", "consulting_opportunity"),
    "leidos.com": ("agc", "consulting_opportunity"),
    "bah.com": ("agc", "consulting_opportunity"),
    "accenture.com": ("agc", "consulting_opportunity"),
}

HIGH_VALUE_TERMS = (
    "rfp",
    "rfq",
    "proposal",
    "quote",
    "pricing",
    "contract",
    "statement of work",
    "scope of work",
)
HIGH_RISK_TERMS = (
    "pricing",
    "terms",
    "insurance",
    "w-9",
    "uei",
    "cage",
    "sam",
    "security",
    "compliance",
    "legal",
    "contract",
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _json_default(value: object):
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _thread_to_payload(thread: EmailThread) -> dict:
    return json.loads(thread.model_dump_json())


def _thread_list_item(thread: EmailThread) -> EmailThread:
    return thread.model_copy(update={"messages": [], "draft_body": None})


def _parse_optional_datetime(value: object) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    normalized = str(value or "").strip()
    if not normalized:
        return None
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _hydrate_codex_job_result(thread: EmailThread) -> tuple[EmailThread, bool]:
    if thread.draft_engine != "codex_job" or not thread.draft_job_id:
        return thread, False
    job = get_codex_job(thread.draft_job_id)
    if not job:
        return thread, False

    status = str(job.get("status") or "").strip().lower()
    if status in {"pending", "claimed", "running"}:
        audit = dict(thread.draft_audit or {})
        diagnostics = dict(audit.get("generation_diagnostics") or {})
        diagnostics["job_status"] = status
        diagnostics["job_id"] = str(job.get("id") or thread.draft_job_id)
        audit["generation_diagnostics"] = diagnostics
        if audit.get("selected_path") != "codex_job_pending":
            audit["selected_path"] = "codex_job_pending"
            updated = thread.model_copy(deep=True)
            updated.draft_audit = audit
            return updated, True
        return thread, False

    updated = thread.model_copy(deep=True)
    audit = dict(updated.draft_audit or {})
    diagnostics = dict(audit.get("generation_diagnostics") or {})
    diagnostics["job_status"] = status
    diagnostics["job_id"] = str(job.get("id") or updated.draft_job_id)

    if status == "completed":
        result_payload = job.get("result_payload") if isinstance(job.get("result_payload"), dict) else {}
        diagnostics.update(dict(result_payload.get("diagnostics") or {}))
        options = list(result_payload.get("options") or [])
        candidate = next((option for option in options if isinstance(option, str) and option.strip()), "")
        normalized_candidate = normalize_generated_email_body(
            candidate,
            signature_block=_signature_for_workspace(updated.workspace_key),
        )
        if normalized_candidate:
            updated.draft_subject = updated.draft_subject or f"Re: {updated.subject}"
            updated.draft_body = normalized_candidate
            updated.draft_generated_at = _parse_optional_datetime(job.get("completed_at")) or _now_utc()
            updated.draft_job_id = None
            updated.draft_confidence = updated.confidence_score
            audit["selected_path"] = "codex_job"
            audit["generation_reason"] = "eligible"
            audit["generation_request_payload"] = job.get("request_payload") if isinstance(job.get("request_payload"), dict) else audit.get("generation_request_payload")
            audit["generation_diagnostics"] = diagnostics
            updated.draft_audit = audit
            updated.status = "drafted" if not updated.needs_human else "human_review"
            return updated, True

    if status in {"failed", "canceled"}:
        diagnostics["error"] = str(job.get("error_message") or "")[:500]
        audit["selected_path"] = "codex_job_failed"
        audit["generation_reason"] = f"codex_job_{status}"
        audit["generation_diagnostics"] = diagnostics
        updated.draft_body = None
        updated.draft_generated_at = None
        updated.draft_job_id = None
        updated.draft_audit = audit
        return updated, True

    return thread, False


def _refresh_codex_job_threads(threads: list[EmailThread]) -> tuple[list[EmailThread], bool]:
    refreshed: list[EmailThread] = []
    changed = False
    for thread in threads:
        hydrated, thread_changed = _hydrate_codex_job_result(thread)
        refreshed.append(hydrated)
        changed = changed or thread_changed
    return refreshed, changed


def _read_threads() -> list[EmailThread]:
    persisted = load_persisted_threads()
    if persisted is not None:
        return persisted
    if not EMAIL_THREADS_CACHE.exists():
        return []
    try:
        payload = json.loads(EMAIL_THREADS_CACHE.read_text())
    except json.JSONDecodeError:
        return []
    threads: list[EmailThread] = []
    for item in payload:
        try:
            threads.append(EmailThread(**item))
        except Exception:
            continue
    return threads


def _write_threads(threads: list[EmailThread]) -> None:
    EMAIL_THREADS_CACHE.write_text(json.dumps([_thread_to_payload(thread) for thread in threads], indent=2, default=_json_default))
    replace_persisted_threads(threads)


def _extract_alias_hint(addresses: list[str]) -> Optional[str]:
    for address in addresses:
        lowered = address.strip().lower()
        if "@" not in lowered:
            continue
        local_part, domain = lowered.split("@", 1)
        if domain != "gmail.com" or "+" not in local_part:
            continue
        return local_part.split("+", 1)[1]
    return None


def _workspace_label_hint(labels: list[str]) -> tuple[Optional[str], Optional[str], list[str]]:
    reasons: list[str] = []
    for label in labels:
        mapped = WORKSPACE_LABEL_MAP.get(label)
        if mapped:
            reasons.append(f"label:{label}")
            return mapped[0], mapped[1], reasons
    return None, None, reasons


def _agc_label_present(thread: EmailThread) -> bool:
    return AGC_REQUIRED_LABEL in {label.strip().lower() for label in thread.provider_labels}


def _sender_domain(address: str) -> str:
    lowered = address.strip().lower()
    return lowered.split("@", 1)[1] if "@" in lowered else ""


def _workspace_bucket(thread: EmailThread) -> str:
    if thread.workspace_key == "shared_ops" and thread.lane == "manual_review":
        return "manual_review"
    return thread.workspace_key


def _latest_message(thread: EmailThread) -> Optional[EmailMessage]:
    if not thread.messages:
        return None
    return max(thread.messages, key=lambda item: item.received_at)


def _compact_text(thread: EmailThread) -> str:
    latest = _latest_message(thread)
    body = latest.body_text if latest else ""
    parts = [thread.subject, body, thread.organization or "", " ".join(thread.to_addresses)]
    return " ".join(parts).lower()


def _summarize_text(thread: EmailThread) -> tuple[str, str]:
    latest = _latest_message(thread)
    body = (latest.body_text if latest else "").strip()
    clean = re.sub(r"\s+", " ", body).strip()
    excerpt = clean[:220] + ("…" if len(clean) > 220 else "") if clean else thread.subject
    summary = excerpt if len(excerpt) <= 140 else excerpt[:140].rstrip() + "…"
    return summary, excerpt


def _decode_gmail_data(data: Optional[str]) -> str:
    if not data:
        return ""
    try:
        padding = "=" * (-len(data) % 4)
        raw = base64.urlsafe_b64decode(f"{data}{padding}")
        return raw.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _strip_html(value: str) -> str:
    text = re.sub(r"<style.*?>.*?</style>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<script.*?>.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _header_map(payload: dict) -> dict[str, str]:
    headers = payload.get("headers") or []
    result: dict[str, str] = {}
    for header in headers:
        name = str(header.get("name") or "").strip().lower()
        if not name:
            continue
        result[name] = str(header.get("value") or "")
    return result


def _extract_body_text(payload: dict) -> str:
    mime_type = str(payload.get("mimeType") or "")
    body = payload.get("body") or {}
    body_data = _decode_gmail_data(body.get("data"))
    if mime_type == "text/plain" and body_data:
        return body_data
    if mime_type == "text/html" and body_data:
        return _strip_html(body_data)

    for part in payload.get("parts") or []:
        text = _extract_body_text(part)
        if text:
            return text

    if body_data:
        return _strip_html(body_data)
    return ""


def _parse_email_list(header_value: str) -> list[str]:
    if not header_value:
        return []
    items = []
    for part in header_value.split(","):
        lowered = part.strip()
        if not lowered:
            continue
        match = re.search(r"([\w.+-]+@[\w.-]+\.\w+)", lowered)
        items.append(match.group(1).lower() if match else lowered.lower())
    return items


def _extract_address(header_value: str) -> tuple[str, Optional[str]]:
    if not header_value:
        return "", None
    match = re.search(r"(.+?)\s*<([\w.+-]+@[\w.-]+\.\w+)>", header_value)
    if match:
        name = match.group(1).strip().strip('"') or None
        return match.group(2).strip().lower(), name
    address_match = re.search(r"([\w.+-]+@[\w.-]+\.\w+)", header_value)
    if address_match:
        return address_match.group(1).strip().lower(), None
    return header_value.strip().lower(), None


def _derive_organization(address: str) -> Optional[str]:
    domain = _sender_domain(address)
    if not domain:
        return None
    parts = domain.split(".")
    if len(parts) < 2:
        return domain
    return parts[-2].replace("-", " ").replace("_", " ").title()


def _gmail_direction(from_address: str, account_email: str) -> str:
    lowered = from_address.lower()
    account = account_email.lower()
    return "outbound" if lowered == account or lowered.startswith(f"{account.split('@', 1)[0]}+") else "inbound"


def _thread_from_gmail_payload(payload: dict, account_email: str) -> EmailThread:
    messages = payload.get("messages") or []
    thread_messages: list[EmailMessage] = []
    latest_subject = payload.get("snippet") or "Gmail thread"
    latest_from = ""
    latest_name: Optional[str] = None
    latest_to: list[str] = []
    latest_at = _now_utc()

    for message in messages:
        message_payload = message.get("payload") or {}
        headers = _header_map(message_payload)
        from_address, from_name = _extract_address(headers.get("from", ""))
        to_addresses = _parse_email_list(headers.get("to", ""))
        cc_addresses = _parse_email_list(headers.get("cc", ""))
        subject = headers.get("subject") or latest_subject
        received_at = datetime.fromtimestamp(int(message.get("internalDate", "0")) / 1000, tz=timezone.utc) if message.get("internalDate") else _now_utc()
        body_text = _extract_body_text(message_payload) or str(message.get("snippet") or "")
        thread_messages.append(
            EmailMessage(
                id=str(message.get("id") or uuid4()),
                direction=_gmail_direction(from_address, account_email),
                from_address=from_address,
                from_name=from_name,
                to_addresses=to_addresses,
                cc_addresses=cc_addresses,
                subject=subject,
                body_text=body_text,
                internet_message_id=headers.get("message-id") or None,
                references_header=headers.get("references") or None,
                in_reply_to_header=headers.get("in-reply-to") or None,
                received_at=received_at,
            )
        )
        if received_at >= latest_at:
            latest_subject = subject
            latest_from = from_address
            latest_name = from_name
            latest_to = to_addresses
            latest_at = received_at

    if not thread_messages:
        raise ValueError("Gmail thread payload contained no messages")

    latest_counterparty = next(
        (item for item in reversed(sorted(thread_messages, key=lambda entry: entry.received_at)) if item.from_address.lower() != account_email.lower()),
        thread_messages[-1],
    )

    return EmailThread(
        id=str(payload.get("id") or uuid4()),
        provider="gmail",
        provider_thread_id=str(payload.get("id") or ""),
        provider_labels=[
            str(label).strip().lower()
            for label in (payload.get("_openclaw_label_names") or [])
            if str(label).strip()
        ],
        subject=latest_subject,
        from_address=latest_counterparty.from_address or latest_from,
        from_name=latest_counterparty.from_name or latest_name,
        organization=_derive_organization(latest_counterparty.from_address or latest_from),
        to_addresses=latest_to or latest_counterparty.to_addresses,
        messages=thread_messages,
        last_message_at=max(item.received_at for item in thread_messages),
        created_at=min(item.received_at for item in thread_messages),
        updated_at=_now_utc(),
    )


def _classify_workspace(thread: EmailThread) -> tuple[str, Optional[str], float, list[str]]:
    label_workspace, label_lane_hint, label_reasons = _workspace_label_hint(thread.provider_labels)
    if label_workspace:
        alias_hint = _extract_alias_hint(thread.to_addresses)
        if label_workspace == "agc" and alias_hint and alias_hint in WORKSPACE_ALIAS_MAP:
            _, alias_lane_hint = WORKSPACE_ALIAS_MAP[alias_hint]
            return label_workspace, alias_lane_hint or label_lane_hint, 0.99, label_reasons
        return label_workspace, label_lane_hint, 0.99, label_reasons

    alias_hint = _extract_alias_hint(thread.to_addresses)
    reasons: list[str] = []
    if alias_hint and alias_hint in WORKSPACE_ALIAS_MAP:
        workspace_key, lane_hint = WORKSPACE_ALIAS_MAP[alias_hint]
        if workspace_key == "agc" and not _agc_label_present(thread):
            reasons.append(f"label_required:{AGC_REQUIRED_LABEL}")
            reasons.append(f"alias_blocked:{alias_hint}")
            return "shared_ops", "manual_review", 0.52, reasons
        reasons.append(f"alias:{alias_hint}")
        return workspace_key, lane_hint, 0.98, reasons

    sender_domain = _sender_domain(thread.from_address)
    if sender_domain in AGC_WATCHLIST_DOMAINS:
        workspace_key, lane_hint = AGC_WATCHLIST_DOMAINS[sender_domain]
        if workspace_key == "agc" and not _agc_label_present(thread):
            reasons.append(f"label_required:{AGC_REQUIRED_LABEL}")
            reasons.append(f"domain_blocked:{sender_domain}")
            return "shared_ops", "manual_review", 0.5, reasons
        reasons.append(f"domain:{sender_domain}")
        return workspace_key, lane_hint, 0.9, reasons

    text = _compact_text(thread)
    scores = {workspace: 0.0 for workspace in WORKSPACE_KEYWORDS}
    for workspace, keywords in WORKSPACE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                scores[workspace] += 1.0

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_workspace, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    if top_score <= 0:
        reasons.append("no_strong_signal")
        return "shared_ops", "manual_review", 0.35, reasons
    if top_workspace == "agc" and not _agc_label_present(thread):
        reasons.append(f"label_required:{AGC_REQUIRED_LABEL}")
        reasons.append("keywords_blocked:agc")
        return "shared_ops", "manual_review", 0.48, reasons
    if top_score - second_score < 1.0:
        reasons.append(f"ambiguous:{top_workspace}")
        return "shared_ops", "manual_review", 0.55, reasons

    reasons.append(f"keywords:{top_workspace}:{int(top_score)}")
    confidence = min(0.88, 0.58 + (top_score * 0.08))
    return top_workspace, None, confidence, reasons


def _classify_agc_lane(text: str, lane_hint: Optional[str]) -> tuple[str, list[str], float]:
    if lane_hint in AGC_LANE_KEYWORDS:
        return lane_hint, [f"lane_hint:{lane_hint}"], 0.95

    scores = {lane: 0.0 for lane in AGC_LANE_KEYWORDS}
    for lane, keywords in AGC_LANE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                scores[lane] += 1.0

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_lane, top_score = ranked[0]
    if top_score <= 0:
        return "consulting_opportunity", ["lane_default:consulting_opportunity"], 0.55
    return top_lane, [f"lane_keywords:{top_lane}:{int(top_score)}"], min(0.92, 0.6 + (top_score * 0.08))


def _classify_thread(thread: EmailThread) -> EmailThread:
    updated = thread.model_copy(deep=True)
    updated.alias_hint = _extract_alias_hint(updated.to_addresses)

    if updated.manual_workspace_key:
        updated.workspace_key = updated.manual_workspace_key
        if updated.manual_workspace_key == "agc" and not updated.manual_lane:
            inferred_lane, lane_reasons, _ = _classify_agc_lane(_compact_text(updated), None)
            updated.lane = inferred_lane
            updated.routing_reasons = ["manual_override"] + lane_reasons + ([updated.manual_notes] if updated.manual_notes else [])
        else:
            updated.lane = updated.manual_lane or ("manual_review" if updated.manual_workspace_key == "shared_ops" else "primary")
            updated.routing_reasons = ["manual_override"] + ([updated.manual_notes] if updated.manual_notes else [])
        updated.last_route_source = "manual"
        updated.confidence_score = max(updated.confidence_score, 0.99)
    else:
        workspace_key, lane_hint, confidence, reasons = _classify_workspace(updated)
        updated.workspace_key = workspace_key
        updated.last_route_source = "auto"
        updated.routing_reasons = reasons
        updated.confidence_score = confidence
        if workspace_key == "agc":
            lane, lane_reasons, lane_confidence = _classify_agc_lane(_compact_text(updated), lane_hint)
            updated.lane = lane
            updated.routing_reasons.extend(lane_reasons)
            updated.confidence_score = max(confidence, lane_confidence)
        else:
            updated.lane = lane_hint or ("manual_review" if workspace_key == "shared_ops" else "primary")

    text = _compact_text(updated)
    updated.high_value = any(term in text for term in HIGH_VALUE_TERMS)
    updated.high_risk = any(term in text for term in HIGH_RISK_TERMS)
    updated.needs_human = updated.high_value or updated.high_risk or updated.confidence_score < 0.7 or updated.lane == "manual_review"
    updated.sla_at_risk = "invoice" in text or "overdue" in text or "past due" in text
    updated.status = "human_review" if updated.needs_human else "routed"
    updated.summary, updated.excerpt = _summarize_text(updated)
    updated.last_message_at = _latest_message(updated).received_at if _latest_message(updated) else updated.last_message_at
    updated.updated_at = _now_utc()
    return updated


def _seed_threads() -> list[EmailThread]:
    now = _now_utc()

    def inbound_message(subject: str, body: str, from_address: str, to_address: str, minutes_ago: int, from_name: Optional[str] = None) -> EmailMessage:
        return EmailMessage(
            id=str(uuid4()),
            from_address=from_address,
            from_name=from_name,
            to_addresses=[to_address],
            subject=subject,
            body_text=body,
            received_at=now - timedelta(minutes=minutes_ago),
        )

    samples = [
        {
            "subject": "University operations discovery for workflow modernization",
            "from_address": "procurement@american.edu",
            "from_name": "American University Procurement",
            "organization": "American University",
            "to_addresses": ["portfolio.runtime+agc-universities@gmail.com"],
            "provider_labels": ["workspace/agc"],
            "messages": [
                inbound_message(
                    "University operations discovery for workflow modernization",
                    "We are reviewing partners who can help us bring more operational clarity to internal workflows and vendor-facing processes. Are you available for a short discovery conversation next week?",
                    "procurement@american.edu",
                    "portfolio.runtime+agc-universities@gmail.com",
                    42,
                    "American University Procurement",
                )
            ],
        },
        {
            "subject": "Reseller onboarding follow-up",
            "from_address": "partnerrelations@quantabio.com",
            "from_name": "QuantaBio Partner Relations",
            "organization": "QuantaBio",
            "to_addresses": ["portfolio.runtime+agc-vendors@gmail.com"],
            "provider_labels": ["workspace/agc"],
            "messages": [
                inbound_message(
                    "Reseller onboarding follow-up",
                    "Following up on your reseller application. Please confirm your current customer segments and whether you need updated onboarding documents or pricing sheets.",
                    "partnerrelations@quantabio.com",
                    "portfolio.runtime+agc-vendors@gmail.com",
                    115,
                    "QuantaBio Partner Relations",
                )
            ],
        },
        {
            "subject": "Family intake question for school placement support",
            "from_address": "parent.intake@example.org",
            "from_name": "Parent Intake",
            "organization": "Prospective Family",
            "to_addresses": ["portfolio.runtime+fusion@gmail.com"],
            "messages": [
                inbound_message(
                    "Family intake question for school placement support",
                    "We were referred to your team for help finding the right therapeutic school environment for our child. What does your intake process look like?",
                    "parent.intake@example.org",
                    "portfolio.runtime+fusion@gmail.com",
                    205,
                    "Parent Intake",
                )
            ],
        },
        {
            "subject": "Podcast invitation and speaking collaboration",
            "from_address": "host@growthoperator.fm",
            "from_name": "Growth Operator FM",
            "organization": "Growth Operator FM",
            "to_addresses": ["portfolio.runtime+feezie@gmail.com"],
            "messages": [
                inbound_message(
                    "Podcast invitation and speaking collaboration",
                    "Would Johnnie be open to a podcast conversation about creator systems, public execution, and operator-led visibility?",
                    "host@growthoperator.fm",
                    "portfolio.runtime+feezie@gmail.com",
                    320,
                    "Growth Operator FM",
                )
            ],
        },
        {
            "subject": "Invoice overdue for shared tool subscription",
            "from_address": "billing@saasvendor.io",
            "from_name": "SaaS Vendor Billing",
            "organization": "SaaS Vendor",
            "to_addresses": ["portfolio.runtime+ops@gmail.com"],
            "messages": [
                inbound_message(
                    "Invoice overdue for shared tool subscription",
                    "Your April invoice is overdue. Please confirm remittance timing or update billing contact information.",
                    "billing@saasvendor.io",
                    "portfolio.runtime+ops@gmail.com",
                    18,
                    "SaaS Vendor Billing",
                )
            ],
        },
        {
            "subject": "Need help improving procurement workflow visibility",
            "from_address": "operations@statecollege.edu",
            "from_name": "State College Operations",
            "organization": "State College",
            "to_addresses": ["portfolio.runtime@gmail.com"],
            "messages": [
                inbound_message(
                    "Need help improving procurement workflow visibility",
                    "We found your organization through a referral and want to understand whether you can help us improve process optimization and workflow modernization across our procurement operations.",
                    "operations@statecollege.edu",
                    "portfolio.runtime@gmail.com",
                    77,
                    "State College Operations",
                )
            ],
        },
        {
            "subject": "Quick introduction",
            "from_address": "hello@unknownconsulting.co",
            "from_name": "Unknown Consulting",
            "organization": "Unknown Consulting",
            "to_addresses": ["portfolio.runtime@gmail.com"],
            "messages": [
                inbound_message(
                    "Quick introduction",
                    "We help companies grow faster with better strategy. Let us know if there is room to collaborate.",
                    "hello@unknownconsulting.co",
                    "portfolio.runtime@gmail.com",
                    260,
                    "Unknown Consulting",
                )
            ],
        },
    ]

    seeded: list[EmailThread] = []
    for sample in samples:
        latest = max(sample["messages"], key=lambda item: item.received_at)
        thread = EmailThread(
            id=str(uuid4()),
            provider="sample",
            provider_thread_id=None,
            provider_labels=sample.get("provider_labels", []),
            subject=sample["subject"],
            from_address=sample["from_address"],
            from_name=sample["from_name"],
            organization=sample["organization"],
            to_addresses=sample["to_addresses"],
            messages=sample["messages"],
            last_message_at=latest.received_at,
            created_at=latest.received_at,
            updated_at=latest.received_at,
        )
        seeded.append(_classify_thread(thread))
    return seeded


def _load_or_seed_threads() -> tuple[list[EmailThread], bool]:
    threads = _read_threads()
    if threads:
        refreshed = [_classify_thread(thread) for thread in threads]
        refreshed, changed = _refresh_codex_job_threads(refreshed)
        if changed or refreshed != threads:
            _write_threads(refreshed)
        return refreshed, False
    status = gmail_connection_status()
    if status.get("connected"):
        live_threads = _fetch_live_gmail_threads(existing_threads=threads)
        if live_threads:
            _write_threads(live_threads)
            return live_threads, False
    seeded = _seed_threads()
    seeded, _ = _refresh_codex_job_threads(seeded)
    _write_threads(seeded)
    return seeded, True


def _fetch_live_gmail_threads(existing_threads: Optional[list[EmailThread]] = None) -> list[EmailThread]:
    account_email = gmail_account_email()
    payloads = fetch_gmail_threads()
    live_threads: list[EmailThread] = []
    for payload in payloads:
        try:
            live_threads.append(_classify_thread(_thread_from_gmail_payload(payload, account_email)))
        except Exception:
            continue
    if existing_threads:
        live_threads = _merge_live_thread_state(existing_threads, live_threads)
    live_threads, _ = _refresh_codex_job_threads(live_threads)
    return sorted(live_threads, key=lambda item: item.last_message_at, reverse=True)


def _merge_live_thread_state(existing_threads: list[EmailThread], live_threads: list[EmailThread]) -> list[EmailThread]:
    existing_by_key = {
        _thread_provider_key(thread): thread
        for thread in existing_threads
        if _thread_provider_key(thread)
    }
    merged: list[EmailThread] = []
    for live_thread in live_threads:
        existing = existing_by_key.get(_thread_provider_key(live_thread))
        if existing is None:
            merged.append(live_thread)
            continue
        candidate = live_thread.model_copy(deep=True)
        for field_name in (
            "manual_workspace_key",
            "manual_lane",
            "manual_notes",
            "draft_subject",
            "draft_body",
            "draft_type",
            "draft_mode",
            "draft_engine",
            "draft_source_mode",
            "draft_generated_at",
            "draft_job_id",
            "draft_audit",
            "draft_confidence",
            "provider_draft_id",
            "provider_draft_status",
            "provider_draft_saved_at",
            "provider_draft_error",
            "pm_card_id",
        ):
            setattr(candidate, field_name, getattr(existing, field_name))
        merged.append(_classify_thread(candidate))
    return merged


def _thread_provider_key(thread: EmailThread) -> str:
    if thread.provider == "gmail" and thread.provider_thread_id:
        return f"gmail:{thread.provider_thread_id}"
    return f"{thread.provider}:{thread.id}"


def list_threads(
    workspace_key: Optional[str] = None,
    lane: Optional[str] = None,
    needs_human: Optional[bool] = None,
    high_value: Optional[bool] = None,
    limit: int = 100,
) -> EmailThreadListResponse:
    threads, _ = _load_or_seed_threads()
    filtered = sorted(threads, key=lambda item: item.last_message_at, reverse=True)
    if workspace_key:
        if workspace_key == "manual_review":
            filtered = [thread for thread in filtered if _workspace_bucket(thread) == "manual_review"]
        else:
            filtered = [thread for thread in filtered if thread.workspace_key == workspace_key]
    if lane:
        filtered = [thread for thread in filtered if thread.lane == lane]
    if needs_human is not None:
        filtered = [thread for thread in filtered if thread.needs_human is needs_human]
    if high_value is not None:
        filtered = [thread for thread in filtered if thread.high_value is high_value]

    workspace_counts: dict[str, int] = {}
    agc_lane_counts: dict[str, int] = {}
    for thread in threads:
        bucket = _workspace_bucket(thread)
        workspace_counts[bucket] = workspace_counts.get(bucket, 0) + 1
        if thread.workspace_key == "agc":
            agc_lane_counts[thread.lane] = agc_lane_counts.get(thread.lane, 0) + 1

    last_synced_at = max((thread.updated_at for thread in threads), default=None)
    return EmailThreadListResponse(
        items=[_thread_list_item(thread) for thread in filtered[:limit]],
        total=len(filtered),
        needs_human_count=sum(1 for thread in filtered if thread.needs_human),
        high_value_count=sum(1 for thread in filtered if thread.high_value),
        high_risk_count=sum(1 for thread in filtered if thread.high_risk),
        workspace_counts=workspace_counts,
        agc_lane_counts=agc_lane_counts,
        data_mode="sample_only" if all(thread.provider == "sample" for thread in threads) else "provider_sync",
        last_synced_at=last_synced_at,
    )


def get_thread(thread_id: str) -> Optional[EmailThread]:
    threads, _ = _load_or_seed_threads()
    for thread in threads:
        if thread.id == thread_id:
            return thread
    return None


def sync_threads() -> EmailSyncResponse:
    status = gmail_connection_status()
    if status.get("connected"):
        threads = _fetch_live_gmail_threads(existing_threads=_read_threads())
        if threads:
            _write_threads(threads)
        return EmailSyncResponse(
            status="gmail_synced",
            thread_count=len(threads),
            data_mode="provider_sync",
            seeded_samples=False,
            last_synced_at=max((thread.updated_at for thread in threads), default=None),
        )

    threads, seeded = _load_or_seed_threads()
    return EmailSyncResponse(
        status="gmail_auth_required" if status.get("configured") and not status.get("connected") else ("sample_seed_ready" if seeded else "refreshed"),
        thread_count=len(threads),
        data_mode="sample_only" if all(thread.provider == "sample" for thread in threads) else "provider_sync",
        seeded_samples=seeded,
        last_synced_at=max((thread.updated_at for thread in threads), default=None),
    )


def _update_thread(thread_id: str, updater) -> EmailThread:
    threads, _ = _load_or_seed_threads()
    updated_thread: Optional[EmailThread] = None
    for index, thread in enumerate(threads):
        if thread.id != thread_id:
            continue
        changed = updater(thread.model_copy(deep=True))
        changed.updated_at = _now_utc()
        threads[index] = changed
        updated_thread = changed
        break
    if updated_thread is None:
        raise ValueError("Email thread not found")
    _write_threads(threads)
    return updated_thread


def reroute_thread(thread_id: str, payload: EmailThreadRouteRequest) -> EmailThread:
    def apply_route(thread: EmailThread) -> EmailThread:
        updated = thread.model_copy(deep=True)
        if payload.workspace_key is not None:
            updated.manual_workspace_key = payload.workspace_key
        if payload.lane is not None:
            updated.manual_lane = payload.lane
        if payload.notes is not None:
            updated.manual_notes = payload.notes
        updated = _classify_thread(updated)
        if payload.needs_human is not None:
            updated.needs_human = payload.needs_human
            updated.status = "human_review" if updated.needs_human else "routed"
        if payload.high_value is not None:
            updated.high_value = payload.high_value
        return updated

    return _update_thread(thread_id, apply_route)


def restore_auto_route(thread_id: str) -> EmailThread:
    def apply_auto_route(thread: EmailThread) -> EmailThread:
        updated = thread.model_copy(deep=True)
        updated.manual_workspace_key = None
        updated.manual_lane = None
        updated.manual_notes = None
        return _classify_thread(updated)

    return _update_thread(thread_id, apply_auto_route)


def _default_draft_type(thread: EmailThread) -> str:
    if thread.workspace_key == "agc":
        if thread.lane in {"consulting_opportunity", "supplier_partner", "product_sourcing"}:
            return "qualify"
        if thread.lane == "registrations_compliance":
            return "acknowledge"
    if thread.workspace_key == "fusion-os":
        return "schedule"
    return "acknowledge"


def _signature_for_workspace(workspace_key: str) -> str:
    if workspace_key == "agc":
        return "Johnnie Fields\nAcorn Global Collective"
    if workspace_key == "fusion-os":
        return "Fusion Team"
    if workspace_key == "feezie-os":
        return "Johnnie"
    return "Operations"


def _draft_body(thread: EmailThread, draft_type: str) -> str:
    if thread.workspace_key == "agc":
        if draft_type == "qualify" and thread.lane == "consulting_opportunity":
            return (
                "Thank you for reaching out. Based on what you shared, this sounds aligned with operational clarity and workflow modernization work.\n\n"
                "To make sure we point you in the right direction, could you share:\n"
                "- the current process or workflow that needs attention\n"
                "- who owns the decision internally\n"
                "- your timing and next-step expectations\n\n"
                "If helpful, we can also set up a short discovery call to understand the scope more clearly.\n\n"
                f"Thanks,\n{_signature_for_workspace(thread.workspace_key)}"
            )
        if draft_type == "qualify" and thread.lane == "supplier_partner":
            return (
                "Thank you for following up. We are interested in understanding the fit more clearly.\n\n"
                "Please send over the current onboarding requirements, pricing structure, and any reseller or partner documents we should review first.\n\n"
                f"Thanks,\n{_signature_for_workspace(thread.workspace_key)}"
            )
        if draft_type == "qualify" and thread.lane == "product_sourcing":
            return (
                "Thanks for sending this over. To move efficiently, please share the exact product specs, quantities, delivery timing, and any required manufacturer preferences.\n\n"
                "Once we have that, we can determine the best next sourcing step.\n\n"
                f"Thanks,\n{_signature_for_workspace(thread.workspace_key)}"
            )
        if draft_type == "acknowledge" and thread.lane == "registrations_compliance":
            return (
                "Thanks, we received your onboarding note and will review the requested documentation and next steps.\n\n"
                "If there is a deadline tied to the registration packet, please send that over as well so we can prioritize correctly.\n\n"
                f"Thanks,\n{_signature_for_workspace(thread.workspace_key)}"
            )

    if thread.workspace_key == "fusion-os":
        return (
            "Thank you for reaching out. We received your note and can follow up with next steps for intake.\n\n"
            "Please let us know a few times that work for a short conversation, and we will coordinate from there.\n\n"
            f"Thanks,\n{_signature_for_workspace(thread.workspace_key)}"
        )

    if draft_type == "schedule":
        return (
            "Thanks for reaching out. We would be glad to continue the conversation.\n\n"
            "Please send a few times that work on your side, and we will coordinate next steps.\n\n"
            f"Thanks,\n{_signature_for_workspace(thread.workspace_key)}"
        )

    return (
        "Thanks for reaching out. We received your note and are reviewing the right next step.\n\n"
        "If there is any timing sensitivity or context we should know, feel free to send it over.\n\n"
        f"Thanks,\n{_signature_for_workspace(thread.workspace_key)}"
    )


async def _run_content_generation_for_thread(
    thread: EmailThread,
    *,
    payload: EmailThreadDraftRequest,
    draft_type: str,
    signature_block: str,
):
    from app.routes.content_generation import ContentGenerationRequest, run_content_generation

    request_payload = build_content_generation_request_payload(
        thread,
        payload=payload,
        draft_type=draft_type,
        signature_block=signature_block,
    )
    request = ContentGenerationRequest(
        user_id=str(request_payload.get("user_id") or "johnnie_fields"),
        topic=str(request_payload.get("topic") or thread.subject or "email reply"),
        context=str(request_payload.get("context") or ""),
        content_type=str(request_payload.get("content_type") or "email_reply"),
        category=str(request_payload.get("category") or "value"),
        tone=str(request_payload.get("tone") or "expert_direct"),
        audience=str(request_payload.get("audience") or "general"),
        source_mode=str(request_payload.get("source_mode") or "email_thread_grounded"),
    )
    result = await run_content_generation(request)
    return result, request_payload


def _queue_codex_job_for_thread(
    thread: EmailThread,
    *,
    payload: EmailThreadDraftRequest,
    draft_type: str,
    signature_block: str,
) -> tuple[dict, dict[str, object], dict[str, object]]:
    request_payload = build_local_codex_email_request_payload(
        thread,
        payload=payload,
        draft_type=draft_type,
        signature_block=signature_block,
    )
    context_packet = build_local_codex_email_context_packet(
        thread,
        payload=payload,
        draft_type=draft_type,
        signature_block=signature_block,
        generated_at=_now_utc(),
    )
    idempotency_key = build_content_job_idempotency_key(
        {
            **request_payload,
            "workspace_slug": request_payload.get("workspace_slug") or "email-drafts",
            "context": f"{request_payload.get('context') or ''}\n\nThread id: {thread.id}",
        }
    )
    job = create_codex_job(
        workspace_slug=str(request_payload.get("workspace_slug") or "email-drafts"),
        requested_by=str(request_payload.get("user_id") or "johnnie_fields"),
        request_payload=request_payload,
        context_packet=context_packet,
        idempotency_key=idempotency_key,
    )
    return job, request_payload, context_packet


async def generate_draft(thread_id: str, payload: EmailThreadDraftRequest) -> EmailThreadDraftResponse:
    thread_snapshot = get_thread(thread_id)
    if thread_snapshot is None:
        raise ValueError("Email thread not found")
    draft_type = payload.draft_type or _default_draft_type(thread_snapshot)
    signature_block = _signature_for_workspace(thread_snapshot.workspace_key)
    packet_generated_at = _now_utc()
    draft_packet = build_email_drafting_packet(
        thread_snapshot,
        payload=payload,
        draft_type=draft_type,
        generated_at=packet_generated_at,
        signature_block=signature_block,
    )
    selected_path = "template"
    generation_request_payload = None
    generation_context_packet = None
    generation_diagnostics = None
    generated_body = None
    queued_job_id: Optional[str] = None
    requested_engine = resolve_draft_engine(payload)

    generation_reason = "draft_engine_not_requested"
    if requested_engine == "codex_job":
        codex_job_allowed, generation_reason = codex_job_eligibility(thread_snapshot, payload)
        if codex_job_allowed:
            try:
                job, generation_request_payload, generation_context_packet = _queue_codex_job_for_thread(
                    thread_snapshot,
                    payload=payload,
                    draft_type=draft_type,
                    signature_block=signature_block,
                )
                queued_job_id = str(job.get("id") or "")
                selected_path = "codex_job_pending"
                generation_diagnostics = {
                    "job_status": str(job.get("status") or "pending"),
                    "job_id": queued_job_id,
                    "fallback_triggered": False,
                }
            except Exception as exc:
                selected_path = "codex_job_failed"
                generation_reason = f"codex_job_queue_error:{type(exc).__name__}"
                generation_diagnostics = {
                    "error": str(exc)[:500],
                    "fallback_triggered": False,
                }
    elif requested_engine == "content_generation":
        eligible_for_generation, generation_reason = content_generation_eligibility(thread_snapshot, payload)
        if eligible_for_generation:
            try:
                generation_result, generation_request_payload = await _run_content_generation_for_thread(
                    thread_snapshot,
                    payload=payload,
                    draft_type=draft_type,
                    signature_block=signature_block,
                )
                generation_diagnostics = dict(getattr(generation_result, "diagnostics", {}) or {})
                options = list(getattr(generation_result, "options", []) or [])
                candidate = next((option for option in options if isinstance(option, str) and option.strip()), "")
                normalized_candidate = normalize_generated_email_body(candidate, signature_block=signature_block)
                if normalized_candidate:
                    generated_body = normalized_candidate
                    selected_path = "content_generation"
                else:
                    selected_path = "template_fallback"
                    generation_reason = "content_generation_returned_no_usable_body"
            except Exception as exc:
                selected_path = "template_fallback"
                generation_reason = f"content_generation_error:{type(exc).__name__}"
                generation_diagnostics = {
                    "error": str(exc)[:500],
                    "fallback_triggered": True,
                }

    def apply_draft(thread: EmailThread) -> EmailThread:
        updated = thread.model_copy(deep=True)
        effective_type = payload.draft_type or _default_draft_type(updated)
        generated_at = _now_utc()
        updated.draft_subject = f"Re: {updated.subject}"
        if queued_job_id:
            updated.draft_body = None
            updated.draft_generated_at = None
            updated.draft_job_id = queued_job_id
            updated.draft_confidence = None
        else:
            updated.draft_body = generated_body or _draft_body(updated, effective_type)
            updated.draft_generated_at = generated_at
            updated.draft_job_id = None
            updated.draft_confidence = updated.confidence_score
        updated.draft_type = effective_type
        updated.draft_mode = resolve_draft_mode(payload)
        updated.draft_engine = resolve_draft_engine(payload)
        updated.draft_source_mode = resolve_source_mode(payload)
        updated.draft_audit = {
            "bridge_version": "email_drafting_bridge/v1",
            "packet": draft_packet,
            "selected_path": selected_path,
            "generation_reason": generation_reason,
            "generation_request_payload": generation_request_payload,
            "generation_context_packet": generation_context_packet,
            "generation_diagnostics": generation_diagnostics,
        }
        if queued_job_id:
            updated.status = "waiting" if not updated.needs_human else "human_review"
        else:
            updated.status = "drafted" if not updated.needs_human else "human_review"
        return updated

    updated = _update_thread(thread_id, apply_draft)
    return EmailThreadDraftResponse(
        thread=updated,
        draft_subject=updated.draft_subject or f"Re: {updated.subject}",
        draft_body=updated.draft_body or "",
        draft_type=updated.draft_type or draft_type,
        draft_mode=updated.draft_mode,
        draft_engine=updated.draft_engine,
        source_mode=updated.draft_source_mode,
    )


def save_thread_draft(thread_id: str, *, overwrite_existing: bool = True) -> EmailThreadSaveDraftResponse:
    thread_snapshot = get_thread(thread_id)
    if thread_snapshot is None:
        raise ValueError("Email thread not found")
    if not thread_snapshot.draft_body:
        raise ValueError("No draft exists on this thread yet.")

    try:
        persist_result = save_gmail_draft(thread_snapshot, overwrite_existing=overwrite_existing)
    except Exception as exc:
        failed_at = _now_utc()

        def apply_provider_draft_error(thread: EmailThread) -> EmailThread:
            updated = thread.model_copy(deep=True)
            updated.provider_draft_status = "error"
            updated.provider_draft_error = str(exc)
            audit = dict(updated.draft_audit or {})
            audit["provider_persist"] = {
                "provider": "gmail",
                "status": "error",
                "failed_at": failed_at.isoformat(),
                "error": str(exc),
            }
            updated.draft_audit = audit
            return updated

        _update_thread(thread_id, apply_provider_draft_error)
        raise
    saved_at = _now_utc()

    def apply_provider_draft(thread: EmailThread) -> EmailThread:
        updated = thread.model_copy(deep=True)
        updated.provider_draft_id = str(persist_result.get("draft_id") or "") or updated.provider_draft_id
        updated.provider_draft_status = "saved"
        updated.provider_draft_saved_at = saved_at
        updated.provider_draft_error = None
        audit = dict(updated.draft_audit or {})
        audit["provider_persist"] = {
            "provider": "gmail",
            "action": persist_result.get("action") or "created",
            "draft_id": updated.provider_draft_id,
            "saved_at": saved_at.isoformat(),
            "thread_id": persist_result.get("thread_id"),
            "message_id": persist_result.get("message_id"),
        }
        updated.draft_audit = audit
        return updated

    updated = _update_thread(thread_id, apply_provider_draft)
    action = str(persist_result.get("action") or "created")
    return EmailThreadSaveDraftResponse(
        thread=updated,
        provider_draft_id=updated.provider_draft_id,
        provider_draft_status=updated.provider_draft_status,
        message=f"Gmail draft {action}.",
    )


def _record_draft_lifecycle_action(
    audit: dict | None,
    *,
    action: str,
    occurred_at: datetime,
    details: Optional[dict[str, object]] = None,
) -> dict:
    base = dict(audit or {})
    lifecycle = dict(base.get("lifecycle") or {})
    lifecycle["last_action"] = action
    lifecycle["last_action_at"] = occurred_at.isoformat()
    if details:
        lifecycle["details"] = details
    else:
        lifecycle.pop("details", None)
    base["lifecycle"] = lifecycle
    return base


def _cancel_thread_draft_job(thread: EmailThread) -> Optional[dict[str, str]]:
    if not thread.draft_job_id:
        return None
    job = get_codex_job(thread.draft_job_id)
    if not job:
        return {
            "job_id": thread.draft_job_id,
            "job_status": "missing",
        }
    status = str(job.get("status") or "").strip().lower() or "unknown"
    if status in {"pending", "claimed", "running"}:
        canceled = cancel_codex_job(thread.draft_job_id)
        return {
            "job_id": thread.draft_job_id,
            "job_status": str(canceled.get("status") or status),
        }
    return {
        "job_id": thread.draft_job_id,
        "job_status": status,
    }


def _status_after_draft_lifecycle(thread: EmailThread) -> str:
    if thread.needs_human:
        return "human_review"
    if thread.draft_body or thread.provider_draft_id:
        return "drafted"
    return "routed"


def update_thread_draft_lifecycle(thread_id: str, *, action: str) -> tuple[EmailThread, str]:
    normalized_action = " ".join((action or "").split()).strip().lower()
    if normalized_action not in {"clear_local_draft", "unlink_provider_draft", "clear_all_draft_state"}:
        raise ValueError("Unsupported email draft lifecycle action.")

    occurred_at = _now_utc()
    thread_snapshot = get_thread(thread_id)
    if thread_snapshot is None:
        raise ValueError("Email thread not found")

    canceled_job = (
        _cancel_thread_draft_job(thread_snapshot)
        if normalized_action in {"clear_local_draft", "clear_all_draft_state"}
        else None
    )

    def apply_lifecycle(thread: EmailThread) -> EmailThread:
        updated = thread.model_copy(deep=True)
        details: dict[str, object] = {}
        if canceled_job:
            details.update(canceled_job)

        if normalized_action in {"clear_local_draft", "clear_all_draft_state"}:
            updated.draft_subject = None
            updated.draft_body = None
            updated.draft_type = None
            updated.draft_mode = None
            updated.draft_engine = None
            updated.draft_source_mode = None
            updated.draft_generated_at = None
            updated.draft_job_id = None
            updated.draft_confidence = None
            updated.draft_audit = _record_draft_lifecycle_action(
                {},
                action=normalized_action,
                occurred_at=occurred_at,
                details=details or None,
            )

        if normalized_action in {"unlink_provider_draft", "clear_all_draft_state"}:
            updated.provider_draft_id = None
            updated.provider_draft_status = None
            updated.provider_draft_saved_at = None
            updated.provider_draft_error = None
            audit = dict(updated.draft_audit or {})
            audit.pop("provider_persist", None)
            updated.draft_audit = _record_draft_lifecycle_action(
                audit if normalized_action == "unlink_provider_draft" else {},
                action=normalized_action,
                occurred_at=occurred_at,
                details=details or None,
            )

        updated.status = _status_after_draft_lifecycle(updated)
        return updated

    updated = _update_thread(thread_id, apply_lifecycle)
    message_map = {
        "clear_local_draft": "Local draft cleared.",
        "unlink_provider_draft": "Gmail draft link cleared.",
        "clear_all_draft_state": "Local draft and Gmail draft link cleared.",
    }
    return updated, message_map[normalized_action]


def escalate_thread(thread_id: str, payload: EmailThreadEscalateRequest) -> EmailThreadEscalateResponse:
    pm_card_id: Optional[str] = None

    def apply_escalation(thread: EmailThread) -> EmailThread:
        updated = thread.model_copy(deep=True)
        updated.needs_human = True
        updated.high_value = True
        updated.status = "human_review"
        if payload.reason:
            updated.routing_reasons = [*updated.routing_reasons, f"escalated:{payload.reason}"]
        return updated

    updated = _update_thread(thread_id, apply_escalation)

    if payload.create_pm_card:
        try:
            card = pm_card_service.create_card(
                PMCardCreate(
                    title=f"Review email: {updated.subject}",
                    owner="Jean-Claude",
                    source="email_ops",
                    payload={
                        "workspace_key": updated.workspace_key,
                        "lane": "email_review",
                        "email_thread_id": updated.id,
                        "from_address": updated.from_address,
                        "reason": payload.reason or "Email thread marked for human review.",
                    },
                )
            )
            pm_card_id = card.id

            def attach_pm_card(thread: EmailThread) -> EmailThread:
                enriched = thread.model_copy(deep=True)
                enriched.pm_card_id = pm_card_id
                return enriched

            updated = _update_thread(thread_id, attach_pm_card)
        except Exception:
            pm_card_id = None

    return EmailThreadEscalateResponse(
        thread=updated,
        pm_card_id=pm_card_id,
        message="Thread escalated for human review.",
    )
