from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class NeoInviteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=120)
    passcode: str = Field(min_length=10, max_length=160)
    expires_at: datetime | None = None


class NeoGuestAccess(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passcode: str = Field(min_length=1, max_length=160)


class NeoGuestMessageBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("content", mode="before")
    @classmethod
    def trim_content(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
        return value


class NeoGuestMessageLegacyCreate(NeoGuestMessageBase):
    client_request_id: UUID | None = None


class NeoGuestMessageCreate(NeoGuestMessageBase):
    client_request_id: UUID


class NeoMeetingRequestBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    visitor_name: str = Field(min_length=1, max_length=160)
    visitor_email: EmailStr
    visitor_phone: str = Field(min_length=5, max_length=40)
    purpose: str = Field(min_length=1, max_length=1200)
    preferred_times: list[Annotated[str, Field(min_length=1, max_length=160)]] = Field(
        min_length=1,
        max_length=5,
    )
    timezone: str = Field(min_length=1, max_length=80)

    @field_validator(
        "visitor_name",
        "visitor_email",
        "visitor_phone",
        "purpose",
        "timezone",
        mode="before",
    )
    @classmethod
    def trim_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
        return value

    @field_validator("preferred_times", mode="before")
    @classmethod
    def trim_preferred_times(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        normalized: list[object] = []
        for item in value:
            if isinstance(item, str):
                item = item.strip()
            normalized.append(item)
        return normalized


class NeoMeetingRequestLegacyCreate(NeoMeetingRequestBase):
    client_request_id: UUID | None = None


class NeoMeetingRequestCreate(NeoMeetingRequestBase):
    client_request_id: UUID


class NeoWorkerClaim(BaseModel):
    worker_id: str = Field(min_length=1, max_length=160)


class NeoWorkerProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")
    worker_id: str = Field(min_length=1, max_length=160)
    partial_response: str = Field(max_length=8000)


class NeoWorkerComplete(BaseModel):
    worker_id: str = Field(min_length=1, max_length=160)
    response: str = Field(min_length=1, max_length=8000)


class NeoWorkerFail(BaseModel):
    worker_id: str = Field(min_length=1, max_length=160)
    error: str = Field(min_length=1, max_length=2000)


class NeoMeetingDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["approved", "declined"]
    owner_notes: str | None = Field(default=None, max_length=2000)
