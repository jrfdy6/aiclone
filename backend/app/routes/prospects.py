from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from app.services.firestore_prospect_authority_service import (
    FirestoreProspectAuthorityError,
    FirestoreProspectNotFoundError,
    ProspectAuthorityReadResult,
    legacy_pipeline_projection,
    read_prospects,
    update_canonical_prospect,
    write_canonical_prospects,
)
from app.services.local_store import load_cached_prospects

router = APIRouter(tags=["Prospects"])


FIRESTORE_STATE_HEADER = "X-AI-Clone-Firestore-State"
DATA_SOURCE_HEADER = "X-AI-Clone-Data-Source"
DATA_AUTHORITY_HEADER = "X-AI-Clone-Data-Authority"
DEGRADED_REASON_HEADER = "X-AI-Clone-Degraded-Reasons"
PROSPECT_PIPELINE_SCHEMA_VERSION = "prospect_pipeline/v1"
ProspectStatus = Literal["new", "analyzed", "contacted", "follow_up_needed"]


class ProspectPipelineInput(BaseModel):
    id: Optional[str] = None
    name: str = Field(min_length=1, max_length=300)
    company: Optional[str] = Field(default=None, max_length=500)
    organization: Optional[str] = Field(default=None, max_length=500)
    job_title: Optional[str] = Field(default=None, max_length=300)
    title: Optional[str] = Field(default=None, max_length=300)
    email: Optional[str] = Field(default=None, max_length=320)
    phone: Optional[str] = Field(default=None, max_length=100)
    website: Optional[str] = Field(default=None, max_length=2_000)
    fit_score: Optional[float] = None
    confidence: Optional[float] = None
    status: ProspectStatus = "new"
    tags: list[str] = Field(default_factory=list, max_length=50)
    source: Optional[str] = Field(default=None, max_length=200)
    source_url: Optional[str] = Field(default=None, max_length=2_000)
    url: Optional[str] = Field(default=None, max_length=2_000)
    location: Optional[str] = Field(default=None, max_length=500)
    bio_snippet: Optional[str] = Field(default=None, max_length=4_000)
    created_at: Optional[datetime | float | str] = None

    def authority_document(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "organization": self.organization or self.company,
            "title": self.title or self.job_title,
            "contact": {
                "email": self.email,
                "phone": self.phone,
                "website": self.website,
            },
            "confidence": self.confidence,
            "fit_score": self.fit_score,
            "status": self.status,
            "tags": self.tags,
            "source": self.source or "owner_selected_discovery",
            "url": self.url or self.source_url,
            "location": self.location,
            "bio_snippet": self.bio_snippet,
            "created_at": self.created_at,
        }


class ProspectBatchCreateRequest(BaseModel):
    user_id: Optional[str] = None
    prospects: list[ProspectPipelineInput] = Field(min_length=1, max_length=100)


class ProspectPatchRequest(BaseModel):
    status: Optional[ProspectStatus] = None
    notes: Optional[str] = Field(default=None, max_length=5_000)
    last_action: Optional[str] = Field(default=None, max_length=500)


class ProspectListResponse(BaseModel):
    schema_version: Literal["prospect_pipeline/v1"] = PROSPECT_PIPELINE_SCHEMA_VERSION
    success: bool = True
    state: str
    data_source: str
    data_authority: str
    reason_codes: list[str] = Field(default_factory=list)
    prospects: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0


class ProspectMutationResponse(BaseModel):
    schema_version: Literal["prospect_pipeline/v1"] = PROSPECT_PIPELINE_SCHEMA_VERSION
    success: bool = True
    state: Literal["ready"] = "ready"
    data_authority: str
    prospects: list[dict[str, Any]] = Field(default_factory=list)
    saved_count: int = 0


def _default_user_id() -> str:
    return os.getenv("DEFAULT_USER_ID", "default-user")


def _owner_user_id(requested: str | None = None) -> str:
    configured = _default_user_id()
    if requested is not None and requested != configured:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The requested user does not match the configured owner authority.",
        )
    return configured


