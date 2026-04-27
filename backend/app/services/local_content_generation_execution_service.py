from __future__ import annotations

import json
import os
import re
from typing import Any

from app.routes import content_generation as content_generation_module


LOCAL_TEMPLATE_PROVIDER = "local_template"
LOCAL_TEMPLATE_MODEL = "local-template-v1"
LOCAL_TEMPLATE_STOCK_LINES = {
    "the prompt is not the system. the workflow is.",
    "the edge comes from clarity, not from piling on more tools.",
    "that lesson showed up in the build before it showed up in the copy.",
    "that sounds smart right up until the handoff breaks.",
    "operator clarity wins.",
    "clarity keeps the advantage.",
    "that is what the build taught us.",
    "that is operator work.",
    "that is the operating model.",
    "that is the part worth carrying forward.",
    "ignore that if you want. the workflow will still expose it.",
}


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _ensure_sentence(text: str) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        return ""
    if cleaned.endswith((".", "!", "?")):
        return cleaned
    return f"{cleaned}."


def _primary_claim(brief: dict[str, Any]) -> str:
    return _ensure_sentence(str(brief.get("primary_claim") or ""))


def _proof_evidence(brief: dict[str, Any]) -> str:
    packet = _clean_text(brief.get("proof_packet"))
    if not packet:
        return ""
    if "->" in packet:
        packet = packet.split("->", 1)[1]
    elif ":" in packet:
        left, right = packet.split(":", 1)
        if _clean_text(left).lower() in {"proof", "evidence", "public-facing proof"}:
            packet = right
    return _ensure_sentence(packet)


def _story_sentence(brief: dict[str, Any]) -> str:
    story = _clean_text(brief.get("story_beat"))
    if not story:
        return ""
    return _ensure_sentence(story)


def _public_lane(brief: dict[str, Any]) -> str:
    lane = _clean_text(brief.get("public_lane"))
    if lane:
        return lane
    try:
        option_number = int(brief.get("option_number") or 1)
    except Exception:
        option_number = 1
    return content_generation_module._public_post_lane_for_option(option_number)


def _looks_internal_operator_catalog(text: str) -> bool:
    normalized = _clean_text(text).lower()
    if not normalized:
        return False
    if content_generation_module._looks_like_operator_catalog_sentence(normalized):
        return True
    marker_count = sum(1 for marker in content_generation_module.OPERATOR_CATALOG_MARKERS if marker in normalized)
    return marker_count >= 3


def _sanitize_public_copy(text: str) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        return ""
    cleaned = content_generation_module._rewrite_audience_slug_public_copy(cleaned)
    replacements = (
        (r"\bai clone\s*/\s*brain system\b", "the system"),
        (r"\bpersona soup\b", "raw context"),
        (r"\bproof packets?\b", "proof"),
        (r"\btyped core, proof, story, and example lanes\b", "clear context lanes"),
        (r"\btyped (?:core|proof|story|example|context|support) lanes?\b", "clear context lanes"),
        (r"\btyped lanes?\b", "clear lanes"),
        (r"\bdomain gates?\b", "topic guardrails"),
        (r"\bgreen[- ]or[- ]red board\b", "clear go/no-go check"),
        (r"\bproof lanes?\b", "evidence lanes"),
        (r"\brouted workspace snapshot\b", "shared context"),
        (r"\bdaily briefs\b", "operating rhythm"),
        (r"\bpersona review\b", "editorial review"),
        (r"\blong-form routing\b", "content routing"),
    )
    rewritten = cleaned
    for pattern, replacement in replacements:
        rewritten = re.sub(pattern, replacement, rewritten, flags=re.IGNORECASE)
    rewritten = content_generation_module._rewrite_public_system_phrases(rewritten)
    return rewritten


def _public_safe_operator_claim(brief: dict[str, Any], lane: str) -> str:
    raw_claim = _sanitize_public_copy(_primary_claim(brief))
    if raw_claim and not _looks_internal_operator_catalog(raw_claim):
        return raw_claim
    if lane == "market_insight":
        return "AI does not create the edge by itself. Clear operating context does."
    if lane == "build_in_public":
        return "The build made one thing obvious: context has to survive the handoff."
    return "If context dies in the handoff, AI just scales confusion."


