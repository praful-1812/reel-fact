# Reel Fact — Project Planning

> An Android app where a user pastes an Instagram Reel link, and the system **downloads → transcribes → fact-checks** the content using a pipeline of LLM agents, returning a verdict ("True / False / Misleading / Unverifiable") plus an explanation of *what's wrong*.

---

## 🎯 Core Concept

```
 ┌──────────────────────┐        ┌───────────────────────────────────────────┐
 │   Android App (Expo) │        │            Backend (FastAPI)                │
 │                      │  URL   │                                             │
 │  Paste Reel link ────┼───────▶│  1. Download reel (yt-dlp) + caption        │
 │                      │        │  2. Extract audio (ffmpeg)                  │
 │  Poll for result ◀───┼────────│  3. Transcribe (Whisper)                    │
 │                      │ status │  4. Agent: extract claims                   │
 │  Show verdict +      │        │  5. Agent: verify each claim                │
 │  per-claim breakdown │ result │  6. Agent: synthesize overall verdict       │
 └──────────────────────┘        └───────────────────────────────────────────┘
```

The user does **one thing**: paste a Reel URL. Everything else (download, transcription,
claim extraction, verification, synthesis) happens server-side as an async job. The app
polls until the job is done, then renders the result.

---

## 🧩 Why this split (Android client + Python backend)

| Concern | Where | Why |
|---|---|---|
| UI / paste link / share-sheet | **Android (Expo / React Native)** | Native mobile UX, share intent from Instagram, builds to a real `.apk`/`.aab` |
| Video download | **Backend (yt-dlp)** | Heavy, needs `ffmpeg`, changes often — keep it off-device |
| Transcription (Whisper) | **Backend** | CPU/GPU heavy, large models, better on a server |
| LLM agents | **Backend (LiteLLM)** | Keep API keys off the device; one place to swap providers |

> The mobile app is intentionally "thin": it submits a URL and renders JSON. All the
> intelligence lives in the backend, exactly like the `vectorless-rag` project's split.

---

## 🏗️ Architecture Overview

### Backend (FastAPI) — mirrors the `vectorless-rag` conventions

```
backend/
├── run.py                     # uvicorn entrypoint
├── requirements.txt
├── .env.example
└── app/
    ├── config.py              # pydantic-settings
    ├── main.py                # FastAPI app + CORS + startup
    ├── schemas.py             # request/response Pydantic models
    ├── api/
    │   ├── factcheck.py       # POST /api/factcheck, GET /api/factcheck/{id}
    │   └── health.py
    ├── db/
    │   ├── database.py        # async SQLAlchemy + SQLite (WAL)
    │   └── models.py          # FactCheckJob
    └── services/
        ├── llm.py             # LiteLLM multi-provider wrapper (+ JSON mode)
        ├── reel.py            # yt-dlp download + caption/metadata
        ├── transcription.py   # Whisper (faster-whisper / OpenAI / Groq)
        ├── agents.py          # claim-extraction / verification / synthesis agents
        ├── pipeline.py        # orchestrates the full job
        └── queue.py           # async background worker queue
```

### Android app (Expo / React Native + TypeScript)

```
mobile/
├── app.json                   # Expo config (Android package id, share intent)
├── package.json
├── tsconfig.json
├── App.tsx                    # navigation root
└── src/
    ├── api/client.ts          # talks to the FastAPI backend, polls job status
    ├── theme.ts               # colors / spacing
    ├── screens/
    │   ├── HomeScreen.tsx      # paste link + submit
    │   └── ResultScreen.tsx    # verdict + transcript + claim breakdown
    └── components/
        ├── VerdictBadge.tsx
        ├── ClaimCard.tsx
        └── StageProgress.tsx
```

---

## 🔬 The Fact-Check Pipeline (multi-agent)

Each job moves through explicit **stages** so the app can show progress:

```
QUEUED → DOWNLOADING → TRANSCRIBING → EXTRACTING_CLAIMS → VERIFYING → SYNTHESIZING → DONE
                                                                              ↘ FAILED
```

