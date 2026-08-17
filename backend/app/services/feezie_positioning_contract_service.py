from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

import yaml


POSITIONING_CONTRACT_PATH = Path("workspaces/linkedin-content-os/docs/positioning_contract.md")
EDITORIAL_MIX_PATH = Path("workspaces/linkedin-content-os/docs/editorial_mix.md")
POSITIONING_SCHEMA = "positioning_contract/v1"
EDITORIAL_MIX_SCHEMA = "editorial_mix/v1"
APPROVED_STATUS = "owner_approved"

CAREER_SIGNAL_VALUES = {"education_anchor", "bridge", "tech_proof"}
EMPLOYER_PROXIMITY_VALUES = {"personal_build", "public_event", "generalized_work", "employer_specific"}
EMPLOYER_SAFETY_VALUES = {"pass", "owner_review_required", "blocked"}
PROOF_POSTURE_VALUES = {
    "verified_public",
    "verified_private_anonymize",
    "owner_confirmation_required",
    "principle_only",
    "missing",
}
INTENT_VALUES = {"value", "invitation", "personal"}
LEGACY_INTENT_ALIASES = {"sales": "invitation"}


class FeeziePositioningContractError(RuntimeError):
    pass


def _default_repo_root(module_file: Path | None = None) -> Path:
    """Resolve both repository and flattened Railway backend layouts.

    In the repository this module lives below ``backend/app/services`` and the
    strategy workspace is three parents up. Railway runs the staged ``backend``
    directory as the application root, so the same module lives below
    ``app/services`` and the workspace is two parents up. Prefer the first
    candidate that actually contains both required owner-approved contracts.
    """

    resolved_module = (module_file or Path(__file__)).resolve()
    candidates = (resolved_module.parents[3], resolved_module.parents[2])
    for candidate in candidates:
        if (candidate / POSITIONING_CONTRACT_PATH).is_file() and (
            candidate / EDITORIAL_MIX_PATH
        ).is_file():
            return candidate
    return candidates[0]


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _string_list(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list):
        raise FeeziePositioningContractError(f"{field} must be a list.")
    cleaned = [_clean_text(item) for item in value]
    if not cleaned or any(not item for item in cleaned):
        raise FeeziePositioningContractError(f"{field} must contain non-empty strings.")
    return cleaned


