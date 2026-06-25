"""Pipeline orchestrator — runs one fact-check job end-to-end.

Drives a job through every stage, committing progress to the DB after each step
so the Android app's polling sees a live status / stage update:

  DOWNLOADING → TRANSCRIBING → EXTRACTING_CLAIMS → VERIFYING → SYNTHESIZING → DONE
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.models import FactCheckJob, JobStatus, JobStage, utcnow
from app.services import agents
from app.services.reel import download_reel, cleanup_job_files, ReelDownloadError
from app.services.transcription import transcribe, TranscriptionError

logger = logging.getLogger(__name__)

# Dedicated engine/session for background work (separate from request sessions).
_engine = create_async_engine(settings.DATABASE_URL, connect_args={"timeout": 30})
_session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def _set_stage(db: AsyncSession, job: FactCheckJob, stage: JobStage) -> None:
    job.stage = stage
    job.status = JobStatus.PROCESSING
    job.updated_at = utcnow()
    await db.commit()
    logger.info(f"[Pipeline] job={job.id} → stage={stage.value}")


async def run_factcheck(job_id: int) -> None:
    """Execute the full pipeline for a single job id."""
    async with _session_factory() as db:
        job = (
            await db.execute(select(FactCheckJob).where(FactCheckJob.id == job_id))
        ).scalar_one_or_none()
        if job is None:
            logger.error(f"[Pipeline] job {job_id} not found")
            return

        model = job.model or settings.DEFAULT_MODEL
        logger.info(f"[Pipeline] ▶ Starting job {job_id} for {job.url} (model={model})")

        try:
            # 1) Download ------------------------------------------------------
            await _set_stage(db, job, JobStage.DOWNLOADING)
            reel = await download_reel(job.url, job_id)
            job.uploader = reel.uploader
            job.title = reel.title
            job.caption = reel.caption
            job.duration = reel.duration
            job.thumbnail_url = reel.thumbnail_url
            await db.commit()

            # 2) Transcribe ----------------------------------------------------
            await _set_stage(db, job, JobStage.TRANSCRIBING)
            transcript = await transcribe(reel.audio_path)
            job.transcript = transcript
            await db.commit()
            cleanup_job_files(job_id)  # free disk; we have the text now

            context = f"{transcript}\n\nCaption: {reel.caption or ''}".strip()

            # 3) Extract claims ------------------------------------------------
            await _set_stage(db, job, JobStage.EXTRACTING_CLAIMS)
            claims = await agents.extract_claims(transcript, reel.caption, model)

            # 4) Verify claims -------------------------------------------------
            await _set_stage(db, job, JobStage.VERIFYING)
            claim_results = await agents.verify_claims(claims, context, model)
            job.claims = claim_results
            await db.commit()

            # 5) Synthesize ----------------------------------------------------
            await _set_stage(db, job, JobStage.SYNTHESIZING)
            overall = await agents.synthesize(transcript, reel.caption, claim_results, model)
            job.overall = overall

            # Done -------------------------------------------------------------
            job.status = JobStatus.DONE
            job.stage = JobStage.DONE
            job.completed_at = utcnow()
            job.updated_at = utcnow()
            await db.commit()
            logger.info(f"[Pipeline] ✓ job {job_id} done → verdict={overall.get('verdict')}")

        except (ReelDownloadError, TranscriptionError) as e:
            await _fail(db, job, str(e))
        except Exception as e:  # noqa: BLE001 — record any failure on the job
            logger.exception(f"[Pipeline] job {job_id} crashed")
            await _fail(db, job, f"Unexpected error: {e}")


async def _fail(db: AsyncSession, job: FactCheckJob, message: str) -> None:
    job.status = JobStatus.FAILED
    job.stage = JobStage.FAILED
    job.error = message
    job.updated_at = utcnow()
    await db.commit()
    logger.error(f"[Pipeline] ✗ job {job.id} failed: {message}")
    # Best-effort cleanup of any partial downloads.
    cleanup_job_files(job.id)
