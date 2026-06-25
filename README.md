# 🔎 Reel Fact

> Paste an **Instagram Reel** link → the app **downloads it, transcribes the audio, and runs a pipeline of LLM agents** that fact-check the claims and tell you whether it's **True / False / Misleading / Unverifiable** — and *what's wrong* with it.

Reel Fact is two pieces:

| Part | Stack | Role |
|---|---|---|
| **`backend/`** | FastAPI · LiteLLM · yt-dlp · Whisper | Download → transcribe → multi-agent fact-check |
| **`mobile/`** | Expo (React Native + TypeScript) | The Android app: paste a link, see the verdict |

📐 Full design & rationale lives in **[`PLANNING.md`](./PLANNING.md)**.

---

## ✨ What it does

```
You paste:   https://www.instagram.com/reel/abc123/
                              │
  backend ▼                   │  (async job, the app polls for progress)
  ─────────────────────────────────────────────────────────────
  download → transcribe → extract claims → verify each → synthesize
  ─────────────────────────────────────────────────────────────
                              │
You get:     ⚠️ Misleading (74%)
             "Mixes one true fact with two false claims…"
             • Claim 2 is false because…
             • Claim 3 is unsupported…
             + full transcript + per-claim breakdown
```

---

## ✅ Prerequisites

- **Python 3.11+** (tested on 3.13)
- **Node.js 18+** and **npm**
- **ffmpeg** on your PATH — used to extract audio
  - macOS: `brew install ffmpeg` · Ubuntu: `sudo apt install ffmpeg`
- **At least one LLM API key** (OpenAI / Anthropic / Google / Groq) — *or* run a local model with [Ollama](https://ollama.com) for zero keys.
- For the app: **Android Studio emulator** *or* the **Expo Go** app on a physical Android phone.

---

## 🚀 Backend — setup & run

```bash
cd reel-fact/backend

# 1) Create a virtual env + install deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2) Configure your keys
cp .env.example .env
#   then edit .env and set ONE provider key + DEFAULT_MODEL, e.g.
#   OPENAI_API_KEY=sk-...
#   DEFAULT_MODEL=openai/gpt-4o-mini

# 3) Run it (listens on 0.0.0.0:8000 so a phone/emulator can reach it)
python run.py
```

Check it's alive:

```bash
curl http://localhost:8000/health
# {"status":"ok","default_model":"openai/gpt-4o-mini","transcription_backend":"faster-whisper","ffmpeg_installed":true}
```

Interactive API docs: **http://localhost:8000/docs**

### Try it without the app (curl)

```bash
# Submit a reel → returns a job with an id
curl -X POST http://localhost:8000/api/factcheck \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.instagram.com/reel/XXXXXXXXX/"}'

# Poll the job (repeat until "status":"done")
curl http://localhost:8000/api/factcheck/1
```

> 💡 **First run is slow**: the default local `faster-whisper` model (~150 MB) downloads once. Prefer not to run Whisper locally? Set `TRANSCRIPTION_BACKEND=groq` (very fast) or `openai` in `.env`.

---

## 📱 Android app — setup & run

```bash
cd reel-fact/mobile
npm install

# Start Expo, then press "a" to open the Android emulator
npm run android
# (or `npm start` and scan the QR code with Expo Go on a physical device)
```

### Point the app at your backend

The app needs to know your backend's URL. It defaults to `http://10.0.2.2:8000`
(the Android emulator's alias for your computer). Change it anytime via
**Backend settings** on the home screen:

| Running the app on… | Use this backend URL |
|---|---|
| Android **emulator** | `http://10.0.2.2:8000` (default) |
| Physical phone (**Expo Go**) | `http://<your-computer-LAN-IP>:8000` (e.g. `http://192.168.1.20:8000`) |
| iOS simulator | `http://localhost:8000` |

> Find your LAN IP with `ipconfig getifaddr en0` (macOS) or `hostname -I` (Linux).
> Phone and computer must be on the **same Wi-Fi**. Tap **Test connection & save** to confirm.

### Build a real APK (optional)

```bash
npm install -g eas-cli
eas build -p android --profile preview   # produces an installable .apk
```

---

## ⚙️ Configuration (`backend/.env`)

| Variable | Default | Notes |
|---|---|---|
| `DEFAULT_MODEL` | `openai/gpt-4o-mini` | Any LiteLLM model id |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` / `GROQ_API_KEY` | – | Set the one matching your model |
| `TRANSCRIPTION_BACKEND` | `faster-whisper` | `faster-whisper` (local) · `openai` · `groq` |
| `WHISPER_MODEL_SIZE` | `base` | `tiny`→`large-v3` (bigger = better/slower) |
| `YTDLP_COOKIES_FILE` | – | Path to `cookies.txt` for login-gated reels |
| `MAX_REEL_DURATION_SECONDS` | `600` | Reject reels longer than this |
| `CORS_ORIGINS` | `*` | Lock down in production |

### Using a local model (no API key)

```bash
# install + run Ollama, then in .env:
DEFAULT_MODEL=ollama/llama3
```

---

## 🧠 How the fact-check works (the agents)

1. **Extract claims** — one LLM call turns the transcript + caption into a list of discrete, checkable statements (opinions/hype dropped).
2. **Verify each claim** — one call *per claim* returns `verdict · confidence · explanation · how-to-verify`. It's told to answer **`unverifiable`** rather than guess.
3. **Synthesize** — a final call combines everything into one overall verdict, a short summary, and a **"what's wrong"** list.

Each step commits progress to the DB, so the app shows a live stage:
`downloading → transcribing → extracting claims → verifying → synthesizing → done`.

---

## 🧯 Troubleshooting

| Symptom | Fix |
|---|---|
| `ffmpeg_installed: false` in `/health` | Install ffmpeg and restart the backend |
| Job fails at **downloading** | The reel may be private/region-locked. Provide `YTDLP_COOKIES_FILE`, or update yt-dlp: `pip install -U yt-dlp` |
| Job fails at **verifying/synthesizing** | Your LLM key/model is wrong or out of quota — check backend logs |
| App says *"Can't reach the backend"* | Wrong URL. Use the table above and **Test connection**; ensure same Wi-Fi |
| Transcription is slow | Use `TRANSCRIPTION_BACKEND=groq`/`openai`, or a smaller `WHISPER_MODEL_SIZE` |
| `ModuleNotFoundError: imghdr` | You're on Python 3.13 with an old litellm — `pip install -U litellm` |

---

## ⚖️ Disclaimer

For **educational / personal** use. Respect Instagram's Terms of Service and content
copyright. Automated fact-checking is **assistive, not authoritative** — always verify
important claims against primary sources.