def _apply_read_headers(response: Response, result: ProspectAuthorityReadResult, *, source: str | None = None) -> None:
    response.headers[FIRESTORE_STATE_HEADER] = result.state
    response.headers[DATA_SOURCE_HEADER] = source or result.source
    response.headers[DATA_AUTHORITY_HEADER] = f"firestore:users/{_default_user_id()}/prospects"
    if result.reason_codes:
        response.headers[DEGRADED_REASON_HEADER] = ",".join(result.reason_codes)
    response.headers["Cache-Control"] = "no-store, max-age=0"


def _apply_write_headers(response: Response, user_id: str) -> None:
    response.headers[FIRESTORE_STATE_HEADER] = "ready"
    response.headers[DATA_SOURCE_HEADER] = "canonical"
    response.headers[DATA_AUTHORITY_HEADER] = f"firestore:users/{user_id}/prospects"
    response.headers["Cache-Control"] = "no-store, max-age=0"


def _filter(
    prospects: list[dict[str, Any]],
    category: Optional[str],
    has_email: Optional[bool],
) -> list[dict[str, Any]]:
    results = prospects
    if category:
        results = [item for item in results if str(item.get("category") or "").lower() == category.lower()]
    if has_email is not None:
        results = [item for item in results if bool(item.get("email")) is has_email]
    return results


@router.get("/", response_model=ProspectListResponse)
async def list_prospects(
    response: Response,
    category: Optional[str] = None,
    has_email: Optional[bool] = None,
    user_id: Optional[str] = None,
    limit: int = Query(default=500, ge=1, le=500),
):
    owner_user_id = _owner_user_id(user_id)
    read_result = read_prospects(owner_user_id)
    projected = [legacy_pipeline_projection(item) for item in read_result.documents]
    source = read_result.source
    result_for_headers = read_result
    if not projected:
        local_rows = [legacy_pipeline_projection(item.model_dump()) for item in load_cached_prospects()]
        if local_rows:
            projected = local_rows
            source = "local_read_only_compatibility"
            result_for_headers = ProspectAuthorityReadResult(
                documents=read_result.documents,
                state="degraded" if read_result.state == "degraded" else "compatibility",
                source=source,
                reason_codes=read_result.reason_codes,
                canonical_count=read_result.canonical_count,
                legacy_count=read_result.legacy_count,
                legacy_only_count=read_result.legacy_only_count,
                conflict_count=read_result.conflict_count,
            )
    filtered = _filter(projected, category, has_email)[:limit]
    _apply_read_headers(response, result_for_headers, source=source)
    return ProspectListResponse(
        state=result_for_headers.state,
        data_source=source,
        data_authority=f"firestore:users/{owner_user_id}/prospects",
        reason_codes=list(result_for_headers.reason_codes),
        prospects=filtered,
        total=len(filtered),
    )


@router.post("/", response_model=ProspectMutationResponse)
async def create_prospects(request: ProspectBatchCreateRequest, response: Response):
    user_id = _owner_user_id(request.user_id)
    try:
        written = write_canonical_prospects(
            user_id,
            [prospect.authority_document() for prospect in request.prospects],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except FirestoreProspectAuthorityError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "state": "degraded",
                "reason_codes": ["canonical_prospect_write_unavailable"],
                "message": "The canonical prospect store is temporarily unavailable.",
            },
        ) from exc
    _apply_write_headers(response, user_id)
    rows = [legacy_pipeline_projection(item) for item in written]
    return ProspectMutationResponse(
        data_authority=f"firestore:users/{user_id}/prospects",
        prospects=rows,
        saved_count=len(rows),
    )


@router.patch("/{prospect_id}", response_model=ProspectMutationResponse)
async def patch_prospect(
    prospect_id: str,
    request: ProspectPatchRequest,
    response: Response,
    user_id: Optional[str] = None,
):
    owner_user_id = _owner_user_id(user_id)
    try:
        updated = update_canonical_prospect(
            owner_user_id,
            prospect_id,
            request.model_dump(exclude_none=True),
        )
    except FirestoreProspectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prospect not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except FirestoreProspectAuthorityError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "state": "degraded",
                "reason_codes": ["canonical_prospect_write_unavailable"],
                "message": "The canonical prospect store is temporarily unavailable.",
            },
        ) from exc
    _apply_write_headers(response, owner_user_id)
    return ProspectMutationResponse(
        data_authority=f"firestore:users/{owner_user_id}/prospects",
        prospects=[legacy_pipeline_projection(updated)],
        saved_count=1,
    )
