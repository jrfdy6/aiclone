from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import Any, Mapping

from app.services.integrated_system_store import IntegratedSystemStore, _canonical_json, _utcnow


class ContentLifecycleConflict(ValueError):
    pass


_WORD_RE = re.compile(r"[a-z0-9]+")
_PRIVATE_LITERAL_RE = re.compile(
    r"(?:/Users/|/home/|BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY|"
    r"\b(?:api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=])",
    re.IGNORECASE,
)
_TERM_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "because",
        "before",
        "but",
        "by",
        "for",
        "from",
        "how",
        "i",
        "in",
        "into",
        "is",
        "it",
        "my",
        "of",
        "on",
        "or",
        "our",
        "that",
        "the",
        "their",
        "this",
        "to",
        "we",
        "when",
        "with",
    }
)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _clean(value: str) -> str:
    return " ".join(value.split()).strip()


def _json_object(value: str | Mapping[str, Any], *, label: str) -> dict[str, Any]:
    parsed: Any = json.loads(value) if isinstance(value, str) else dict(value)
    if not isinstance(parsed, dict):
        raise ContentLifecycleConflict(f"{label} must be an object")
    return parsed


def _term_root(value: str) -> str:
    """Return a conservative lexical root for deterministic integrity checks."""

    if len(value) >= 8:
        return value[:6]
    if len(value) >= 6:
        return value[:5]
    return value


def _terms(value: str) -> set[str]:
    return {
        _term_root(token)
        for token in _WORD_RE.findall(value.lower())
        if len(token) >= 3 and token not in _TERM_STOPWORDS
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean(str(item)) for item in value if _clean(str(item))]


class PrivateContentArtifactStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).expanduser().resolve()

    def write_text(self, body: str, *, artifact_kind: str) -> dict[str, Any]:
        encoded = body.encode("utf-8")
        digest = _sha256_bytes(encoded)
        target = self.root / artifact_kind / digest[:2] / f"{digest}.txt"
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if target.exists():
            if target.is_symlink() or not target.is_file() or target.read_bytes() != encoded:
                raise ContentLifecycleConflict("content-addressed artifact conflicts with existing bytes")
        else:
            descriptor, temporary_name = tempfile.mkstemp(prefix=f".{digest}.", dir=target.parent)
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.chmod(temporary_name, 0o600)
                os.replace(temporary_name, target)
            finally:
                if os.path.exists(temporary_name):
                    os.unlink(temporary_name)
        return {
            "content_sha256": digest,
            "logical_ref": target.relative_to(self.root).as_posix(),
            "byte_size": len(encoded),
            "media_type": "text/plain; charset=utf-8",
        }

    def read_text(self, logical_ref: str) -> str:
        target = (self.root / logical_ref).resolve()
        if self.root != target and self.root not in target.parents:
            raise ContentLifecycleConflict("content artifact escaped the private artifact root")
        if target.is_symlink() or not target.is_file():
            raise ContentLifecycleConflict("content artifact is missing or unsafe")
        return target.read_text(encoding="utf-8")


