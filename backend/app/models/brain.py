from __future__ import annotations

from pydantic import BaseModel, model_validator


class BrainLongFormIngestRequest(BaseModel):
    url: str | None = None
    title: str | None = None
    summary: str | None = None
    notes: str | None = None
    transcript_text: str | None = None
    source_type: str | None = None
    author: str | None = None
    run_refresh: bool = True

    @model_validator(mode="after")
    def ensure_source(self) -> "BrainLongFormIngestRequest":
        if not ((self.url or "").strip() or (self.transcript_text or "").strip() or (self.notes or "").strip()):
            raise ValueError("Provide a url, transcript_text, or notes.")
        return self
