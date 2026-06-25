"""LLM service — multi-provider via LiteLLM.

A single thin wrapper so every agent can call any provider just by setting the
matching environment variable (mirrors the `vectorless-rag` approach):

  OpenAI     → OPENAI_API_KEY      → openai/gpt-4o-mini
  Anthropic  → ANTHROPIC_API_KEY   → anthropic/claude-3-5-haiku-latest
  Google     → GEMINI_API_KEY      → gemini/gemini-2.0-flash
  Groq       → GROQ_API_KEY        → groq/llama-3.3-70b-versatile
  Ollama     → (no key, local)     → ollama/llama3

`complete_json()` is the workhorse used by the agents: it asks the model for a
JSON object and parses it defensively (models love to wrap JSON in prose or
```json fences).
"""

import json
import logging
import asyncio
import re

import litellm

from app.config import settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 4
RETRY_BASE_DELAY = 3  # seconds


def _extra_params(model: str) -> dict:
    """Provider-specific tweaks (e.g. point Ollama at the local server)."""
    params: dict = {}
    if model.startswith("ollama/"):
        params["api_base"] = "http://localhost:11434"
    return params


async def complete(
    system: str,
    user: str,
    model: str | None = None,
    max_tokens: int = 800,
    temperature: float = 0.2,
) -> str:
    """Plain text completion with retry/backoff on rate limits."""
    model = model or settings.DEFAULT_MODEL
    logger.info(f"[LLM] complete → model={model}, user_len={len(user)}")

    for attempt in range(MAX_RETRIES):
        try:
            response = await litellm.acompletion(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                **_extra_params(model),
            )
            return response.choices[0].message.content or ""
        except litellm.RateLimitError:
            delay = RETRY_BASE_DELAY * (attempt + 1)
            logger.warning(
                f"[LLM] Rate limited (attempt {attempt + 1}/{MAX_RETRIES}); retry in {delay}s"
            )
            await asyncio.sleep(delay)
        except Exception:
            logger.exception(f"[LLM] ✗ FAILED ({model})")
            raise

    raise RuntimeError(f"Rate limit exceeded after {MAX_RETRIES} retries")


def _extract_json(text: str):
    """Pull a JSON object/array out of a model response, tolerating fences/prose."""
    text = text.strip()

    # Strip ```json ... ``` fences if present.
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    # Fast path.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: grab the first {...} or [...] block.
    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from LLM response: {text[:300]}")


async def complete_json(
    system: str,
    user: str,
    model: str | None = None,
    max_tokens: int = 1200,
    temperature: float = 0.1,
):
    """Completion that returns parsed JSON.

    Tries provider-native JSON mode first; if the provider rejects the
    `response_format` argument we retry once without it and parse manually.
    """
    model = model or settings.DEFAULT_MODEL
    system_json = system + "\n\nRespond with ONLY valid JSON. No prose, no markdown fences."

    messages = [
        {"role": "system", "content": system_json},
        {"role": "user", "content": user},
    ]

    for attempt in range(MAX_RETRIES):
        try:
            try:
                response = await litellm.acompletion(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    **_extra_params(model),
                )
            except Exception:
                # Provider may not support response_format — retry plain.
                response = await litellm.acompletion(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **_extra_params(model),
                )

            raw = response.choices[0].message.content or ""
            return _extract_json(raw)

        except litellm.RateLimitError:
            delay = RETRY_BASE_DELAY * (attempt + 1)
            logger.warning(
                f"[LLM] Rate limited (attempt {attempt + 1}/{MAX_RETRIES}); retry in {delay}s"
            )
            await asyncio.sleep(delay)
        except ValueError as e:
            # JSON parse failed — give the model one more chance with a nudge.
            logger.warning(f"[LLM] JSON parse failed (attempt {attempt + 1}): {e}")
            if attempt == MAX_RETRIES - 1:
                raise
            messages.append({"role": "user", "content": "That was not valid JSON. Reply with ONLY the JSON object."})
        except Exception:
            logger.exception(f"[LLM] ✗ JSON completion FAILED ({model})")
            raise

    raise RuntimeError(f"complete_json failed after {MAX_RETRIES} retries")
