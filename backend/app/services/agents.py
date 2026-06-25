"""Fact-check agents — the multi-step LLM reasoning pipeline.

Three cooperating "agents", each a focused LLM call:

  1. extract_claims  — pull discrete, checkable factual claims out of the reel.
  2. verify_claim    — judge a single claim (true/false/misleading/unverifiable).
  3. synthesize      — combine per-claim judgments into one overall verdict.

Keeping them separate (rather than one giant prompt) makes each step easier to
reason about, lets us verify claims in parallel, and produces structured output
the Android app can render directly.
"""

import asyncio
import logging

from app.services.llm import complete_json

logger = logging.getLogger(__name__)

VALID_VERDICTS = {"true", "false", "misleading", "unverifiable"}

# How many claims to verify concurrently (avoid hammering rate limits).
VERIFY_CONCURRENCY = 3
# Safety cap so a rambling reel doesn't spawn dozens of LLM calls.
MAX_CLAIMS = 8


# ── Agent 1: claim extraction ─────────────────────────────────────────────
CLAIM_SYSTEM = """You are a meticulous fact-checking assistant.
Read the transcript and caption of a short social-media video (an Instagram Reel)
and extract the DISTINCT, checkable factual claims it makes.

Rules:
- A claim must be a statement of fact that could in principle be verified
  (numbers, cause/effect, historical/scientific/medical/financial assertions, etc.).
- Ignore opinions, jokes, calls-to-action, greetings, and vague hype.
- Rephrase each claim into a clear, self-contained sentence.
- Merge duplicates. Return at most 8 of the most important claims.

Output JSON: {"claims": ["claim 1", "claim 2", ...]}
If there are no checkable factual claims, return {"claims": []}."""


async def extract_claims(transcript: str, caption: str | None, model: str | None) -> list[str]:
    context = f"TRANSCRIPT:\n{transcript or '(no speech detected)'}\n\nCAPTION:\n{caption or '(none)'}"
    logger.info("[Agent] Extracting claims...")
    data = await complete_json(CLAIM_SYSTEM, context, model=model, max_tokens=700)

    claims = data.get("claims", []) if isinstance(data, dict) else []
    # Normalize: strings only, stripped, de-duplicated, capped.
    seen, cleaned = set(), []
    for c in claims:
        if not isinstance(c, str):
            continue
        c = c.strip()
        key = c.lower()
        if c and key not in seen:
            seen.add(key)
            cleaned.append(c)
        if len(cleaned) >= MAX_CLAIMS:
            break
    logger.info(f"[Agent] ✓ Extracted {len(cleaned)} claim(s)")
    return cleaned


# ── Agent 2: per-claim verification ───────────────────────────────────────
VERIFY_SYSTEM = """You are a rigorous, neutral fact-checker.
Assess the single CLAIM below using well-established knowledge.

Choose exactly one verdict:
- "true"          — well-supported by evidence and broadly accepted.
- "false"         — contradicted by evidence.
- "misleading"    — contains a kernel of truth but is framed in a deceptive,
                    cherry-picked, or out-of-context way.
- "unverifiable"  — cannot be confidently judged (too vague, lacks context,
                    depends on private/unknown data, or is genuinely contested).

Be honest about uncertainty: prefer "unverifiable" over guessing.
Do NOT invent specific statistics or sources you are not sure about.

Output JSON:
{
  "verdict": "true|false|misleading|unverifiable",
  "confidence": 0.0-1.0,
  "explanation": "2-4 sentences of plain-language reasoning",
  "what_to_check": "a concrete way a person could verify this themselves"
}"""


def _coerce_claim_result(claim: str, data: dict) -> dict:
    verdict = str(data.get("verdict", "unverifiable")).lower().strip()
    if verdict not in VALID_VERDICTS:
        verdict = "unverifiable"
    try:
        confidence = float(data.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))
    return {
        "claim": claim,
        "verdict": verdict,
        "confidence": round(confidence, 2),
        "explanation": str(data.get("explanation", "")).strip(),
        "what_to_check": str(data.get("what_to_check", "")).strip(),
    }


