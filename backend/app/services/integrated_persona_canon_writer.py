from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

from app.persona_promotion_targets import (
    TARGET_CLAIMS,
    TARGET_CONTENT_PILLARS,
    TARGET_DECISION_PRINCIPLES,
    TARGET_VOICE,
    validate_persona_promotion_target,
)
from app.services.persona_bundle_writer import (
    remove_promotion_items_from_bundle,
    resolve_persona_bundle_state_root,
    write_promotion_items_to_bundle,
)
from app.services.persona_learning_service import (
    AUTOMATIC_RULE,
    GOVERNED_WRITER_ID,
    PersonaGovernanceBlocked,
)


_AUTOMATIC_TARGETS = frozenset(
    {
        TARGET_CLAIMS,
        TARGET_CONTENT_PILLARS,
        TARGET_DECISION_PRINCIPLES,
        TARGET_VOICE,
    }
)
_CLAIM_FIELDS = (
    ("voice_pattern", TARGET_VOICE, "phrase_candidate"),
    ("pattern", TARGET_VOICE, "phrase_candidate"),
    ("decision_principle", TARGET_DECISION_PRINCIPLES, "framework"),
    ("content_pillar", TARGET_CONTENT_PILLARS, "framework"),
    ("claim", TARGET_CLAIMS, "claim"),
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _sha256_file(path: Path) -> str | None:
    if path.is_symlink() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _promotion_item(request: Mapping[str, Any]) -> dict[str, Any]:
    claim = request.get("claim")
    if not isinstance(claim, Mapping):
        raise PersonaGovernanceBlocked("persona promotion requires a structured claim")
    selected_field = ""
    default_target = ""
    item_kind = ""
    content = ""
    for field, target, kind in _CLAIM_FIELDS:
        candidate = _clean(claim.get(field))
        if candidate:
            selected_field = field
            default_target = target
            item_kind = kind
            content = candidate
            break
    if not content:
        raise PersonaGovernanceBlocked(
            "automatic persona promotion requires a bounded recurring-pattern claim"
        )
    requested_target = _clean(claim.get("target_file")) or default_target
    try:
        target_file = validate_persona_promotion_target(requested_target)
    except ValueError as exc:
        raise PersonaGovernanceBlocked("automatic persona target is not governed") from exc
    if target_file not in _AUTOMATIC_TARGETS:
        raise PersonaGovernanceBlocked(
            "automatic recurring-pattern promotion cannot write this identity-risk target"
        )
    return {
        "id": f"automatic-pattern:{request['persona_candidate_id']}",
        "label": _clean(claim.get("label")) or "Recurring owner-approved pattern",
        "content": content,
        "kind": item_kind,
        "target_file": target_file,
        "evidence": (
            "Derived from three exact owner-approved and confirmed-published posts "
            "across at least two independent source or owner-experience contexts."
        ),
        "promotion_rule": AUTOMATIC_RULE,
        "canon_version": request["canon_version"],
        "persona_candidate_id": request["persona_candidate_id"],
        "claim_field": selected_field,
    }


class IntegratedPersonaCanonWriter:
    """Governed adapter from recurring-pattern eligibility into private canon.

    The adapter accepts only the approved automatic rule and a bounded set of
    reversible targets.  The tracked seed is never mutated; existing persona
    bundle helpers write only to the configured private canonical overlay.
    """

    def __call__(self, raw_request: Mapping[str, Any]) -> Mapping[str, Any]:
        request = dict(raw_request)
        if request.get("schema_version") != "persona_canon_write_request/v1":
            raise PersonaGovernanceBlocked("unsupported persona writer request schema")
        if request.get("writer_id") != GOVERNED_WRITER_ID:
            raise PersonaGovernanceBlocked("persona writer authority mismatch")
        action = request.get("action")
        if action == "promote":
            return self._promote(request)
        if action == "reverse":
            return self._reverse(request)
        raise PersonaGovernanceBlocked("unsupported persona canon action")

    @staticmethod
    def _promote(request: Mapping[str, Any]) -> Mapping[str, Any]:
        eligibility = request.get("eligibility")
        if (
            request.get("candidate_kind") != "reversible_pattern"
            or request.get("promotion_rule") != AUTOMATIC_RULE
            or not isinstance(eligibility, Mapping)
            or eligibility.get("automatic_promotion_eligible") is not True
            or int(eligibility.get("qualifying_post_count") or 0) < 3
            or int(eligibility.get("independent_context_count") or 0) < 2
        ):
            raise PersonaGovernanceBlocked("automatic persona eligibility is not proven")
        item = _promotion_item(request)
        target_file = item["target_file"]
        target_path = resolve_persona_bundle_state_root() / target_file
        before_sha256 = _sha256_file(target_path)
        result = write_promotion_items_to_bundle([item])
        target_result = dict(result.get("file_results", {}).get(target_file) or {})
        added = int(target_result.get("added") or 0)
        skipped = int(target_result.get("skipped") or 0)
        if added + skipped != 1:
            raise PersonaGovernanceBlocked("persona writer did not account for the promotion item")
        after_sha256 = _sha256_file(target_path)
        if not after_sha256:
            raise PersonaGovernanceBlocked("persona writer did not produce canonical state")
        return {
            "schema_version": "persona_canon_write_receipt/v1",
            "writer_id": GOVERNED_WRITER_ID,
            "action": "promote",
            "persona_candidate_id": request["persona_candidate_id"],
            "canon_version": request["canon_version"],
            "applied": True,
            "reversible": True,
            "artifact_refs": [f"private-persona:{target_file}"],
            "target_file": target_file,
            "promotion_item": item,
            "mutation_state": "added" if added == 1 else "bound_to_existing",
            "before_sha256": before_sha256,
            "after_sha256": after_sha256,
        }
    @staticmethod
    def _reverse(request: Mapping[str, Any]) -> Mapping[str, Any]:
        original = request.get("original_writer_receipt")
        if not isinstance(original, Mapping):
            raise PersonaGovernanceBlocked("persona reversal requires the original writer receipt")
        if (
            original.get("writer_id") != GOVERNED_WRITER_ID
            or original.get("action") != "promote"
            or original.get("persona_candidate_id") != request.get("persona_candidate_id")
            or original.get("canon_version") != request.get("canon_version")
        ):
            raise PersonaGovernanceBlocked("persona reversal receipt lineage mismatch")
        item = original.get("promotion_item")
        if not isinstance(item, Mapping):
            raise PersonaGovernanceBlocked("persona reversal is missing the exact promotion item")
        target_file = _clean(item.get("target_file"))
        if target_file not in _AUTOMATIC_TARGETS:
            raise PersonaGovernanceBlocked("persona reversal target is not governed")
        target_path = resolve_persona_bundle_state_root() / target_file
        before_sha256 = _sha256_file(target_path)
        mutation_state = original.get("mutation_state")
        removed = 0
        if mutation_state == "added":
            result = remove_promotion_items_from_bundle([dict(item)])
            removed = int(
                (result.get("file_results", {}).get(target_file) or {}).get("removed") or 0
            )
        elif mutation_state != "bound_to_existing":
            raise PersonaGovernanceBlocked("persona reversal mutation state is invalid")
        after_sha256 = _sha256_file(target_path)
        return {
            "schema_version": "persona_canon_write_receipt/v1",
            "writer_id": GOVERNED_WRITER_ID,
            "action": "reverse",
            "persona_candidate_id": request["persona_candidate_id"],
            "promotion_id": request["promotion_id"],
            "canon_version": request["canon_version"],
            "applied": True,
            "reversible": True,
            "artifact_refs": [f"private-persona:{target_file}"],
            "target_file": target_file,
            "mutation_state": (
                "removed" if removed == 1 else "already_absent"
                if mutation_state == "added" else "preserved_preexisting"
            ),
            "before_sha256": before_sha256,
            "after_sha256": after_sha256,
        }
