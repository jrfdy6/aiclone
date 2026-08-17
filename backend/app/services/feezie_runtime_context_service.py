from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from app.services.workspace_snapshot_store import get_snapshot_payload


FEEZIE_RUNTIME_CONTEXT_SCHEMA = "feezie_runtime_context/v1"
FEEZIE_RUNTIME_CONTEXT_RECEIPT_SCHEMA = "feezie_runtime_context_receipt/v1"
FEEZIE_RUNTIME_CONTEXT_STATUS_SCHEMA = "feezie_private_runtime_context_status/v1"
FEEZIE_RUNTIME_CONTEXT_WORKSPACE_KEY = "feezie-os"
FEEZIE_RUNTIME_CONTEXT_SNAPSHOT_TYPE = "feezie_runtime_context"
FEEZIE_RUNTIME_CONTEXT_MAX_FUTURE_SKEW_SECONDS = 5 * 60
FEEZIE_RUNTIME_CONTEXT_STALE_AFTER_SECONDS = 36 * 60 * 60

MAX_RUNTIME_CONTEXT_BYTES = 768 * 1024
MAX_STRATEGY_CONTRACT_BYTES = 128 * 1024
MAX_PERSONA_CHUNKS = 384
MAX_PERSONA_TEXT_BYTES = 384 * 1024
MAX_CHUNK_TEXT_BYTES = 4 * 1024
MAX_ANONYMIZED_PROOF_RECORDS = 24
MAX_ANONYMIZED_PROOF_TEXT_BYTES = 128 * 1024

_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_EMAIL_RE = re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![A-Za-z0-9._%+-])")
_ABSOLUTE_PATH_RE = re.compile(
    r"(?:"
    r"(?<![A-Za-z0-9])/(?:Users|home|private|var|tmp|Volumes|root|etc|opt|srv|mnt|media|Library|System|Applications)(?:/|\b)"
    r"|(?:^|[\s\"'(=])~/"
    r"|file://"
    r"|(?<![A-Za-z0-9])[A-Za-z]:[\\/]"
    r"|(?:^|[\s\"'(=])\\\\[^\\/\s]+\\[^\\/\s]+"
    r")",
    re.IGNORECASE,
)
_CREDENTIAL_LITERAL_RES = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:sk|rk)-(?:live|test|proj)?-?[A-Za-z0-9_-]{20,}\b", re.IGNORECASE),
    re.compile(r"\b(?:ghp|github_pat|xox[baprs])_[A-Za-z0-9_-]{20,}\b", re.IGNORECASE),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{2,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}\b", re.IGNORECASE),
    re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@", re.IGNORECASE),
    re.compile(
        r"\b(?:api[_ -]?key|client[_ -]?secret|password|access[_ -]?token)\s*[:=]\s*[\"']?[A-Za-z0-9._~+/=-]{12,}",
        re.IGNORECASE,
    ),
)
_CREDENTIAL_FIELD_NAMES = {
    "access_token",
    "api_key",
    "authorization",
    "client_secret",
    "cookie",
    "credential",
    "credentials",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "token",
}
_RAW_SOURCE_FIELD_NAMES = {
    "body",
    "raw",
    "raw_body",
    "raw_content",
    "raw_source",
    "raw_text",
    "source_body",
    "transcript",
    "transcript_text",
}

_TOP_LEVEL_KEYS = {
    "schema_version",
    "generated_at",
    "workspace_key",
    "strategy_contract",
    "persona_chunks",
    "anonymized_proof_records",
    "counts",
    "data_policy",
    "payload_sha256",
    "receipt",
}
_POSITIONING_KEYS = {
    "schema_version",
    "status",
    "approved_at",
    "owner",
    "canonical_identity_sources",
    "positioning_model",
    "audience_priority",
    "career_signal_values",
    "employer_proximity_values",
    "employer_safety_values",
    "proof_posture_values",
    "career_posture",
    "generation_disallowed_moves",
    "generation_quality_contract",
    "standup_relevance",
}
_EDITORIAL_KEYS = {
    "schema_version",
    "status",
    "approved_at",
    "owner",
    "positioning_contract",
    "canonical_pillars",
    "qualification_runtime",
    "qualification_sop_recovery_ref",
    "pillars",
    "rolling_topic_mix",
    "intent_mix",
    "measurement",
    "weekly_model",
    "planner",
}
_PERSONA_CHUNK_KEYS = {
    "chunk_id",
    "bundle_path",
    "chunk_index",
    "text",
    "persona_tag",
    "memory_role",
    "domain_tags",
    "audience_tags",
    "proof_kind",
    "proof_strength",
    "artifact_backed",
    "usage_modes",
    "source_kind",
}
_ANONYMIZED_PROOF_RECORD_KEYS = {
    "macro_thesis",
    "public_takeaway",
    "public_proof",
    "safe_angle",
    "topic_tags",
    "provenance_hash",
}
_ALLOWED_BUNDLE_PATHS = {
    "identity/VOICE_PATTERNS.md",
    "identity/claims.md",
    "identity/philosophy.md",
    "identity/audience_communication.md",
    "identity/decision_principles.md",
    "prompts/content_guardrails.md",
    "prompts/content_examples.md",
    "prompts/content_pillars.md",
    "history/initiatives.md",
    "history/wins.md",
}
_REQUIRED_BUNDLE_PATHS = {
    "identity/VOICE_PATTERNS.md",
    "identity/claims.md",
    "prompts/content_guardrails.md",
    "prompts/content_examples.md",
}
_PATH_PRIORITY = {
    "identity/VOICE_PATTERNS.md": 0,
    "identity/claims.md": 1,
    "identity/philosophy.md": 2,
    "identity/audience_communication.md": 3,
    "identity/decision_principles.md": 4,
    "prompts/content_guardrails.md": 5,
    "prompts/content_pillars.md": 6,
    "prompts/content_examples.md": 7,
    "history/initiatives.md": 8,
    "history/wins.md": 9,
}
_MEMORY_ROLES = {"core", "proof", "example"}
_PROOF_STRENGTHS = {"none", "weak", "medium", "strong"}
_SOURCE_KINDS = {"canonical_bundle", "committed_overlay"}
_DATA_POLICY = {
    "private_runtime_only": True,
    "browser_projection_allowed": False,
    "derived_canonical_chunks_only": True,
    "derived_public_safe_proof_only": True,
    "raw_source_bodies_included": False,
    "credentials_included": False,
    "absolute_paths_included": False,
    "anonymized_proof_only": True,
}