def _trim_public_proof(brief: dict[str, Any]) -> str:
    evidence = _sanitize_public_copy(_proof_evidence(brief))
    if not evidence:
        return ""
    lane = _public_lane(brief)
    if _looks_internal_operator_catalog(evidence):
        if lane == "market_insight":
            return "The gains showed up when the workflow, handoff rules, and proof standard got clearer, not when more tooling was layered on."
        if lane == "build_in_public":
            return "Once the workflow carried context cleanly from one step to the next, the system became easier to trust."
        return "Clearer handoffs and clearer proof rules made the workflow more reliable."
    clauses = [segment.strip(" .") for segment in re.split(r"[;]", evidence) if segment.strip()]
    if not clauses:
        return _ensure_sentence(evidence)
    selected: list[str] = []
    metric_added = 0
    for clause in clauses:
        metric_count = len(re.findall(r"\b\d+(?:[.,]\d+)?%?\b", clause))
        if metric_count > 0:
            if metric_added >= 1:
                continue
            metric_added += 1
        selected.append(clause)
        if len(selected) >= 2:
            break
    compact = ". ".join(selected) if selected else clauses[0]
    return _ensure_sentence(compact)


def _bridge_line(mode: str) -> str:
    return {
        "operator_lesson": "The prompt is not the system. The workflow is.",
        "contrarian_reframe": "That sounds smart right up until the workflow slips.",
        "agree_and_extend": "Agreement is easy. Operational follow-through is harder.",
        "drama_tension": "That is where the friction usually shows up.",
        "story_with_payoff": "The lesson only counts if the work changed because of it.",
        "recognition": "That kind of signal is worth naming out loud.",
        "warning": "If that stays fuzzy, the output will drift.",
        "reframe": "That is the difference between sounding prepared and being operationally ready.",
    }.get(mode, "The workflow tells the truth faster than the prompt does.")


def _closing_line(mode: str) -> str:
    return {
        "operator_lesson": "The workflow still has to hold.",
        "contrarian_reframe": "Clarity has to come first.",
        "agree_and_extend": "Clarity is the part that scales.",
        "drama_tension": "That is when the work starts slipping.",
        "story_with_payoff": "That changed how the work ran.",
        "recognition": "That deserves more credit than it gets.",
        "warning": "Ignore that if you want. The workflow will still expose it.",
        "reframe": "The workflow still tells the truth.",
    }.get(mode, "Clarity has to come first.")


def _compose_option(brief: dict[str, Any]) -> str:
    mode = _clean_text(brief.get("framing_mode")) or "operator_lesson"
    lane = _public_lane(brief)
    claim = _ensure_sentence(_public_safe_operator_claim(brief, lane))
    proof = _trim_public_proof(brief)
    story = _ensure_sentence(_sanitize_public_copy(_story_sentence(brief)))
    if re.search(r"\bquiet inefficiency cleanup\b", story, flags=re.IGNORECASE):
        story = "The lesson came from cleaning up quiet workflow friction." if lane == "build_in_public" else ""

    paragraphs: list[str] = []
    if claim:
        paragraphs.append(claim)
    bridge_line = _bridge_line(mode)
    if lane == "market_insight":
        bridge_line = "The edge comes from clarity, not from piling on more tools."
    elif lane == "build_in_public":
        bridge_line = "That lesson showed up in the build before it showed up in the copy."
    bridge = _ensure_sentence(bridge_line)
    if bridge and bridge.lower() not in claim.lower():
        paragraphs.append(bridge)
    if proof:
        paragraphs.append(proof)
    if story:
        paragraphs.append(story)
    closing_line = _closing_line(mode)
    if lane == "market_insight":
        closing_line = "Clarity keeps the advantage."
    elif lane == "operator_lesson":
        closing_line = "Operator clarity wins."
    elif lane == "build_in_public":
        closing_line = "That is what the build taught us."
    closing = _ensure_sentence(closing_line)
    if closing:
        paragraphs.append(closing)
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)


def _public_replacement_line(lane: str) -> str:
    if lane == "market_insight":
        return "Clarity changed the operating edge."
    if lane == "build_in_public":
        return "The build only improved once context stopped getting lost."
    return "Context has to survive the handoff."