### Stage 1 — Download (`services/reel.py`)
- `yt-dlp` resolves the Reel URL, downloads the video (lowest acceptable quality to
  save bandwidth) and grabs metadata: **caption/description, uploader, title, duration**.
- `ffmpeg` extracts a 16 kHz mono WAV for transcription.

### Stage 2 — Transcribe (`services/transcription.py`)
- Default: **`faster-whisper`** running locally (no API key, model auto-downloads once).
- Optional backends via env: **OpenAI** `whisper-1`, **Groq** `whisper-large-v3`.
- Output: full transcript text (+ caption text is appended as additional context).

### Stage 3 — Extract Claims (`agents.extract_claims`)
- One LLM call. Input = transcript + caption. Output = a JSON list of **discrete,
  checkable factual claims** (opinions and fluff are dropped).

### Stage 4 — Verify Each Claim (`agents.verify_claim`)
- One LLM call **per claim**. The "verifier agent" returns structured JSON:
  `{ verdict, confidence, explanation, what_to_check }`.
- Verdicts per claim: `true | false | misleading | unverifiable`.
- Designed to be honest about uncertainty (it must say `unverifiable` rather than guess).
- 🔌 **Optional web search tool** can be plugged in here (Tavily/SerpAPI) to ground
  verification in fresh sources. Off by default so the app runs with just an LLM key.

### Stage 5 — Synthesize (`agents.synthesize`)
- Final LLM call aggregates per-claim results into one **overall verdict**, a short
  human summary, and a **"what's wrong"** list highlighting the most misleading parts.

### Final result shape (returned to the app)

```jsonc
{
  "id": 12,
  "status": "done",
  "stage": "done",
  "source": { "url": "...", "uploader": "...", "caption": "...", "duration": 42 },
  "transcript": "full transcript text ...",
  "overall": {
    "verdict": "misleading",          // true | false | misleading | unverifiable
    "confidence": 0.74,
    "summary": "The reel mixes one true fact with two false claims ...",
    "whats_wrong": ["Claim 2 is false because ...", "Claim 3 is unsupported ..."]
  },
  "claims": [
    {
      "claim": "Drinking lemon water burns fat.",
      "verdict": "false",
      "confidence": 0.9,
      "explanation": "No evidence that lemon water increases fat oxidation ...",
      "what_to_check": "Look for peer-reviewed studies on citrus and metabolism."
    }
  ]
}
```

---

## 🤖 LLM Providers (LiteLLM)

Same approach as `vectorless-rag`: a single wrapper over **LiteLLM** so any provider works
by setting the matching env var. Pick the default model with `DEFAULT_MODEL` / `.env`.

| Provider | Env var | Example model |
|---|---|---|
| OpenAI | `OPENAI_API_KEY` | `openai/gpt-4o-mini` |
| Anthropic | `ANTHROPIC_API_KEY` | `anthropic/claude-3-5-haiku-latest` |
| Google | `GEMINI_API_KEY` | `gemini/gemini-2.0-flash` |
| Groq | `GROQ_API_KEY` | `groq/llama-3.3-70b-versatile` |
| Ollama (local) | _none_ | `ollama/llama3` |

---

## 🛣️ Roadmap / Stretch goals

- [ ] **On-screen text (OCR)** — many reels put claims as text overlays; sample frames and OCR them.
- [ ] **Web-search grounding** — plug Tavily/SerpAPI into the verifier for cited sources.
- [ ] **Share-sheet ingest** — open the app directly from Instagram's "Share → Reel Fact".
- [ ] **History** — store past checks per device and let users revisit them.
- [ ] **Source citations** — return clickable links the user can verify themselves.
- [ ] **Streaming progress** — switch polling to WebSocket/SSE for live stage updates.

---

## ⚖️ Disclaimers

- Built for **educational / personal** use. Respect Instagram's Terms of Service and
  copyright when downloading content.
- Automated fact-checking is **assistive, not authoritative** — always verify important
  claims against primary sources. The app surfaces reasoning and confidence precisely so
  users don't treat a verdict as the final word.