_POSITIONING_CONTRACT_PATH = "workspaces/linkedin-content-os/docs/positioning_contract.md"
_EDITORIAL_MIX_PATH = "workspaces/linkedin-content-os/docs/editorial_mix.md"


class FeezieRuntimeContextError(RuntimeError):
    pass


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        rendered = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise FeezieRuntimeContextError("FEEZIE runtime context is not canonical JSON.") from exc
    return rendered.encode("utf-8")


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def _require_exact_keys(value: Any, expected: set[str], *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise FeezieRuntimeContextError(f"{field} does not match the required schema.")
    return dict(value)


def _require_nonempty_string(value: Any, *, field: str, maximum_bytes: int = 12 * 1024) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FeezieRuntimeContextError(f"{field} must be a non-empty string.")
    if len(value.encode("utf-8")) > maximum_bytes:
        raise FeezieRuntimeContextError(f"{field} exceeds its bounded size.")
    return value


def _require_sha256(value: Any, *, field: str) -> str:
    normalized = str(value or "").strip().lower()
    if _SHA256_RE.fullmatch(normalized) is None:
        raise FeezieRuntimeContextError(f"{field} must be a lowercase SHA-256 digest.")
    return normalized


def _parse_timezone_timestamp(value: Any, *, field: str) -> tuple[str, datetime]:
    text = _require_nonempty_string(value, field=field, maximum_bytes=100)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FeezieRuntimeContextError(f"{field} must be a timezone-aware ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FeezieRuntimeContextError(f"{field} must be a timezone-aware ISO-8601 timestamp.")
    return text, parsed.astimezone(timezone.utc)


def _require_timezone_timestamp(value: Any, *, field: str) -> str:
    text, _ = _parse_timezone_timestamp(value, field=field)
    return text


def _normalized_now(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise FeezieRuntimeContextError("FEEZIE runtime context freshness requires a timezone-aware current time.")
    return current.astimezone(timezone.utc)


def _runtime_context_age_seconds(payload: dict[str, Any], *, now: datetime | None = None) -> tuple[datetime, int]:
    current = _normalized_now(now)
    _, generated_at = _parse_timezone_timestamp(
        payload.get("generated_at"),
        field="feezie_runtime_context.generated_at",
    )
    return generated_at, int((current - generated_at).total_seconds())


def require_current_feezie_runtime_context_bundle(
    value: Any,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate the exact bundle and reject stale or clock-poisoned runtime state."""

    payload = validate_feezie_runtime_context_bundle(value)
    current = _normalized_now(now)
    generated_at, _ = _runtime_context_age_seconds(payload, now=current)
    if generated_at > current + timedelta(seconds=FEEZIE_RUNTIME_CONTEXT_MAX_FUTURE_SKEW_SECONDS):
        raise FeezieRuntimeContextError("FEEZIE runtime context is too far in the future.")
    if generated_at < current - timedelta(
        seconds=FEEZIE_RUNTIME_CONTEXT_STALE_AFTER_SECONDS
    ):
        raise FeezieRuntimeContextError("FEEZIE runtime context is stale.")
    return payload


def _validate_relative_path(value: Any, *, field: str) -> str:
    text = _require_nonempty_string(value, field=field, maximum_bytes=1_024)
    candidate = Path(text)
    if candidate.is_absolute() or text.startswith(("~", "file://")) or "\\" in text or ".." in candidate.parts:
        raise FeezieRuntimeContextError(f"{field} must be a contained relative path.")
    return candidate.as_posix()


def _validate_private_material(value: Any, *, field: str = "runtime_context", depth: int = 0) -> None:
    if depth > 14:
        raise FeezieRuntimeContextError("FEEZIE runtime context exceeds the maximum nesting depth.")
    if isinstance(value, dict):
        if len(value) > 128:
            raise FeezieRuntimeContextError(f"{field} exceeds the maximum field count.")
        for raw_key, item in value.items():
            key = str(raw_key or "").strip().lower()
            if not key:
                raise FeezieRuntimeContextError(f"{field} contains an empty field name.")
            if key in _CREDENTIAL_FIELD_NAMES or key in _RAW_SOURCE_FIELD_NAMES:
                raise FeezieRuntimeContextError(f"{field} contains a prohibited private-data field.")
            _validate_private_material(item, field=f"{field}.{key}", depth=depth + 1)
        return
    if isinstance(value, list):
        if len(value) > MAX_PERSONA_CHUNKS:
            raise FeezieRuntimeContextError(f"{field} exceeds the maximum list length.")
        for index, item in enumerate(value):
            _validate_private_material(item, field=f"{field}[{index}]", depth=depth + 1)
        return
    if isinstance(value, str):
        if len(value.encode("utf-8")) > 12 * 1024:
            raise FeezieRuntimeContextError(f"{field} contains an oversized string.")
        if _ABSOLUTE_PATH_RE.search(value):
            raise FeezieRuntimeContextError(f"{field} contains an absolute filesystem path.")
        if _EMAIL_RE.search(value):
            raise FeezieRuntimeContextError(f"{field} contains an email address.")
        if any(pattern.search(value) for pattern in _CREDENTIAL_LITERAL_RES):
            raise FeezieRuntimeContextError(f"{field} contains a credential-like literal.")
        return
    if value is not None and not isinstance(value, (bool, int, float)):
        raise FeezieRuntimeContextError(f"{field} contains a non-JSON value.")


def _validate_strategy_contract(value: Any) -> dict[str, Any]:
    contract = _require_exact_keys(
        value,
        {"schema_version", "contract_hash", "positioning", "editorial_mix", "sources"},
        field="strategy_contract",
    )
    if len(_canonical_json_bytes(contract)) > MAX_STRATEGY_CONTRACT_BYTES:
        raise FeezieRuntimeContextError("strategy_contract exceeds its bounded size.")
    if contract.get("schema_version") != "feezie_strategy_contract/v1":
        raise FeezieRuntimeContextError("strategy_contract has an unsupported schema_version.")
    contract_hash = _require_sha256(
        contract.get("contract_hash"),
        field="strategy_contract.contract_hash",
    )

    positioning = _require_exact_keys(contract.get("positioning"), _POSITIONING_KEYS, field="strategy_contract.positioning")
    editorial = _require_exact_keys(contract.get("editorial_mix"), _EDITORIAL_KEYS, field="strategy_contract.editorial_mix")
    sources = _require_exact_keys(contract.get("sources"), {"positioning", "editorial_mix"}, field="strategy_contract.sources")

    if positioning.get("schema_version") != "positioning_contract/v1" or positioning.get("status") != "owner_approved":
        raise FeezieRuntimeContextError("strategy_contract positioning is not owner-approved v1.")
    career_posture = _require_exact_keys(
        positioning.get("career_posture"),
        {
            "mode",
            "public_job_search",
            "explicit_transition_default",
            "employer_specific_default",
            "publication_requires_owner_approval",
        },
        field="strategy_contract.positioning.career_posture",
    )
    if career_posture != {
        "mode": "proof_led_technology_expansion",
        "public_job_search": False,
        "explicit_transition_default": "blocked",
        "employer_specific_default": "owner_review_required",
        "publication_requires_owner_approval": True,
    }:
        raise FeezieRuntimeContextError("strategy_contract career posture is not the approved safe posture.")
    generation_quality = _require_exact_keys(
        positioning.get("generation_quality_contract"),
        {
            "required_option_count",
            "maximum_option_count",
            "meaningful_difference_required",
            "independent_critic_required",
            "critic_dimensions",
            "hook_variants_per_option",
            "owner_review_requires_critic_ready",
        },
        field="strategy_contract.positioning.generation_quality_contract",
    )
    if generation_quality != {
        "required_option_count": 2,
        "maximum_option_count": 2,
        "meaningful_difference_required": True,
        "independent_critic_required": True,
        "critic_dimensions": ["truth", "safety", "intent", "voice", "hook"],
        "hook_variants_per_option": 8,
        "owner_review_requires_critic_ready": True,
    }:
        raise FeezieRuntimeContextError("strategy_contract generation quality policy is not canonical.")

    if editorial.get("schema_version") != "editorial_mix/v1" or editorial.get("status") != "owner_approved":
        raise FeezieRuntimeContextError("strategy_contract editorial mix is not owner-approved v1.")
    if editorial.get("rolling_topic_mix") != {
        "window": 10,
        "counts": {"ai_native": 4, "leadership_operator": 4, "trust_systems": 2},
    }:
        raise FeezieRuntimeContextError("strategy_contract topic mix is not the approved 40/40/20 contract.")
    if editorial.get("intent_mix") != {
        "window": 11,
        "counts": {"value": 9, "invitation": 1, "personal": 1},
    }:
        raise FeezieRuntimeContextError("strategy_contract intent mix is not the approved 9/1/1 contract.")

    source_hashes: dict[str, str] = {}
    expected_source_paths = {
        "positioning": _POSITIONING_CONTRACT_PATH,
        "editorial_mix": _EDITORIAL_MIX_PATH,
    }
    for source_name in ("positioning", "editorial_mix"):
        source = _require_exact_keys(
            sources.get(source_name),
            {"path", "sha256"},
            field=f"strategy_contract.sources.{source_name}",
        )
        source_path = _validate_relative_path(
            source.get("path"),
            field=f"strategy_contract.sources.{source_name}.path",
        )
        if source_path != expected_source_paths[source_name]:
            raise FeezieRuntimeContextError(
                f"strategy_contract.sources.{source_name}.path is not the canonical strategy source."
            )
        source_hashes[source_name] = _require_sha256(
            source.get("sha256"),
            field=f"strategy_contract.sources.{source_name}.sha256",
        )

    expected_contract_hash = hashlib.sha256(
        f"{source_hashes['positioning']}:{source_hashes['editorial_mix']}".encode("utf-8")
    ).hexdigest()
    if contract_hash != expected_contract_hash:
        raise FeezieRuntimeContextError(
            "strategy_contract.contract_hash does not match its canonical source hashes."
        )

    _validate_private_material(contract, field="strategy_contract")
    return copy.deepcopy(contract)


def _string_list(value: Any, *, field: str, maximum: int = 32) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum or any(not isinstance(item, str) or not item.strip() for item in value):
        raise FeezieRuntimeContextError(f"{field} must be a bounded list of non-empty strings.")
    return list(value)


def _validate_persona_chunk(value: Any, *, index: int) -> dict[str, Any]:
    chunk = _require_exact_keys(value, _PERSONA_CHUNK_KEYS, field=f"persona_chunks[{index}]")
    bundle_path = _validate_relative_path(chunk.get("bundle_path"), field=f"persona_chunks[{index}].bundle_path")
    if bundle_path not in _ALLOWED_BUNDLE_PATHS:
        raise FeezieRuntimeContextError("persona_chunks contains a non-runtime persona source.")
    chunk_index = chunk.get("chunk_index")
    if isinstance(chunk_index, bool) or not isinstance(chunk_index, int) or not 0 <= chunk_index <= 100_000:
        raise FeezieRuntimeContextError(f"persona_chunks[{index}].chunk_index is invalid.")
    text = _require_nonempty_string(
        chunk.get("text"),
        field=f"persona_chunks[{index}].text",
        maximum_bytes=MAX_CHUNK_TEXT_BYTES,
    )
    persona_tag = _require_nonempty_string(chunk.get("persona_tag"), field=f"persona_chunks[{index}].persona_tag", maximum_bytes=80)
    memory_role = str(chunk.get("memory_role") or "")
    if memory_role not in _MEMORY_ROLES:
        raise FeezieRuntimeContextError(f"persona_chunks[{index}].memory_role is unsupported.")
    proof_strength = str(chunk.get("proof_strength") or "")
    if proof_strength not in _PROOF_STRENGTHS:
        raise FeezieRuntimeContextError(f"persona_chunks[{index}].proof_strength is unsupported.")
    source_kind = str(chunk.get("source_kind") or "")
    if source_kind not in _SOURCE_KINDS:
        raise FeezieRuntimeContextError(f"persona_chunks[{index}].source_kind is unsupported.")
    if not isinstance(chunk.get("artifact_backed"), bool):
        raise FeezieRuntimeContextError(f"persona_chunks[{index}].artifact_backed must be boolean.")
    _string_list(chunk.get("domain_tags"), field=f"persona_chunks[{index}].domain_tags")
    _string_list(chunk.get("audience_tags"), field=f"persona_chunks[{index}].audience_tags")
    _string_list(chunk.get("usage_modes"), field=f"persona_chunks[{index}].usage_modes")
    _require_nonempty_string(chunk.get("proof_kind"), field=f"persona_chunks[{index}].proof_kind", maximum_bytes=80)
    chunk_id = _require_sha256(chunk.get("chunk_id"), field=f"persona_chunks[{index}].chunk_id")
    expected_chunk_id = hashlib.sha256(
        f"{bundle_path}\n{chunk_index}\n{text}".encode("utf-8")
    ).hexdigest()
    if chunk_id != expected_chunk_id:
        raise FeezieRuntimeContextError(f"persona_chunks[{index}].chunk_id does not match its content.")
    _validate_private_material(chunk, field=f"persona_chunks[{index}]")
    return copy.deepcopy(chunk)


def _proof_record_core(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(value[key])
        for key in (
            "macro_thesis",
            "public_takeaway",
            "public_proof",
            "safe_angle",
            "topic_tags",
        )
    }


def _validate_anonymized_proof_record(value: Any, *, index: int) -> dict[str, Any]:
    record = _require_exact_keys(
        value,
        _ANONYMIZED_PROOF_RECORD_KEYS,
        field=f"anonymized_proof_records[{index}]",
    )
    _require_nonempty_string(
        record.get("macro_thesis"),
        field=f"anonymized_proof_records[{index}].macro_thesis",
        maximum_bytes=1_000,
    )
    _require_nonempty_string(
        record.get("public_takeaway"),
        field=f"anonymized_proof_records[{index}].public_takeaway",
        maximum_bytes=1_200,
    )
    _require_nonempty_string(
        record.get("public_proof"),
        field=f"anonymized_proof_records[{index}].public_proof",
        maximum_bytes=1_000,
    )
    _require_nonempty_string(
        record.get("safe_angle"),
        field=f"anonymized_proof_records[{index}].safe_angle",
        maximum_bytes=120,
    )
    _string_list(
        record.get("topic_tags"),
        field=f"anonymized_proof_records[{index}].topic_tags",
        maximum=16,
    )
    provenance_hash = _require_sha256(
        record.get("provenance_hash"),
        field=f"anonymized_proof_records[{index}].provenance_hash",
    )
    if provenance_hash != _sha256_json(_proof_record_core(record)):
        raise FeezieRuntimeContextError(
            f"anonymized_proof_records[{index}].provenance_hash does not match its public-safe fields."
        )
    _validate_private_material(record, field=f"anonymized_proof_records[{index}]")
    return copy.deepcopy(record)


def _runtime_counts(
    chunks: list[dict[str, Any]],
    proof_records: list[dict[str, Any]],
) -> dict[str, int]:
    role_counts = {role: 0 for role in sorted(_MEMORY_ROLES)}
    for chunk in chunks:
        role = str(chunk.get("memory_role") or "")
        if role in role_counts:
            role_counts[role] += 1
    return {
        "chunk_count": len(chunks),
        "core_count": role_counts["core"],
        "example_count": role_counts["example"],
        "proof_count": role_counts["proof"],
        "anonymized_proof_count": len(proof_records),
    }


def _payload_core(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(payload[key])
        for key in (
            "schema_version",
            "generated_at",
            "workspace_key",
            "strategy_contract",
            "persona_chunks",
            "anonymized_proof_records",
            "counts",
            "data_policy",
        )
    }


def validate_feezie_runtime_context_bundle(value: Any) -> dict[str, Any]:
    payload = _require_exact_keys(value, _TOP_LEVEL_KEYS, field="feezie_runtime_context")
    if payload.get("schema_version") != FEEZIE_RUNTIME_CONTEXT_SCHEMA:
        raise FeezieRuntimeContextError("FEEZIE runtime context has an unsupported schema_version.")
    if payload.get("workspace_key") != FEEZIE_RUNTIME_CONTEXT_WORKSPACE_KEY:
        raise FeezieRuntimeContextError("FEEZIE runtime context has an unsupported workspace_key.")
    _require_timezone_timestamp(payload.get("generated_at"), field="feezie_runtime_context.generated_at")
    strategy_contract = _validate_strategy_contract(payload.get("strategy_contract"))

    raw_chunks = payload.get("persona_chunks")
    if not isinstance(raw_chunks, list) or not 1 <= len(raw_chunks) <= MAX_PERSONA_CHUNKS:
        raise FeezieRuntimeContextError("persona_chunks must contain a bounded non-empty list.")
    chunks = [_validate_persona_chunk(item, index=index) for index, item in enumerate(raw_chunks)]
    if len({chunk["chunk_id"] for chunk in chunks}) != len(chunks):
        raise FeezieRuntimeContextError("persona_chunks contains duplicate chunk identities.")
    if sum(len(str(chunk["text"]).encode("utf-8")) for chunk in chunks) > MAX_PERSONA_TEXT_BYTES:
        raise FeezieRuntimeContextError("persona_chunks exceeds the bounded text budget.")
    available_paths = {str(chunk.get("bundle_path") or "") for chunk in chunks}
    if not _REQUIRED_BUNDLE_PATHS.issubset(available_paths):
        raise FeezieRuntimeContextError("persona_chunks is missing required identity, voice, guardrail, or example context.")

    raw_proof_records = payload.get("anonymized_proof_records")
    if not isinstance(raw_proof_records, list) or not 1 <= len(raw_proof_records) <= MAX_ANONYMIZED_PROOF_RECORDS:
        raise FeezieRuntimeContextError("anonymized_proof_records must contain a bounded non-empty list.")
    proof_records = [
        _validate_anonymized_proof_record(item, index=index)
        for index, item in enumerate(raw_proof_records)
    ]
    if len({record["provenance_hash"] for record in proof_records}) != len(proof_records):
        raise FeezieRuntimeContextError("anonymized_proof_records contains duplicate records.")
    if sum(
        len(_canonical_json_bytes(record))
        for record in proof_records
    ) > MAX_ANONYMIZED_PROOF_TEXT_BYTES:
        raise FeezieRuntimeContextError("anonymized_proof_records exceeds the bounded text budget.")

    counts = _require_exact_keys(
        payload.get("counts"),
        {"chunk_count", "core_count", "example_count", "proof_count", "anonymized_proof_count"},
        field="feezie_runtime_context.counts",
    )
    if counts != _runtime_counts(chunks, proof_records):
        raise FeezieRuntimeContextError("feezie_runtime_context counts do not match its derived context records.")
    if payload.get("data_policy") != _DATA_POLICY:
        raise FeezieRuntimeContextError("feezie_runtime_context data_policy is not the private-only contract.")

    payload_sha256 = _require_sha256(payload.get("payload_sha256"), field="feezie_runtime_context.payload_sha256")
    expected_payload_sha256 = _sha256_json(_payload_core(payload))
    if payload_sha256 != expected_payload_sha256:
        raise FeezieRuntimeContextError("feezie_runtime_context payload hash does not match its content.")

    receipt = _require_exact_keys(
        payload.get("receipt"),
        {
            "schema_version",
            "payload_sha256",
            "strategy_contract_sha256",
            "persona_chunks_sha256",
            "anonymized_proof_records_sha256",
            "persona_chunk_count",
            "anonymized_proof_record_count",
        },
        field="feezie_runtime_context.receipt",
    )
    expected_receipt = {
        "schema_version": FEEZIE_RUNTIME_CONTEXT_RECEIPT_SCHEMA,
        "payload_sha256": payload_sha256,
        "strategy_contract_sha256": _sha256_json(strategy_contract),
        "persona_chunks_sha256": _sha256_json(chunks),
        "anonymized_proof_records_sha256": _sha256_json(proof_records),
        "persona_chunk_count": len(chunks),
        "anonymized_proof_record_count": len(proof_records),
    }
    if receipt != expected_receipt:
        raise FeezieRuntimeContextError("feezie_runtime_context receipt does not match its content.")
    _validate_private_material(payload, field="feezie_runtime_context")
    if len(_canonical_json_bytes(payload)) > MAX_RUNTIME_CONTEXT_BYTES:
        raise FeezieRuntimeContextError("FEEZIE runtime context exceeds its maximum payload size.")
    return copy.deepcopy(payload)


def _project_persona_chunks(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[tuple[int, int, dict[str, Any]]] = []
    seen: set[str] = set()
    for ordinal, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        bundle_path = str(metadata.get("bundle_path") or item.get("source_file_id") or "").strip()
        if bundle_path not in _ALLOWED_BUNDLE_PATHS:
            continue
        text = _clean_text(item.get("chunk"))
        if not text:
            continue
        if len(text.encode("utf-8")) > MAX_CHUNK_TEXT_BYTES:
            raise FeezieRuntimeContextError("A canonical persona chunk exceeds the runtime context bound.")
        raw_index = item.get("chunk_index")
        try:
            chunk_index = int(raw_index)
        except (TypeError, ValueError) as exc:
            raise FeezieRuntimeContextError("A canonical persona chunk has an invalid index.") from exc
        chunk_id = hashlib.sha256(f"{bundle_path}\n{chunk_index}\n{text}".encode("utf-8")).hexdigest()
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        memory_role = str(metadata.get("memory_role") or "").strip()
        if memory_role not in _MEMORY_ROLES:
            continue
        source_kind = str(metadata.get("source_kind") or "canonical_bundle").strip()
        if source_kind not in _SOURCE_KINDS:
            continue
        projected = {
            "chunk_id": chunk_id,
            "bundle_path": bundle_path,
            "chunk_index": chunk_index,
            "text": text,
            "persona_tag": _clean_text(item.get("persona_tag")) or "UNTAGGED",
            "memory_role": memory_role,
            "domain_tags": sorted({_clean_text(value) for value in metadata.get("domain_tags") or [] if _clean_text(value)}),
            "audience_tags": sorted({_clean_text(value) for value in metadata.get("audience_tags") or [] if _clean_text(value)}),
            "proof_kind": _clean_text(metadata.get("proof_kind")) or "support",
            "proof_strength": str(metadata.get("proof_strength") or "none").strip().lower(),
            "artifact_backed": metadata.get("artifact_backed") is True,
            "usage_modes": sorted({_clean_text(value) for value in metadata.get("usage_modes") or [] if _clean_text(value)}),
            "source_kind": source_kind,
        }
        candidates.append((_PATH_PRIORITY[bundle_path], ordinal, projected))

    selected: list[dict[str, Any]] = []
    text_bytes = 0
    for _, _, chunk in sorted(candidates, key=lambda entry: (entry[0], entry[1])):
        chunk_bytes = len(str(chunk["text"]).encode("utf-8"))
        if len(selected) >= MAX_PERSONA_CHUNKS or text_bytes + chunk_bytes > MAX_PERSONA_TEXT_BYTES:
            continue
        selected.append(chunk)
        text_bytes += chunk_bytes
    return selected


def _project_anonymized_proof_records(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    total_bytes = 0
    for item in items:
        if not isinstance(item, dict) or str(item.get("visibility") or "") != "public_safe":
            continue
        core = {
            "macro_thesis": _clean_text(item.get("macro_thesis")),
            "public_takeaway": _clean_text(item.get("public_takeaway")),
            "public_proof": _clean_text(item.get("public_proof")),
            "safe_angle": _clean_text(item.get("safe_angle")),
            "topic_tags": sorted(
                {
                    _clean_text(value)
                    for value in item.get("topic_tags") or []
                    if _clean_text(value)
                }
            ),
        }
        if not all(core[field] for field in ("macro_thesis", "public_takeaway", "public_proof", "safe_angle")):
            continue
        provenance_hash = _sha256_json(core)
        if provenance_hash in seen:
            continue
        record = {**core, "provenance_hash": provenance_hash}
        _validate_anonymized_proof_record(record, index=len(records))
        record_bytes = len(_canonical_json_bytes(record))
        if len(records) >= MAX_ANONYMIZED_PROOF_RECORDS or total_bytes + record_bytes > MAX_ANONYMIZED_PROOF_TEXT_BYTES:
            continue
        seen.add(provenance_hash)
        records.append(record)
        total_bytes += record_bytes
    return records


def build_feezie_runtime_context_bundle(
    *,
    generated_at: str | None = None,
    strategy_contract: dict[str, Any] | None = None,
    persona_chunks: Iterable[dict[str, Any]] | None = None,
    content_safe_operator_lessons: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if strategy_contract is None:
        from app.services.feezie_positioning_contract_service import load_feezie_strategy_contract

        strategy_contract = load_feezie_strategy_contract()
    if persona_chunks is None:
        from app.services.persona_bundle_context_service import (
            load_bundle_persona_chunks,
            load_committed_overlay_chunks,
        )

        persona_chunks = [*load_committed_overlay_chunks(), *load_bundle_persona_chunks()]
    if content_safe_operator_lessons is None:
        from app.services.content_safe_operator_lesson_service import (
            build_content_safe_operator_lessons_payload,
        )

        lesson_payload = build_content_safe_operator_lessons_payload()
        content_safe_operator_lessons = (
            lesson_payload.get("lessons")
            if isinstance(lesson_payload.get("lessons"), list)
            else []
        )

    normalized_strategy = _validate_strategy_contract(strategy_contract)
    normalized_chunks = _project_persona_chunks(persona_chunks)
    normalized_proof_records = _project_anonymized_proof_records(content_safe_operator_lessons)
    timestamp = generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    core = {
        "schema_version": FEEZIE_RUNTIME_CONTEXT_SCHEMA,
        "generated_at": timestamp,
        "workspace_key": FEEZIE_RUNTIME_CONTEXT_WORKSPACE_KEY,
        "strategy_contract": normalized_strategy,
        "persona_chunks": normalized_chunks,
        "anonymized_proof_records": normalized_proof_records,
        "counts": _runtime_counts(normalized_chunks, normalized_proof_records),
        "data_policy": copy.deepcopy(_DATA_POLICY),
    }
    payload_sha256 = _sha256_json(core)
    payload = {
        **core,
        "payload_sha256": payload_sha256,
        "receipt": {
            "schema_version": FEEZIE_RUNTIME_CONTEXT_RECEIPT_SCHEMA,
            "payload_sha256": payload_sha256,
            "strategy_contract_sha256": _sha256_json(normalized_strategy),
            "persona_chunks_sha256": _sha256_json(normalized_chunks),
            "anonymized_proof_records_sha256": _sha256_json(normalized_proof_records),
            "persona_chunk_count": len(normalized_chunks),
            "anonymized_proof_record_count": len(normalized_proof_records),
        },
    }
    return validate_feezie_runtime_context_bundle(payload)


def load_persisted_feezie_runtime_context_bundle() -> dict[str, Any] | None:
    payload = get_snapshot_payload(
        FEEZIE_RUNTIME_CONTEXT_WORKSPACE_KEY,
        FEEZIE_RUNTIME_CONTEXT_SNAPSHOT_TYPE,
    )
    if payload is None:
        return None
    return require_current_feezie_runtime_context_bundle(payload)


def load_persisted_feezie_strategy_contract() -> dict[str, Any] | None:
    payload = load_persisted_feezie_runtime_context_bundle()
    if payload is None:
        return None
    return copy.deepcopy(payload["strategy_contract"])


def load_persisted_feezie_persona_chunks() -> list[dict[str, Any]] | None:
    payload = load_persisted_feezie_runtime_context_bundle()
    if payload is None:
        return None
    hydrated: list[dict[str, Any]] = []
    for item in payload["persona_chunks"]:
        bundle_path = str(item["bundle_path"])
        hydrated.append(
            {
                "source_id": f"runtime:{item['chunk_id']}",
                "source_file_id": bundle_path,
                "chunk_index": item["chunk_index"],
                "chunk": item["text"],
                "persona_tag": item["persona_tag"],
                "metadata": {
                    "source": "private runtime context",
                    "source_kind": item["source_kind"],
                    "file_name": bundle_path,
                    "persona_tag": item["persona_tag"],
                    "bundle_path": bundle_path,
                    "memory_role": item["memory_role"],
                    "domain_tags": list(item["domain_tags"]),
                    "audience_tags": list(item["audience_tags"]),
                    "proof_kind": item["proof_kind"],
                    "proof_strength": item["proof_strength"],
                    "artifact_backed": item["artifact_backed"],
                    "usage_modes": list(item["usage_modes"]),
                    "runtime_context_backed": True,
                },
            }
        )
    return hydrated


def load_persisted_feezie_anonymized_proof_payload() -> dict[str, Any] | None:
    payload = load_persisted_feezie_runtime_context_bundle()
    if payload is None:
        return None
    lessons = [
        {
            "id": item["provenance_hash"],
            "macro_thesis": item["macro_thesis"],
            "public_takeaway": item["public_takeaway"],
            "public_proof": item["public_proof"],
            "safe_angle": item["safe_angle"],
            "topic_tags": list(item["topic_tags"]),
            "visibility": "public_safe",
            "workspace_scope": "shared_pattern",
            "source_kind": "feezie_runtime_context",
        }
        for item in payload["anonymized_proof_records"]
    ]
    return {
        "schema_version": "content_safe_operator_lessons_runtime_projection/v1",
        "generated_at": payload["generated_at"],
        "workspace": "linkedin-content-os",
        "lessons": lessons,
        "counts": {"total": len(lessons)},
        "data_policy": {
            "derived_public_safe_only": True,
            "raw_source_content_included": False,
            "private_identifiers_included": False,
        },
    }


def _feezie_runtime_context_status_shell(
    *,
    checked_at: str,
    context_generated_at: str | None,
    age_seconds: int | None,
    state: str,
    reason_code: str,
) -> dict[str, Any]:
    return {
        "schema_version": FEEZIE_RUNTIME_CONTEXT_STATUS_SCHEMA,
        "checked_at": checked_at,
        "context_generated_at": context_generated_at,
        "age_seconds": age_seconds,
        "stale_after_seconds": FEEZIE_RUNTIME_CONTEXT_STALE_AFTER_SECONDS,
        "state": state,
        "ready": False,
        "reason_codes": [reason_code],
        "persona_canon": {"ready": False, "count": 0},
        "approved_voice_examples": {"ready": False, "count": 0},
        "anonymized_proof": {"ready": False, "count": 0},
        "source_grounding": {
            "ready": False,
            "strategy_contract_present": False,
            "content_integrity_valid": False,
        },
        "data_policy": {"aggregate_only": True, "private_context_included": False},
    }


def build_feezie_private_runtime_context_status(
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = _normalized_now(now)
    checked_at = current.isoformat().replace("+00:00", "Z")
    try:
        persisted = get_snapshot_payload(
            FEEZIE_RUNTIME_CONTEXT_WORKSPACE_KEY,
            FEEZIE_RUNTIME_CONTEXT_SNAPSHOT_TYPE,
        )
    except Exception:
        return _feezie_runtime_context_status_shell(
            checked_at=checked_at,
            context_generated_at=None,
            age_seconds=None,
            state="invalid",
            reason_code="runtime_context_invalid",
        )
    if persisted is None:
        return _feezie_runtime_context_status_shell(
            checked_at=checked_at,
            context_generated_at=None,
            age_seconds=None,
            state="missing",
            reason_code="runtime_context_missing",
        )

    try:
        payload = validate_feezie_runtime_context_bundle(persisted)
        context_generated_at, age_seconds = _runtime_context_age_seconds(
            payload,
            now=current,
        )
    except Exception:
        return _feezie_runtime_context_status_shell(
            checked_at=checked_at,
            context_generated_at=None,
            age_seconds=None,
            state="invalid",
            reason_code="runtime_context_invalid",
        )

    context_generated_at_text = str(payload["generated_at"])
    if context_generated_at > current + timedelta(
        seconds=FEEZIE_RUNTIME_CONTEXT_MAX_FUTURE_SKEW_SECONDS
    ):
        status = _feezie_runtime_context_status_shell(
            checked_at=checked_at,
            context_generated_at=context_generated_at_text,
            age_seconds=age_seconds,
            state="invalid",
            reason_code="runtime_context_future",
        )
        status["source_grounding"] = {
            "ready": False,
            "strategy_contract_present": True,
            "content_integrity_valid": True,
        }
        return status
    if context_generated_at < current - timedelta(
        seconds=FEEZIE_RUNTIME_CONTEXT_STALE_AFTER_SECONDS
    ):
        status = _feezie_runtime_context_status_shell(
            checked_at=checked_at,
            context_generated_at=context_generated_at_text,
            age_seconds=age_seconds,
            state="stale",
            reason_code="runtime_context_stale",
        )
        status["source_grounding"] = {
            "ready": False,
            "strategy_contract_present": True,
            "content_integrity_valid": True,
        }
        return status

    chunks = payload["persona_chunks"]
    voice_example_count = sum(
        1
        for item in chunks
        if item.get("bundle_path") == "prompts/content_examples.md" and item.get("memory_role") == "example"
    )
    proof_count = len(payload["anonymized_proof_records"])
    persona_count = len(chunks)
    facets = {
        "persona_canon": {"ready": persona_count > 0, "count": persona_count},
        "approved_voice_examples": {"ready": voice_example_count > 0, "count": voice_example_count},
        "anonymized_proof": {"ready": proof_count > 0, "count": proof_count},
        "source_grounding": {"ready": True, "strategy_contract_present": True, "content_integrity_valid": True},
    }
    reason_codes = [
        code
        for code, ready in (
            ("persona_canon_missing", facets["persona_canon"]["ready"]),
            ("approved_voice_examples_missing", facets["approved_voice_examples"]["ready"]),
            ("anonymized_proof_missing", facets["anonymized_proof"]["ready"]),
            ("source_grounding_missing", facets["source_grounding"]["ready"]),
        )
        if not ready
    ]
    ready = not reason_codes
    return {
        "schema_version": FEEZIE_RUNTIME_CONTEXT_STATUS_SCHEMA,
        "checked_at": checked_at,
        "context_generated_at": context_generated_at_text,
        "age_seconds": age_seconds,
        "stale_after_seconds": FEEZIE_RUNTIME_CONTEXT_STALE_AFTER_SECONDS,
        "state": "ready" if ready else "degraded",
        "ready": ready,
        "reason_codes": reason_codes,
        **facets,
        "data_policy": {"aggregate_only": True, "private_context_included": False},
    }
