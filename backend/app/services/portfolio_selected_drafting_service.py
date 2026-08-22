from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from typing import Any, Awaitable, Callable, Mapping
import uuid

from app.services.content_lifecycle_service import (
    ContentLifecycleConflict,
    ContentLifecycleService,
)
from app.services.integrated_production_generator_service import (
    CONTENT_POST_GENERATION_CONTEXT_SCHEMA,
    bounded_remote_source_excerpt,
    normalized_remote_controls,
    unpack_integrated_generation_result,
)
from app.services.integrated_memory_readiness_service import READINESS_SCHEMA_VERSION
from app.services.integrated_system_store import _canonical_json, _utcnow
from app.services.owner_requested_post_service import (
    _validate_generation_receipt_binding,
)
from app.services.source_sharing_policy_service import source_remote_sharing


PORTFOLIO_DRAFTING_SCHEMA = "portfolio_selected_drafting_cycle/v1"
PORTFOLIO_DRAFTING_JOB_SCHEMA = "portfolio_selected_drafting_job/v1"
PORTFOLIO_DRAFTING_POLICY = "portfolio_selected_canonical_drafting/v1"
_LEASE_SECONDS = 20 * 60
_SAFE_CODE_RE = re.compile(r"[^a-z0-9_.:-]+")
_PILLAR_AUDIENCE = {
    "ai_native": "tech_ai",
    "leadership_operator": "leadership",
    "trust_systems": "education_admissions",
}


class ContentDraftingInProgress(ContentLifecycleConflict):
    """Another healthy lease already owns the same canonical drafting job."""


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _safe_error_code(exc: BaseException, *, stage: str) -> str:
    value = f"{type(exc).__name__}:{stage}".lower()
    return _SAFE_CODE_RE.sub("_", value).strip("_")[:120]


