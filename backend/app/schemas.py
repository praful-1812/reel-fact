"""Pydantic request/response schemas (the API contract used by the Android app)."""

from datetime import datetime
from pydantic import BaseModel, Field

from app.db.models import JobStatus, JobStage, STAGE_ORDER


# ── Requests ──────────────────────────────────────────────────────────────
class FactCheckRequest(BaseModel):
    url: str = Field(..., description="Instagram Reel URL to fact-check")
    model: str | None = Field(
        default=None,
        description="Optional LiteLLM model override, e.g. 'openai/gpt-4o-mini'",
    )


# ── Nested response pieces ────────────────────────────────────────────────
class ClaimResult(BaseModel):
    claim: str
    verdict: str          # true | false | misleading | unverifiable
    confidence: float     # 0.0 – 1.0
    explanation: str
    what_to_check: str = ""


class OverallResult(BaseModel):
    verdict: str          # true | false | misleading | unverifiable
    confidence: float
    summary: str
    whats_wrong: list[str] = []


class ReelSource(BaseModel):
    url: str
    uploader: str | None = None
    title: str | None = None
    caption: str | None = None
    duration: int | None = None
    thumbnail_url: str | None = None


# ── Main job response ─────────────────────────────────────────────────────
class JobResponse(BaseModel):
    id: int
    status: JobStatus
    stage: JobStage
    stage_index: int = 0
    stage_total: int = len(STAGE_ORDER)
    error: str | None = None

    source: ReelSource
    transcript: str | None = None
    claims: list[ClaimResult] = []
    overall: OverallResult | None = None

    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    @classmethod
    def from_job(cls, job) -> "JobResponse":
        """Build the API response from a FactCheckJob ORM row."""
        try:
            stage_index = STAGE_ORDER.index(job.stage)
        except ValueError:
            stage_index = 0

        return cls(
            id=job.id,
            status=job.status,
            stage=job.stage,
            stage_index=stage_index,
            error=job.error,
            source=ReelSource(
                url=job.url,
                uploader=job.uploader,
                title=job.title,
                caption=job.caption,
                duration=job.duration,
                thumbnail_url=job.thumbnail_url,
            ),
            transcript=job.transcript,
            claims=[ClaimResult(**c) for c in (job.claims or [])],
            overall=OverallResult(**job.overall) if job.overall else None,
            created_at=job.created_at,
            updated_at=job.updated_at,
            completed_at=job.completed_at,
        )
