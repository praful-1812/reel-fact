"""Health + capability probe — handy for the app to verify the backend is reachable."""

import shutil

from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("/health")
async def health():
    """Liveness check plus a quick report of optional dependencies."""
    return {
        "status": "ok",
        "default_model": settings.DEFAULT_MODEL,
        "transcription_backend": settings.TRANSCRIPTION_BACKEND,
        "ffmpeg_installed": shutil.which("ffmpeg") is not None,
    }