def _mapping(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FeeziePositioningContractError(f"{field} must be a mapping.")
    return dict(value)


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise FeeziePositioningContractError(f"{field} must be a positive integer.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise FeeziePositioningContractError(f"{field} must be a positive integer.") from exc
    if parsed <= 0:
        raise FeeziePositioningContractError(f"{field} must be a positive integer.")
    return parsed


def normalize_feezie_intent(value: Any, *, default: str | None = None) -> str:
    """Return the owner-approved post intent, normalizing only known legacy aliases."""

    cleaned = _clean_text(value).lower()
    if not cleaned and default is not None:
        cleaned = _clean_text(default).lower()
    cleaned = LEGACY_INTENT_ALIASES.get(cleaned, cleaned)
    if cleaned not in INTENT_VALUES:
        raise ValueError(f"Unsupported FEEZIE intent: {value!r}")
    return cleaned


def normalize_feezie_pillar(
    value: Any,
    *,
    default: str | None = None,
    repo_root: Path | None = None,
) -> str:
    """Resolve an approved pillar id, label, or alias to its canonical id."""

    cleaned = _clean_text(value).lower()
    if not cleaned and default is not None:
        cleaned = _clean_text(default).lower()
    if not cleaned:
        raise ValueError("FEEZIE canonical pillar is required.")

    contract = load_feezie_strategy_contract(repo_root)
    for pillar in contract["editorial_mix"]["pillars"]:
        pillar_id = _clean_text(pillar.get("id")).lower()
        aliases = {
            pillar_id,
            _clean_text(pillar.get("label")).lower(),
            *(_clean_text(item).lower() for item in pillar.get("aliases") or []),
        }
        if cleaned in aliases:
            return pillar_id
    raise ValueError(f"Unsupported FEEZIE canonical pillar: {value!r}")


def _parse_markdown_contract(path: Path) -> tuple[dict[str, Any], str, str]:
    if not path.exists():
        raise FeeziePositioningContractError(f"Required FEEZIE contract is missing: {path}")
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        raise FeeziePositioningContractError(f"FEEZIE contract has no YAML frontmatter: {path}")
    parts = raw.split("---", 2)
    if len(parts) != 3:
        raise FeeziePositioningContractError(f"FEEZIE contract frontmatter is malformed: {path}")
    try:
        frontmatter = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        raise FeeziePositioningContractError(f"FEEZIE contract YAML is invalid: {path}") from exc
    if not isinstance(frontmatter, dict):
        raise FeeziePositioningContractError(f"FEEZIE contract frontmatter must be a mapping: {path}")
    body = parts[2].lstrip()
    if not body.startswith("# "):
        raise FeeziePositioningContractError(f"FEEZIE contract must have a document title: {path}")
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return frontmatter, body, digest


def _require_approved(frontmatter: dict[str, Any], *, schema: str, path: Path) -> None:
    if _clean_text(frontmatter.get("schema_version")) != schema:
        raise FeeziePositioningContractError(f"Unexpected schema_version in {path}; expected {schema}.")
    if _clean_text(frontmatter.get("status")) != APPROVED_STATUS:
        raise FeeziePositioningContractError(f"FEEZIE contract is not owner-approved: {path}")
    if not _clean_text(frontmatter.get("owner")):
        raise FeeziePositioningContractError(f"FEEZIE contract has no owner: {path}")
    if not _clean_text(frontmatter.get("approved_at")):
        raise FeeziePositioningContractError(f"FEEZIE contract has no approval date: {path}")


def _validate_repo_reference(
    repo_root: Path,
    value: Any,
    *,
    field: str,
    allow_missing_under: str | None = None,
) -> str:
    relative = _clean_text(value)
    if not relative:
        raise FeeziePositioningContractError(f"{field} must name a repository file.")
    candidate = (repo_root / relative).resolve()
    try:
        candidate.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise FeeziePositioningContractError(f"{field} escapes the repository root.") from exc
    missing_private_reference = bool(
        allow_missing_under
        and relative.startswith(allow_missing_under)
        and not candidate.exists()
    )
    if not candidate.is_file() and not missing_private_reference:
        raise FeeziePositioningContractError(f"{field} references a missing file: {relative}")
    return relative


def _validate_positioning(
    frontmatter: dict[str, Any],
    *,
    repo_root: Path,
    path: Path,
    allow_missing_private_identity_files: bool = False,
) -> dict[str, Any]:
    _require_approved(frontmatter, schema=POSITIONING_SCHEMA, path=path)
    identity_sources = _string_list(frontmatter.get("canonical_identity_sources"), field="canonical_identity_sources")
    for source in identity_sources:
        _validate_repo_reference(
            repo_root,
            source,
            field="canonical_identity_sources",
            allow_missing_under=(
                "knowledge/persona/feeze/"
                if allow_missing_private_identity_files
                else None
            ),
        )

    positioning_model = _string_list(frontmatter.get("positioning_model"), field="positioning_model")
    audience_priority = _mapping(frontmatter.get("audience_priority"), field="audience_priority")
    primary_audiences = _string_list(audience_priority.get("primary"), field="audience_priority.primary")
    bridge_audiences = _string_list(audience_priority.get("bridge"), field="audience_priority.bridge")

    enum_contracts = {
        "career_signal_values": CAREER_SIGNAL_VALUES,
        "employer_proximity_values": EMPLOYER_PROXIMITY_VALUES,
        "employer_safety_values": EMPLOYER_SAFETY_VALUES,
        "proof_posture_values": PROOF_POSTURE_VALUES,
    }
    normalized_enums: dict[str, list[str]] = {}
    for field, expected in enum_contracts.items():
        values = _string_list(frontmatter.get(field), field=field)
        if set(values) != expected:
            raise FeeziePositioningContractError(f"{field} must equal {sorted(expected)}.")
        normalized_enums[field] = values

    career_posture = _mapping(frontmatter.get("career_posture"), field="career_posture")
    if _clean_text(career_posture.get("mode")) != "proof_led_technology_expansion":
        raise FeeziePositioningContractError("career_posture.mode must be proof_led_technology_expansion.")
    if career_posture.get("public_job_search") is not False:
        raise FeeziePositioningContractError("career_posture.public_job_search must remain false.")
    if _clean_text(career_posture.get("explicit_transition_default")) != "blocked":
        raise FeeziePositioningContractError("career_posture.explicit_transition_default must be blocked.")
    if _clean_text(career_posture.get("employer_specific_default")) != "owner_review_required":
        raise FeeziePositioningContractError("career_posture.employer_specific_default must be owner_review_required.")
    if career_posture.get("publication_requires_owner_approval") is not True:
        raise FeeziePositioningContractError("career_posture.publication_requires_owner_approval must be true.")

    generation_disallowed_moves = _string_list(
        frontmatter.get("generation_disallowed_moves"),
        field="generation_disallowed_moves",
    )
    generation_quality_contract = _mapping(
        frontmatter.get("generation_quality_contract"),
        field="generation_quality_contract",
    )
    required_option_count = _positive_int(
        generation_quality_contract.get("required_option_count"),
        field="generation_quality_contract.required_option_count",
    )
    maximum_option_count = _positive_int(
        generation_quality_contract.get("maximum_option_count"),
        field="generation_quality_contract.maximum_option_count",
    )
    critic_dimensions = _string_list(
        generation_quality_contract.get("critic_dimensions"),
        field="generation_quality_contract.critic_dimensions",
    )
    hook_variants_per_option = _positive_int(
        generation_quality_contract.get("hook_variants_per_option"),
        field="generation_quality_contract.hook_variants_per_option",
    )
    if required_option_count != 2 or maximum_option_count != 2:
        raise FeeziePositioningContractError("generation_quality_contract must require and cap generation at exactly two options.")
    if generation_quality_contract.get("meaningful_difference_required") is not True:
        raise FeeziePositioningContractError("generation_quality_contract must require meaningful draft difference.")
    if generation_quality_contract.get("independent_critic_required") is not True:
        raise FeeziePositioningContractError("generation_quality_contract must require an independent critic.")
    if critic_dimensions != ["truth", "safety", "intent", "voice", "hook"]:
        raise FeeziePositioningContractError("generation_quality_contract critic dimensions must be truth, safety, intent, voice, and hook.")
    if hook_variants_per_option != 8:
        raise FeeziePositioningContractError("generation_quality_contract must require exactly eight hook variants per option.")
    if generation_quality_contract.get("owner_review_requires_critic_ready") is not True:
        raise FeeziePositioningContractError("generation_quality_contract must block owner review until critic-ready.")
    standup_relevance = _mapping(frontmatter.get("standup_relevance"), field="standup_relevance")
    if set(standup_relevance) != {"jean_claude", "yoda", "neo"}:
        raise FeeziePositioningContractError("standup_relevance must define jean_claude, yoda, and neo.")

    return {
        "schema_version": POSITIONING_SCHEMA,
        "status": APPROVED_STATUS,
        "approved_at": _clean_text(frontmatter.get("approved_at")),
        "owner": _clean_text(frontmatter.get("owner")),
        "canonical_identity_sources": identity_sources,
        "positioning_model": positioning_model,
        "audience_priority": {"primary": primary_audiences, "bridge": bridge_audiences},
        **normalized_enums,
        "career_posture": {
            "mode": "proof_led_technology_expansion",
            "public_job_search": False,
            "explicit_transition_default": "blocked",
            "employer_specific_default": "owner_review_required",
            "publication_requires_owner_approval": True,
        },
        "generation_disallowed_moves": generation_disallowed_moves,
        "generation_quality_contract": {
            "required_option_count": required_option_count,
            "maximum_option_count": maximum_option_count,
            "meaningful_difference_required": True,
            "independent_critic_required": True,
            "critic_dimensions": critic_dimensions,
            "hook_variants_per_option": hook_variants_per_option,
            "owner_review_requires_critic_ready": True,
        },
        "standup_relevance": {key: _clean_text(value) for key, value in standup_relevance.items()},
    }


def _validate_editorial(
    frontmatter: dict[str, Any],
    *,
    repo_root: Path,
    path: Path,
    allow_missing_private_identity_files: bool = False,
) -> dict[str, Any]:
    _require_approved(frontmatter, schema=EDITORIAL_MIX_SCHEMA, path=path)
    positioning_contract = _validate_repo_reference(
        repo_root,
        frontmatter.get("positioning_contract"),
        field="positioning_contract",
    )
    canonical_pillars = _validate_repo_reference(
        repo_root,
        frontmatter.get("canonical_pillars"),
        field="canonical_pillars",
        allow_missing_under=(
            "knowledge/persona/feeze/"
            if allow_missing_private_identity_files
            else None
        ),
    )
    qualification_runtime = _validate_repo_reference(
        repo_root,
        frontmatter.get("qualification_runtime"),
        field="qualification_runtime",
    )

    raw_pillars = frontmatter.get("pillars")
    if not isinstance(raw_pillars, list) or not raw_pillars:
        raise FeeziePositioningContractError("pillars must be a non-empty list.")
    pillars: list[dict[str, Any]] = []
    pillar_ids: set[str] = set()
    for index, raw_pillar in enumerate(raw_pillars):
        pillar = _mapping(raw_pillar, field=f"pillars[{index}]")
        pillar_id = _clean_text(pillar.get("id"))
        label = _clean_text(pillar.get("label"))
        career_signal = _clean_text(pillar.get("career_signal"))
        aliases = _string_list(pillar.get("aliases"), field=f"pillars[{index}].aliases")
        if not pillar_id or pillar_id in pillar_ids:
            raise FeeziePositioningContractError("Every editorial pillar must have a unique id.")
        if not label:
            raise FeeziePositioningContractError("Every editorial pillar must have a label.")
        if career_signal not in CAREER_SIGNAL_VALUES:
            raise FeeziePositioningContractError(f"Unsupported career_signal for pillar {pillar_id}.")
        pillar_ids.add(pillar_id)
        pillars.append(
            {
                "id": pillar_id,
                "label": label,
                "career_signal": career_signal,
                "aliases": aliases,
            }
        )

    rolling_topic_mix = _mapping(frontmatter.get("rolling_topic_mix"), field="rolling_topic_mix")
    rolling_window = _positive_int(rolling_topic_mix.get("window"), field="rolling_topic_mix.window")
    rolling_counts_raw = _mapping(rolling_topic_mix.get("counts"), field="rolling_topic_mix.counts")
    rolling_counts = {
        _clean_text(key): _positive_int(value, field=f"rolling_topic_mix.counts.{key}")
        for key, value in rolling_counts_raw.items()
    }
    if set(rolling_counts) != pillar_ids or sum(rolling_counts.values()) != rolling_window:
        raise FeeziePositioningContractError("rolling_topic_mix counts must cover every pillar and sum to the window.")

    intent_mix = _mapping(frontmatter.get("intent_mix"), field="intent_mix")
    intent_window = _positive_int(intent_mix.get("window"), field="intent_mix.window")
    intent_counts_raw = _mapping(intent_mix.get("counts"), field="intent_mix.counts")
    intent_counts = {
        _clean_text(key): _positive_int(value, field=f"intent_mix.counts.{key}")
        for key, value in intent_counts_raw.items()
    }
    if set(intent_counts) != INTENT_VALUES or sum(intent_counts.values()) != intent_window:
        raise FeeziePositioningContractError("intent_mix must define value, invitation, and personal counts that sum to the window.")

    measurement = _mapping(frontmatter.get("measurement"), field="measurement")
    observation_windows = _mapping(
        measurement.get("observation_windows_hours"),
        field="measurement.observation_windows_hours",
    )
    normalized_observation_windows = {
        _clean_text(key): _positive_int(
            value,
            field=f"measurement.observation_windows_hours.{key}",
        )
        for key, value in observation_windows.items()
    }
    if normalized_observation_windows != {
        "metrics_24h_recorded": 24,
        "metrics_7d_recorded": 168,
    }:
        raise FeeziePositioningContractError(
            "measurement observation windows must define the 24-hour and 7-day event windows."
        )

    learning_gate = _mapping(measurement.get("learning_gate"), field="measurement.learning_gate")
    normalized_learning_gate = {
        "minimum_owner_decisions": _positive_int(
            learning_gate.get("minimum_owner_decisions"),
            field="measurement.learning_gate.minimum_owner_decisions",
        ),
        "minimum_confirmed_publications": _positive_int(
            learning_gate.get("minimum_confirmed_publications"),
            field="measurement.learning_gate.minimum_confirmed_publications",
        ),
        "minimum_complete_feedback_posts": _positive_int(
            learning_gate.get("minimum_complete_feedback_posts"),
            field="measurement.learning_gate.minimum_complete_feedback_posts",
        ),
    }
    primary_kpi = _clean_text(measurement.get("primary_kpi"))
    if primary_kpi != "meaningful_target_audience_conversations_per_10_assessed_posts":
        raise FeeziePositioningContractError("measurement.primary_kpi is not the approved portfolio KPI.")

    initial_pilot = _mapping(measurement.get("initial_pilot"), field="measurement.initial_pilot")
    pilot_id = _clean_text(initial_pilot.get("id"))
    pilot_target = _positive_int(initial_pilot.get("target_count"), field="measurement.initial_pilot.target_count")
    pilot_treatments_raw = _mapping(initial_pilot.get("treatments"), field="measurement.initial_pilot.treatments")
    pilot_treatments = {
        _clean_text(key): _positive_int(value, field=f"measurement.initial_pilot.treatments.{key}")
        for key, value in pilot_treatments_raw.items()
    }
    expected_pilot_treatments = {
        "practical_ai_systems",
        "education_or_trust",
        "operator_story_personal_technology",
        "operator_story_education_community",
    }
    if (
        not pilot_id
        or set(pilot_treatments) != expected_pilot_treatments
        or sum(pilot_treatments.values()) != pilot_target
    ):
        raise FeeziePositioningContractError(
            "measurement.initial_pilot treatments must define the approved six-post 2/2/1/1 pilot."
        )

    weekly_model = _mapping(frontmatter.get("weekly_model"), field="weekly_model")
    max_posts = _positive_int(weekly_model.get("max_posts"), field="weekly_model.max_posts")
    minimum_consequence = _positive_int(
        weekly_model.get("minimum_human_or_operating_consequence_posts"),
        field="weekly_model.minimum_human_or_operating_consequence_posts",
    )
    if weekly_model.get("may_publish_fewer") is not True or minimum_consequence > max_posts:
        raise FeeziePositioningContractError("weekly_model must permit fewer posts and keep its consequence minimum within max_posts.")

    planner = _mapping(frontmatter.get("planner"), field="planner")
    max_recommendations = _positive_int(planner.get("max_recommendations"), field="planner.max_recommendations")
    max_development_cards = _positive_int(planner.get("max_development_cards"), field="planner.max_development_cards")
    eligible_routes = _string_list(planner.get("eligible_net_new_routes"), field="planner.eligible_net_new_routes")
    if max_recommendations < len(pillars) or max_development_cards > max_recommendations:
        raise FeeziePositioningContractError("planner card limits cannot satisfy the approved pillar contract.")
    if planner.get("reserve_each_represented_pillar") is not True:
        raise FeeziePositioningContractError("planner.reserve_each_represented_pillar must be true.")
    if eligible_routes != ["pass"]:
        raise FeeziePositioningContractError("planner.eligible_net_new_routes must be exactly ['pass'].")
    if _clean_text(planner.get("missing_pillar_behavior")) != "warn_without_filler":
        raise FeeziePositioningContractError("planner.missing_pillar_behavior must be warn_without_filler.")

    return {
        "schema_version": EDITORIAL_MIX_SCHEMA,
        "status": APPROVED_STATUS,
        "approved_at": _clean_text(frontmatter.get("approved_at")),
        "owner": _clean_text(frontmatter.get("owner")),
        "positioning_contract": positioning_contract,
        "canonical_pillars": canonical_pillars,
        "qualification_runtime": qualification_runtime,
        "qualification_sop_recovery_ref": _clean_text(frontmatter.get("qualification_sop_recovery_ref")),
        "pillars": pillars,
        "rolling_topic_mix": {"window": rolling_window, "counts": rolling_counts},
        "intent_mix": {"window": intent_window, "counts": intent_counts},
        "measurement": {
            "observation_windows_hours": normalized_observation_windows,
            "learning_gate": normalized_learning_gate,
            "primary_kpi": primary_kpi,
            "initial_pilot": {
                "id": pilot_id,
                "target_count": pilot_target,
                "treatments": pilot_treatments,
            },
        },
        "weekly_model": {
            "max_posts": max_posts,
            "may_publish_fewer": True,
            "minimum_human_or_operating_consequence_posts": minimum_consequence,
        },
        "planner": {
            "max_recommendations": max_recommendations,
            "max_development_cards": max_development_cards,
            "reserve_each_represented_pillar": True,
            "eligible_net_new_routes": eligible_routes,
            "missing_pillar_behavior": "warn_without_filler",
        },
    }


def _load_feezie_strategy_contract(
    repo_root_text: str,
    *,
    allow_missing_private_identity_files: bool = False,
) -> dict[str, Any]:
    repo_root = Path(repo_root_text).resolve()
    positioning_path = repo_root / POSITIONING_CONTRACT_PATH
    editorial_path = repo_root / EDITORIAL_MIX_PATH
    positioning_frontmatter, _, positioning_hash = _parse_markdown_contract(positioning_path)
    editorial_frontmatter, _, editorial_hash = _parse_markdown_contract(editorial_path)
    positioning = _validate_positioning(
        positioning_frontmatter,
        repo_root=repo_root,
        path=positioning_path,
        allow_missing_private_identity_files=allow_missing_private_identity_files,
    )
    editorial_mix = _validate_editorial(
        editorial_frontmatter,
        repo_root=repo_root,
        path=editorial_path,
        allow_missing_private_identity_files=allow_missing_private_identity_files,
    )
    if editorial_mix["positioning_contract"] != POSITIONING_CONTRACT_PATH.as_posix():
        raise FeeziePositioningContractError(
            "editorial_mix.positioning_contract must reference the loaded positioning contract."
        )
    if editorial_mix["canonical_pillars"] not in positioning["canonical_identity_sources"]:
        raise FeeziePositioningContractError(
            "editorial_mix.canonical_pillars must be one of the positioning contract's canonical identity sources."
        )
    contract_hash = hashlib.sha256(f"{positioning_hash}:{editorial_hash}".encode("utf-8")).hexdigest()
    return {
        "schema_version": "feezie_strategy_contract/v1",
        "contract_hash": contract_hash,
        "positioning": positioning,
        "editorial_mix": editorial_mix,
        "sources": {
            "positioning": {
                "path": POSITIONING_CONTRACT_PATH.as_posix(),
                "sha256": positioning_hash,
            },
            "editorial_mix": {
                "path": EDITORIAL_MIX_PATH.as_posix(),
                "sha256": editorial_hash,
            },
        },
    }


def _load_persisted_strategy_contract() -> dict[str, Any]:
    try:
        from app.services.feezie_runtime_context_service import (
            FeezieRuntimeContextError,
            load_persisted_feezie_strategy_contract,
        )
    except Exception as exc:
        raise FeeziePositioningContractError(
            "Persisted FEEZIE runtime strategy context is unavailable."
        ) from exc

    try:
        persisted = load_persisted_feezie_strategy_contract()
    except FeezieRuntimeContextError as exc:
        raise FeeziePositioningContractError(
            "Persisted FEEZIE runtime strategy context is invalid."
        ) from exc
    except Exception as exc:
        raise FeeziePositioningContractError(
            "Persisted FEEZIE runtime strategy context is unavailable."
        ) from exc
    if persisted is None:
        raise FeeziePositioningContractError(
            "Required FEEZIE strategy files are missing and no private runtime context is available."
        )
    return copy.deepcopy(persisted)


def load_feezie_strategy_contract(repo_root: Path | None = None) -> dict[str, Any]:
    resolved_root = (repo_root or _default_repo_root()).resolve()
    positioning_path = resolved_root / POSITIONING_CONTRACT_PATH
    editorial_path = resolved_root / EDITORIAL_MIX_PATH
    if positioning_path.is_file() or editorial_path.is_file():
        try:
            return copy.deepcopy(_load_feezie_strategy_contract(str(resolved_root)))
        except FeeziePositioningContractError:
            # A privacy-reduced Railway/public checkout intentionally keeps the
            # approved strategy documents while omitting private persona canon.
            # Revalidate every other contract field and repository reference;
            # only missing references beneath the canonical private persona
            # root are relaxed here.
            staged_contract = _load_feezie_strategy_contract(
                str(resolved_root),
                allow_missing_private_identity_files=True,
            )
            persisted = _load_persisted_strategy_contract()
            if persisted != staged_contract:
                raise FeeziePositioningContractError(
                    "Persisted FEEZIE runtime strategy context does not match the staged strategy contracts."
                )
            return copy.deepcopy(persisted)

    return _load_persisted_strategy_contract()


def build_feezie_generation_disallowed_moves(
    *,
    audience: str,
    grounding_mode: str,
    repo_root: Path | None = None,
) -> list[str]:
    strategy_contract = load_feezie_strategy_contract(repo_root)
    moves = [
        "Do not invent outcomes, causal claims, or cleaner metrics than the approved proof actually states.",
        "Do not borrow names, employers, systems, or projects that are not present in the approved claims, proof packets, or story beats.",
    ]
    moves.extend(strategy_contract["positioning"]["generation_disallowed_moves"])
    if audience == "tech_ai":
        moves.extend(
            [
                "Do not drift into generic leadership, admissions, school-process, or community anecdotes for AI/operator posts.",
                "Do not use generic AI filler like seamless integration, unlock potential, efficiency skyrocketed, or game changer.",
            ]
        )
    if grounding_mode == "principle_only":
        moves.append(
            "Do not use named metrics, case studies, employers, or systems unless they appear directly in the approved primary claims."
        )
    return moves


def clear_feezie_strategy_contract_cache() -> None:
    cache_clear = getattr(_load_feezie_strategy_contract, "cache_clear", None)
    if callable(cache_clear):
        cache_clear()
