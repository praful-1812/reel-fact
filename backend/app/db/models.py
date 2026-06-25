"""SQLAlchemy models for Reel Fact."""

from datetime import datetime, timezone
import enum

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Enum

from app.db.database import Base


def utcnow() -> datetime:
    """Timezone-aware UTC now (datetime.utcnow() is deprecated on Python 3.12+)."""
    return datetime.now(timezone.utc)


class JobStatus(str, enum.Enum):
    """High-level lifecycle state of a fact-check job."""

    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class JobStage(str, enum.Enum):
    """Fine-grained pipeline stage, surfaced to the app as a progress indicator."""

    QUEUED = "queued"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    EXTRACTING_CLAIMS = "extracting_claims"
    VERIFYING = "verifying"
    SYNTHESIZING = "synthesizing"
    DONE = "done"
    FAILED = "failed"


# Ordered list so the UI can render a progress bar / step count.
STAGE_ORDER = [
    JobStage.QUEUED,
    JobStage.DOWNLOADING,
    JobStage.TRANSCRIBING,
    JobStage.EXTRACTING_CLAIMS,
    JobStage.VERIFYING,
    JobStage.SYNTHESIZING,
    JobStage.DONE,
]


class FactCheckJob(Base):
    __tablename__ = "factcheck_jobs"

    id = Column(Integer, primary_key=True)

    # Input
    url = Column(String, nullable=False)
    model = Column(String, nullable=True)  # LLM model override (optional)

    # Lifecycle
    status = Column(Enum(JobStatus), default=JobStatus.QUEUED, nullable=False)
    stage = Column(Enum(JobStage), default=JobStage.QUEUED, nullable=False)
    error = Column(Text, nullable=True)

    # Reel metadata (filled after download)
    uploader = Column(String, nullable=True)
    title = Column(String, nullable=True)
    caption = Column(Text, nullable=True)
    duration = Column(Integer, nullable=True)  # seconds
    thumbnail_url = Column(String, nullable=True)

    # Pipeline artifacts
    transcript = Column(Text, nullable=True)
    claims = Column(JSON, default=list)     # [{claim, verdict, confidence, explanation, what_to_check}]
    overall = Column(JSON, nullable=True)   # {verdict, confidence, summary, whats_wrong: [...]}

    # Timing
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    completed_at = Column(DateTime, nullable=True)
