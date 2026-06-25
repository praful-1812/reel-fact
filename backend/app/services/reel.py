"""Reel ingestion — download the video + metadata (yt-dlp) and extract audio (ffmpeg).

Instagram Reels are resolved with `yt-dlp`. We grab the lowest acceptable video
quality (we only need the audio) plus metadata: uploader, title, caption, duration
and thumbnail. Audio is transcoded to 16 kHz mono WAV which is ideal for Whisper.
"""

import asyncio
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ReelData:
    url: str
    media_path: str            # downloaded video/audio file
    audio_path: str            # 16 kHz mono wav for transcription
    uploader: str | None = None
    title: str | None = None
    caption: str | None = None
    duration: int | None = None
    thumbnail_url: str | None = None
    extra: dict = field(default_factory=dict)


class ReelDownloadError(Exception):
    """Raised when a reel cannot be downloaded or is otherwise unusable."""


def _job_dir(job_id: int) -> str:
    path = os.path.join(settings.DOWNLOAD_DIR, str(job_id))
    os.makedirs(path, exist_ok=True)
    return path


def _ydl_opts(job_id: int) -> dict:
    out_dir = _job_dir(job_id)
    opts: dict = {
        # Prefer a small mp4; fall back to whatever single file is available.
        "format": "worst[ext=mp4]/worst/best",
        "outtmpl": os.path.join(out_dir, "reel.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "retries": 3,
    }
    if settings.YTDLP_COOKIES_FILE and os.path.exists(settings.YTDLP_COOKIES_FILE):
        opts["cookiefile"] = settings.YTDLP_COOKIES_FILE
        logger.info(f"[Reel] Using cookies file: {settings.YTDLP_COOKIES_FILE}")
    return opts


def _download_sync(url: str, job_id: int) -> ReelData:
    """Blocking download — run inside an executor."""
    import yt_dlp

    logger.info(f"[Reel] Downloading {url}")
    with yt_dlp.YoutubeDL(_ydl_opts(job_id)) as ydl:
        info = ydl.extract_info(url, download=True)
        # Some extractors wrap the real entry in 'entries'.
        if "entries" in info and info["entries"]:
            info = info["entries"][0]
        media_path = ydl.prepare_filename(info)

    if not media_path or not os.path.exists(media_path):
        # yt-dlp may have remuxed/renamed — find whatever landed in the dir.
        candidates = [
            os.path.join(_job_dir(job_id), f)
            for f in os.listdir(_job_dir(job_id))
            if f.startswith("reel")
        ]
        if not candidates:
            raise ReelDownloadError("Download produced no media file.")
        media_path = max(candidates, key=os.path.getsize)

    duration = info.get("duration")
    if duration and duration > settings.MAX_REEL_DURATION_SECONDS:
        raise ReelDownloadError(
            f"Reel is too long ({int(duration)}s > {settings.MAX_REEL_DURATION_SECONDS}s limit)."
        )

    caption = info.get("description") or info.get("title")

    return ReelData(
        url=url,
        media_path=media_path,
        audio_path="",  # filled in by audio extraction
        uploader=info.get("uploader") or info.get("channel") or info.get("uploader_id"),
        title=info.get("title"),
        caption=caption,
        duration=int(duration) if duration else None,
        thumbnail_url=info.get("thumbnail"),
        extra={"webpage_url": info.get("webpage_url"), "id": info.get("id")},
    )


def _extract_audio_sync(media_path: str, job_id: int) -> str:
    """Transcode media → 16 kHz mono WAV with ffmpeg. Returns the wav path."""
    if shutil.which("ffmpeg") is None:
        logger.warning("[Reel] ffmpeg not found on PATH; using raw media for transcription.")
        return media_path

    audio_path = os.path.join(_job_dir(job_id), "audio.wav")
    cmd = [
        "ffmpeg", "-y",
        "-i", media_path,
        "-vn",                # drop video
        "-ac", "1",           # mono
        "-ar", "16000",       # 16 kHz
        "-f", "wav",
        audio_path,
    ]
    logger.info("[Reel] Extracting audio via ffmpeg...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not os.path.exists(audio_path):
        logger.warning(f"[Reel] ffmpeg failed; falling back to raw media. stderr: {result.stderr[:300]}")
        return media_path
    return audio_path


async def download_reel(url: str, job_id: int) -> ReelData:
    """Download a reel and extract its audio. Returns a populated ReelData."""
    loop = asyncio.get_event_loop()
    try:
        data = await loop.run_in_executor(None, _download_sync, url, job_id)
    except ReelDownloadError:
        raise
    except Exception as e:  # noqa: BLE001 — surface yt-dlp errors uniformly
        logger.exception("[Reel] yt-dlp download failed")
        raise ReelDownloadError(f"Could not download reel: {e}") from e

    data.audio_path = await loop.run_in_executor(
        None, _extract_audio_sync, data.media_path, job_id
    )
    logger.info(
        f"[Reel] ✓ Ready: uploader={data.uploader!r}, duration={data.duration}s, "
        f"audio={os.path.basename(data.audio_path)}"
    )
    return data


def cleanup_job_files(job_id: int) -> None:
    """Delete downloaded media for a job (call after transcription to save disk)."""
    path = os.path.join(settings.DOWNLOAD_DIR, str(job_id))
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
        logger.info(f"[Reel] Cleaned up files for job {job_id}")
