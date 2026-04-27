from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from linkedin_strategy_utils import (
    clean_text,
    drafts_root,
    load_social_feed_items,
    now_iso,
    parse_frontmatter_markdown,
    plans_root,
    ranking_total,
    read_json,
    slugify,
    workspace_source_path,
    write_json,
    write_text,
)


ALLOWED_LANES = {
    "ai",
    "ops-pm",
    "program-leadership",
    "admissions",
    "current-role",
    "referral",
    "therapy",
    "personal-story",
    "entrepreneurship",
}

UTILITY_HINTS = (
    "how ",
    "how we",
    "playbook",
    "workflow",
    "checklist",
    "operating model",
    "what changed",
    "run ",
    "system for",
    "template",
)

CLAIM_MARKERS = (
    " is ",
    " means ",
    " matters ",
    " breaks ",
    " fails ",
    " changes ",
    " taught ",
    " forced ",
    " started ",
    " became ",
    " works ",
    " keeps ",
    " turns ",
    " moved ",
)

CONTRAST_MARKERS = (
    " but ",
    " instead ",
    " not ",
    " rather than ",
    " only if ",
    " the real ",
    " what matters ",
    " once ",
    " not because ",
)

GENERIC_DELTA_PHRASES = (
    "this matters",
    "worth watching",
    "worth paying attention",
    "signal",
    "operator view",
    "stays grounded",
    "stay grounded in lived work",
    "higher-ed operations",
    "this sharpens",
)

AUDIENCE_BY_LANE = {
    "ai": "AI builders and operators",
    "ops-pm": "operators and execution leaders",
    "program-leadership": "leaders and managers",
    "admissions": "school leaders and admissions operators",
    "current-role": "families, operators, and trust-building stakeholders",
    "referral": "partners and referral relationship builders",
    "therapy": "human-centered education and support leaders",
    "personal-story": "people tracking lived-work credibility",
    "entrepreneurship": "builders and intrapreneurs",
}

STRATEGIC_GOAL_BY_LANE = {
    "ai": "Build the AI/operator positioning lane with lived proof.",
    "ops-pm": "Make the operator and execution voice more legible.",
    "program-leadership": "Strengthen leadership and execution credibility.",
    "admissions": "Reinforce trust and practical admissions leadership.",
    "current-role": "Translate current-role work into public credibility.",
    "referral": "Reinforce partner trust and relationship credibility.",
    "therapy": "Protect the trust-and-clarity dimension of the brand.",
    "personal-story": "Turn lived experience into defensible public signal.",
    "entrepreneurship": "Show honest builder lessons without fake founder performance.",
}

LANE_CONSEQUENCE_FOCUS = {
    "ai": "whether the workflow, interface, and surrounding context make better judgment easier or just scale confusion",
    "ops-pm": "whether the system makes execution clearer, faster, and more accountable",
    "program-leadership": "whether leaders and teams can actually feel the change in day-to-day execution",
    "admissions": "whether families, students, and frontline teams get more trust, clarity, and follow-through",
    "current-role": "whether the next person in the chain experiences more clarity, trust, or follow-through",
    "referral": "whether partners feel more confidence, clarity, and trust in the relationship",
    "therapy": "whether the human-centered part of the work becomes more trustworthy and less confusing",
    "personal-story": "whether the lived lesson becomes publicly defensible instead of merely interesting",
    "entrepreneurship": "whether the builder lesson changes how operators make decisions in the real work",
}

IDEA_QUALIFICATION_VERSION = "2026-04-24-latent-source-grounding-v1"
LATENT_IDEA_VERSION = "2026-04-24-latent-source-grounding-v1"


