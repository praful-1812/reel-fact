"""Reel Fact — FastAPI backend.

Pipeline: Instagram Reel URL → download → transcribe → LLM fact-check agents → verdict.
"""

import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env into os.environ so LiteLLM (and friends) can read API keys.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.api import factcheck, health  # noqa: E402  (after load_dotenv)
from app.config import settings  # noqa: E402
from app.db.database import engine, Base  # noqa: E402
from app.services.queue import factcheck_queue  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
# Trim noise from chatty third-party libraries.
for noisy in ("httpcore", "httpx", "litellm", "yt_dlp", "faster_whisper"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

app = FastAPI(
    title="Reel Fact",
    description="Fact-check Instagram Reels: transcribe + verify with LLM agents.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(factcheck.router, prefix="/api/factcheck", tags=["factcheck"])


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await factcheck_queue.start()


@app.on_event("shutdown")
async def shutdown():
    await factcheck_queue.stop()
