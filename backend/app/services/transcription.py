"""Transcription — turn reel audio into text.

Pluggable backends (set TRANSCRIPTION_BACKEND in .env):

  • "faster-whisper"  → runs locally, no API key, downloads the model once (default)
  • "openai"          → OpenAI whisper-1   (needs OPENAI_API_KEY)
  • "groq"            → Groq whisper-large-v3 (needs GROQ_API_KEY, very fast)
"""

import asyncio
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Lazily-loaded local model (loading is expensive, so we cache it).
_whisper_model = None


class TranscriptionError(Exception):
    pass


def _get_faster_whisper():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        size = settings.WHISPER_MODEL_SIZE
        compute = settings.WHISPER_COMPUTE_TYPE
        logger.info(f"[Transcribe] Loading faster-whisper model '{size}' (compute={compute})...")
        _whisper_model = WhisperModel(size, device="cpu", compute_type=compute)
        logger.info("[Transcribe] ✓ Model loaded")
    return _whisper_model


def _transcribe_local_sync(audio_path: str) -> str:
    model = _get_faster_whisper()
    segments, info = model.transcribe(audio_path, beam_size=5, vad_filter=True)
    lang = getattr(info, "language", "?")
    logger.info(f"[Transcribe] Detected language: {lang}")
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return text


async def _transcribe_local(audio_path: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _transcribe_local_sync, audio_path)


def _transcribe_api_sync(audio_path: str, model: str) -> str:
    """Use a hosted Whisper endpoint through LiteLLM (OpenAI / Groq)."""
    import litellm

    with open(audio_path, "rb") as f:
        response = litellm.transcription(model=model, file=f)
    # LiteLLM returns an object with a `.text` attribute (or dict-like).
    if isinstance(response, dict):
        return response.get("text", "")
    return getattr(response, "text", "") or ""


async def _transcribe_api(audio_path: str, model: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _transcribe_api_sync, audio_path, model)


async def transcribe(audio_path: str) -> str:
    """Transcribe `audio_path` using the configured backend. Returns plain text."""
    backend = settings.TRANSCRIPTION_BACKEND.lower()
    logger.info(f"[Transcribe] Backend={backend}, file={audio_path}")

    try:
        if backend == "openai":
            text = await _transcribe_api(audio_path, "whisper-1")
        elif backend == "groq":
            text = await _transcribe_api(audio_path, "groq/whisper-large-v3")
        else:  # default: faster-whisper
            text = await _transcribe_local(audio_path)
    except Exception as e:  # noqa: BLE001
        logger.exception("[Transcribe] Transcription failed")
        raise TranscriptionError(str(e)) from e

    text = (text or "").strip()
    if not text:
        logger.warning("[Transcribe] ⚠ Empty transcript (reel may have no speech).")
    else:
        logger.info(f"[Transcribe] ✓ {len(text)} chars transcribed")
    return text