def _clean_list(values: list[Any] | None, *, limit: int | None = None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = clean_text(value)
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
        if limit is not None and len(cleaned) >= limit:
            break
    return cleaned


def _normalized(value: str) -> str:
    return clean_text(value).lower()


def _has_any(text: str, markers: tuple[str, ...]) -> bool:
    lowered = f" {_normalized(text)} "
    return any(marker in lowered for marker in markers)


def _is_distinct(left: str, right: str) -> bool:
    return _normalized(left).strip(".") != _normalized(right).strip(".")


def _generic_delta(text: str) -> bool:
    lowered = _normalized(text)
    if not lowered:
        return True
    if len(lowered.split()) < 5:
        return True
    return any(phrase in lowered for phrase in GENERIC_DELTA_PHRASES)


def _derive_content_type(item: dict[str, Any]) -> str:
    combined = " ".join(
        [
            clean_text(item.get("title")),
            clean_text(item.get("why_it_matters")),
            clean_text(item.get("core_claim")),
        ]
    ).lower()
    if any(hint in combined for hint in UTILITY_HINTS):
        return "utility"
    return "insight"


def _derive_source_kind(item: dict[str, Any]) -> str:
    source_class = clean_text(item.get("source_class")).lower()
    capture_method = clean_text(item.get("capture_method")).lower()
    if source_class == "long_form_media":
        return "long_form_segment"
    if capture_method in {"saved_signal", "manual_capture", "manual_signal"}:
        return "external_signal"
    return "external_signal"


def _derive_new_belief(item: dict[str, Any]) -> str:
    belief = item.get("belief_assessment") or {}
    article_understanding = item.get("article_understanding") or {}
    return (
        clean_text(belief.get("belief_used"))
        or clean_text(article_understanding.get("world_context"))
        or clean_text(item.get("why_it_matters"))
    )


def _derive_delta(current_belief: str, new_belief: str, item: dict[str, Any]) -> str:
    article_understanding = item.get("article_understanding") or {}
    comparison_summary = clean_text(article_understanding.get("comparison_summary"))
    if comparison_summary and not _generic_delta(comparison_summary):
        return comparison_summary
    if current_belief and new_belief and _is_distinct(current_belief, new_belief) and _has_any(new_belief, CONTRAST_MARKERS):
        return new_belief
    return ""


def _audience_for_lane(lane: str) -> str:
    return AUDIENCE_BY_LANE.get(lane, "operators and decision-makers")


def _strategic_goal_for_lane(lane: str) -> str:
    return STRATEGIC_GOAL_BY_LANE.get(lane, "Strengthen public signal without drifting into generic posting.")


def _lane_consequence_focus(lane: str) -> str:
    return LANE_CONSEQUENCE_FOCUS.get(lane, "whether this creates a real consequence for the audience instead of just sounding smart")


@dataclass
class IdeaSourceRef:
    source_path: str | None = None
    source_url: str | None = None
    source_id: str | None = None
    source_asset_id: str | None = None


@dataclass
class IdeaCandidate:
    idea_id: str
    workspace: str
    source_kind: str
    source_ref: IdeaSourceRef
    content_lane: str
    content_type: str
    title: str
    raw_angle: str
    current_belief: str
    new_belief: str
    delta: str
    source_summary: str
    source_supporting_claim: str
    audience: str
    audience_consequence: str
    strategic_goal: str
    why_now: str
    proof_refs: list[str] = field(default_factory=list)
    proof_summary: str = ""
    lived_experience_present: bool = False
    repeated_pattern_present: bool = False
    high_variance_hint: bool = False
    portfolio_tags: list[str] = field(default_factory=list)
    upstream_scores: dict[str, float] = field(default_factory=dict)
    created_at: str = ""

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QualificationTest:
    passed: bool
    reason: str
    evidence: str = ""
    current_belief: str = ""
    new_belief: str = ""
    delta: str = ""
    proof_mode: str = ""
    audience_consequence: str = ""

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        return {key: value for key, value in payload.items() if value not in {"", None}}


@dataclass
class IdeaQualificationReport:
    idea_id: str
    qualified: bool
    route: str
    content_type_confirmed: str
    core_tests: dict[str, QualificationTest]
    variance: dict[str, str]
    failure_dimensions: list[str]
    latent_reason: str | None
    salvageable: bool
    suggested_fix: str
    downstream_permissions: dict[str, bool]
    created_at: str

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["core_tests"] = {key: value.to_payload() for key, value in self.core_tests.items()}
        return payload


def normalize_feed_item_to_idea_candidate(item: dict[str, Any]) -> IdeaCandidate:
    lane = clean_text(item.get("priority_lane")) or clean_text((item.get("lenses") or ["current-role"])[0]) or "current-role"
    lane = lane if lane in ALLOWED_LANES else "current-role"
    content_type = _derive_content_type(item)
    article_understanding = item.get("article_understanding") or {}
    belief = item.get("belief_assessment") or {}
    supporting_claims = _clean_list(item.get("supporting_claims"), limit=3)
    source_summary = clean_text(article_understanding.get("summary")) or clean_text(item.get("summary")) or (supporting_claims[0] if supporting_claims else "")
    source_supporting_claim = clean_text(article_understanding.get("comparison_summary")) or (supporting_claims[0] if supporting_claims else "")
    current_belief = clean_text(article_understanding.get("main_claim")) or clean_text(item.get("core_claim")) or clean_text(item.get("title"))
    new_belief = _derive_new_belief(item)
    raw_angle = new_belief or clean_text(item.get("why_it_matters")) or current_belief
    proof_refs = _clean_list(
        [
            workspace_source_path(item.get("source_path")),
            clean_text(item.get("shared_source_packet_path")),
        ],
        limit=4,
    )
    proof_summary = clean_text(belief.get("experience_summary")) or clean_text(article_understanding.get("world_context"))
    novelty_level = clean_text(article_understanding.get("novelty_level")).lower()
    topic_tags = _clean_list(item.get("topic_tags"), limit=4)
    idea_id = clean_text(item.get("id")) or slugify(clean_text(item.get("title")) or now_iso())
    return IdeaCandidate(
        idea_id=idea_id,
        workspace="linkedin-os",
        source_kind=_derive_source_kind(item),
        source_ref=IdeaSourceRef(
            source_path=workspace_source_path(item.get("source_path")) or None,
            source_url=clean_text(item.get("source_url")) or None,
            source_id=idea_id,
            source_asset_id=clean_text((item.get("shared_source_packet") or {}).get("asset_id")) or None,
        ),
        content_lane=lane,
        content_type=content_type,
        title=clean_text(item.get("title")) or "Untitled signal",
        raw_angle=raw_angle,
        current_belief=current_belief,
        new_belief=new_belief,
        delta=_derive_delta(current_belief, new_belief, item),
        source_summary=source_summary,
        source_supporting_claim=source_supporting_claim,
        audience=_audience_for_lane(lane),
        audience_consequence=clean_text(item.get("why_it_matters")) or clean_text(article_understanding.get("world_stakes")),
        strategic_goal=_strategic_goal_for_lane(lane),
        why_now=clean_text(item.get("why_it_matters")) or clean_text(article_understanding.get("world_stakes")),
        proof_refs=proof_refs,
        proof_summary=proof_summary,
        lived_experience_present=bool(clean_text(belief.get("experience_summary"))),
        repeated_pattern_present=False,
        high_variance_hint=novelty_level == "high",
        portfolio_tags=_clean_list([content_type, lane, *topic_tags], limit=6),
        upstream_scores={"ranking_total": ranking_total(item)},
        created_at=now_iso(),
    )


def _evaluate_sharpness(candidate: IdeaCandidate) -> QualificationTest:
    text = clean_text(candidate.raw_angle)
    if not text:
        return QualificationTest(False, "no clear angle is present", evidence="raw_angle is empty")
    if len(text.split()) < 5:
        return QualificationTest(False, "angle is too thin to stand alone", evidence=text)
    if _normalized(text).strip(".") == _normalized(candidate.current_belief).strip(".") and not _has_any(text, CONTRAST_MARKERS):
        return QualificationTest(False, "angle only restates the source claim", evidence=text)
    if not _has_any(text, CLAIM_MARKERS + CONTRAST_MARKERS):
        return QualificationTest(False, "angle does not yet state a clean claim", evidence=text)
    return QualificationTest(True, "angle states one clear point", evidence=text)


def _evaluate_non_obviousness(candidate: IdeaCandidate) -> QualificationTest:
    if candidate.content_type == "utility":
        if candidate.audience_consequence and candidate.proof_summary:
            return QualificationTest(
                True,
                "utility lane accepted through practical clarity and proof support",
                current_belief=candidate.current_belief,
                new_belief=candidate.new_belief,
                delta=candidate.delta,
            )
        return QualificationTest(
            False,
            "utility item still lacks enough practical consequence or proof support",
            current_belief=candidate.current_belief,
            new_belief=candidate.new_belief,
            delta=candidate.delta,
        )
    if not candidate.current_belief or not candidate.new_belief or not candidate.delta:
        return QualificationTest(
            False,
            "insight item is missing current belief, new belief, or delta",
            current_belief=candidate.current_belief,
            new_belief=candidate.new_belief,
            delta=candidate.delta,
        )
    if not _is_distinct(candidate.current_belief, candidate.new_belief):
        return QualificationTest(
            False,
            "new belief does not materially differ from the current belief",
            current_belief=candidate.current_belief,
            new_belief=candidate.new_belief,
            delta=candidate.delta,
        )
    if _generic_delta(candidate.delta) and not _has_any(candidate.new_belief, CONTRAST_MARKERS):
        return QualificationTest(
            False,
            "belief shift is too generic",
            current_belief=candidate.current_belief,
            new_belief=candidate.new_belief,
            delta=candidate.delta,
        )
    return QualificationTest(
        True,
        "idea creates a real belief shift",
        current_belief=candidate.current_belief,
        new_belief=candidate.new_belief,
        delta=candidate.delta,
    )


def _evaluate_proof_potential(candidate: IdeaCandidate) -> QualificationTest:
    if candidate.lived_experience_present and candidate.proof_summary and len(candidate.proof_summary.split()) >= 6:
        return QualificationTest(True, "lived experience is present to back the claim", proof_mode="story")
    if candidate.source_kind in {"own_thinking", "existing_backlog"} and candidate.proof_refs:
        return QualificationTest(True, "artifact references exist to back the claim", proof_mode="artifact")
    if candidate.repeated_pattern_present and candidate.proof_summary:
        return QualificationTest(True, "a repeated pattern exists that could support the claim", proof_mode="pattern")
    return QualificationTest(False, "no real proof path is visible yet", proof_mode="none")


def _evaluate_strategic_relevance(candidate: IdeaCandidate) -> QualificationTest:
    if candidate.content_lane not in ALLOWED_LANES:
        return QualificationTest(False, "lane is not part of the current positioning system", audience_consequence=candidate.audience_consequence)
    if not candidate.audience_consequence:
        return QualificationTest(False, "audience consequence is missing", audience_consequence=candidate.audience_consequence)
    if len(candidate.audience_consequence.split()) < 4:
        return QualificationTest(False, "audience consequence is too thin", audience_consequence=candidate.audience_consequence)
    if candidate.source_kind == "external_signal" and _generic_delta(candidate.audience_consequence):
        return QualificationTest(False, "external signal still reads like broad relevance instead of your angle", audience_consequence=candidate.audience_consequence)
    if not candidate.strategic_goal:
        return QualificationTest(False, "strategic goal is missing", audience_consequence=candidate.audience_consequence)
    return QualificationTest(True, "idea serves a real audience and lane right now", audience_consequence=candidate.audience_consequence)


def qualify_idea(candidate: IdeaCandidate) -> IdeaQualificationReport:
    sharpness = _evaluate_sharpness(candidate)
    non_obviousness = _evaluate_non_obviousness(candidate)
    proof_potential = _evaluate_proof_potential(candidate)
    strategic_relevance = _evaluate_strategic_relevance(candidate)
    core_tests = {
        "sharpness": sharpness,
        "non_obviousness": non_obviousness,
        "proof_potential": proof_potential,
        "strategic_relevance": strategic_relevance,
    }
    failure_dimensions = [name for name, result in core_tests.items() if not result.passed]

    variance = {"level": "low", "reason": "no unusual upside signal detected"}
    if candidate.high_variance_hint or (_has_any(candidate.raw_angle, CONTRAST_MARKERS) and not proof_potential.passed):
        variance = {"level": "high", "reason": "idea is under-formed but contains a strong contrast or novelty hint"}

    route = "discard"
    latent_reason: str | None = None
    salvageable = False
    suggested_fix = "Kill this early instead of sending it downstream."

    if not failure_dimensions:
        route = "pass"
        suggested_fix = "Qualified. Safe to promote into post-seed and weekly-plan recommendation lanes."
    elif (
        candidate.content_type == "utility"
        and sharpness.passed
        and non_obviousness.passed
        and proof_potential.passed
        and not strategic_relevance.passed
    ):
        route = "latent"
        latent_reason = "needs_context_translation"
        salvageable = True
        suggested_fix = "The core point is real, but it still needs a clearer audience consequence or your angle before it earns a draft."
    elif sharpness.passed and non_obviousness.passed and strategic_relevance.passed and not proof_potential.passed:
        route = "latent"
        latent_reason = "missing_proof"
        salvageable = True
        suggested_fix = "Keep the angle, but wait for a real example, artifact, or lived proof packet."
    elif candidate.content_type == "utility" and sharpness.passed and proof_potential.passed and strategic_relevance.passed and not non_obviousness.passed:
        route = "latent"
        latent_reason = "reinforcement_without_fresh_work"
        salvageable = True
        suggested_fix = "Only bring this back if it gains new proof, better framing, or a new audience segment."
    elif variance["level"] == "high" and strategic_relevance.passed:
        route = "latent"
        latent_reason = "high_variance"
        salvageable = True
        suggested_fix = "Store it as high-variance and wait for either a sharper angle or better proof."
    elif variance["level"] == "high" and proof_potential.passed and non_obviousness.passed:
        route = "latent"
        latent_reason = "high_variance"
        salvageable = True
        suggested_fix = "The idea may matter, but it still needs a cleaner angle and tighter context before it belongs in the draft lane."

    qualified = route == "pass"
    downstream_permissions = {
        "allow_reaction_comment": True,
        "allow_post_seed": qualified,
        "allow_weekly_plan_recommendation": qualified,
        "allow_weekly_plan_hold_item": route == "latent",
        "allow_queue_promotion": qualified,
        "allow_draft_materialization": qualified,
    }

    return IdeaQualificationReport(
        idea_id=candidate.idea_id,
        qualified=qualified,
        route=route,
        content_type_confirmed=candidate.content_type,
        core_tests=core_tests,
        variance=variance,
        failure_dimensions=failure_dimensions,
        latent_reason=latent_reason,
        salvageable=salvageable,
        suggested_fix=suggested_fix,
        downstream_permissions=downstream_permissions,
        created_at=now_iso(),
    )


def build_idea_qualification_payload(workspace_dir: Path) -> dict[str, Any]:
    items = sorted(load_social_feed_items(workspace_dir), key=ranking_total, reverse=True)
    results: list[dict[str, Any]] = []
    summary = {"total": 0, "pass": 0, "latent": 0, "discard": 0}

    for item in items:
        candidate = normalize_feed_item_to_idea_candidate(item)
        report = qualify_idea(candidate)
        results.append(
            {
                "idea_id": candidate.idea_id,
                "title": candidate.title,
                "score": round(candidate.upstream_scores.get("ranking_total") or 0.0, 1),
                "source_path": candidate.source_ref.source_path,
                "candidate": candidate.to_payload(),
                "report": report.to_payload(),
            }
        )
        summary["total"] += 1
        summary[report.route] += 1

    return {
        "generated_at": now_iso(),
        "contract_version": IDEA_QUALIFICATION_VERSION,
        "workspace": "workspaces/linkedin-content-os",
        "summary": summary,
        "items": results,
    }


def _markdown_for_payload(payload: dict[str, Any]) -> str:
    lines = ["# LinkedIn Idea Qualification", f"Generated: {payload.get('generated_at')}", ""]
    summary = payload.get("summary") or {}
    lines.extend(
        [
            "## Summary",
            f"- Total: {summary.get('total', 0)}",
            f"- Pass: {summary.get('pass', 0)}",
            f"- Latent: {summary.get('latent', 0)}",
            f"- Discard: {summary.get('discard', 0)}",
            "",
        ]
    )
    for route in ("pass", "latent", "discard"):
        lines.append(f"## {route.title()} Ideas")
        route_items = [item for item in payload.get("items", []) if ((item.get("report") or {}).get("route") == route)]
        if not route_items:
            lines.append("_None._")
            lines.append("")
            continue
        for item in route_items[:12]:
            report = item.get("report") or {}
            candidate = item.get("candidate") or {}
            lines.append(f"### {item.get('title') or 'Untitled'}")
            lines.append(f"- Score: {item.get('score', 0)}")
            lines.append(f"- Lane: {candidate.get('content_lane') or ''}")
            lines.append(f"- Type: {candidate.get('content_type') or ''}")
            lines.append(f"- Angle: {candidate.get('raw_angle') or ''}")
            lines.append(f"- Failures: {', '.join(report.get('failure_dimensions') or []) or 'none'}")
            if report.get("latent_reason"):
                lines.append(f"- Latent reason: {report.get('latent_reason')}")
            if report.get("suggested_fix"):
                lines.append(f"- Suggested fix: {report.get('suggested_fix')}")
            lines.append("")
    return "\n".join(lines)


def write_idea_qualification_artifacts(workspace_dir: Path, payload: dict[str, Any]) -> None:
    root = plans_root(workspace_dir)
    write_json(root / "idea_qualification.json", payload)
    write_text(root / "idea_qualification.md", _markdown_for_payload(payload))


def load_or_build_idea_qualification_payload(workspace_dir: Path) -> dict[str, Any]:
    artifact_path = plans_root(workspace_dir) / "idea_qualification.json"
    feed_path = plans_root(workspace_dir) / "social_feed.json"
    existing = read_json(artifact_path)
    if existing and artifact_path.exists() and feed_path.exists():
        if artifact_path.stat().st_mtime >= feed_path.stat().st_mtime:
            if clean_text(existing.get("contract_version")) != IDEA_QUALIFICATION_VERSION:
                payload = build_idea_qualification_payload(workspace_dir)
                write_idea_qualification_artifacts(workspace_dir, payload)
                return payload
            items = existing.get("items")
            if isinstance(items, list):
                first = items[0] if items else {}
                report = first.get("report") if isinstance(first, dict) else {}
                if isinstance(report, dict) and clean_text(report.get("route")) in {"pass", "latent", "discard"}:
                    return existing
    payload = build_idea_qualification_payload(workspace_dir)
    write_idea_qualification_artifacts(workspace_dir, payload)
    return payload


def qualification_indexes(payload: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_idea_id: dict[str, dict[str, Any]] = {}
    by_source_path: dict[str, dict[str, Any]] = {}
    for entry in payload.get("items", []):
        if not isinstance(entry, dict):
            continue
        idea_id = clean_text(entry.get("idea_id"))
        report = entry.get("report")
        candidate = entry.get("candidate")
        if not isinstance(report, dict):
            continue
        if idea_id:
            by_idea_id[idea_id] = report
        if isinstance(candidate, dict):
            source_ref = candidate.get("source_ref")
            source_path = ""
            if isinstance(source_ref, dict):
                source_path = workspace_source_path(source_ref.get("source_path"))
            if source_path:
                by_source_path[source_path] = report
    return by_idea_id, by_source_path


def active_draft_indexes(workspace_dir: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_idea_id: dict[str, dict[str, Any]] = {}
    by_source_path: dict[str, dict[str, Any]] = {}
    for path in sorted(drafts_root(workspace_dir).glob("*.md")):
        if path.name == "README.md" or path.name.startswith("queue_") or path.name.startswith("feezie_owner_review_packet_"):
            continue
        frontmatter, _ = parse_frontmatter_markdown(path)
        metadata = {
            "draft_path": workspace_source_path(path.relative_to(workspace_dir).as_posix()),
            "draft_fs_path": str(path),
            "source_kind": clean_text(frontmatter.get("source_kind")),
            "publish_posture": clean_text(frontmatter.get("publish_posture")),
        }
        source_path = workspace_source_path(clean_text(frontmatter.get("source_path")))
        idea_id = clean_text(frontmatter.get("idea_id")) or clean_text(frontmatter.get("qualification_id"))
        if source_path:
            by_source_path[source_path] = metadata
        if idea_id:
            by_idea_id[idea_id] = metadata
    return by_idea_id, by_source_path


def _latent_resurface_triggers(candidate: dict[str, Any], report: dict[str, Any]) -> list[str]:
    latent_reason = clean_text(report.get("latent_reason"))
    content_type = clean_text(candidate.get("content_type"))
    source_kind = clean_text(candidate.get("source_kind"))
    if latent_reason == "needs_context_translation":
        return [
            "your angle becomes explicit",
            "audience consequence becomes concrete",
            "the source gets translated into a lived operator example",
        ]
    if latent_reason == "missing_proof":
        return [
            "new proof artifact logged",
            "new lived example captured",
            "queue item gains defendable proof anchor",
        ]
    if latent_reason == "wrong_timing":
        return [
            "new market event changes timing",
            "portfolio mix opens the lane again",
            "audience consequence becomes more concrete",
        ]
    if latent_reason == "high_variance":
        return [
            "angle sharpens into one clear claim",
            "new counterexample or contrast appears",
            "owner note confirms this is worth developing",
        ]
    if latent_reason == "reinforcement_without_fresh_work":
        return [
            "new proof or case study appears",
            "new audience segment needs this framing",
            "the idea gains a sharper consequence or hook",
        ]
    triggers = ["qualification rerun"]
    if content_type == "utility":
        triggers.append("operator workflow needs clearer explanation")
    if source_kind == "external_signal":
        triggers.append("source signal becomes more personally grounded")
    return triggers


def _latent_resurface_hint(candidate: dict[str, Any], report: dict[str, Any]) -> str:
    latent_reason = clean_text(report.get("latent_reason"))
    title = clean_text(candidate.get("title"))
    if latent_reason == "needs_context_translation":
        return f"`{title}` has a real core point, but it should stay latent until the system can state why this matters for your audience in your language."
    if latent_reason == "missing_proof":
        return f"Do not bring `{title}` back until it has real proof, not just a sharper take."
    if latent_reason == "wrong_timing":
        return f"`{title}` is strategically real, but it should wait for a better moment."
    if latent_reason == "high_variance":
        return f"`{title}` may be valuable later, but it needs angle development before it earns a draft."
    if latent_reason == "reinforcement_without_fresh_work":
        return f"`{title}` should return only if it can do fresh work for a new audience, proof set, or framing."
    return f"`{title}` should stay out of drafting until it passes qualification cleanly."


def _latent_transform_plan(candidate: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    latent_reason = clean_text(report.get("latent_reason"))
    lane = clean_text(candidate.get("content_lane"))
    title = clean_text(candidate.get("title"))
    raw_angle = clean_text(candidate.get("raw_angle"))
    delta = clean_text(candidate.get("delta"))
    audience = clean_text(candidate.get("audience"))
    proof_summary = clean_text(candidate.get("proof_summary"))
    source_signal = clean_text(candidate.get("source_summary")) or clean_text(candidate.get("source_supporting_claim")) or clean_text(candidate.get("current_belief")) or title
    focus = _lane_consequence_focus(lane)
    base_claim = raw_angle or delta or title

    if latent_reason == "needs_context_translation":
        proof_prompt = proof_summary or "the closest lived proof artifact for this lane"
        if base_claim and source_signal and _is_distinct(source_signal, base_claim):
            proposed_angle = f"{base_claim}. Anchor it in the source signal: {source_signal.rstrip('.')}."
        else:
            proposed_angle = base_claim or title
        return {
            "transform_type": "context_translation",
            "autotransform_ready": True,
            "proposed_angle": (
                f"{proposed_angle} The part worth saying publicly is {focus}."
                if proposed_angle
                else f"The part worth saying publicly is {focus}."
            ),
            "source_signal": source_signal,
            "owner_question": f"What concrete change should {audience.lower()} notice if this is true?",
            "revision_goals": [
                "replace generic relevance with a concrete audience consequence",
                "anchor the angle in one lived proof line",
                "state the claim in operator language instead of source language",
            ],
            "proof_prompt": proof_prompt,
            "promotion_rule": "Promote only after the angle names a concrete audience consequence and one lived proof line.",
        }
    if latent_reason == "high_variance":
        working_claim = delta or base_claim
        return {
            "transform_type": "angle_development",
            "autotransform_ready": False,
            "proposed_angle": (
                f"{title} is not just a headline. The real issue is {working_claim.lower().rstrip('.')}"
                if working_claim
                else f"{title} may matter, but it still needs one clean public claim."
            ),
            "owner_question": "What is the one claim you would actually stand behind publicly here?",
            "revision_goals": [
                "choose one defendable claim instead of a broad theme",
                "translate the signal into a trust, clarity, or delivery consequence",
                "attach one lived proof anchor before drafting",
            ],
            "proof_prompt": proof_summary or "the strongest lived proof anchor you can defend here",
            "promotion_rule": "Promote only when the signal has one clean claim plus one defendable proof anchor.",
        }
    if latent_reason == "missing_proof":
        return {
            "transform_type": "proof_wait",
            "autotransform_ready": False,
            "proposed_angle": base_claim,
            "owner_question": "What real example, artifact, or outcome would make this claim defensible?",
            "revision_goals": [
                "find one real example",
                "narrow the claim to defendable scope",
            ],
            "proof_prompt": proof_summary or "the missing proof artifact this idea needs",
            "promotion_rule": "Promote only after the claim is paired with real proof.",
        }
    if latent_reason == "reinforcement_without_fresh_work":
        return {
            "transform_type": "fresh_work_check",
            "autotransform_ready": False,
            "proposed_angle": base_claim,
            "owner_question": "What new proof, framing, or audience makes this worth saying again?",
            "revision_goals": [
                "add new proof or a new audience consequence",
                "show what fresh work this post would do",
            ],
            "proof_prompt": proof_summary or "the new evidence that would make this feel fresh",
            "promotion_rule": "Promote only if the idea does new work for a new audience, proof set, or framing.",
        }
    return {
        "transform_type": "latent_hold",
        "autotransform_ready": False,
        "proposed_angle": base_claim,
        "owner_question": "What would need to change for this to deserve a draft?",
        "revision_goals": ["clarify the missing condition before promotion"],
        "proof_prompt": proof_summary or "the missing proof or context",
        "promotion_rule": "Keep latent until the missing condition is resolved.",
    }


def build_latent_idea_payload(workspace_dir: Path) -> dict[str, Any]:
    qualification_payload = load_or_build_idea_qualification_payload(workspace_dir)
    items: list[dict[str, Any]] = []
    by_reason: dict[str, int] = {}
    by_transform_type: dict[str, int] = {}
    autotransform_ready = 0
    autotransform_pending = 0
    drafted_count = 0
    draft_by_idea_id, draft_by_source_path = active_draft_indexes(workspace_dir)

    for entry in qualification_payload.get("items", []):
        if not isinstance(entry, dict):
            continue
        report = entry.get("report")
        candidate = entry.get("candidate")
        if not isinstance(report, dict) or not isinstance(candidate, dict):
            continue
        if clean_text(report.get("route")) != "latent":
            continue
        latent_reason = clean_text(report.get("latent_reason")) or "latent"
        transform_plan = _latent_transform_plan(candidate, report)
        by_reason[latent_reason] = by_reason.get(latent_reason, 0) + 1
        transform_type = clean_text(transform_plan.get("transform_type")) or "latent_hold"
        by_transform_type[transform_type] = by_transform_type.get(transform_type, 0) + 1
        if bool(transform_plan.get("autotransform_ready")):
            autotransform_ready += 1
        source_ref = candidate.get("source_ref") if isinstance(candidate.get("source_ref"), dict) else {}
        source_path = workspace_source_path(source_ref.get("source_path"))
        idea_id = clean_text(entry.get("idea_id"))
        active_draft = draft_by_source_path.get(source_path) or draft_by_idea_id.get(idea_id)
        transform_status = "drafted" if active_draft else "pending"
        if transform_status == "drafted":
            drafted_count += 1
        elif bool(transform_plan.get("autotransform_ready")):
            autotransform_pending += 1
        items.append(
            {
                "idea_id": idea_id,
                "title": clean_text(entry.get("title")),
                "score": round(float(entry.get("score") or 0.0), 1),
                "source_kind": clean_text(candidate.get("source_kind")),
                "content_lane": clean_text(candidate.get("content_lane")),
                "content_type": clean_text(candidate.get("content_type")),
                "source_summary": clean_text(candidate.get("source_summary")),
                "source_supporting_claim": clean_text(candidate.get("source_supporting_claim")),
                "source_path": source_path,
                "source_url": clean_text(source_ref.get("source_url")),
                "latent_reason": latent_reason,
                "variance_level": clean_text((report.get("variance") or {}).get("level")) or "low",
                "suggested_fix": clean_text(report.get("suggested_fix")),
                "resurface_triggers": _latent_resurface_triggers(candidate, report),
                "resurface_hint": _latent_resurface_hint(candidate, report),
                "failure_dimensions": [clean_text(value) for value in (report.get("failure_dimensions") or []) if clean_text(value)],
                "transform_plan": transform_plan,
                "transform_status": transform_status,
                "draft_path": clean_text((active_draft or {}).get("draft_path")),
                "created_at": clean_text(report.get("created_at")) or now_iso(),
            }
        )

    return {
        "generated_at": now_iso(),
        "contract_version": LATENT_IDEA_VERSION,
        "workspace": "workspaces/linkedin-content-os",
        "summary": {
            "total": len(items),
            "by_reason": by_reason,
            "by_transform_type": by_transform_type,
            "autotransform_ready": autotransform_ready,
            "autotransform_pending": autotransform_pending,
            "drafted": drafted_count,
        },
        "items": items,
    }


def _markdown_for_latent_payload(payload: dict[str, Any]) -> str:
    lines = ["# LinkedIn Latent Ideas", f"Generated: {payload.get('generated_at')}", ""]
    summary = payload.get("summary") or {}
    lines.extend(
        [
            "## Summary",
            f"- Total latent ideas: {summary.get('total', 0)}",
        ]
    )
    by_reason = summary.get("by_reason") if isinstance(summary.get("by_reason"), dict) else {}
    if by_reason:
        for key in sorted(by_reason):
            lines.append(f"- {key}: {by_reason.get(key, 0)}")
    transform_types = summary.get("by_transform_type") if isinstance(summary.get("by_transform_type"), dict) else {}
    if transform_types:
        lines.append(f"- Worker-ready transforms: {summary.get('autotransform_ready', 0)}")
        lines.append(f"- Worker-ready pending: {summary.get('autotransform_pending', 0)}")
        lines.append(f"- Already drafted: {summary.get('drafted', 0)}")
        for key in sorted(transform_types):
            lines.append(f"- {key}: {transform_types.get(key, 0)}")
    lines.append("")
    items = payload.get("items") or []
    if not items:
        lines.append("_No latent ideas right now._")
        return "\n".join(lines)
    for item in items:
        transform_plan = item.get("transform_plan") if isinstance(item.get("transform_plan"), dict) else {}
        lines.extend(
            [
                f"## {item.get('title') or 'Untitled latent idea'}",
                f"- Lane: {item.get('content_lane') or ''}",
                f"- Type: {item.get('content_type') or ''}",
                f"- Reason: {item.get('latent_reason') or ''}",
                f"- Score: {item.get('score', 0)}",
                f"- Failures: {', '.join(item.get('failure_dimensions') or []) or 'none'}",
                f"- Suggested fix: {item.get('suggested_fix') or ''}",
                f"- Resurface hint: {item.get('resurface_hint') or ''}",
                f"- Transform type: {transform_plan.get('transform_type') or ''}",
                f"- Worker-ready: {'yes' if transform_plan.get('autotransform_ready') else 'no'}",
                f"- Transform status: {item.get('transform_status') or ''}",
                f"- Proposed angle: {transform_plan.get('proposed_angle') or ''}",
                f"- Owner question: {transform_plan.get('owner_question') or ''}",
                f"- Proof prompt: {transform_plan.get('proof_prompt') or ''}",
                f"- Promotion rule: {transform_plan.get('promotion_rule') or ''}",
                "- Revision goals:",
            ]
        )
        for goal in transform_plan.get("revision_goals") or []:
            lines.append(f"  - {goal}")
        lines.extend(
            [
                "- Triggers:",
            ]
        )
        for trigger in item.get("resurface_triggers") or []:
            lines.append(f"  - {trigger}")
        if item.get("draft_path"):
            lines.append(f"- Draft path: `{item.get('draft_path')}`")
        if item.get("source_path"):
            lines.append(f"- Source file: `{item.get('source_path')}`")
        if item.get("source_url"):
            lines.append(f"- Source URL: {item.get('source_url')}")
        lines.append("")
    return "\n".join(lines)


def write_latent_idea_artifacts(workspace_dir: Path, payload: dict[str, Any]) -> None:
    root = plans_root(workspace_dir)
    write_json(root / "latent_ideas.json", payload)
    write_text(root / "latent_ideas.md", _markdown_for_latent_payload(payload))


def load_or_build_latent_idea_payload(workspace_dir: Path) -> dict[str, Any]:
    artifact_path = plans_root(workspace_dir) / "latent_ideas.json"
    qualification_path = plans_root(workspace_dir) / "idea_qualification.json"
    existing = read_json(artifact_path)
    if existing and artifact_path.exists() and qualification_path.exists():
        if artifact_path.stat().st_mtime >= qualification_path.stat().st_mtime:
            if clean_text(existing.get("contract_version")) != LATENT_IDEA_VERSION:
                payload = build_latent_idea_payload(workspace_dir)
                write_latent_idea_artifacts(workspace_dir, payload)
                return payload
            items = existing.get("items")
            if isinstance(items, list):
                return existing
    payload = build_latent_idea_payload(workspace_dir)
    write_latent_idea_artifacts(workspace_dir, payload)
    return payload


def latent_idea_indexes(payload: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_idea_id: dict[str, dict[str, Any]] = {}
    by_source_path: dict[str, dict[str, Any]] = {}
    for entry in payload.get("items", []):
        if not isinstance(entry, dict):
            continue
        idea_id = clean_text(entry.get("idea_id"))
        source_path = workspace_source_path(entry.get("source_path"))
        if idea_id:
            by_idea_id[idea_id] = entry
        if source_path:
            by_source_path[source_path] = entry
    return by_idea_id, by_source_path


def _stale_reaction_archive_dir(workspace_dir: Path) -> Path:
    return drafts_root(workspace_dir) / "archive" / "stale_reaction_drafts"


def _stale_reaction_manifest_paths(workspace_dir: Path) -> tuple[Path, Path]:
    root = drafts_root(workspace_dir) / "archive"
    return root / "stale_reaction_manifest.json", root / "stale_reaction_manifest.md"


def _archive_path_for_file(archive_dir: Path, path: Path) -> Path:
    candidate = archive_dir / path.name
    if not candidate.exists():
        return candidate
    stem = path.stem
    suffix = path.suffix or ".md"
    index = 2
    while True:
        candidate = archive_dir / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _archive_manifest_payload(
    workspace_dir: Path,
    records: list[dict[str, Any]],
    *,
    moved_this_run: list[dict[str, Any]],
) -> dict[str, Any]:
    by_route: dict[str, int] = {}
    for record in records:
        route = clean_text(record.get("route")) or "archived"
        by_route[route] = by_route.get(route, 0) + 1
    return {
        "generated_at": now_iso(),
        "workspace": "workspaces/linkedin-content-os",
        "summary": {
            "total_archived": len(records),
            "moved_this_run": len(moved_this_run),
            "by_route": by_route,
        },
        "moved_this_run": moved_this_run,
        "items": records,
    }


def _markdown_for_archive_manifest(payload: dict[str, Any]) -> str:
    lines = ["# Stale Reaction Draft Archive", f"Generated: {payload.get('generated_at')}", ""]
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    lines.extend(
        [
            "## Summary",
            f"- Total archived drafts: {summary.get('total_archived', 0)}",
            f"- Moved this run: {summary.get('moved_this_run', 0)}",
        ]
    )
    by_route = summary.get("by_route") if isinstance(summary.get("by_route"), dict) else {}
    if by_route:
        for route in sorted(by_route):
            lines.append(f"- {route}: {by_route.get(route, 0)}")
    lines.append("")
    moved_this_run = payload.get("moved_this_run") or []
    if moved_this_run:
        lines.append("## Moved This Run")
        for item in moved_this_run:
            lines.extend(
                [
                    f"### {item.get('title') or 'Untitled archived draft'}",
                    f"- Route: {item.get('route') or ''}",
                    f"- Failures: {', '.join(item.get('failure_dimensions') or []) or 'none'}",
                    f"- Archived from: `{item.get('archived_from') or ''}`",
                    f"- Archive path: `{item.get('archive_path') or ''}`",
                    f"- Reason: {item.get('suggested_fix') or ''}",
                    "",
                ]
            )
    items = payload.get("items") or []
    if not items:
        lines.append("_No archived reaction drafts._")
        return "\n".join(lines)
    lines.append("## Archive Inventory")
    for item in items:
        lines.extend(
            [
                f"### {item.get('title') or 'Untitled archived draft'}",
                f"- Route: {item.get('route') or ''}",
                f"- Failures: {', '.join(item.get('failure_dimensions') or []) or 'none'}",
                f"- Archived at: {item.get('archived_at') or ''}",
                f"- Archive path: `{item.get('archive_path') or ''}`",
                (f"- Source file: `{item.get('source_path')}`" if item.get("source_path") else ""),
                (f"- Source URL: {item.get('source_url')}" if item.get("source_url") else ""),
                f"- Reason: {item.get('suggested_fix') or ''}",
                "",
            ]
        )
    return "\n".join(line for line in lines if line != "")


def quarantine_stale_reaction_drafts(workspace_dir: Path) -> dict[str, Any]:
    qualification_payload = load_or_build_idea_qualification_payload(workspace_dir)
    _, qualification_by_source_path = qualification_indexes(qualification_payload)
    archive_dir = _stale_reaction_archive_dir(workspace_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)
    manifest_json_path, manifest_md_path = _stale_reaction_manifest_paths(workspace_dir)
    existing_manifest = read_json(manifest_json_path) or {}
    existing_items = existing_manifest.get("items") if isinstance(existing_manifest.get("items"), list) else []
    records: list[dict[str, Any]] = [item for item in existing_items if isinstance(item, dict)]
    record_by_archive_path = {
        clean_text(item.get("archive_path")): item for item in records if clean_text(item.get("archive_path"))
    }
    moved_this_run: list[dict[str, Any]] = []

    for path in sorted(drafts_root(workspace_dir).glob("*.md")):
        if path.name == "README.md" or path.name.startswith("queue_") or path.name.startswith("feezie_owner_review_packet_"):
            continue
        frontmatter, _ = parse_frontmatter_markdown(path)
        if clean_text(frontmatter.get("source_kind")) != "reaction_seed":
            continue
        source_path = workspace_source_path(clean_text(frontmatter.get("source_path")))
        report = qualification_by_source_path.get(source_path) if source_path else None
        route = clean_text((report or {}).get("route")) or clean_text(frontmatter.get("qualification_route")) or "discard"
        if route == "pass":
            continue
        archive_path = _archive_path_for_file(archive_dir, path)
        path.replace(archive_path)
        failure_dimensions = [clean_text(value) for value in ((report or {}).get("failure_dimensions") or []) if clean_text(value)]
        suggested_fix = clean_text((report or {}).get("suggested_fix"))
        if not report:
            failure_dimensions = ["missing_current_signal"]
            suggested_fix = "Archived because this reaction-seed draft no longer has a live qualifying source signal."
        record = {
            "title": clean_text(frontmatter.get("title")) or path.stem,
            "archive_path": workspace_source_path(archive_path.relative_to(workspace_dir).as_posix()),
            "archived_from": workspace_source_path(path.relative_to(workspace_dir).as_posix()),
            "source_path": source_path,
            "source_url": clean_text(frontmatter.get("source_url")),
            "route": route,
            "latent_reason": clean_text((report or {}).get("latent_reason")),
            "failure_dimensions": failure_dimensions,
            "suggested_fix": suggested_fix or "Archived because this reaction-seed draft no longer passes idea qualification.",
            "archived_at": now_iso(),
        }
        record_by_archive_path[record["archive_path"]] = record
        moved_this_run.append(record)

    merged_records = sorted(
        record_by_archive_path.values(),
        key=lambda item: (
            clean_text(item.get("archived_at")),
            clean_text(item.get("title")).lower(),
        ),
        reverse=True,
    )
    payload = _archive_manifest_payload(workspace_dir, merged_records, moved_this_run=moved_this_run)
    write_json(manifest_json_path, payload)
    write_text(manifest_md_path, _markdown_for_archive_manifest(payload))
    return {
        "workspace": "workspaces/linkedin-content-os",
        "moved_this_run": len(moved_this_run),
        "total_archived": len(merged_records),
    }
