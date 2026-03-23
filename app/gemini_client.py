"""
Gemini Vision API client.

Wraps google-genai to send two images + a structured prompt
and parse the JSON response. Includes retry logic with exponential
backoff and configurable timeouts.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Callable, Optional, TypeVar

from google import genai
from google.genai import types

from app.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

RETRYABLE_ERRORS = (
    ConnectionError,
    TimeoutError,
    asyncio.TimeoutError,
)


def _get_client() -> genai.Client:
    settings = get_settings()
    return genai.Client(api_key=settings.gemini_api_key)


def _strip_fences(text: str) -> str:
    """Remove markdown code fences if the model wraps its JSON."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _is_retryable(exc: Exception) -> bool:
    """Determine if an exception warrants a retry."""
    if isinstance(exc, RETRYABLE_ERRORS):
        return True
    exc_str = str(exc).lower()
    return any(keyword in exc_str for keyword in (
        "rate limit", "quota", "503", "502", "504", "timeout", "unavailable"
    ))


async def retry_with_backoff(
    func: Callable[[], T],
    max_retries: Optional[int] = None,
    base_delay: Optional[float] = None,
    max_delay: Optional[float] = None,
) -> T:
    """
    Execute an async function with exponential backoff retry.
    
    Retries on transient errors (rate limits, timeouts, server errors).
    """
    settings = get_settings()
    max_retries = max_retries if max_retries is not None else settings.max_retries
    base_delay = base_delay if base_delay is not None else settings.retry_base_delay
    max_delay = max_delay if max_delay is not None else settings.retry_max_delay

    last_exc: Optional[Exception] = None
    
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as exc:
            last_exc = exc
            if not _is_retryable(exc) or attempt >= max_retries - 1:
                raise
            
            delay = min(base_delay * (2 ** attempt), max_delay)
            logger.warning(
                "Attempt %d/%d failed: %s. Retrying in %.1fs...",
                attempt + 1, max_retries, exc, delay
            )
            await asyncio.sleep(delay)
    
    raise last_exc  # type: ignore


async def call_gemini_vision(
    *,
    system_prompt: str,
    user_prompt: str,
    figma_png: bytes,
    web_png: bytes,
    model_override: str | None = None,
    temperature_override: float | None = None,
    timeout_override: float | None = None,
    response_schema: Optional[types.Schema] = None,
) -> dict[str, Any]:
    """
    Send two images + prompt to Gemini and return parsed JSON.

    Features:
    - Retry with exponential backoff on transient failures
    - Configurable timeout per request
    - Optional response schema for structured output
    
    Raises ValueError if the response is not valid JSON.
    """
    settings = get_settings()
    client = _get_client()

    model = model_override or settings.gemini_model
    temperature = temperature_override or settings.gemini_temperature
    timeout = timeout_override or settings.gemini_timeout

    contents = [
        types.Part.from_text(text="IMAGE 1 — FIGMA DESIGN:"),
        types.Part.from_bytes(data=figma_png, mime_type="image/png"),
        types.Part.from_text(text="IMAGE 2 — LIVE WEBPAGE:"),
        types.Part.from_bytes(data=web_png, mime_type="image/png"),
        types.Part.from_text(text=user_prompt),
    ]

    config_kwargs: dict[str, Any] = {
        "system_instruction": system_prompt,
        "temperature": temperature,
        "response_mime_type": "application/json",
    }
    
    if response_schema is not None:
        config_kwargs["response_schema"] = response_schema
    
    config = types.GenerateContentConfig(**config_kwargs)

    logger.info("Calling Gemini model=%s temp=%.2f timeout=%.0fs", model, temperature, timeout)

    async def _make_request() -> str:
        """Inner function for retry wrapper."""
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.models.generate_content,
                model=model,
                contents=contents,
                config=config,
            ),
            timeout=timeout,
        )
        
        raw_text = response.text
        if not raw_text:
            raise ValueError("Gemini returned an empty response")
        return raw_text

    raw_text = await retry_with_backoff(_make_request)
    cleaned = _strip_fences(raw_text)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse Gemini JSON:\n%s", cleaned[:500])
        raise ValueError(f"Gemini returned invalid JSON: {exc}") from exc
