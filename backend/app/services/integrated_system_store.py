from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping

from app.services.source_authorship_policy_service import (
    AUTHORSHIP_POLICY_VERSION,
    conservative_combined_rights,
    owner_authorship_attested,
)


SCHEMA_VERSION = 7


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _migration_statements(sql: str) -> Iterator[str]:
    """Yield complete SQLite statements without splitting trigger bodies."""

    pending = ""
    for line in sql.splitlines():
        pending += f"{line}\n"
        if sqlite3.complete_statement(pending):
            statement = pending.strip()
            if statement:
                yield statement
            pending = ""
    if pending.strip():
        raise ValueError("migration contains an incomplete SQL statement")


def default_database_path() -> Path:
    state_root = Path(os.getenv("AI_CLONE_STATE_ROOT", Path.home() / ".codex" / "ai-clone" / "state"))
    return state_root / "system" / "ai-clone.sqlite3"


MIGRATIONS: tuple[tuple[int, str], ...] = (
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL,
            migration_sha256 TEXT NOT NULL UNIQUE
        ) STRICT;

        CREATE TABLE artifacts (
            artifact_id TEXT PRIMARY KEY,
            content_sha256 TEXT NOT NULL,
            artifact_kind TEXT NOT NULL,
            media_type TEXT,
            logical_ref TEXT NOT NULL,
            byte_size INTEGER CHECK (byte_size IS NULL OR byte_size >= 0),
            created_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            UNIQUE (content_sha256, artifact_kind)
        ) STRICT;

        CREATE TABLE sources (
            source_id TEXT PRIMARY KEY,
            canonical_identity TEXT NOT NULL UNIQUE,
            source_kind TEXT NOT NULL,
            canonical_url TEXT,
            author_or_publisher TEXT,
            title TEXT,
            rights_state TEXT NOT NULL DEFAULT 'unknown'
                CHECK (rights_state IN ('unknown','permitted','owner_controlled','restricted','blocked')),
            admissibility_state TEXT NOT NULL DEFAULT 'pending'
                CHECK (admissibility_state IN ('pending','admissible','restricted','blocked')),
            content_sha256 TEXT,
            raw_artifact_id TEXT REFERENCES artifacts(artifact_id) ON DELETE RESTRICT,
            transcript_artifact_id TEXT REFERENCES artifacts(artifact_id) ON DELETE RESTRICT,
            captured_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        ) STRICT;
        CREATE INDEX sources_kind_idx ON sources(source_kind, created_at DESC);
        CREATE INDEX sources_content_sha_idx ON sources(content_sha256);

        CREATE TABLE discovery_events (
            discovery_id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE RESTRICT,
            origin TEXT NOT NULL,
            discovery_route TEXT NOT NULL,
            external_ref TEXT,
            discovered_at TEXT NOT NULL,
            relevance_state TEXT NOT NULL DEFAULT 'pending'
                CHECK (relevance_state IN ('pending','qualified','backlog','rejected')),
            idempotency_key TEXT NOT NULL UNIQUE,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        ) STRICT;
        CREATE INDEX discovery_source_idx ON discovery_events(source_id, discovered_at DESC);
        CREATE INDEX discovery_origin_idx ON discovery_events(origin, discovered_at DESC);

        CREATE TABLE evidence_records (
            evidence_id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE RESTRICT,
            extractor_name TEXT NOT NULL,
            extractor_version TEXT NOT NULL,
            artifact_id TEXT REFERENCES artifacts(artifact_id) ON DELETE RESTRICT,
            evidence_refs_json TEXT NOT NULL,
            confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
            created_at TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE
        ) STRICT;
        CREATE INDEX evidence_source_idx ON evidence_records(source_id, created_at DESC);

        CREATE TABLE interpretations (
            interpretation_id TEXT PRIMARY KEY,
            evidence_id TEXT NOT NULL REFERENCES evidence_records(evidence_id) ON DELETE RESTRICT,
            lens_name TEXT NOT NULL,
            lens_version TEXT NOT NULL,
            reading_json TEXT NOT NULL,
            confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
            created_at TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE
        ) STRICT;
        CREATE INDEX interpretations_evidence_idx ON interpretations(evidence_id, created_at DESC);

        CREATE TABLE content_opportunities (
            opportunity_id TEXT PRIMARY KEY,
            thesis TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'qualified'
                CHECK (status IN ('qualified','backlog','selected','drafting','review','parked','published','rejected','blocked')),
            owner_requested INTEGER NOT NULL DEFAULT 0 CHECK (owner_requested IN (0,1)),
            truth_state TEXT NOT NULL DEFAULT 'pending'
                CHECK (truth_state IN ('pending','pass','blocked')),
            safety_state TEXT NOT NULL DEFAULT 'pending'
                CHECK (safety_state IN ('pending','pass','owner_review_required','blocked')),
            attribution_state TEXT NOT NULL DEFAULT 'pending'
                CHECK (attribution_state IN ('pending','pass','required','blocked')),
            strategy_contract_ref TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        ) STRICT;
        CREATE INDEX opportunities_status_idx ON content_opportunities(status, owner_requested DESC, created_at DESC);

        CREATE TABLE opportunity_sources (
            opportunity_id TEXT NOT NULL REFERENCES content_opportunities(opportunity_id) ON DELETE CASCADE,
            source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE RESTRICT,
            relationship_kind TEXT NOT NULL DEFAULT 'material_source',
            PRIMARY KEY (opportunity_id, source_id, relationship_kind)
        ) STRICT;

        CREATE TABLE portfolio_cycles (
            portfolio_cycle_id TEXT PRIMARY KEY,
            cycle_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open'
                CHECK (status IN ('open','waiting','ready','degraded','complete','failed')),
            expected_workspace_count INTEGER NOT NULL DEFAULT 0 CHECK (expected_workspace_count >= 0),
            created_at TEXT NOT NULL,
            completed_at TEXT,
            idempotency_key TEXT NOT NULL UNIQUE,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        ) STRICT;

        CREATE TABLE portfolio_selections (
            selection_id TEXT PRIMARY KEY,
            portfolio_cycle_id TEXT REFERENCES portfolio_cycles(portfolio_cycle_id) ON DELETE RESTRICT,
            opportunity_id TEXT NOT NULL REFERENCES content_opportunities(opportunity_id) ON DELETE RESTRICT,
            disposition TEXT NOT NULL CHECK (disposition IN ('selected','held','rejected')),
            reason_json TEXT NOT NULL,
            selected_at TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE
        ) STRICT;

        CREATE TABLE canonical_posts (
            post_id TEXT PRIMARY KEY,
            opportunity_id TEXT NOT NULL UNIQUE REFERENCES content_opportunities(opportunity_id) ON DELETE RESTRICT,
            platform_base TEXT NOT NULL DEFAULT 'canonical',
            status TEXT NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft','review','approved','parked','published','withdrawn','blocked')),
            current_revision_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        ) STRICT;

        CREATE TABLE content_revisions (
            revision_id TEXT PRIMARY KEY,
            post_id TEXT NOT NULL REFERENCES canonical_posts(post_id) ON DELETE CASCADE,
            parent_revision_id TEXT REFERENCES content_revisions(revision_id) ON DELETE RESTRICT,
            revision_kind TEXT NOT NULL CHECK (revision_kind IN ('base','edit','variant','revision')),
            platform TEXT,
            control_json TEXT NOT NULL DEFAULT '{}',
            body_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id) ON DELETE RESTRICT,
            thesis_sha256 TEXT NOT NULL,
            evidence_binding_json TEXT NOT NULL,
            attribution_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE
        ) STRICT;
        CREATE INDEX revisions_post_idx ON content_revisions(post_id, created_at);

        CREATE TABLE learning_events (
            learning_event_id TEXT PRIMARY KEY,
            post_id TEXT REFERENCES canonical_posts(post_id) ON DELETE RESTRICT,
            revision_id TEXT REFERENCES content_revisions(revision_id) ON DELETE RESTRICT,
            event_kind TEXT NOT NULL,
            edit_classification TEXT CHECK (edit_classification IS NULL OR edit_classification IN
                ('factual','voice','audience','strategy','evidence_attribution','safety_privacy','platform','worldview','one_off')),
            payload_json TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE
        ) STRICT;
        CREATE INDEX learning_post_idx ON learning_events(post_id, occurred_at DESC);

        CREATE TABLE persona_candidates (
            persona_candidate_id TEXT PRIMARY KEY,
            candidate_kind TEXT NOT NULL CHECK (candidate_kind IN ('factual_continuity','reversible_pattern','identity_claim')),
            claim_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected','promoted','reversed','blocked')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE
        ) STRICT;

        CREATE TABLE persona_candidate_evidence (
            persona_candidate_id TEXT NOT NULL REFERENCES persona_candidates(persona_candidate_id) ON DELETE CASCADE,
            post_id TEXT REFERENCES canonical_posts(post_id) ON DELETE RESTRICT,
            revision_id TEXT REFERENCES content_revisions(revision_id) ON DELETE RESTRICT,
            source_id TEXT REFERENCES sources(source_id) ON DELETE RESTRICT,
            context_key TEXT NOT NULL,
            owner_approved INTEGER NOT NULL CHECK (owner_approved IN (0,1)),
            publication_confirmed INTEGER NOT NULL CHECK (publication_confirmed IN (0,1)),
            PRIMARY KEY (persona_candidate_id, context_key)
        ) STRICT;

        CREATE TABLE persona_promotions (
            promotion_id TEXT PRIMARY KEY,
            persona_candidate_id TEXT NOT NULL REFERENCES persona_candidates(persona_candidate_id) ON DELETE RESTRICT,
            canon_version TEXT NOT NULL,
            promotion_rule TEXT NOT NULL,
            evidence_receipt_json TEXT NOT NULL,
            promoted_at TEXT NOT NULL,
            reversed_at TEXT,
            reversal_reason TEXT,
            idempotency_key TEXT NOT NULL UNIQUE
        ) STRICT;

        CREATE TABLE memory_consolidations (
            consolidation_id TEXT PRIMARY KEY,
            window_start TEXT NOT NULL,
            window_end TEXT NOT NULL,
            source_event_cursor TEXT,
            receipt_json TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('complete','degraded','failed')),
            created_at TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE
        ) STRICT;

        CREATE TABLE readiness_receipts (
            readiness_id TEXT PRIMARY KEY,
            consolidation_id TEXT REFERENCES memory_consolidations(consolidation_id) ON DELETE RESTRICT,
            retrieval_refreshed_at TEXT,
            recall_probe_json TEXT NOT NULL,
            last_verified_memory_at TEXT,
            failed_component TEXT,
            status TEXT NOT NULL CHECK (status IN ('ready','degraded','failed')),
            created_at TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE
        ) STRICT;

        CREATE TABLE workspace_conclusions (
            conclusion_id TEXT PRIMARY KEY,
            portfolio_cycle_id TEXT NOT NULL REFERENCES portfolio_cycles(portfolio_cycle_id) ON DELETE RESTRICT,
            workspace_key TEXT NOT NULL,
            conclusion_kind TEXT NOT NULL CHECK (conclusion_kind IN ('conclusion','healthy_no_change')),
            provenance_kind TEXT NOT NULL CHECK (provenance_kind IN ('independent_agent','deterministic_policy','synthesized_lens')),
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE,
            UNIQUE (portfolio_cycle_id, workspace_key)
        ) STRICT;

        CREATE TABLE ops_conclusions (
            ops_conclusion_id TEXT PRIMARY KEY,
            portfolio_cycle_id TEXT NOT NULL UNIQUE REFERENCES portfolio_cycles(portfolio_cycle_id) ON DELETE RESTRICT,
            summary_artifact_id TEXT REFERENCES artifacts(artifact_id) ON DELETE RESTRICT,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('complete','degraded','failed')),
            created_at TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE
        ) STRICT;

        CREATE TABLE decision_records (
            decision_id TEXT PRIMARY KEY,
            decision_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_session','resolved','superseded','canceled','blocked')),
            title TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            state_version INTEGER NOT NULL DEFAULT 1 CHECK (state_version > 0),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            resolved_at TEXT,
            idempotency_key TEXT NOT NULL UNIQUE
        ) STRICT;

        CREATE TABLE decision_links (
            decision_id TEXT NOT NULL REFERENCES decision_records(decision_id) ON DELETE CASCADE,
            surface TEXT NOT NULL,
            external_ref TEXT NOT NULL,
            PRIMARY KEY (decision_id, surface, external_ref)
        ) STRICT;

        CREATE TABLE backup_receipts (
            backup_receipt_id TEXT PRIMARY KEY,
            backup_kind TEXT NOT NULL CHECK (backup_kind IN ('local_snapshot','offsite_backup','isolated_restore_drill')),
            manifest_sha256 TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('complete','degraded','failed')),
            verification_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE
        ) STRICT;

        CREATE TABLE system_events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            aggregate_type TEXT NOT NULL,
            aggregate_id TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            actor_type TEXT NOT NULL,
            actor_id TEXT,
            payload_json TEXT NOT NULL,
            provenance_json TEXT NOT NULL,
            artifact_refs_json TEXT NOT NULL DEFAULT '[]',
            idempotency_key TEXT NOT NULL UNIQUE,
            schema_version INTEGER NOT NULL DEFAULT 1 CHECK (schema_version > 0)
        ) STRICT;
        CREATE INDEX events_aggregate_idx ON system_events(aggregate_type, aggregate_id, occurred_at);
        CREATE INDEX events_type_idx ON system_events(event_type, occurred_at);
        """,
    ),
    (
        2,
        """
        CREATE TRIGGER canonical_posts_current_revision_update
        BEFORE UPDATE OF current_revision_id ON canonical_posts
        WHEN NEW.current_revision_id IS NOT NULL
        BEGIN
            SELECT CASE WHEN NOT EXISTS (
                SELECT 1 FROM content_revisions
                WHERE revision_id = NEW.current_revision_id AND post_id = NEW.post_id
            ) THEN RAISE(ABORT, 'current revision must belong to canonical post') END;
        END;
        """,
    ),
    (
        3,
        """
        CREATE TABLE structured_memory_entries (
            memory_entry_id TEXT PRIMARY KEY,
            consolidation_id TEXT NOT NULL REFERENCES memory_consolidations(consolidation_id) ON DELETE RESTRICT,
            source_event_id TEXT NOT NULL UNIQUE REFERENCES system_events(event_id) ON DELETE RESTRICT,
            source_event_sha256 TEXT NOT NULL CHECK (
                length(source_event_sha256) = 64 AND source_event_sha256 = lower(source_event_sha256)
            ),
            memory_lane TEXT NOT NULL CHECK (memory_lane IN
                ('factual_continuity','operational_continuity','reversible_pattern','identity_candidate')),
            subject_type TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            fact_json TEXT NOT NULL,
            provenance_json TEXT NOT NULL,
            durability_policy TEXT NOT NULL,
            verification_status TEXT NOT NULL DEFAULT 'pending'
                CHECK (verification_status IN ('pending','verified','rejected')),
            created_at TEXT NOT NULL,
            verified_at TEXT,
            schema_version INTEGER NOT NULL DEFAULT 1 CHECK (schema_version > 0)
        ) STRICT;
        CREATE INDEX structured_memory_lane_idx
            ON structured_memory_entries(memory_lane, verification_status, created_at DESC);
        CREATE INDEX structured_memory_consolidation_idx
            ON structured_memory_entries(consolidation_id, verification_status);

        CREATE TABLE readiness_attempts (
            attempt_id TEXT PRIMARY KEY,
            readiness_id TEXT NOT NULL REFERENCES readiness_receipts(readiness_id) ON DELETE CASCADE,
            attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
            receipt_json TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('ready','degraded','failed')),
            created_at TEXT NOT NULL,
            UNIQUE (readiness_id, attempt_number)
        ) STRICT;
        CREATE INDEX readiness_attempts_status_idx
            ON readiness_attempts(readiness_id, status, attempt_number DESC);
        """,
    ),
    (
        4,
        """
        CREATE TABLE ops_conclusion_attempts (
            attempt_id TEXT PRIMARY KEY,
            ops_conclusion_id TEXT NOT NULL REFERENCES ops_conclusions(ops_conclusion_id) ON DELETE CASCADE,
            attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('complete','degraded','failed')),
            created_at TEXT NOT NULL,
            UNIQUE (ops_conclusion_id, attempt_number)
        ) STRICT;
        CREATE INDEX ops_conclusion_attempts_status_idx
            ON ops_conclusion_attempts(ops_conclusion_id, status, attempt_number DESC);
        """,
    ),
    (
        5,
        """
        ALTER TABLE sources ADD COLUMN merged_into_source_id TEXT
            REFERENCES sources(source_id) ON DELETE RESTRICT;
        CREATE INDEX sources_canonical_active_idx
            ON sources(merged_into_source_id, updated_at DESC);
        """,
    ),
    (
        6,
        """
        CREATE TABLE content_generation_jobs (
            generation_job_id TEXT PRIMARY KEY,
            opportunity_id TEXT NOT NULL UNIQUE
                REFERENCES content_opportunities(opportunity_id) ON DELETE RESTRICT,
            portfolio_cycle_id TEXT
                REFERENCES portfolio_cycles(portfolio_cycle_id) ON DELETE RESTRICT,
            draft_authority TEXT NOT NULL
                CHECK (draft_authority IN ('owner_requested','portfolio_selected')),
            status TEXT NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued','running','succeeded','failed')),
            controls_json TEXT NOT NULL,
            controls_sha256 TEXT NOT NULL CHECK (
                length(controls_sha256) = 64 AND controls_sha256 = lower(controls_sha256)
            ),
            source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE RESTRICT,
            evidence_id TEXT NOT NULL REFERENCES evidence_records(evidence_id) ON DELETE RESTRICT,
            artifact_sha256 TEXT NOT NULL CHECK (
                length(artifact_sha256) = 64 AND artifact_sha256 = lower(artifact_sha256)
            ),
            attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
            lease_token TEXT,
            lease_expires_at TEXT,
            post_id TEXT REFERENCES canonical_posts(post_id) ON DELETE RESTRICT,
            revision_id TEXT REFERENCES content_revisions(revision_id) ON DELETE RESTRICT,
            generation_receipt_sha256 TEXT CHECK (
                generation_receipt_sha256 IS NULL OR
                (length(generation_receipt_sha256) = 64 AND
                 generation_receipt_sha256 = lower(generation_receipt_sha256))
            ),
            safe_error_code TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT,
            idempotency_key TEXT NOT NULL UNIQUE,
            CHECK (
                (status = 'running' AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)
                OR status != 'running'
            ),
            CHECK (
                (status = 'succeeded' AND post_id IS NOT NULL AND revision_id IS NOT NULL
                 AND completed_at IS NOT NULL)
                OR status != 'succeeded'
            )
        ) STRICT;
        CREATE INDEX content_generation_jobs_status_idx
            ON content_generation_jobs(status, lease_expires_at, updated_at DESC);
        CREATE INDEX content_generation_jobs_cycle_idx
            ON content_generation_jobs(portfolio_cycle_id, status, updated_at DESC);
        """,
    ),
    (
        7,
        """
        CREATE UNIQUE INDEX content_revisions_single_base_idx
            ON content_revisions(post_id) WHERE revision_kind = 'base';

        CREATE TRIGGER content_generation_jobs_succeeded_insert_guard
        BEFORE INSERT ON content_generation_jobs
        WHEN NEW.status = 'succeeded'
        BEGIN
            SELECT CASE WHEN NOT EXISTS (
                SELECT 1
                FROM canonical_posts AS post
                JOIN content_revisions AS revision
                  ON revision.post_id = post.post_id
                WHERE post.post_id = NEW.post_id
                  AND post.opportunity_id = NEW.opportunity_id
                  AND revision.revision_id = NEW.revision_id
                  AND revision.revision_kind = 'base'
            ) THEN RAISE(
                ABORT,
                'succeeded generation job must bind its opportunity, post, and base revision'
            ) END;
        END;

        CREATE TRIGGER content_generation_jobs_succeeded_update_guard
        BEFORE UPDATE OF status, opportunity_id, post_id, revision_id
        ON content_generation_jobs
        WHEN NEW.status = 'succeeded'
        BEGIN
            SELECT CASE WHEN NOT EXISTS (
                SELECT 1
                FROM canonical_posts AS post
                JOIN content_revisions AS revision
                  ON revision.post_id = post.post_id
                WHERE post.post_id = NEW.post_id
                  AND post.opportunity_id = NEW.opportunity_id
                  AND revision.revision_id = NEW.revision_id
                  AND revision.revision_kind = 'base'
            ) THEN RAISE(
                ABORT,
                'succeeded generation job must bind its opportunity, post, and base revision'
            ) END;
        END;

        CREATE TRIGGER content_generation_jobs_succeeded_terminal_guard
        BEFORE UPDATE OF status ON content_generation_jobs
        WHEN OLD.status = 'succeeded' AND NEW.status != 'succeeded'
        BEGIN
            SELECT RAISE(
                ABORT,
                'succeeded generation job status is terminal'
            );
        END;

        CREATE TRIGGER canonical_posts_succeeded_job_update_guard
        BEFORE UPDATE OF post_id, opportunity_id ON canonical_posts
        WHEN EXISTS (
            SELECT 1
            FROM content_generation_jobs AS job
            WHERE job.status = 'succeeded'
              AND job.post_id = OLD.post_id
              AND (
                  NEW.post_id != job.post_id
                  OR NEW.opportunity_id != job.opportunity_id
              )
        )
        BEGIN
            SELECT RAISE(
                ABORT,
                'canonical post update would invalidate a succeeded generation job'
            );
        END;

        CREATE TRIGGER content_revisions_succeeded_job_update_guard
        BEFORE UPDATE OF revision_id, post_id, revision_kind ON content_revisions
        WHEN EXISTS (
            SELECT 1
            FROM content_generation_jobs AS job
            WHERE job.status = 'succeeded'
              AND job.revision_id = OLD.revision_id
              AND (
                  NEW.revision_id != job.revision_id
                  OR NEW.post_id != job.post_id
                  OR NEW.revision_kind != 'base'
              )
        )
        BEGIN
            SELECT RAISE(
                ABORT,
                'content revision update would invalidate a succeeded generation job'
            );
        END;

        CREATE TRIGGER system_events_append_only_update_guard
        BEFORE UPDATE ON system_events
        BEGIN
            SELECT RAISE(ABORT, 'system event ledger is append-only');
        END;

        CREATE TRIGGER system_events_append_only_delete_guard
        BEFORE DELETE ON system_events
        BEGIN
            SELECT RAISE(ABORT, 'system event ledger is append-only');
        END;

        CREATE TRIGGER content_revisions_immutable_update_guard
        BEFORE UPDATE ON content_revisions
        BEGIN
            SELECT RAISE(ABORT, 'content revisions are immutable');
        END;

        CREATE TRIGGER content_revisions_immutable_delete_guard
        BEFORE DELETE ON content_revisions
        BEGIN
            SELECT RAISE(ABORT, 'content revisions are immutable');
        END;

        CREATE TRIGGER artifacts_immutable_update_guard
        BEFORE UPDATE ON artifacts
        BEGIN
            SELECT RAISE(ABORT, 'artifacts are immutable');
        END;

        CREATE TRIGGER artifacts_immutable_delete_guard
        BEFORE DELETE ON artifacts
        BEGIN
            SELECT RAISE(ABORT, 'artifacts are immutable');
        END;
        """,
    ),
)


class IntegratedSystemStore:
    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = Path(database_path or default_database_path()).expanduser().resolve()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        try:
            yield connection
        finally:
            connection.close()

    def migrate(self) -> int:
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL, migration_sha256 TEXT NOT NULL UNIQUE) STRICT"
                )
                known_versions = [version for version, _sql in MIGRATIONS]
                if not known_versions or known_versions != list(
                    range(1, known_versions[-1] + 1)
                ):
                    raise RuntimeError(
                        "code migration history must be a contiguous sequence beginning at one"
                    )
                known_hashes = {
                    version: _sha256_text(sql) for version, sql in MIGRATIONS
                }
                applied_rows = connection.execute(
                    """SELECT version,migration_sha256 FROM schema_migrations
                    ORDER BY version"""
                ).fetchall()
                applied_versions = [int(row["version"]) for row in applied_rows]
                newer_versions = [
                    version
                    for version in applied_versions
                    if version > known_versions[-1]
                ]
                if newer_versions:
                    raise RuntimeError(
                        "database migration history is newer than this code"
                    )
                unknown_versions = [
                    version
                    for version in applied_versions
                    if version not in known_hashes
                ]
                if unknown_versions:
                    raise RuntimeError(
                        "database migration history contains an unknown version"
                    )
                if applied_versions != list(range(1, len(applied_versions) + 1)):
                    raise RuntimeError(
                        "database migration history must be a contiguous prefix"
                    )
                for row in applied_rows:
                    version = int(row["version"])
                    if row["migration_sha256"] != known_hashes[version]:
                        raise RuntimeError(
                            f"database migration {version} hash does not match this code"
                        )
                applied = set(applied_versions)
                for version, sql in MIGRATIONS:
                    if version in applied:
                        continue
                    for statement in _migration_statements(sql):
                        connection.execute(statement)
                    connection.execute(
                        "INSERT INTO schema_migrations(version, applied_at, migration_sha256) VALUES (?, ?, ?)",
                        (version, _utcnow(), _sha256_text(sql)),
                    )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
            return int(connection.execute("PRAGMA user_version").fetchone()[0] or max(v for v, _ in MIGRATIONS))

    def append_event(
        self,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        actor_type: str,
        payload: Mapping[str, Any],
        provenance: Mapping[str, Any],
        idempotency_key: str,
        actor_id: str | None = None,
        artifact_refs: list[str] | None = None,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        self.migrate()
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:event:{idempotency_key}"))
        values = (
            event_id,
            event_type,
            aggregate_type,
            aggregate_id,
            occurred_at or _utcnow(),
            actor_type,
            actor_id,
            _canonical_json(dict(payload)),
            _canonical_json(dict(provenance)),
            _canonical_json(artifact_refs or []),
            idempotency_key,
        )
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """INSERT INTO system_events(
                        event_id,event_type,aggregate_type,aggregate_id,occurred_at,actor_type,actor_id,
                        payload_json,provenance_json,artifact_refs_json,idempotency_key
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING""",
                    values,
                )
                row = connection.execute("SELECT * FROM system_events WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
                if not row:
                    raise RuntimeError("event persistence failed")
                if any(
                    row[key] != expected
                    for key, expected in {
                        "event_type": event_type,
                        "aggregate_type": aggregate_type,
                        "aggregate_id": aggregate_id,
                        "payload_json": values[7],
                        "provenance_json": values[8],
                        "artifact_refs_json": values[9],
                    }.items()
                ):
                    raise ValueError("idempotency key already belongs to a different event")
                connection.execute("COMMIT")
                return dict(row)
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def put_artifact(
        self,
        *,
        content_sha256: str,
        artifact_kind: str,
        logical_ref: str,
        byte_size: int,
        media_type: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.migrate()
        if not re_full_sha256(content_sha256):
            raise ValueError("content_sha256 must be a lowercase SHA-256")
        artifact_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:artifact:{artifact_kind}:{content_sha256}"))
        metadata_json = _canonical_json(dict(metadata or {}))
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """INSERT INTO artifacts(
                        artifact_id,content_sha256,artifact_kind,media_type,logical_ref,byte_size,created_at,metadata_json
                    ) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(content_sha256,artifact_kind) DO NOTHING""",
                    (artifact_id, content_sha256, artifact_kind, media_type, logical_ref, byte_size, _utcnow(), metadata_json),
                )
                row = connection.execute(
                    "SELECT * FROM artifacts WHERE content_sha256 = ? AND artifact_kind = ?",
                    (content_sha256, artifact_kind),
                ).fetchone()
                if not row or row["byte_size"] != byte_size:
                    raise ValueError("artifact identity conflict")
                connection.execute("COMMIT")
                return dict(row)
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def register_source_discovery(
        self,
        *,
        canonical_identity: str,
        source_kind: str,
        origin: str,
        discovery_route: str,
        idempotency_key: str,
        canonical_url: str | None = None,
        author_or_publisher: str | None = None,
        title: str | None = None,
        rights_state: str = "unknown",
        external_ref: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.migrate()
        source_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:source:{canonical_identity}"))
        discovery_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:discovery:{idempotency_key}"))
        now = _utcnow()
        incoming_metadata = dict(metadata or {})
        metadata_json = _canonical_json(incoming_metadata)
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                existing_source = connection.execute(
                    "SELECT * FROM sources WHERE canonical_identity = ?",
                    (canonical_identity,),
                ).fetchone()
                effective_rights_state = rights_state
                effective_source_metadata = incoming_metadata
                if existing_source:
                    try:
                        existing_metadata = json.loads(existing_source["metadata_json"])
                    except (TypeError, ValueError, json.JSONDecodeError):
                        existing_metadata = {}
                    existing_metadata = (
                        dict(existing_metadata) if isinstance(existing_metadata, Mapping) else {}
                    )
                    effective_rights_state = conservative_combined_rights(
                        left_state=str(existing_source["rights_state"]),
                        left_metadata=existing_metadata,
                        right_state=rights_state,
                        right_metadata=incoming_metadata,
                    )
                    effective_source_metadata = existing_metadata
                    if (
                        effective_rights_state == "owner_controlled"
                        and owner_authorship_attested(incoming_metadata)
                    ):
                        effective_source_metadata["owner_authorship_attested"] = True
                        effective_source_metadata["authorship_policy_version"] = (
                            AUTHORSHIP_POLICY_VERSION
                        )
                    if (
                        existing_source["rights_state"] == "owner_controlled"
                        and not owner_authorship_attested(existing_metadata)
                    ):
                        effective_source_metadata["authorship_classification"] = (
                            "unattested_attribution_required"
                        )
                        effective_source_metadata["authorship_policy_version"] = (
                            AUTHORSHIP_POLICY_VERSION
                        )
                    metadata_json = _canonical_json(effective_source_metadata)
                connection.execute(
                    """INSERT INTO sources(
                        source_id,canonical_identity,source_kind,canonical_url,author_or_publisher,title,
                        rights_state,created_at,updated_at,metadata_json
                    ) VALUES (?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(canonical_identity) DO UPDATE SET
                        canonical_url=COALESCE(sources.canonical_url,excluded.canonical_url),
                        author_or_publisher=COALESCE(sources.author_or_publisher,excluded.author_or_publisher),
                        title=COALESCE(sources.title,excluded.title),
                        rights_state=excluded.rights_state,
                        metadata_json=excluded.metadata_json,
                        updated_at=excluded.updated_at""",
                    (
                        source_id,
                        canonical_identity,
                        source_kind,
                        canonical_url,
                        author_or_publisher,
                        title,
                        effective_rights_state,
                        now,
                        now,
                        metadata_json,
                    ),
                )
                registered_source = connection.execute(
                    "SELECT * FROM sources WHERE canonical_identity = ?", (canonical_identity,)
                ).fetchone()
                if not registered_source or registered_source["source_kind"] != source_kind:
                    raise ValueError("canonical source identity conflicts with an existing source kind")
                source = registered_source
                visited_source_ids: set[str] = set()
                while source["merged_into_source_id"]:
                    if source["source_id"] in visited_source_ids:
                        raise ValueError("canonical source alias cycle detected")
                    visited_source_ids.add(source["source_id"])
                    source = connection.execute(
                        "SELECT * FROM sources WHERE source_id=?",
                        (source["merged_into_source_id"],),
                    ).fetchone()
                    if not source:
                        raise ValueError("canonical source alias target is missing")
                if source["source_id"] != registered_source["source_id"]:
                    target_metadata = json.loads(source["metadata_json"] or "{}")
                    registered_metadata = json.loads(
                        registered_source["metadata_json"] or "{}"
                    )
                    combined_rights = conservative_combined_rights(
                        left_state=str(source["rights_state"]),
                        left_metadata=target_metadata,
                        right_state=str(registered_source["rights_state"]),
                        right_metadata=registered_metadata,
                    )
                    if combined_rights != source["rights_state"]:
                        connection.execute(
                            "UPDATE sources SET rights_state=?,updated_at=? WHERE source_id=?",
                            (combined_rights, now, source["source_id"]),
                        )
                        source = connection.execute(
                            "SELECT * FROM sources WHERE source_id=?", (source["source_id"],)
                        ).fetchone()
                connection.execute(
                    """INSERT INTO discovery_events(
                        discovery_id,source_id,origin,discovery_route,external_ref,discovered_at,idempotency_key,metadata_json
                    ) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING""",
                    (discovery_id, source["source_id"], origin, discovery_route, external_ref, now, idempotency_key, metadata_json),
                )
                discovery = connection.execute("SELECT * FROM discovery_events WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
                if (
                    not discovery
                    or discovery["source_id"] != source["source_id"]
                    or discovery["origin"] != origin
                    or discovery["discovery_route"] != discovery_route
                ):
                    raise ValueError("idempotency key already belongs to a different discovery")
                event_key = f"source-discovery:{idempotency_key}"
                event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ai-clone:event:{event_key}"))
                event_payload = _canonical_json(
                    {
                        "discovery_id": discovery["discovery_id"],
                        "origin": origin,
                        # Registration truth is immutable even when the
                        # discovery later advances through qualification.
                        "relevance_state": "pending",
                    }
                )
                event_provenance = _canonical_json(
                    {
                        "canonical_identity": canonical_identity,
                        "discovery_route": discovery_route,
                        "external_ref": external_ref,
                    }
                )
                connection.execute(
                    """INSERT INTO system_events(
                        event_id,event_type,aggregate_type,aggregate_id,occurred_at,actor_type,
                        payload_json,provenance_json,artifact_refs_json,idempotency_key
                    ) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING""",
                    (
                        event_id,
                        "source.discovered",
                        "source",
                        source["source_id"],
                        discovery["discovered_at"],
                        "source_adapter",
                        event_payload,
                        event_provenance,
                        "[]",
                        event_key,
                    ),
                )
                event = connection.execute("SELECT * FROM system_events WHERE idempotency_key = ?", (event_key,)).fetchone()
                if not event or event["aggregate_id"] != source["source_id"] or event["payload_json"] != event_payload:
                    raise ValueError("discovery event idempotency conflict")
                connection.execute("COMMIT")
                return {"source": dict(source), "discovery": dict(discovery), "event": dict(event)}
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def integrity_report(self) -> dict[str, Any]:
        self.migrate()
        with self.connection() as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_key_errors = [dict(row) for row in connection.execute("PRAGMA foreign_key_check")]
            version = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
            return {
                "schema_version": version,
                "integrity": integrity,
                "foreign_key_errors": foreign_key_errors,
                "ready": integrity == "ok" and not foreign_key_errors and version == SCHEMA_VERSION,
            }


def re_full_sha256(value: str) -> bool:
    return len(value) == 64 and value == value.lower() and all(char in "0123456789abcdef" for char in value)