class ContentLifecycleService:
    def __init__(self, store: IntegratedSystemStore, artifact_store: PrivateContentArtifactStore) -> None:
        self.store = store
        self.artifact_store = artifact_store

    def create_or_reuse_opportunity(
        self,
        *,
        thesis: str,
        idempotency_key: str,
        source_ids: list[str],
        owner_requested: bool = False,
        blockers: list[str] | None = None,
        strategy_contract_ref: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        thesis = _clean(thesis)
        if not thesis:
            raise ValueError("opportunity thesis is required")
        blockers = sorted({_clean(item) for item in blockers or [] if _clean(item)})
        now = _utcnow()
        opportunity_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:opportunity:{idempotency_key}"))
        status = "blocked" if blockers else ("drafting" if owner_requested else "qualified")
        self.store.migrate()
        resolved_opportunity_id = opportunity_id
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                normalized_source_ids = sorted({_clean(source_id) for source_id in source_ids if _clean(source_id)})
                if not normalized_source_ids:
                    raise ValueError("opportunity requires at least one source")
                for source_id in normalized_source_ids:
                    if not connection.execute(
                        "SELECT 1 FROM sources WHERE source_id=? AND merged_into_source_id IS NULL",
                        (source_id,),
                    ).fetchone():
                        raise ValueError(f"unknown source_id: {source_id}")
                row = connection.execute(
                    "SELECT * FROM content_opportunities WHERE idempotency_key = ?",
                    (idempotency_key,),
                ).fetchone()
                if row is None:
                    for candidate in connection.execute(
                        "SELECT * FROM content_opportunities WHERE thesis=? ORDER BY created_at,opportunity_id",
                        (thesis,),
                    ):
                        candidate_sources = {
                            item["source_id"]
                            for item in connection.execute(
                                "SELECT source_id FROM opportunity_sources WHERE opportunity_id=?",
                                (candidate["opportunity_id"],),
                            )
                        }
                        if candidate_sources == set(normalized_source_ids):
                            row = candidate
                            break
                inserted = row is None
                if inserted:
                    connection.execute(
                        """INSERT INTO content_opportunities(
                            opportunity_id,thesis,status,owner_requested,strategy_contract_ref,
                            created_at,updated_at,idempotency_key,metadata_json
                        ) VALUES (?,?,?,?,?,?,?,?,?)""",
                        (
                            opportunity_id,
                            thesis,
                            status,
                            int(owner_requested),
                            strategy_contract_ref,
                            now,
                            now,
                            idempotency_key,
                            _canonical_json({**dict(metadata or {}), "blockers": blockers}),
                        ),
                    )
                    row = connection.execute(
                        "SELECT * FROM content_opportunities WHERE opportunity_id = ?",
                        (opportunity_id,),
                    ).fetchone()
                if not row or row["thesis"] != thesis:
                    raise ContentLifecycleConflict("opportunity idempotency key conflicts with another thesis")
                resolved_opportunity_id = row["opportunity_id"]
                existing_sources = {
                    item["source_id"]
                    for item in connection.execute(
                        "SELECT source_id FROM opportunity_sources WHERE opportunity_id=?",
                        (row["opportunity_id"],),
                    )
                }
                if existing_sources and existing_sources != set(normalized_source_ids):
                    raise ContentLifecycleConflict("opportunity idempotency key conflicts with source lineage")
                if strategy_contract_ref and row["strategy_contract_ref"] and row["strategy_contract_ref"] != strategy_contract_ref:
                    raise ContentLifecycleConflict("opportunity strategy contract conflict")
                if blockers:
                    current_metadata = _json_object(row["metadata_json"], label="opportunity metadata")
                    current_metadata["blockers"] = sorted(
                        set(_string_list(current_metadata.get("blockers"))) | set(blockers)
                    )
                    connection.execute(
                        "UPDATE content_opportunities SET owner_requested=?,status='blocked',metadata_json=?,updated_at=? WHERE opportunity_id=?",
                        (int(owner_requested or row["owner_requested"]), _canonical_json(current_metadata), now, row["opportunity_id"]),
                    )
                elif owner_requested and not row["owner_requested"] and row["status"] != "blocked":
                    next_status = "drafting" if row["status"] in {"qualified", "backlog", "selected", "parked"} else row["status"]
                    connection.execute(
                        "UPDATE content_opportunities SET owner_requested=1,status=?,updated_at=? WHERE opportunity_id=?",
                        (next_status, now, row["opportunity_id"]),
                    )
                for source_id in normalized_source_ids:
                    connection.execute(
                        "INSERT OR IGNORE INTO opportunity_sources(opportunity_id,source_id,relationship_kind) VALUES (?,?,?)",
                        (row["opportunity_id"], source_id, "material_source"),
                    )
                if owner_requested and not blockers:
                    selection_key = f"owner-request:{row['opportunity_id']}"
                    selection_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:selection:{selection_key}"))
                    connection.execute(
                        """INSERT INTO portfolio_selections(
                            selection_id,opportunity_id,disposition,reason_json,selected_at,idempotency_key
                        ) VALUES (?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING""",
                        (selection_id, row["opportunity_id"], "selected", '{"reason":"owner_requested"}', now, selection_key),
                    )
                event_is_creation_identity = inserted or row["idempotency_key"] == idempotency_key
                event_key = f"opportunity-{'created' if event_is_creation_identity else 'reused'}:{idempotency_key}"
                event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:event:{event_key}"))
                current = connection.execute(
                    "SELECT * FROM content_opportunities WHERE opportunity_id=?",
                    (row["opportunity_id"],),
                ).fetchone()
                event_payload = _canonical_json(
                    {"owner_requested": owner_requested, "status": current["status"], "blockers": blockers}
                )
                connection.execute(
                    """INSERT INTO system_events(
                        event_id,event_type,aggregate_type,aggregate_id,occurred_at,actor_type,payload_json,
                        provenance_json,artifact_refs_json,idempotency_key
                    ) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING""",
                    (
                        event_id,
                        "content_opportunity.created" if event_is_creation_identity else "content_opportunity.reused",
                        "content_opportunity",
                        row["opportunity_id"],
                        now,
                        "owner" if owner_requested else "synthesis_router",
                        event_payload,
                        _canonical_json({"source_ids": normalized_source_ids, "strategy_contract_ref": strategy_contract_ref}),
                        "[]",
                        event_key,
                    ),
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
        with self.store.connection() as connection:
            opportunity = dict(
                connection.execute(
                    "SELECT * FROM content_opportunities WHERE opportunity_id=?",
                    (resolved_opportunity_id,),
                ).fetchone()
            )
            selection = connection.execute("SELECT * FROM portfolio_selections WHERE opportunity_id=?", (opportunity["opportunity_id"],)).fetchone()
            return {"opportunity": opportunity, "selection": dict(selection) if selection else None}

    def create_canonical_post(
        self,
        *,
        opportunity_id: str,
        body: str,
        evidence_binding: Mapping[str, Any],
        attribution: Mapping[str, Any],
        controls: Mapping[str, Any] | None = None,
        idempotency_key: str,
        generation_receipt: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = body.strip()
        if not body:
            raise ValueError("canonical post body is required")
        normalized_controls = dict(controls or {})
        controls_json = _canonical_json(normalized_controls)
        existing_post_id: str | None = None
        with self.store.connection() as connection:
            opportunity = connection.execute("SELECT * FROM content_opportunities WHERE opportunity_id=?", (opportunity_id,)).fetchone()
            if not opportunity:
                raise ValueError("unknown opportunity")
            if opportunity["status"] == "blocked":
                raise ContentLifecycleConflict("blocked opportunity cannot create a post")
            normalized_evidence, normalized_attribution, integrity = self._validate_canonical_integrity(
                connection,
                opportunity=opportunity,
                body=body,
                evidence_binding=evidence_binding,
                attribution=attribution,
            )
            existing = connection.execute(
                """SELECT r.*,p.opportunity_id,a.content_sha256
                FROM content_revisions r
                JOIN canonical_posts p ON p.post_id=r.post_id
                JOIN artifacts a ON a.artifact_id=r.body_artifact_id
                WHERE r.idempotency_key=?""",
                (idempotency_key,),
            ).fetchone()
            if existing:
                if (
                    existing["opportunity_id"] != opportunity_id
                    or existing["revision_kind"] != "base"
                    or existing["content_sha256"] != _sha256_text(body)
                    or existing["control_json"] != controls_json
                    or existing["evidence_binding_json"] != _canonical_json(normalized_evidence)
                    or existing["attribution_json"] != _canonical_json(normalized_attribution)
                ):
                    raise ContentLifecycleConflict("canonical revision idempotency conflict")
                if generation_receipt is not None:
                    metadata = _json_object(
                        opportunity["metadata_json"], label="opportunity metadata"
                    )
                    if metadata.get("generation_receipt") != dict(generation_receipt):
                        raise ContentLifecycleConflict(
                            "canonical generation receipt idempotency conflict"
                        )
                existing_post_id = existing["post_id"]
            conflicting_base = connection.execute(
                """SELECT r.idempotency_key FROM canonical_posts p
                JOIN content_revisions r ON r.post_id=p.post_id
                WHERE p.opportunity_id=? AND r.revision_kind='base'
                  AND r.idempotency_key<>?
                ORDER BY r.created_at,r.revision_id LIMIT 1""",
                (opportunity_id, idempotency_key),
            ).fetchone()
            if conflicting_base:
                raise ContentLifecycleConflict(
                    "canonical post already has a different base revision"
                )
        if existing_post_id:
            return self.get_post(existing_post_id)
        artifact = self.artifact_store.write_text(body, artifact_kind="content_revision")
        artifact_row = self.store.put_artifact(artifact_kind="content_revision", metadata={"private": True}, **artifact)
        now = _utcnow()
        with self.store.connection() as connection:
            opportunity = connection.execute("SELECT * FROM content_opportunities WHERE opportunity_id=?", (opportunity_id,)).fetchone()
            if not opportunity or opportunity["status"] == "blocked":
                raise ContentLifecycleConflict("opportunity changed before canonical post persistence")
            post_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:post:{opportunity_id}"))
            revision_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:revision:{idempotency_key}"))
            thesis_sha = _sha256_text(opportunity["thesis"])
            connection.execute("BEGIN IMMEDIATE")
            try:
                opportunity = connection.execute(
                    "SELECT * FROM content_opportunities WHERE opportunity_id=?",
                    (opportunity_id,),
                ).fetchone()
                if not opportunity or opportunity["status"] == "blocked":
                    raise ContentLifecycleConflict("opportunity changed before canonical post persistence")
                if _sha256_text(opportunity["thesis"]) != thesis_sha:
                    raise ContentLifecycleConflict("opportunity thesis changed before canonical post persistence")
                revalidated_evidence, revalidated_attribution, revalidated_integrity = self._validate_canonical_integrity(
                    connection,
                    opportunity=opportunity,
                    body=body,
                    evidence_binding=normalized_evidence,
                    attribution=normalized_attribution,
                )
                if (
                    revalidated_evidence != normalized_evidence
                    or revalidated_attribution != normalized_attribution
                    or revalidated_integrity != integrity
                ):
                    raise ContentLifecycleConflict("canonical integrity state changed before persistence")
                connection.execute(
                    """INSERT INTO canonical_posts(post_id,opportunity_id,status,created_at,updated_at,metadata_json)
                    VALUES (?,?, 'draft', ?, ?, '{}') ON CONFLICT(opportunity_id) DO NOTHING""",
                    (post_id, opportunity_id, now, now),
                )
                post = connection.execute("SELECT * FROM canonical_posts WHERE opportunity_id=?", (opportunity_id,)).fetchone()
                conflicting_base = connection.execute(
                    """SELECT idempotency_key FROM content_revisions
                    WHERE post_id=? AND revision_kind='base' AND idempotency_key<>?
                    ORDER BY created_at,revision_id LIMIT 1""",
                    (post["post_id"], idempotency_key),
                ).fetchone()
                if conflicting_base:
                    raise ContentLifecycleConflict(
                        "canonical post already has a different base revision"
                    )
                connection.execute(
                    """INSERT INTO content_revisions(
                        revision_id,post_id,revision_kind,control_json,body_artifact_id,thesis_sha256,
                        evidence_binding_json,attribution_json,created_at,idempotency_key
                    ) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING""",
                    (
                        revision_id,
                        post["post_id"],
                        "base",
                        controls_json,
                        artifact_row["artifact_id"],
                        thesis_sha,
                        _canonical_json(normalized_evidence),
                        _canonical_json(normalized_attribution),
                        now,
                        idempotency_key,
                    ),
                )
                revision = connection.execute("SELECT * FROM content_revisions WHERE idempotency_key=?", (idempotency_key,)).fetchone()
                if (
                    not revision
                    or revision["post_id"] != post["post_id"]
                    or revision["body_artifact_id"] != artifact_row["artifact_id"]
                    or revision["control_json"] != controls_json
                ):
                    raise ContentLifecycleConflict("canonical revision idempotency conflict")
                connection.execute(
                    "UPDATE canonical_posts SET current_revision_id=?,updated_at=? WHERE post_id=?",
                    (revision["revision_id"], now, post["post_id"]),
                )
                if generation_receipt is not None:
                    opportunity_metadata = _json_object(
                        opportunity["metadata_json"], label="opportunity metadata"
                    )
                    existing_receipt = opportunity_metadata.get("generation_receipt")
                    if existing_receipt is not None and existing_receipt != dict(
                        generation_receipt
                    ):
                        raise ContentLifecycleConflict(
                            "canonical generation receipt changed before persistence"
                        )
                    opportunity_metadata["generation_receipt"] = dict(
                        generation_receipt
                    )
                    connection.execute(
                        """UPDATE content_opportunities
                        SET status='review',metadata_json=?,updated_at=?
                        WHERE opportunity_id=?""",
                        (
                            _canonical_json(opportunity_metadata),
                            now,
                            opportunity_id,
                        ),
                    )
                else:
                    connection.execute(
                        "UPDATE content_opportunities SET status='review',updated_at=? WHERE opportunity_id=?",
                        (now, opportunity_id),
                    )
                self._append_revision_event(
                    connection,
                    revision=revision,
                    event_type="canonical_post.created",
                    event_key=f"canonical-post:{idempotency_key}",
                    extra_payload={"integrity": integrity},
                )
                if generation_receipt is not None:
                    self._append_revision_event(
                        connection,
                        revision=revision,
                        event_type="canonical_post.generation_receipt",
                        event_key=f"canonical-post-generation-receipt:{idempotency_key}",
                        actor_type="codex_remote_safe_generator",
                        extra_payload={"generation_receipt": dict(generation_receipt)},
                    )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
        return self.get_post(post_id)

    def create_variant(
        self,
        *,
        post_id: str,
        parent_revision_id: str,
        body: str,
        platform: str,
        controls: Mapping[str, Any],
        idempotency_key: str,
        thesis: str,
        generation_receipt: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = body.strip()
        if not body:
            raise ValueError("variant body is required")
        existing_variant_post_id: str | None = None
        with self.store.connection() as connection:
            post = connection.execute(
                """SELECT p.*,o.thesis FROM canonical_posts p JOIN content_opportunities o ON o.opportunity_id=p.opportunity_id
                WHERE p.post_id=?""",
                (post_id,),
            ).fetchone()
            parent = connection.execute("SELECT * FROM content_revisions WHERE revision_id=? AND post_id=?", (parent_revision_id, post_id)).fetchone()
            if not post or not parent:
                raise ValueError("unknown post or parent revision")
            thesis_sha = _sha256_text(_clean(thesis))
            if thesis_sha != parent["thesis_sha256"] or _clean(thesis) != post["thesis"]:
                raise ContentLifecycleConflict("materially different thesis requires a new ContentOpportunity")
            parent_artifact = connection.execute(
                "SELECT logical_ref FROM artifacts WHERE artifact_id=?",
                (parent["body_artifact_id"],),
            ).fetchone()
            if not parent_artifact:
                raise ContentLifecycleConflict("parent revision artifact is missing")
            parent_body = self.artifact_store.read_text(parent_artifact["logical_ref"])
            integrity = self.validate_variant_integrity(
                parent_body=parent_body,
                variant_body=body,
                thesis=post["thesis"],
                evidence_binding=_json_object(parent["evidence_binding_json"], label="parent evidence binding"),
                attribution=_json_object(parent["attribution_json"], label="parent attribution"),
            )
            existing = connection.execute(
                """SELECT r.*,a.content_sha256 FROM content_revisions r
                JOIN artifacts a ON a.artifact_id=r.body_artifact_id WHERE r.idempotency_key=?""",
                (idempotency_key,),
            ).fetchone()
            if existing:
                if (
                    existing["post_id"] != post_id
                    or existing["parent_revision_id"] != parent_revision_id
                    or existing["revision_kind"] != "variant"
                    or existing["platform"] != platform
                    or existing["control_json"] != _canonical_json(dict(controls))
                    or existing["content_sha256"] != _sha256_text(body)
                    or existing["thesis_sha256"] != parent["thesis_sha256"]
                    or existing["evidence_binding_json"] != parent["evidence_binding_json"]
                    or existing["attribution_json"] != parent["attribution_json"]
                ):
                    raise ContentLifecycleConflict("variant idempotency conflict")
                existing_variant_post_id = existing["post_id"]
            elif post["status"] == "published":
                raise ContentLifecycleConflict("a published post cannot receive a new variant")
        if existing_variant_post_id:
            return self.get_post(existing_variant_post_id)
        artifact = self.artifact_store.write_text(body, artifact_kind="content_revision")
        artifact_row = self.store.put_artifact(artifact_kind="content_revision", metadata={"private": True}, **artifact)
        now = _utcnow()
        with self.store.connection() as connection:
            post = connection.execute(
                """SELECT p.*,o.thesis FROM canonical_posts p JOIN content_opportunities o ON o.opportunity_id=p.opportunity_id
                WHERE p.post_id=?""",
                (post_id,),
            ).fetchone()
            parent = connection.execute("SELECT * FROM content_revisions WHERE revision_id=? AND post_id=?", (parent_revision_id, post_id)).fetchone()
            if not post or not parent:
                raise ContentLifecycleConflict("post or parent revision changed before variant persistence")
            revision_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:revision:{idempotency_key}"))
            connection.execute("BEGIN IMMEDIATE")
            try:
                latest_post = connection.execute(
                    "SELECT status FROM canonical_posts WHERE post_id=?",
                    (post_id,),
                ).fetchone()
                concurrent_replay = connection.execute(
                    "SELECT 1 FROM content_revisions WHERE idempotency_key=?",
                    (idempotency_key,),
                ).fetchone()
                if not latest_post:
                    raise ContentLifecycleConflict("post changed before variant persistence")
                if latest_post["status"] == "published" and not concurrent_replay:
                    raise ContentLifecycleConflict(
                        "post became published before variant persistence"
                    )
                connection.execute(
                    """INSERT INTO content_revisions(
                        revision_id,post_id,parent_revision_id,revision_kind,platform,control_json,body_artifact_id,
                        thesis_sha256,evidence_binding_json,attribution_json,created_at,idempotency_key
                    ) VALUES (?,?,?,'variant',?,?,?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING""",
                    (
                        revision_id,
                        post_id,
                        parent_revision_id,
                        platform,
                        _canonical_json(dict(controls)),
                        artifact_row["artifact_id"],
                        parent["thesis_sha256"],
                        parent["evidence_binding_json"],
                        parent["attribution_json"],
                        now,
                        idempotency_key,
                    ),
                )
                revision = connection.execute("SELECT * FROM content_revisions WHERE idempotency_key=?", (idempotency_key,)).fetchone()
                if not revision or revision["post_id"] != post_id or revision["parent_revision_id"] != parent_revision_id:
                    raise ContentLifecycleConflict("variant idempotency conflict")
                if revision["evidence_binding_json"] != parent["evidence_binding_json"] or revision["attribution_json"] != parent["attribution_json"]:
                    raise ContentLifecycleConflict("variant cannot change evidence or attribution")
                self._append_revision_event(
                    connection,
                    revision=revision,
                    event_type="content_variant.created",
                    event_key=f"variant:{idempotency_key}",
                    extra_payload={"integrity": integrity},
                )
                if generation_receipt is not None:
                    self._append_revision_event(
                        connection,
                        revision=revision,
                        event_type="content_variant.generation_receipt",
                        event_key=f"variant-generation-receipt:{idempotency_key}",
                        actor_type="codex_remote_safe_generator",
                        extra_payload={"generation_receipt": dict(generation_receipt)},
                    )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
        return self.get_post(post_id)

    def create_manual_edit(
        self,
        *,
        post_id: str,
        parent_revision_id: str,
        body: str,
        edit_classification: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Persist owner-edited bytes as one immutable child revision.

        Manual editing may change expression or presentation, but it cannot replace
        the canonical thesis, evidence binding, attribution, or privacy gates. The
        separate learning ledger records why the owner made the edit.
        """

        from app.services.content_learning_service import EDIT_CLASSES

        body = body.strip()
        edit_classification = _clean(edit_classification)
        idempotency_key = _clean(idempotency_key)
        if not body or not post_id or not parent_revision_id or not idempotency_key:
            raise ValueError("manual edit requires post, parent revision, body, and idempotency key")
        if edit_classification not in EDIT_CLASSES:
            raise ValueError("manual edit requires one approved classification")

        existing_post_id: str | None = None
        with self.store.connection() as connection:
            post = connection.execute(
                """SELECT p.*,o.thesis FROM canonical_posts p
                JOIN content_opportunities o ON o.opportunity_id=p.opportunity_id
                WHERE p.post_id=?""",
                (post_id,),
            ).fetchone()
            parent = connection.execute(
                """SELECT r.*,a.logical_ref,a.content_sha256 FROM content_revisions r
                JOIN artifacts a ON a.artifact_id=r.body_artifact_id
                WHERE r.revision_id=? AND r.post_id=?""",
                (parent_revision_id, post_id),
            ).fetchone()
            if not post or not parent:
                raise ValueError("unknown post or parent revision")
            existing = connection.execute(
                """SELECT r.*,a.content_sha256 FROM content_revisions r
                JOIN artifacts a ON a.artifact_id=r.body_artifact_id
                WHERE r.idempotency_key=?""",
                (idempotency_key,),
            ).fetchone()
            expected_controls = _canonical_json({"edit_classification": edit_classification})
            if existing:
                if (
                    existing["post_id"] != post_id
                    or existing["parent_revision_id"] != parent_revision_id
                    or existing["revision_kind"] != "edit"
                    or existing["control_json"] != expected_controls
                    or existing["content_sha256"] != _sha256_text(body)
                    or existing["thesis_sha256"] != parent["thesis_sha256"]
                    or existing["evidence_binding_json"] != parent["evidence_binding_json"]
                    or existing["attribution_json"] != parent["attribution_json"]
                ):
                    raise ContentLifecycleConflict("manual edit idempotency conflict")
                existing_post_id = existing["post_id"]
            else:
                if post["status"] == "published":
                    raise ContentLifecycleConflict("a published post cannot be edited in place")
                if post["current_revision_id"] != parent_revision_id:
                    raise ContentLifecycleConflict("manual edit must descend from the exact current revision")
                if parent["content_sha256"] == _sha256_text(body):
                    raise ContentLifecycleConflict("manual edit must change the revision bytes")
                parent_body = self.artifact_store.read_text(parent["logical_ref"])
                self.validate_variant_integrity(
                    parent_body=parent_body,
                    variant_body=body,
                    thesis=post["thesis"],
                    evidence_binding=_json_object(
                        parent["evidence_binding_json"], label="parent evidence binding"
                    ),
                    attribution=_json_object(parent["attribution_json"], label="parent attribution"),
                )
        if existing_post_id:
            return self.get_post(existing_post_id)

        artifact = self.artifact_store.write_text(body, artifact_kind="content_revision")
        artifact_row = self.store.put_artifact(
            artifact_kind="content_revision", metadata={"private": True}, **artifact
        )
        now = _utcnow()
        revision_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:revision:{idempotency_key}"))
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                post = connection.execute(
                    """SELECT p.*,o.thesis FROM canonical_posts p
                    JOIN content_opportunities o ON o.opportunity_id=p.opportunity_id
                    WHERE p.post_id=?""",
                    (post_id,),
                ).fetchone()
                parent = connection.execute(
                    """SELECT r.*,a.logical_ref,a.content_sha256 FROM content_revisions r
                    JOIN artifacts a ON a.artifact_id=r.body_artifact_id
                    WHERE r.revision_id=? AND r.post_id=?""",
                    (parent_revision_id, post_id),
                ).fetchone()
                if not post or not parent:
                    raise ContentLifecycleConflict("post or parent revision changed before edit persistence")
                if post["status"] == "published" or post["current_revision_id"] != parent_revision_id:
                    raise ContentLifecycleConflict("post state changed before manual edit persistence")
                if parent["content_sha256"] == artifact_row["content_sha256"]:
                    raise ContentLifecycleConflict("manual edit must change the revision bytes")
                parent_body = self.artifact_store.read_text(parent["logical_ref"])
                self.validate_variant_integrity(
                    parent_body=parent_body,
                    variant_body=body,
                    thesis=post["thesis"],
                    evidence_binding=_json_object(
                        parent["evidence_binding_json"], label="parent evidence binding"
                    ),
                    attribution=_json_object(parent["attribution_json"], label="parent attribution"),
                )
                connection.execute(
                    """INSERT INTO content_revisions(
                        revision_id,post_id,parent_revision_id,revision_kind,platform,control_json,
                        body_artifact_id,thesis_sha256,evidence_binding_json,attribution_json,
                        created_at,idempotency_key
                    ) VALUES (?,?,?,'edit',?,?,?,?,?,?,?,?)
                    ON CONFLICT(idempotency_key) DO NOTHING""",
                    (
                        revision_id,
                        post_id,
                        parent_revision_id,
                        parent["platform"],
                        _canonical_json({"edit_classification": edit_classification}),
                        artifact_row["artifact_id"],
                        parent["thesis_sha256"],
                        parent["evidence_binding_json"],
                        parent["attribution_json"],
                        now,
                        idempotency_key,
                    ),
                )
                revision = connection.execute(
                    "SELECT * FROM content_revisions WHERE idempotency_key=?",
                    (idempotency_key,),
                ).fetchone()
                if (
                    not revision
                    or revision["post_id"] != post_id
                    or revision["parent_revision_id"] != parent_revision_id
                    or revision["body_artifact_id"] != artifact_row["artifact_id"]
                ):
                    raise ContentLifecycleConflict("manual edit idempotency conflict")
                connection.execute(
                    "UPDATE canonical_posts SET status='review',current_revision_id=?,updated_at=? WHERE post_id=?",
                    (revision["revision_id"], now, post_id),
                )
                connection.execute(
                    "UPDATE content_opportunities SET status='review',updated_at=? WHERE opportunity_id=?",
                    (now, post["opportunity_id"]),
                )
                self._append_revision_event(
                    connection,
                    revision=revision,
                    event_type="content_revision.edited",
                    event_key=f"manual-edit:{idempotency_key}",
                    actor_type="owner",
                    extra_payload={"edit_classification": edit_classification},
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
        return self.get_post(post_id)

    @staticmethod
    def _append_revision_event(
        connection: Any,
        *,
        revision: Any,
        event_type: str,
        event_key: str,
        actor_type: str = "content_lifecycle",
        extra_payload: Mapping[str, Any] | None = None,
    ) -> None:
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:event:{event_key}"))
        payload = {"revision_id": revision["revision_id"], "revision_kind": revision["revision_kind"]}
        payload.update(dict(extra_payload or {}))
        connection.execute(
            """INSERT INTO system_events(
                event_id,event_type,aggregate_type,aggregate_id,occurred_at,actor_type,payload_json,
                provenance_json,artifact_refs_json,idempotency_key
            ) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING""",
            (
                event_id,
                event_type,
                "canonical_post",
                revision["post_id"],
                revision["created_at"],
                actor_type,
                _canonical_json(payload),
                _canonical_json({"parent_revision_id": revision["parent_revision_id"]}),
                _canonical_json([revision["body_artifact_id"]]),
                event_key,
            ),
        )

    def _validate_canonical_integrity(
        self,
        connection: Any,
        *,
        opportunity: Any,
        body: str,
        evidence_binding: Mapping[str, Any],
        attribution: Mapping[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        """Bind a canonical copy to passed gates and authoritative source evidence."""

        truth_state = str(opportunity["truth_state"])
        safety_state = str(opportunity["safety_state"])
        attribution_state = str(opportunity["attribution_state"])
        metadata = _json_object(opportunity["metadata_json"], label="opportunity metadata")
        integrity_metadata = metadata.get("integrity") if isinstance(metadata.get("integrity"), dict) else {}
        privacy_state = str(integrity_metadata.get("privacy_state") or metadata.get("privacy_state") or safety_state)
        if truth_state != "pass":
            raise ContentLifecycleConflict(f"canonical copy requires truth_state=pass, got {truth_state}")
        if safety_state not in {"pass", "owner_review_required"}:
            raise ContentLifecycleConflict(f"canonical copy requires a resolved safety state, got {safety_state}")
        if privacy_state not in {"pass", "owner_review_required"}:
            raise ContentLifecycleConflict(f"canonical copy requires a resolved privacy state, got {privacy_state}")
        if attribution_state not in {"pass", "required"}:
            raise ContentLifecycleConflict(f"canonical copy requires a resolved attribution state, got {attribution_state}")
        if _PRIVATE_LITERAL_RE.search(body):
            raise ContentLifecycleConflict("canonical copy contains a prohibited private literal")

        normalized_evidence = dict(evidence_binding)
        opportunity_sources = {
            row["source_id"]
            for row in connection.execute(
                "SELECT source_id FROM opportunity_sources WHERE opportunity_id=?",
                (opportunity["opportunity_id"],),
            )
        }
        if not opportunity_sources:
            raise ContentLifecycleConflict("canonical copy requires at least one opportunity source")
        requested_source_ids = set(_string_list(normalized_evidence.get("source_ids")))
        single_source_id = _clean(str(normalized_evidence.get("source_id") or ""))
        if single_source_id:
            requested_source_ids.add(single_source_id)
        if requested_source_ids and not requested_source_ids.issubset(opportunity_sources):
            raise ContentLifecycleConflict("evidence binding references a source outside the opportunity")

        evidence_ids = set(_string_list(normalized_evidence.get("evidence_ids")))
        evidence_ids.update(_string_list(normalized_evidence.get("authoritative_evidence_ids")))
        single_evidence_id = _clean(str(normalized_evidence.get("evidence_id") or ""))
        if single_evidence_id:
            evidence_ids.add(single_evidence_id)
        metadata_evidence_id = _clean(str(metadata.get("evidence_id") or ""))
        if metadata_evidence_id:
            evidence_ids.add(metadata_evidence_id)
        if not evidence_ids:
            placeholders = ",".join("?" for _ in opportunity_sources)
            evidence_ids = {
                row["evidence_id"]
                for row in connection.execute(
                    f"SELECT evidence_id FROM evidence_records WHERE source_id IN ({placeholders})",
                    tuple(sorted(opportunity_sources)),
                )
            }
        if not evidence_ids:
            raise ContentLifecycleConflict("canonical copy requires authoritative evidence")
        placeholders = ",".join("?" for _ in evidence_ids)
        evidence_rows = connection.execute(
            f"SELECT evidence_id,source_id FROM evidence_records WHERE evidence_id IN ({placeholders})",
            tuple(sorted(evidence_ids)),
        ).fetchall()
        if {row["evidence_id"] for row in evidence_rows} != evidence_ids:
            raise ContentLifecycleConflict("evidence binding references unknown evidence")
        evidence_source_ids = {row["source_id"] for row in evidence_rows}
        if not evidence_source_ids.issubset(opportunity_sources):
            raise ContentLifecycleConflict("authoritative evidence is not bound to the opportunity")
        if requested_source_ids and not evidence_source_ids.issubset(requested_source_ids):
            raise ContentLifecycleConflict("evidence and declared source bindings disagree")
        normalized_evidence["source_ids"] = sorted(requested_source_ids or evidence_source_ids)
        normalized_evidence["authoritative_evidence_ids"] = sorted(evidence_ids)

        normalized_attribution = dict(attribution)
        if attribution_state == "required":
            if normalized_attribution.get("required") is not True:
                raise ContentLifecycleConflict("required attribution must be explicitly retained")
            source_name = _clean(str(normalized_attribution.get("public_source_name") or ""))
            if not source_name:
                raise ContentLifecycleConflict("required attribution needs a public source name")
            source_urls = {
                str(row["canonical_url"])
                for row in connection.execute(
                    f"SELECT canonical_url FROM sources WHERE source_id IN ({','.join('?' for _ in evidence_source_ids)})",
                    tuple(sorted(evidence_source_ids)),
                )
                if row["canonical_url"]
            }
            public_url = _clean(str(normalized_attribution.get("public_source_url") or ""))
            if source_urls and public_url not in source_urls:
                raise ContentLifecycleConflict("required attribution must retain the exact external source URL")

        return normalized_evidence, normalized_attribution, {
            "schema_version": "content_integrity_receipt/v1",
            "truth_state": truth_state,
            "safety_state": safety_state,
            "privacy_state": privacy_state,
            "attribution_state": attribution_state,
            "authoritative_evidence_ids": sorted(evidence_ids),
            "publication_ready": (
                truth_state == "pass"
                and safety_state == "pass"
                and privacy_state == "pass"
                and attribution_state in {"pass", "required"}
            ),
            "body_sha256": _sha256_text(body),
        }

    @staticmethod
    def validate_variant_integrity(
        *,
        parent_body: str,
        variant_body: str,
        thesis: str,
        evidence_binding: Mapping[str, Any],
        attribution: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Deterministically inspect generated bytes before a variant is persisted.

        This is intentionally stricter than a prompt instruction.  It proves lexical
        continuity for the thesis and evidence anchors, exact linked-attribution
        continuity, and absence of declared privacy/prohibited terms.  It does not
        claim a general semantic-equivalence proof.
        """

        parent_body = parent_body.strip()
        variant_body = variant_body.strip()
        if not parent_body or not variant_body:
            raise ContentLifecycleConflict("variant integrity requires non-empty parent and variant copy")
        thesis_terms = _terms(thesis)
        variant_terms = _terms(variant_body)
        required_thesis_overlap = min(2, len(thesis_terms))
        thesis_overlap = sorted(thesis_terms & variant_terms)
        if required_thesis_overlap == 0 or len(thesis_overlap) < required_thesis_overlap:
            raise ContentLifecycleConflict("generated variant does not retain the canonical thesis")

        explicit_evidence = []
        for key in ("required_terms", "evidence_terms", "claim_anchors"):
            explicit_evidence.extend(_string_list(evidence_binding.get(key)))
        if explicit_evidence:
            missing_evidence = []
            for term in explicit_evidence:
                anchor_terms = _terms(term)
                required_anchor_overlap = min(2, len(anchor_terms))
                if required_anchor_overlap == 0 or len(anchor_terms & variant_terms) < required_anchor_overlap:
                    missing_evidence.append(term)
            if missing_evidence:
                raise ContentLifecycleConflict("generated variant drops required evidence anchors")
            evidence_overlap = sorted({_term_root(term) for phrase in explicit_evidence for term in _WORD_RE.findall(phrase.lower())} & variant_terms)
            evidence_basis = "declared_anchors"
        else:
            parent_terms = _terms(parent_body)
            parent_evidence_terms = parent_terms - thesis_terms or parent_terms
            required_evidence_overlap = min(2, len(parent_evidence_terms))
            evidence_overlap = sorted(parent_evidence_terms & variant_terms)
            if required_evidence_overlap == 0 or len(evidence_overlap) < required_evidence_overlap:
                raise ContentLifecycleConflict("generated variant does not retain evidence from the parent copy")
            evidence_basis = "parent_copy_lexical_continuity"

        source_name = _clean(str(attribution.get("public_source_name") or ""))
        source_url = _clean(str(attribution.get("public_source_url") or ""))
        attribution_required = attribution.get("required") is True
        in_copy_required = attribution.get("in_copy_required") is True or (
            bool(source_name) and source_name.lower() in parent_body.lower()
        )
        if attribution_required and not source_name:
            raise ContentLifecycleConflict("generated variant has no retained source attribution")
        if attribution_required and in_copy_required:
            visible = (source_name and source_name.lower() in variant_body.lower()) or (
                source_url and source_url.lower() in variant_body.lower()
            )
            if not visible:
                raise ContentLifecycleConflict("generated variant drops attribution visible in the parent copy")

        prohibited = []
        for key in ("prohibited_terms", "privacy_prohibited_terms", "unsupported_claims"):
            prohibited.extend(_string_list(evidence_binding.get(key)))
        lowered_variant = variant_body.lower()
        if any(term.lower() in lowered_variant for term in prohibited) or _PRIVATE_LITERAL_RE.search(variant_body):
            raise ContentLifecycleConflict("generated variant violates truth, safety, or privacy constraints")

        return {
            "schema_version": "content_variant_integrity_receipt/v1",
            "validator": "deterministic_lexical_integrity/v1",
            "thesis_retained": True,
            "thesis_overlap": thesis_overlap,
            "evidence_retained": True,
            "evidence_basis": evidence_basis,
            "evidence_overlap": evidence_overlap,
            "attribution_retained": True,
            "attribution_mode": "visible_copy" if in_copy_required else "immutable_linked_metadata",
            "truth_safety_privacy_constraints_passed": True,
            "parent_body_sha256": _sha256_text(parent_body),
            "variant_body_sha256": _sha256_text(variant_body),
        }

    @staticmethod
    def derive_grounding_anchors(
        *,
        source_body: str,
        draft_body: str,
        exclude_text: str = "",
        limit: int = 2,
    ) -> list[str]:
        """Select source-ordered lexical anchors that are present in draft bytes."""

        if limit < 1:
            raise ValueError("grounding anchor limit must be positive")
        draft_terms = _terms(draft_body)
        excluded = _terms(exclude_text)
        anchors: list[str] = []
        seen: set[str] = set()
        for token in _WORD_RE.findall(source_body.lower()):
            root = _term_root(token)
            if (
                len(token) < 4
                or token in _TERM_STOPWORDS
                or root in excluded
                or root not in draft_terms
                or root in seen
            ):
                continue
            seen.add(root)
            anchors.append(token)
            if len(anchors) >= limit:
                break
        return anchors

    def get_post(self, post_id: str) -> dict[str, Any]:
        with self.store.connection() as connection:
            post = connection.execute("SELECT * FROM canonical_posts WHERE post_id=?", (post_id,)).fetchone()
            if not post:
                raise ValueError("unknown post")
            revisions = [dict(row) for row in connection.execute("SELECT * FROM content_revisions WHERE post_id=? ORDER BY created_at,revision_id", (post_id,))]
            return {"post": dict(post), "revisions": revisions}