def _sanitize_public_option(option: str, lane: str) -> str:
    cleaned = (option or "").strip()
    if not cleaned:
        return cleaned
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", cleaned) if segment.strip()]
    revised: list[str] = []
    inserted_replacement = False
    replacement_line = _public_replacement_line(lane)
    for paragraph in paragraphs:
        sentences = [content_generation_module._ensure_sentence(sentence.strip()) for sentence in content_generation_module._split_sentences(paragraph) if sentence.strip()]
        kept: list[str] = []
        for sentence in sentences:
            normalized = _sanitize_public_copy(sentence)
            if " ".join(normalized.lower().split()) in content_generation_module.HOUSE_SCAFFOLD_SENTENCES:
                continue
            if _looks_internal_operator_catalog(normalized) or content_generation_module._internal_public_jargon_hits(normalized):
                if not inserted_replacement:
                    kept.append(replacement_line)
                    inserted_replacement = True
                continue
            kept.append(normalized)
        if kept:
            revised.append(" ".join(kept).strip())
    return "\n\n".join(paragraph for paragraph in revised if paragraph)


def _looks_like_label_paragraph(paragraph: str) -> bool:
    normalized = _clean_text(paragraph).strip(".")
    if not normalized:
        return False
    if content_generation_module._phrase_is_flat_label(normalized):
        return True
    if len(normalized.split()) > 5:
        return False
    if re.search(r"\b(?:is|are|was|were|be|am|do|does|did|have|has|had|will|can|should|could|would|not)\b", normalized, flags=re.IGNORECASE):
        return False
    words = re.findall(r"[A-Za-z0-9]+", normalized)
    if not words:
        return False
    if not all(word[:1].isupper() or word.isupper() for word in words):
        return False
    return True


def _stock_template_hit_count(option: str) -> int:
    hits = 0
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", option or "") if segment.strip()]
    for paragraph in paragraphs:
        normalized_paragraph = _clean_text(paragraph).lower()
        if normalized_paragraph in LOCAL_TEMPLATE_STOCK_LINES:
            hits += 1
            continue
        for sentence in content_generation_module._split_sentences(paragraph):
            normalized_sentence = _clean_text(sentence).lower()
            if normalized_sentence in LOCAL_TEMPLATE_STOCK_LINES:
                hits += 1
    return hits


def _opening_signature(option: str) -> str:
    first_line = content_generation_module._first_content_line(option).lower()
    terms = [
        token
        for token in re.findall(r"[a-z0-9]+", first_line)
        if token not in content_generation_module.STOPWORDS and token not in {"ai", "an"}
    ]
    return " ".join(terms[:4]).strip()


def _starts_with_persona_bio(option: str) -> bool:
    first_line = content_generation_module._first_content_line(option)
    return bool(re.match(r"^johnnie\b", first_line, flags=re.IGNORECASE))


def _local_publishability_failures(option: str, brief: content_generation_module.ContentOptionBrief | None) -> list[str]:
    failures: list[str] = []
    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", option or "") if segment.strip()]
    if _starts_with_persona_bio(option):
        failures.append("persona_bio_opening")
    if any(_looks_like_label_paragraph(paragraph) for paragraph in paragraphs):
        failures.append("label_paragraph")
    stock_hits = _stock_template_hit_count(option)
    if stock_hits >= 2:
        failures.append(f"stock_template_scaffold:{stock_hits}")
    if brief is not None:
        publishability = content_generation_module._publishability_score(option, brief)
        if publishability < 10:
            failures.append(f"publishability_low:{publishability}")
    return failures


def compose_local_template_options(context_packet: dict[str, Any]) -> list[str]:
    briefs = context_packet.get("planned_option_briefs")
    if not isinstance(briefs, list) or not briefs:
        return []
    options = [_compose_option(item) for item in briefs if isinstance(item, dict)][:3]
    deserialized_briefs = content_generation_module._deserialize_content_option_briefs(briefs)
    if options and deserialized_briefs:
        options = content_generation_module.finalize_planned_options(
            options=options,
            briefs=deserialized_briefs,
            grounding_mode=_clean_text(context_packet.get("grounding_mode")) or "principle_only",
        )
    sanitized_options: list[str] = []
    for index, option in enumerate(options):
        lane = _public_lane(briefs[index] if index < len(briefs) and isinstance(briefs[index], dict) else {})
        sanitized_options.append(_sanitize_public_option(option, lane))
    return sanitized_options