def _parse_json_object(raw: str, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise ContentLifecycleConflict(f"{label} is malformed") from exc
    if not isinstance(value, dict):
        raise ContentLifecycleConflict(f"{label} must be an object")
    return value


def _evidence_bound_excerpt(
    *, source_body: str, evidence: Mapping[str, Any], artifact: Mapping[str, Any]
) -> str:
    try:
        refs = json.loads(str(evidence.get("evidence_refs_json") or "[]"))
    except json.JSONDecodeError as exc:
        raise ContentLifecycleConflict(
            "portfolio-selected authoritative evidence references are malformed"
        ) from exc
    if not isinstance(refs, list) or not refs:
        raise ContentLifecycleConflict(
            "portfolio-selected authoritative evidence has no source references"
        )
    spans: list[str] = []
    for ref in refs:
        if not isinstance(ref, dict):
            raise ContentLifecycleConflict(
                "portfolio-selected authoritative evidence reference is invalid"
            )
        if ref.get("artifact_id") not in {None, artifact["artifact_id"]} or ref.get(
            "artifact_sha256"
        ) not in {None, artifact["content_sha256"]}:
            raise ContentLifecycleConflict(
                "portfolio-selected evidence reference changed its artifact binding"
            )
        has_start = "start" in ref
        has_end = "end" in ref
        if has_start != has_end:
            raise ContentLifecycleConflict(
                "portfolio-selected evidence span is incomplete"
            )
        if not has_start:
            continue
        start = ref["start"]
        end = ref["end"]
        if (
            isinstance(start, bool)
            or isinstance(end, bool)
            or not isinstance(start, int)
            or not isinstance(end, int)
            or start < 0
            or end <= start
            or end > len(source_body)
        ):
            raise ContentLifecycleConflict(
                "portfolio-selected evidence span is outside the source artifact"
            )
        exact = source_body[start:end]
        quote_sha256 = ref.get("quote_sha256")
        if quote_sha256 is not None and quote_sha256 != hashlib.sha256(
            exact.encode("utf-8")
        ).hexdigest():
            raise ContentLifecycleConflict(
                "portfolio-selected evidence span hash mismatch"
            )
        spans.append(exact)
    if not spans:
        raise ContentLifecycleConflict(
            "portfolio-selected evidence has no exact source span for remote drafting"
        )
    excerpt = bounded_remote_source_excerpt("\n\n".join(spans))
    if not excerpt:
        raise ContentLifecycleConflict(
            "portfolio-selected authoritative evidence excerpt is empty"
        )
    return excerpt


def default_portfolio_drafting_controls(metadata: Mapping[str, Any]) -> dict[str, str]:
    """Choose a bounded base-post emphasis without changing the core audience."""

    pillar = str(metadata.get("canonical_pillar") or "").strip()
    controls = {
        "audience_emphasis": _PILLAR_AUDIENCE.get(pillar, "general"),
        "tone": "expert_direct",
    }
    if metadata.get("exploratory_conflict") is True:
        controls["evidence_emphasis"] = "make the disagreement or open question explicit"
    return controls


class PortfolioSelectedDraftingService:
    """Own the selected-opportunity -> one canonical draft transition.

    The SQL job is orchestration state, not a second content authority. Canonical
    post/revision bytes remain authoritative in ``ContentLifecycleService``.
    """

    def __init__(
        self,
        lifecycle: ContentLifecycleService,
        *,
        require_generation_receipt: bool = True,
    ) -> None:
        self.lifecycle = lifecycle
        self.store = lifecycle.store
        self.require_generation_receipt = require_generation_receipt
        self.store.migrate()

    @staticmethod
    def _cycle_readiness(
        connection: Any, *, portfolio_cycle_id: str
    ) -> dict[str, Any]:
        cycle = connection.execute(
            "SELECT * FROM portfolio_cycles WHERE portfolio_cycle_id=?",
            (portfolio_cycle_id,),
        ).fetchone()
        if not cycle:
            raise ValueError("unknown portfolio cycle")
        cycle_metadata = _parse_json_object(
            cycle["metadata_json"], label="portfolio cycle metadata"
        )
        readiness_id = str(cycle_metadata.get("readiness_id") or "").strip()
        if not readiness_id:
            raise ContentLifecycleConflict(
                "portfolio cycle has no bound memory readiness receipt"
            )
        readiness = connection.execute(
            "SELECT * FROM readiness_receipts WHERE readiness_id=?",
            (readiness_id,),
        ).fetchone()
        if not readiness:
            raise ContentLifecycleConflict(
                "portfolio cycle memory readiness receipt is missing"
            )
        readiness_payload = _parse_json_object(
            readiness["recall_probe_json"], label="memory readiness receipt"
        )
        if (
            str(readiness_payload.get("status") or "") != readiness["status"]
            or str(readiness_payload.get("schema_version") or "")
            != READINESS_SCHEMA_VERSION
        ):
            raise ContentLifecycleConflict(
                "portfolio cycle memory readiness receipt is inconsistent"
            )
        return {
            "readiness_id": readiness_id,
            "status": readiness["status"],
            "last_verified_memory_at": readiness_payload.get(
                "last_verified_memory_at"
            ),
            "failed_component": readiness_payload.get("failed_component"),
        }

    def _load_binding(
        self,
        *,
        opportunity_id: str,
        portfolio_cycle_id: str,
        allow_review: bool,
    ) -> dict[str, Any]:
        with self.store.connection() as connection:
            cycle_readiness = self._cycle_readiness(
                connection, portfolio_cycle_id=portfolio_cycle_id
            )
            if cycle_readiness["status"] != "ready":
                raise ContentLifecycleConflict(
                    "portfolio-selected drafting requires ready verified memory"
                )
            selection = connection.execute(
                """SELECT * FROM portfolio_selections
                WHERE portfolio_cycle_id=? AND opportunity_id=? AND disposition='selected'
                ORDER BY selected_at,selection_id LIMIT 1""",
                (portfolio_cycle_id, opportunity_id),
            ).fetchone()
            if not selection:
                raise ContentLifecycleConflict(
                    "portfolio drafting requires an exact selected opportunity"
                )
            opportunity = connection.execute(
                "SELECT * FROM content_opportunities WHERE opportunity_id=?",
                (opportunity_id,),
            ).fetchone()
            if not opportunity:
                raise ValueError("unknown content opportunity")
            if bool(opportunity["owner_requested"]):
                raise ContentLifecycleConflict(
                    "owner-requested opportunity requires owner-requested drafting authority"
                )
            allowed_statuses = {"selected", "drafting"}
            if allow_review:
                allowed_statuses.add("review")
            if opportunity["status"] not in allowed_statuses:
                raise ContentLifecycleConflict(
                    "portfolio-selected opportunity is no longer draftable"
                )
            if (
                opportunity["truth_state"] != "pass"
                or opportunity["safety_state"] not in {"pass", "owner_review_required"}
                or opportunity["attribution_state"] not in {"pass", "required"}
            ):
                raise ContentLifecycleConflict(
                    "portfolio-selected opportunity failed a truth, safety, privacy, or attribution gate"
                )
            sources = connection.execute(
                """SELECT s.* FROM opportunity_sources os
                JOIN sources s ON s.source_id=os.source_id
                WHERE os.opportunity_id=? AND os.relationship_kind='material_source'
                ORDER BY s.source_id""",
                (opportunity_id,),
            ).fetchall()
            if len(sources) != 1:
                raise ContentLifecycleConflict(
                    "Version 1 portfolio drafting requires exactly one material source"
                )
            source = sources[0]
            if (
                source["merged_into_source_id"]
                or source["admissibility_state"] != "admissible"
                or source["rights_state"] not in {"permitted", "owner_controlled"}
            ):
                raise ContentLifecycleConflict(
                    "portfolio-selected source is not an active admissible canonical source"
                )
            metadata = _parse_json_object(
                opportunity["metadata_json"], label="content opportunity metadata"
            )
            integrity = (
                metadata.get("integrity")
                if isinstance(metadata.get("integrity"), dict)
                else {}
            )
            privacy_state = str(
                integrity.get("privacy_state")
                or metadata.get("privacy_state")
                or opportunity["safety_state"]
            )
            if privacy_state not in {"pass", "owner_review_required"}:
                raise ContentLifecycleConflict(
                    "portfolio-selected opportunity failed its privacy gate"
                )
            evidence_id = str(metadata.get("evidence_id") or "").strip()
            if not evidence_id:
                raise ContentLifecycleConflict(
                    "portfolio-selected opportunity has no routed authoritative evidence"
                )
            evidence = connection.execute(
                "SELECT * FROM evidence_records WHERE evidence_id=? AND source_id=?",
                (evidence_id, source["source_id"]),
            ).fetchone()
            if not evidence or not evidence["artifact_id"]:
                raise ContentLifecycleConflict(
                    "portfolio-selected opportunity evidence is missing or belongs to another source"
                )
            artifact = connection.execute(
                "SELECT * FROM artifacts WHERE artifact_id=?",
                (evidence["artifact_id"],),
            ).fetchone()
            if not artifact:
                raise ContentLifecycleConflict(
                    "portfolio-selected authoritative evidence artifact is missing"
                )
        sharing = source_remote_sharing(source)
        if sharing is None:
            raise ContentLifecycleConflict(
                "portfolio-selected source has no explicit public-cloud sharing classification"
            )
        return {
            "selection": dict(selection),
            "opportunity": dict(opportunity),
            "opportunity_metadata": metadata,
            "source": dict(source),
            "evidence": dict(evidence),
            "artifact": dict(artifact),
            "source_sharing": sharing,
            "cycle_readiness": cycle_readiness,
        }

    def _existing_base_revision(
        self, *, opportunity_id: str, revision_key: str
    ) -> dict[str, Any] | None:
        with self.store.connection() as connection:
            post = connection.execute(
                "SELECT * FROM canonical_posts WHERE opportunity_id=?",
                (opportunity_id,),
            ).fetchone()
            if not post:
                return None
            revision = connection.execute(
                """SELECT r.*,a.content_sha256,a.logical_ref
                FROM content_revisions r
                JOIN artifacts a ON a.artifact_id=r.body_artifact_id
                WHERE r.post_id=? AND r.idempotency_key=?""",
                (post["post_id"], revision_key),
            ).fetchone()
            if not revision or revision["revision_kind"] != "base":
                raise ContentLifecycleConflict(
                    "portfolio-selected opportunity already has a different canonical post"
                )
            opportunity = connection.execute(
                "SELECT metadata_json FROM content_opportunities WHERE opportunity_id=?",
                (opportunity_id,),
            ).fetchone()
        metadata = _parse_json_object(
            opportunity["metadata_json"], label="content opportunity metadata"
        )
        receipt = metadata.get("generation_receipt")
        if receipt is not None and not isinstance(receipt, dict):
            raise ContentLifecycleConflict("canonical generation receipt is malformed")
        return {
            "post": dict(post),
            "revision": dict(revision),
            "generation_receipt": receipt,
        }

    def _validate_existing_base_revision(
        self,
        *,
        existing_revision: Mapping[str, Any],
        binding: Mapping[str, Any],
        controls_json: str,
    ) -> str | None:
        revision = existing_revision["revision"]
        if revision["control_json"] != controls_json:
            raise ContentLifecycleConflict(
                "persisted canonical draft controls do not match the drafting job"
            )
        body = self.lifecycle.artifact_store.read_text(revision["logical_ref"])
        body_sha256 = hashlib.sha256(body.encode("utf-8")).hexdigest()
        if body_sha256 != revision["content_sha256"]:
            raise ContentLifecycleConflict(
                "persisted canonical draft artifact hash mismatch"
            )
        evidence_binding = _parse_json_object(
            revision["evidence_binding_json"],
            label="persisted canonical evidence binding",
        )
        if (
            evidence_binding.get("source_id")
            != binding["source"]["source_id"]
            or evidence_binding.get("evidence_id")
            != binding["evidence"]["evidence_id"]
            or evidence_binding.get("artifact_sha256")
            != binding["artifact"]["content_sha256"]
        ):
            raise ContentLifecycleConflict(
                "persisted canonical draft evidence binding changed"
            )
        receipt = existing_revision["generation_receipt"]
        if self.require_generation_receipt and receipt is None:
            raise ContentLifecycleConflict(
                "persisted portfolio draft has no production generation receipt"
            )
        if receipt is None:
            return None
        source_body = self.lifecycle.artifact_store.read_text(
            binding["artifact"]["logical_ref"]
        )
        if (
            hashlib.sha256(source_body.encode("utf-8")).hexdigest()
            != binding["artifact"]["content_sha256"]
        ):
            raise ContentLifecycleConflict(
                "persisted portfolio draft source artifact hash mismatch"
            )
        source_excerpt = _evidence_bound_excerpt(
            source_body=source_body,
            evidence=binding["evidence"],
            artifact=binding["artifact"],
        )
        _validate_generation_receipt_binding(
            receipt,
            body=body,
            source_id=binding["source"]["source_id"],
            evidence_id=binding["evidence"]["evidence_id"],
            artifact_sha256=binding["artifact"]["content_sha256"],
            source_excerpt=source_excerpt,
            controls=_parse_json_object(
                controls_json, label="persisted canonical draft controls"
            ),
            expected_draft_authority="portfolio_selected",
        )
        return _sha256_json(receipt)

    def _claim_job(
        self,
        *,
        binding: Mapping[str, Any],
        portfolio_cycle_id: str,
        controls: Mapping[str, Any],
        revision_key: str,
        now: datetime,
    ) -> tuple[dict[str, Any], str | None, bool]:
        opportunity_id = binding["opportunity"]["opportunity_id"]
        job_key = f"portfolio-selected-draft:{opportunity_id}"
        job_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:generation-job:{job_key}"))
        controls_json = _canonical_json(dict(controls))
        controls_sha256 = hashlib.sha256(controls_json.encode("utf-8")).hexdigest()
        now_text = now.isoformat()
        existing_revision = self._existing_base_revision(
            opportunity_id=opportunity_id,
            revision_key=revision_key,
        )
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """INSERT INTO content_generation_jobs(
                        generation_job_id,opportunity_id,portfolio_cycle_id,draft_authority,
                        status,controls_json,controls_sha256,source_id,evidence_id,artifact_sha256,
                        created_at,updated_at,idempotency_key
                    ) VALUES (?,?,?,'portfolio_selected','queued',?,?,?,?,?,?,?,?)
                    ON CONFLICT(opportunity_id) DO NOTHING""",
                    (
                        job_id,
                        opportunity_id,
                        portfolio_cycle_id,
                        controls_json,
                        controls_sha256,
                        binding["source"]["source_id"],
                        binding["evidence"]["evidence_id"],
                        binding["artifact"]["content_sha256"],
                        now_text,
                        now_text,
                        job_key,
                    ),
                )
                job = connection.execute(
                    "SELECT * FROM content_generation_jobs WHERE opportunity_id=?",
                    (opportunity_id,),
                ).fetchone()
                if not job:
                    raise RuntimeError("content generation job persistence failed")
                expected = {
                    "draft_authority": "portfolio_selected",
                    "controls_json": controls_json,
                    "controls_sha256": controls_sha256,
                    "source_id": binding["source"]["source_id"],
                    "evidence_id": binding["evidence"]["evidence_id"],
                    "artifact_sha256": binding["artifact"]["content_sha256"],
                    "idempotency_key": job_key,
                }
                if any(job[key] != value for key, value in expected.items()):
                    raise ContentLifecycleConflict(
                        "portfolio drafting job conflicts with its immutable source or control binding"
                    )
                lease_expires_at = None
                if job["lease_expires_at"]:
                    try:
                        lease_expires_at = datetime.fromisoformat(
                            job["lease_expires_at"]
                        )
                    except ValueError as exc:
                        raise ContentLifecycleConflict(
                            "content drafting lease timestamp is malformed"
                        ) from exc
                    if lease_expires_at.tzinfo is None:
                        raise ContentLifecycleConflict(
                            "content drafting lease timestamp has no timezone"
                        )
                healthy_running_lease = (
                    job["status"] == "running"
                    and lease_expires_at is not None
                    and lease_expires_at > now
                )
                if job["portfolio_cycle_id"] != portfolio_cycle_id:
                    if healthy_running_lease:
                        raise ContentDraftingInProgress(
                            "portfolio-selected canonical drafting is already in progress"
                        )
                    if existing_revision is not None or job["status"] == "succeeded":
                        raise ContentLifecycleConflict(
                            "completed portfolio drafting job belongs to another portfolio cycle"
                        )
                if existing_revision is not None:
                    revision = existing_revision["revision"]
                    receipt_sha256 = self._validate_existing_base_revision(
                        existing_revision=existing_revision,
                        binding=binding,
                        controls_json=controls_json,
                    )
                    if (
                        job["generation_receipt_sha256"] is not None
                        and job["generation_receipt_sha256"] != receipt_sha256
                    ):
                        raise ContentLifecycleConflict(
                            "persisted portfolio draft receipt conflicts with its drafting job"
                        )
                    connection.execute(
                        """UPDATE content_generation_jobs
                        SET status='succeeded',lease_token=NULL,lease_expires_at=NULL,
                            post_id=?,revision_id=?,generation_receipt_sha256=?,safe_error_code=NULL,
                            updated_at=?,completed_at=?
                        WHERE generation_job_id=?""",
                        (
                            existing_revision["post"]["post_id"],
                            revision["revision_id"],
                            receipt_sha256,
                            now_text,
                            now_text,
                            job["generation_job_id"],
                        ),
                    )
                    connection.execute("COMMIT")
                    return (
                        dict(
                            connection.execute(
                                "SELECT * FROM content_generation_jobs WHERE generation_job_id=?",
                                (job["generation_job_id"],),
                            ).fetchone()
                        ),
                        None,
                        True,
                    )
                if job["status"] == "succeeded":
                    raise ContentLifecycleConflict(
                        "successful drafting job has no recoverable canonical revision"
                    )
                if healthy_running_lease:
                    raise ContentDraftingInProgress(
                        "portfolio-selected canonical drafting is already in progress"
                    )
                lease_token = str(uuid.uuid4())
                lease_expiry = (now + timedelta(seconds=_LEASE_SECONDS)).isoformat()
                connection.execute(
                    """UPDATE content_generation_jobs
                    SET status='running',attempt_count=attempt_count+1,lease_token=?,
                        lease_expires_at=?,safe_error_code=NULL,updated_at=?,
                        portfolio_cycle_id=?
                    WHERE generation_job_id=?""",
                    (
                        lease_token,
                        lease_expiry,
                        now_text,
                        portfolio_cycle_id,
                        job["generation_job_id"],
                    ),
                )
                connection.execute(
                    """UPDATE content_opportunities
                    SET status='drafting',updated_at=?
                    WHERE opportunity_id=? AND status='selected'""",
                    (now_text, opportunity_id),
                )
                claimed = connection.execute(
                    "SELECT * FROM content_generation_jobs WHERE generation_job_id=?",
                    (job["generation_job_id"],),
                ).fetchone()
                connection.execute("COMMIT")
                return dict(claimed), lease_token, False
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def _mark_failed(
        self, *, generation_job_id: str, lease_token: str, safe_error_code: str
    ) -> None:
        now = _utcnow()
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                job = connection.execute(
                    "SELECT * FROM content_generation_jobs WHERE generation_job_id=?",
                    (generation_job_id,),
                ).fetchone()
                if (
                    job
                    and job["status"] == "running"
                    and job["lease_token"] == lease_token
                ):
                    connection.execute(
                        """UPDATE content_generation_jobs
                        SET status='failed',lease_token=NULL,lease_expires_at=NULL,
                            safe_error_code=?,updated_at=? WHERE generation_job_id=?""",
                        (safe_error_code, now, generation_job_id),
                    )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def _complete_job(
        self,
        *,
        generation_job_id: str,
        lease_token: str,
        post_id: str,
        revision_id: str,
        generation_receipt_sha256: str | None,
    ) -> dict[str, Any]:
        now = _utcnow()
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                job = connection.execute(
                    "SELECT * FROM content_generation_jobs WHERE generation_job_id=?",
                    (generation_job_id,),
                ).fetchone()
                if (
                    not job
                    or job["status"] != "running"
                    or job["lease_token"] != lease_token
                ):
                    raise ContentLifecycleConflict(
                        "portfolio drafting lease changed before completion"
                    )
                revision = connection.execute(
                    """SELECT r.*,p.opportunity_id,p.current_revision_id,
                        o.metadata_json AS opportunity_metadata_json
                    FROM content_revisions r
                    JOIN canonical_posts p ON p.post_id=r.post_id
                    JOIN content_opportunities o ON o.opportunity_id=p.opportunity_id
                    WHERE r.revision_id=? AND r.post_id=?""",
                    (revision_id, post_id),
                ).fetchone()
                if (
                    not revision
                    or revision["opportunity_id"] != job["opportunity_id"]
                    or revision["revision_kind"] != "base"
                    or revision["current_revision_id"] != revision_id
                    or revision["control_json"] != job["controls_json"]
                    or hashlib.sha256(
                        revision["control_json"].encode("utf-8")
                    ).hexdigest()
                    != job["controls_sha256"]
                ):
                    raise ContentLifecycleConflict(
                        "portfolio drafting completion cannot verify its canonical revision"
                    )
                evidence_binding = _parse_json_object(
                    revision["evidence_binding_json"],
                    label="completed canonical evidence binding",
                )
                if (
                    evidence_binding.get("source_id") != job["source_id"]
                    or evidence_binding.get("evidence_id") != job["evidence_id"]
                    or evidence_binding.get("artifact_sha256")
                    != job["artifact_sha256"]
                ):
                    raise ContentLifecycleConflict(
                        "portfolio drafting completion evidence binding changed"
                    )
                opportunity_metadata = _parse_json_object(
                    revision["opportunity_metadata_json"],
                    label="completed content opportunity metadata",
                )
                persisted_receipt = opportunity_metadata.get("generation_receipt")
                if persisted_receipt is not None and not isinstance(
                    persisted_receipt, dict
                ):
                    raise ContentLifecycleConflict(
                        "portfolio drafting completion receipt is malformed"
                    )
                persisted_receipt_sha256 = (
                    _sha256_json(persisted_receipt)
                    if persisted_receipt is not None
                    else None
                )
                if (
                    persisted_receipt_sha256 != generation_receipt_sha256
                    or (
                        self.require_generation_receipt
                        and persisted_receipt_sha256 is None
                    )
                ):
                    raise ContentLifecycleConflict(
                        "portfolio drafting completion receipt binding changed"
                    )
                connection.execute(
                    """UPDATE content_generation_jobs
                    SET status='succeeded',lease_token=NULL,lease_expires_at=NULL,
                        post_id=?,revision_id=?,generation_receipt_sha256=?,safe_error_code=NULL,
                        updated_at=?,completed_at=? WHERE generation_job_id=?""",
                    (
                        post_id,
                        revision_id,
                        generation_receipt_sha256,
                        now,
                        now,
                        generation_job_id,
                    ),
                )
                completed = connection.execute(
                    "SELECT * FROM content_generation_jobs WHERE generation_job_id=?",
                    (generation_job_id,),
                ).fetchone()
                connection.execute("COMMIT")
                return dict(completed)
            except Exception:
                connection.execute("ROLLBACK")
                raise

    async def draft_one(
        self,
        *,
        opportunity_id: str,
        portfolio_cycle_id: str,
        generator: Callable[[dict[str, Any]], Awaitable[Any]],
        controls: Mapping[str, Any] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        stage = "preflight"
        job: dict[str, Any] | None = None
        lease_token: str | None = None
        try:
            binding = self._load_binding(
                opportunity_id=opportunity_id,
                portfolio_cycle_id=portfolio_cycle_id,
                allow_review=True,
            )
            normalized_controls = normalized_remote_controls(
                controls
                if controls is not None
                else default_portfolio_drafting_controls(
                    binding["opportunity_metadata"]
                )
            )
            revision_key = f"portfolio-selected-base:{opportunity_id}"
            stage = "job_claim"
            job, lease_token, replayed = self._claim_job(
                binding=binding,
                portfolio_cycle_id=portfolio_cycle_id,
                controls=normalized_controls,
                revision_key=revision_key,
                now=now,
            )
            if replayed:
                post = self.lifecycle.get_post(str(job["post_id"]))
                self._append_completed_event(
                    job=job,
                    binding=binding,
                    portfolio_cycle_id=portfolio_cycle_id,
                    replayed=True,
                )
                return {
                    "schema_version": PORTFOLIO_DRAFTING_JOB_SCHEMA,
                    "status": "succeeded",
                    "replayed": True,
                    "generation_job": job,
                    **post,
                }
            stage = "post_claim_revalidation"
            binding = self._load_binding(
                opportunity_id=opportunity_id,
                portfolio_cycle_id=portfolio_cycle_id,
                allow_review=False,
            )

            stage = "artifact_verification"
            source_body = self.lifecycle.artifact_store.read_text(
                binding["artifact"]["logical_ref"]
            )
            if (
                hashlib.sha256(source_body.encode("utf-8")).hexdigest()
                != binding["artifact"]["content_sha256"]
            ):
                raise ContentLifecycleConflict(
                    "portfolio-selected authoritative evidence artifact hash mismatch"
                )
            source_body = _evidence_bound_excerpt(
                source_body=source_body,
                evidence=binding["evidence"],
                artifact=binding["artifact"],
            )
            source = binding["source"]
            evidence = binding["evidence"]
            thesis = str(binding["opportunity"]["thesis"])
            request = {
                "topic": thesis,
                "context": {
                    "schema_version": CONTENT_POST_GENERATION_CONTEXT_SCHEMA,
                    "draft_authority": "portfolio_selected",
                    "source_id": source["source_id"],
                    "evidence_id": evidence["evidence_id"],
                    "artifact_sha256": binding["artifact"]["content_sha256"],
                    "source_excerpt": source_body,
                    "source_title": source["title"],
                    "source_author": source["author_or_publisher"],
                    "source_url": source["canonical_url"],
                    "source_sharing": binding["source_sharing"],
                    "controls": normalized_controls,
                    "rules": [
                        "Do not present external ideas as firsthand experience",
                        "Preserve explicit attribution",
                        "Use owner persona and approved worldview only",
                    ],
                },
                "content_type": "canonical_post",
            }
            stage = "generation"
            generated_value = await generator(request)
            generated_options, generation_receipt = unpack_integrated_generation_result(
                generated_value
            )
            options = [item.strip() for item in generated_options if item.strip()]
            if len(options) != 1:
                raise ContentLifecycleConflict(
                    "portfolio drafting generator must return exactly one canonical draft"
                )
            body = options[0]
            if self.require_generation_receipt and generation_receipt is None:
                raise ContentLifecycleConflict(
                    "portfolio drafting requires a production generation receipt"
                )
            if generation_receipt is not None:
                _validate_generation_receipt_binding(
                    generation_receipt,
                    body=body,
                    source_id=source["source_id"],
                    evidence_id=evidence["evidence_id"],
                    artifact_sha256=binding["artifact"]["content_sha256"],
                    source_excerpt=source_body,
                    controls=normalized_controls,
                    expected_draft_authority="portfolio_selected",
                )

            stage = "integrity_gate"
            public_source_name = (
                source["author_or_publisher"]
                or source["title"]
                or "Original source"
            )
            attribution_required = (
                binding["opportunity"]["attribution_state"] == "required"
            )
            attribution = {
                "required": attribution_required,
                "in_copy_required": attribution_required,
                "public_source_name": (
                    public_source_name if attribution_required else None
                ),
                "public_source_url": source["canonical_url"],
            }
            grounding_anchors = self.lifecycle.derive_grounding_anchors(
                source_body=source_body,
                draft_body=body,
                exclude_text=public_source_name,
                limit=2,
            )
            if len(grounding_anchors) < 2:
                raise ContentLifecycleConflict(
                    "portfolio canonical copy does not retain enough authoritative evidence anchors"
                )
            evidence_binding = {
                "evidence_id": evidence["evidence_id"],
                "artifact_sha256": binding["artifact"]["content_sha256"],
                "source_id": source["source_id"],
                "required_terms": grounding_anchors,
            }
            self.lifecycle.validate_variant_integrity(
                parent_body=body,
                variant_body=body,
                thesis=thesis,
                evidence_binding=evidence_binding,
                attribution=attribution,
            )

            stage = "state_revalidation"
            revalidated = self._load_binding(
                opportunity_id=opportunity_id,
                portfolio_cycle_id=portfolio_cycle_id,
                allow_review=False,
            )
            immutable_binding = (
                "selection",
                "opportunity",
                "source",
                "evidence",
                "artifact",
                "source_sharing",
                "cycle_readiness",
            )
            if any(
                _canonical_json(revalidated[key]) != _canonical_json(binding[key])
                for key in immutable_binding
            ):
                raise ContentLifecycleConflict(
                    "portfolio drafting source or lifecycle state changed before persistence"
                )
            with self.store.connection() as connection:
                current_job = connection.execute(
                    "SELECT status,lease_token FROM content_generation_jobs WHERE generation_job_id=?",
                    (job["generation_job_id"],),
                ).fetchone()
            if (
                not current_job
                or current_job["status"] != "running"
                or current_job["lease_token"] != lease_token
            ):
                raise ContentLifecycleConflict(
                    "portfolio drafting lease changed before canonical persistence"
                )

            stage = "canonical_persistence"
            post = self.lifecycle.create_canonical_post(
                opportunity_id=opportunity_id,
                body=body,
                evidence_binding=evidence_binding,
                attribution=attribution,
                controls=normalized_controls,
                idempotency_key=revision_key,
                generation_receipt=generation_receipt,
            )
            revision_id = str(post["revisions"][0]["revision_id"])
            receipt_sha256 = (
                _sha256_json(generation_receipt)
                if generation_receipt is not None
                else None
            )
            stage = "job_completion"
            job = self._complete_job(
                generation_job_id=job["generation_job_id"],
                lease_token=str(lease_token),
                post_id=str(post["post"]["post_id"]),
                revision_id=revision_id,
                generation_receipt_sha256=receipt_sha256,
            )
            self._append_completed_event(
                job=job,
                binding=binding,
                portfolio_cycle_id=portfolio_cycle_id,
                replayed=False,
            )
            return {
                "schema_version": PORTFOLIO_DRAFTING_JOB_SCHEMA,
                "status": "succeeded",
                "replayed": False,
                "generation_job": job,
                **post,
            }
        except ContentDraftingInProgress:
            raise
        except Exception as exc:
            safe_error_code = _safe_error_code(exc, stage=stage)
            if job is not None and lease_token is not None:
                self._mark_failed(
                    generation_job_id=job["generation_job_id"],
                    lease_token=lease_token,
                    safe_error_code=safe_error_code,
                )
            self.store.append_event(
                event_type="content_drafting.failed",
                aggregate_type="content_opportunity",
                aggregate_id=opportunity_id,
                actor_type="content_drafting_orchestrator",
                payload={
                    "schema_version": PORTFOLIO_DRAFTING_JOB_SCHEMA,
                    "draft_authority": "portfolio_selected",
                    "generation_job_id": (
                        job.get("generation_job_id") if job is not None else None
                    ),
                    "attempt_count": (
                        int(job.get("attempt_count") or 0) if job is not None else 0
                    ),
                    "failed_component": stage,
                    "safe_error_code": safe_error_code,
                },
                provenance={
                    "policy_version": PORTFOLIO_DRAFTING_POLICY,
                    "portfolio_cycle_id": portfolio_cycle_id,
                },
                idempotency_key=(
                    f"portfolio-drafting-failed:{portfolio_cycle_id}:{opportunity_id}:"
                    f"{int(job.get('attempt_count') or 0) if job is not None else 0}:"
                    f"{safe_error_code}"
                ),
            )
            raise

    def _append_completed_event(
        self,
        *,
        job: Mapping[str, Any],
        binding: Mapping[str, Any],
        portfolio_cycle_id: str,
        replayed: bool,
    ) -> None:
        self.store.append_event(
            event_type="content_drafting.completed",
            aggregate_type="content_opportunity",
            aggregate_id=binding["opportunity"]["opportunity_id"],
            actor_type="content_drafting_orchestrator",
            payload={
                "schema_version": PORTFOLIO_DRAFTING_JOB_SCHEMA,
                "draft_authority": "portfolio_selected",
                "generation_job_id": job["generation_job_id"],
                "post_id": job["post_id"],
                "revision_id": job["revision_id"],
                "generation_receipt_sha256": job["generation_receipt_sha256"],
                "status": "succeeded",
            },
            provenance={
                "policy_version": PORTFOLIO_DRAFTING_POLICY,
                "portfolio_cycle_id": portfolio_cycle_id,
                "selection_id": binding["selection"]["selection_id"],
            },
            artifact_refs=[binding["artifact"]["artifact_id"]],
            idempotency_key=(
                f"portfolio-drafting-completed:{binding['opportunity']['opportunity_id']}"
            ),
        )

    async def run_cycle(
        self,
        *,
        portfolio_cycle_id: str,
        readiness: Mapping[str, Any],
        generator: Callable[[dict[str, Any]], Awaitable[Any]],
        development_slots: int = 3,
    ) -> dict[str, Any]:
        if not 1 <= development_slots <= 10:
            raise ValueError("content drafting development slots must be between one and ten")
        with self.store.connection() as connection:
            try:
                cycle_readiness = self._cycle_readiness(
                    connection, portfolio_cycle_id=portfolio_cycle_id
                )
            except (ContentLifecycleConflict, ValueError) as exc:
                cycle_readiness = {
                    "readiness_id": None,
                    "status": "degraded",
                    "last_verified_memory_at": None,
                    "failed_component": "memory_readiness_binding",
                    "safe_error_code": _safe_error_code(
                        exc, stage="memory_readiness_binding"
                    ),
                }
            selected_rows = connection.execute(
                """SELECT selection.opportunity_id,opportunity.owner_requested
                FROM portfolio_selections AS selection
                JOIN content_opportunities AS opportunity
                  ON opportunity.opportunity_id=selection.opportunity_id
                WHERE selection.portfolio_cycle_id=?
                  AND selection.disposition='selected'
                ORDER BY selection.selected_at,selection.opportunity_id""",
                (portfolio_cycle_id,),
            ).fetchall()
            selected_ids = [row["opportunity_id"] for row in selected_rows]
            ordinary_selected_count = sum(
                1 for row in selected_rows if not bool(row["owner_requested"])
            )
        if ordinary_selected_count > development_slots:
            raise ContentLifecycleConflict(
                "portfolio selection exceeds the bounded canonical drafting capacity"
            )
        supplied_readiness_id = str(readiness.get("readiness_id") or "").strip()
        supplied_status = str(readiness.get("status") or "").strip()
        readiness_bound = (
            bool(supplied_readiness_id)
            and supplied_readiness_id == cycle_readiness.get("readiness_id")
            and supplied_status == cycle_readiness.get("status")
        )
        if cycle_readiness.get("status") != "ready" or not readiness_bound:
            failed_component = str(
                cycle_readiness.get("failed_component")
                or (
                    "memory_readiness_binding"
                    if not readiness_bound
                    else "memory_readiness"
                )
            )
            payload = {
                "schema_version": PORTFOLIO_DRAFTING_SCHEMA,
                "status": "degraded",
                "portfolio_cycle_id": portfolio_cycle_id,
                "selected_count": len(selected_ids),
                "succeeded_count": 0,
                "failed_count": 0,
                "in_progress_count": 0,
                "results": [],
                "failures": [],
                "failed_component": failed_component,
                "last_verified_memory_at": cycle_readiness.get(
                    "last_verified_memory_at"
                ),
                "fresh_source_drafting_allowed": False,
            }
            self.store.append_event(
                event_type="content_drafting.degraded",
                aggregate_type="portfolio_cycle",
                aggregate_id=portfolio_cycle_id,
                actor_type="content_drafting_orchestrator",
                payload=payload,
                provenance={
                    "policy_version": PORTFOLIO_DRAFTING_POLICY,
                    "readiness_id": cycle_readiness.get("readiness_id"),
                    "supplied_readiness_matches_cycle": readiness_bound,
                },
                idempotency_key=(
                    f"portfolio-drafting-readiness-degraded:{portfolio_cycle_id}:"
                    f"{cycle_readiness.get('readiness_id') or 'missing'}:"
                    f"{failed_component}:{_sha256_json(payload)[:16]}"
                ),
            )
            return payload
        if not selected_ids:
            payload = {
                "schema_version": PORTFOLIO_DRAFTING_SCHEMA,
                "status": "healthy_no_change",
                "portfolio_cycle_id": portfolio_cycle_id,
                "selected_count": 0,
                "succeeded_count": 0,
                "failed_count": 0,
                "in_progress_count": 0,
                "results": [],
                "failures": [],
            }
            self.store.append_event(
                event_type="content_drafting.no_change",
                aggregate_type="portfolio_cycle",
                aggregate_id=portfolio_cycle_id,
                actor_type="content_drafting_orchestrator",
                payload=payload,
                provenance={"policy_version": PORTFOLIO_DRAFTING_POLICY},
                idempotency_key=f"portfolio-drafting-no-change:{portfolio_cycle_id}",
            )
            return payload
        results: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []
        in_progress: list[str] = []
        for opportunity_id in selected_ids:
            try:
                result = await self.draft_one(
                    opportunity_id=opportunity_id,
                    portfolio_cycle_id=portfolio_cycle_id,
                    generator=generator,
                )
                results.append(
                    {
                        "opportunity_id": opportunity_id,
                        "generation_job_id": result["generation_job"]["generation_job_id"],
                        "post_id": result["post"]["post_id"],
                        "revision_id": result["generation_job"]["revision_id"],
                        "replayed": result["replayed"],
                    }
                )
            except ContentDraftingInProgress:
                in_progress.append(opportunity_id)
            except Exception as exc:
                failures.append(
                    {
                        "opportunity_id": opportunity_id,
                        "safe_error_code": _safe_error_code(
                            exc, stage="selected_opportunity"
                        ),
                    }
                )
        status = "complete" if not failures and not in_progress else "degraded"
        payload = {
            "schema_version": PORTFOLIO_DRAFTING_SCHEMA,
            "status": status,
            "portfolio_cycle_id": portfolio_cycle_id,
            "selected_count": len(selected_ids),
            "succeeded_count": len(results),
            "failed_count": len(failures),
            "in_progress_count": len(in_progress),
            "results": results,
            "failures": failures,
            "in_progress_opportunity_ids": in_progress,
        }
        event_type = (
            "content_drafting.batch_completed"
            if status == "complete"
            else "content_drafting.batch_degraded"
        )
        digest = _sha256_json(payload)[:16]
        self.store.append_event(
            event_type=event_type,
            aggregate_type="portfolio_cycle",
            aggregate_id=portfolio_cycle_id,
            actor_type="content_drafting_orchestrator",
            payload=payload,
            provenance={
                "policy_version": PORTFOLIO_DRAFTING_POLICY,
                "readiness_id": readiness.get("readiness_id"),
            },
            idempotency_key=(
                f"portfolio-drafting-batch:{portfolio_cycle_id}:{status}:{digest}"
            ),
        )
        return payload
