"""Fact-check API — submit a reel URL, poll the job, fetch the result."""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import FactCheckJob, JobStatus, JobStage
from app.schemas import FactCheckRequest, JobResponse
from app.services.queue import factcheck_queue

logger = logging.getLogger(__name__)
router = APIRouter()

# Accept instagram reel / post / tv / share links.
_INSTAGRAM_RE = re.compile(
    r"https?://(?:www\.)?instagram\.com/(?:reel|reels|p|tv|share)/[\w\-./?=&%]+",
    re.IGNORECASE,
)


def _validate_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="A reel URL is required.")
    if not _INSTAGRAM_RE.match(url):
        raise HTTPException(
            status_code=400,
            detail="That doesn't look like an Instagram Reel link. "
                   "Expected something like https://www.instagram.com/reel/XXXXXX(...)",
        )
    return url


@router.post("", response_model=JobResponse)
@router.post("/", response_model=JobResponse)
async def create_factcheck(payload: FactCheckRequest, db: AsyncSession = Depends(get_db)):
    """Submit a reel for fact-checking. Returns a QUEUED job to poll."""
    url = _validate_url(payload.url)

    job = FactCheckJob(
        url=url,
        model=payload.model,
        status=JobStatus.QUEUED,
        stage=JobStage.QUEUED,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    await factcheck_queue.enqueue(job.id)
    logger.info(f"[API] Created job {job.id} for {url}")
    return JobResponse.from_job(job)


@router.get("/{job_id}", response_model=JobResponse)
async def get_factcheck(job_id: int, db: AsyncSession = Depends(get_db)):
    """Poll a job's status / fetch its result once done."""
    job = (
        await db.execute(select(FactCheckJob).where(FactCheckJob.id == job_id))
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobResponse.from_job(job)


@router.get("", response_model=list[JobResponse])
@router.get("/", response_model=list[JobResponse])
async def list_factchecks(limit: int = 20, db: AsyncSession = Depends(get_db)):
    """Recent fact-check jobs (simple history for the app)."""
    limit = max(1, min(limit, 100))
    rows = (
        await db.execute(
            select(FactCheckJob).order_by(FactCheckJob.id.desc()).limit(limit)
        )
    ).scalars().all()
    return [JobResponse.from_job(j) for j in rows]