def evaluate_local_quality(context_packet: dict[str, Any], options: list[str]) -> dict[str, Any]:
    briefs = content_generation_module._deserialize_content_option_briefs(context_packet.get("planned_option_briefs"))
    primary_claims = [str(item) for item in (context_packet.get("primary_claims") or []) if str(item).strip()]
    proof_packets = [str(item) for item in (context_packet.get("proof_packets") or []) if str(item).strip()]
    story_beats = [str(item) for item in (context_packet.get("story_beats") or []) if str(item).strip()]
    grounding_mode = _clean_text(context_packet.get("grounding_mode")) or "principle_only"
    threshold = int(os.getenv("LOCAL_CODEX_QUALITY_GATE_THRESHOLD_PROOF", "76")) if grounding_mode == "proof_ready" else int(
        os.getenv("LOCAL_CODEX_QUALITY_GATE_THRESHOLD_PRINCIPLE", "68")
    )
    critical_warnings = {"claim_not_leading", "weak_closer", "soft_opening_subject", "soft_operator_pronoun", "internal_public_leak", "proof_overloaded"}
    if grounding_mode == "proof_ready":
        critical_warnings.update({"proof_not_visible", "named_reference_missing"})

    taste_scores = [
        content_generation_module.score_option_taste(
            option,
            brief=briefs[index] if index < len(briefs) else None,
            primary_claims=primary_claims,
            proof_packets=proof_packets,
            story_beats=story_beats,
        )
        for index, option in enumerate(options[: max(1, len(briefs))])
    ]

    failed_reasons: list[str] = []
    for index, taste in enumerate(taste_scores, start=1):
        overall = int(taste.get("overall") or 0)
        warnings = [str(item) for item in (taste.get("warnings") or [])]
        brief = briefs[index - 1] if index - 1 < len(briefs) else None
        if overall < threshold:
            failed_reasons.append(f"option_{index}_below_threshold:{overall}")
        for warning in warnings:
            if warning in critical_warnings:
                failed_reasons.append(f"option_{index}_{warning}")
            if warning.startswith("genericity:"):
                try:
                    genericity = int(warning.split(":", 1)[1])
                except Exception:
                    genericity = 1
                if genericity >= 2:
                    failed_reasons.append(f"option_{index}_genericity:{genericity}")
        for failure in _local_publishability_failures(options[index - 1], brief):
            failed_reasons.append(f"option_{index}_{failure}")

    opening_signatures = [signature for signature in (_opening_signature(option) for option in options[: max(1, len(briefs))]) if signature]
    if len(opening_signatures) >= 2 and len(set(opening_signatures)) < len(opening_signatures):
        failed_reasons.append("opening_variety_low")

    passed = len(failed_reasons) == 0 and len(options) >= max(1, len(briefs))
    return {
        "passed": passed,
        "grounding_mode": grounding_mode,
        "threshold": threshold,
        "taste_scores": taste_scores,
        "failed_reasons": failed_reasons,
        "evaluated_option_count": len(options),
    }