async def verify_claim(claim: str, context: str, model: str | None) -> dict:
    user = f"CLAIM: {claim}\n\nFor context, this came from a reel whose overall content was:\n{context[:1500]}"
    try:
        data = await complete_json(VERIFY_SYSTEM, user, model=model, max_tokens=500)
    except Exception:  # noqa: BLE001 — one bad claim shouldn't kill the job
        logger.exception(f"[Agent] verify failed for claim: {claim[:60]}")
        return _coerce_claim_result(
            claim,
            {"verdict": "unverifiable", "confidence": 0.0,
             "explanation": "The verifier could not evaluate this claim due to an error.",
             "what_to_check": "Try re-running the check."},
        )
    return _coerce_claim_result(claim, data if isinstance(data, dict) else {})


async def verify_claims(claims: list[str], context: str, model: str | None) -> list[dict]:
    """Verify all claims with bounded concurrency, preserving order."""
    logger.info(f"[Agent] Verifying {len(claims)} claim(s) (concurrency={VERIFY_CONCURRENCY})...")
    semaphore = asyncio.Semaphore(VERIFY_CONCURRENCY)

    async def _bounded(claim: str) -> dict:
        async with semaphore:
            return await verify_claim(claim, context, model)

    results = await asyncio.gather(*[_bounded(c) for c in claims])
    logger.info("[Agent] ✓ Verification complete")
    return list(results)


# ── Agent 3: synthesis ────────────────────────────────────────────────────
SYNTHESIS_SYSTEM = """You are the lead editor of a fact-checking team.
You are given the per-claim verdicts for a social-media reel. Produce a single
overall assessment of the reel for a general audience.

Overall verdict guidance:
- "true"          — claims are accurate; nothing materially misleading.
- "false"         — central message rests on false claims.
- "misleading"    — mixes true and false/decontextualized claims, leaving a false impression.
- "unverifiable"  — not enough checkable content to judge.

Output JSON:
{
  "verdict": "true|false|misleading|unverifiable",
  "confidence": 0.0-1.0,
  "summary": "3-5 sentence plain-language verdict a viewer can quickly read",
  "whats_wrong": ["specific problem 1", "specific problem 2"]
}
"whats_wrong" should list the most important inaccurate or misleading points
(empty list if the reel is accurate)."""


def _fallback_overall(claim_results: list[dict]) -> dict:
    """Deterministic verdict if the synthesis LLM call fails — keeps the job usable."""
    counts = dict.fromkeys(VALID_VERDICTS, 0)
    for r in claim_results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    if counts["false"] or counts["misleading"]:
        verdict = "misleading" if counts["true"] else "false"
    elif counts["true"]:
        verdict = "true"
    else:
        verdict = "unverifiable"
    whats_wrong = [
        f"{r['claim']} — {r['explanation']}"
        for r in claim_results
        if r["verdict"] in ("false", "misleading")
    ]
    return {
        "verdict": verdict,
        "confidence": 0.4,
        "summary": "Automated summary (synthesis model unavailable). See individual claims below.",
        "whats_wrong": whats_wrong,
    }


async def synthesize(
    transcript: str,
    caption: str | None,
    claim_results: list[dict],
    model: str | None,
) -> dict:
    if not claim_results:
        return {
            "verdict": "unverifiable",
            "confidence": 0.0,
            "summary": "This reel contains no specific factual claims that can be checked "
                       "(it may be opinion, entertainment, or have no spoken content).",
            "whats_wrong": [],
        }

    logger.info("[Agent] Synthesizing overall verdict...")
    claims_block = "\n".join(
        f"- CLAIM: {r['claim']}\n  VERDICT: {r['verdict']} (confidence {r['confidence']})\n  WHY: {r['explanation']}"
        for r in claim_results
    )
    user = (
        f"REEL CAPTION: {caption or '(none)'}\n\n"
        f"REEL TRANSCRIPT (excerpt): {(transcript or '(no speech)')[:1200]}\n\n"
        f"PER-CLAIM RESULTS:\n{claims_block}"
    )

    try:
        data = await complete_json(SYNTHESIS_SYSTEM, user, model=model, max_tokens=700)
    except Exception:  # noqa: BLE001
        logger.exception("[Agent] synthesis failed; using deterministic fallback")
        return _fallback_overall(claim_results)

    verdict = str(data.get("verdict", "unverifiable")).lower().strip()
    if verdict not in VALID_VERDICTS:
        verdict = "unverifiable"
    try:
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
    except (TypeError, ValueError):
        confidence = 0.5
    whats_wrong = [str(x).strip() for x in data.get("whats_wrong", []) if str(x).strip()]

    return {
        "verdict": verdict,
        "confidence": round(confidence, 2),
        "summary": str(data.get("summary", "")).strip(),
        "whats_wrong": whats_wrong,
    }
