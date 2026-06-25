"""Application configuration (pydantic-settings).

All values can be overridden via environment variables or a `.env` file.
See `.env.example` for the full list.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Core ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./reel_fact.db"
    DOWNLOAD_DIR: str = "./downloads"

    # CORS: comma-separated list of allowed origins. "*" allows everything,
    # which is convenient while developing the Expo app on a device.
    CORS_ORIGINS: str = "*"

    # ── LLM (LiteLLM) ─────────────────────────────────────────────────────
    # Default model used by every agent. Override per environment.
    #   openai/gpt-4o-mini · anthropic/claude-3-5-haiku-latest ·
    #   gemini/gemini-2.0-flash · groq/llama-3.3-70b-versatile · ollama/llama3
    DEFAULT_MODEL: str = "openai/gpt-4o-mini"

    # ── Transcription ─────────────────────────────────────────────────────
    # Backend to use: "faster-whisper" (local, no key) | "openai" | "groq"
    TRANSCRIPTION_BACKEND: str = "faster-whisper"
    # faster-whisper model size: tiny | base | small | medium | large-v3
    WHISPER_MODEL_SIZE: str = "base"
    # Compute type for faster-whisper: int8 (CPU friendly) | float16 (GPU)
    WHISPER_COMPUTE_TYPE: str = "int8"

    # ── Reel download ─────────────────────────────────────────────────────
    # Optional path to a cookies.txt file so yt-dlp can fetch login-gated reels.
    YTDLP_COOKIES_FILE: str = ""
    # Hard cap on how long (seconds) a reel may be before we refuse to process.
    MAX_REEL_DURATION_SECONDS: int = 600

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