def build_result_payload(
    *,
    request_payload: dict[str, Any],
    context_packet: dict[str, Any],
    options: list[str],
    provider: str,
    model: str,
    quality_gate: dict[str, Any] | None = None,
    raw_output: str | None = None,
    command_stdout: str | None = None,
    command_stderr: str | None = None,
) -> dict[str, Any]:
    briefs = content_generation_module._deserialize_content_option_briefs(context_packet.get("planned_option_briefs"))
    primary_claims = [str(item) for item in (context_packet.get("primary_claims") or []) if str(item).strip()]
    proof_packets = [str(item) for item in (context_packet.get("proof_packets") or []) if str(item).strip()]
    story_beats = [str(item) for item in (context_packet.get("story_beats") or []) if str(item).strip()]
    grounding_mode = _clean_text(context_packet.get("grounding_mode")) or "principle_only"
    if briefs:
        options = content_generation_module.finalize_planned_options(
            options=options[:3],
            briefs=briefs,
            grounding_mode=grounding_mode,
        )
        sanitized_options: list[str] = []
        for index, option in enumerate(options[:3]):
            brief = briefs[index] if index < len(briefs) else briefs[-1]
            lane = _public_lane(
                {
                    "option_number": brief.option_number,
                    "public_lane": brief.public_lane,
                }
            )
            revised = content_generation_module._sanitize_public_output(option, brief)
            revised = _sanitize_public_option(revised, lane)
            sanitized_options.append(revised)
        options = sanitized_options
    taste_scores = [
        content_generation_module.score_option_taste(
            option,
            brief=briefs[index] if index < len(briefs) else None,
            primary_claims=primary_claims,
            proof_packets=proof_packets,
            story_beats=story_beats,
        )
        for index, option in enumerate(options[:3])
    ]
    ordered_options, ordered_briefs, ordered_scores = content_generation_module._rank_options_by_taste(
        options=options[:3],
        briefs=briefs or [content_generation_module.ContentOptionBrief(1, "operator_lesson", "", "", "")],
        taste_scores=taste_scores,
        topic=str(request_payload.get("topic") or ""),
        audience=str(request_payload.get("audience") or ""),
    )
    return {
        "success": True,
        "options": ordered_options[:3],
        "persona_context": context_packet.get("persona_context_summary"),
        "examples_used": list(context_packet.get("examples_used") or []),
        "diagnostics": {
            "grounding_mode": context_packet.get("grounding_mode"),
            "generation_strategy": provider,
            "primary_claims": primary_claims,
            "proof_packets": proof_packets,
            "approved_references": list(context_packet.get("approved_references") or []),
            "voice_directives": list(context_packet.get("voice_directives") or []),
            "planned_option_briefs": content_generation_module._serialize_content_option_briefs(ordered_briefs),
            "taste_scores": ordered_scores,
            "topic_anchor_preview": list(context_packet.get("topic_anchor_preview") or []),
            "core_chunk_preview": list(context_packet.get("core_chunk_preview") or []),
            "proof_anchor_preview": list(context_packet.get("proof_anchor_preview") or []),
            "content_signal_source": context_packet.get("content_signal_source") or "persona_only",
            "content_signal_preview": list(context_packet.get("content_signal_preview") or context_packet.get("content_reservoir_preview") or []),
            "content_signal_count": int(context_packet.get("content_signal_count") or context_packet.get("content_reservoir_count") or 0),
            "content_signal_support": list(context_packet.get("content_signal_support") or context_packet.get("content_reservoir_support") or []),
            "content_reservoir_preview": list(context_packet.get("content_reservoir_preview") or context_packet.get("content_signal_preview") or []),
            "content_reservoir_count": int(context_packet.get("content_reservoir_count") or context_packet.get("content_signal_count") or 0),
            "content_reservoir_support": list(context_packet.get("content_reservoir_support") or context_packet.get("content_signal_support") or []),
            "llm_provider_trace": [
                {
                    "provider": provider,
                    "actual_model": model,
                    "status": "success",
                }
            ],
            "source_mode": request_payload.get("source_mode"),
            "quality_gate": quality_gate or {},
            "raw_codex_output_preview": (raw_output or "")[:800],
            "runner_stdout_preview": (command_stdout or "")[-800:],
            "runner_stderr_preview": (command_stderr or "")[-800:],
        },
    }


def build_local_template_artifacts(
    *,
    context_packet: dict[str, Any],
    options: list[str],
    quality_gate: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            "kind": "quality_gate",
            "label": "quality-gate.json",
            "filename": "quality-gate.json",
            "mime_type": "application/json",
            "content": json.dumps(quality_gate, indent=2) + "\n",
        },
        {
            "kind": "draft_options",
            "label": "local-template-options.json",
            "filename": "local-template-options.json",
            "mime_type": "application/json",
            "content": json.dumps(
                {
                    "provider": LOCAL_TEMPLATE_PROVIDER,
                    "model": LOCAL_TEMPLATE_MODEL,
                    "planned_option_briefs": context_packet.get("planned_option_briefs") or [],
                    "options": options,
                },
                indent=2,
            )
            + "\n",
        },
    ]
