"""Gemini AI client. The API key never leaves the backend.

Prompts are constructed here; sensitive data (passwords, payment data) is never
sent. Customer names/emails are only included when the user explicitly requests
them as part of a task (e.g. follow-up message).

Model selection is dynamic and content-aware: the backend fetches the list of
models enabled for the configured API key, keeps only models that advertise
"generateContent" via supportedGenerationMethods and are intended for plain
text generation (TTS / audio / embedding / image / robotics / experimental-only
models are excluded by name), then uses the first usable one. GEMINI_MODEL can
pin a specific model; if that model is not usable for the key, the best
compatible one is used instead. No model names are hardcoded.
"""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

from app.core.config import settings
from app.core.errors import bad_request

logger = logging.getLogger("quoteflow.ai")

_GENERATE_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
_MODELS_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"

# Models whose names contain any of these are not usable for plain text
# generation (TTS, audio, embeddings, image generation, robotics, or
# experimental-only variants).
_MODEL_BLOCKLIST_SUBSTRINGS = (
    "tts",
    "audio",
    "embedding",
    "image",
    "robotics",
    "experimental",
)

# After filtering, fall back through at most this many candidate models before
# giving up. Avoids blindly retrying every model the API lists.
MAX_MODEL_PROBE_ATTEMPTS = 3

AI_UNSUPPORTED_HINT = "The AI assistant is currently unavailable. You can still create and edit quotes manually."


class AIUnavailableError(Exception):
    pass


class NoAvailableModelError(AIUnavailableError):
    """Raised when the configured API key has no model that supports generation."""


class _ModelCache:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._at: float = 0.0
        self._models: list[dict] = []
        self._active: str = ""


_model_cache = _ModelCache()


def reset_models_cache() -> None:
    """Clear the in-memory model cache (used by tests and diagnostics)."""
    _model_cache._at = 0.0
    _model_cache._models = []
    _model_cache._active = ""


def _build_payload(prompt: str) -> dict:
    return {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.6, "maxOutputTokens": 500},
    }


async def _list_models() -> list[dict]:
    if not settings.gemini_api_key:
        raise AIUnavailableError("Gemini API key is not configured.")

    headers = {"x-goog-api-key": settings.gemini_api_key}
    async with httpx.AsyncClient(timeout=settings.ai_request_timeout_seconds) as client:
        response = await client.get(_MODELS_ENDPOINT, headers=headers)

    if response.status_code in (401, 403):
        raise AIUnavailableError("The Gemini API key was rejected.")
    if response.status_code >= 500:
        raise AIUnavailableError("The Gemini API is temporarily unavailable.")
    if response.status_code != 200:
        # Never log the API key or the request; status is safe.
        logger.warning("Gemini models list failed with status=%s", response.status_code)
        raise AIUnavailableError("Could not fetch available Gemini models.")

    try:
        data = response.json()
    except ValueError:
        raise AIUnavailableError("The Gemini API returned an unexpected response.") from None

    models = data.get("models", []) if isinstance(data, dict) else []
    return [model for model in models if isinstance(model, dict)]


def _compatible_models(models: list[dict]) -> list[dict]:
    """Models that can be used for plain text generation.

    A candidate must (a) advertise "generateContent" via its
    supportedGenerationMethods field and (b) not be a TTS / audio / embedding /
    image / robotics / experimental-only model (matched on the model name). The
    full resource name (e.g. "models/gemini-3.6-flash") is preserved.
    """
    compatible = []
    for model in models:
        if not isinstance(model, dict):
            continue
        if "generateContent" not in (model.get("supportedGenerationMethods") or []):
            continue
        lowered = (model.get("name") or "").lower()
        if any(token in lowered for token in _MODEL_BLOCKLIST_SUBSTRINGS):
            continue
        compatible.append(model)
    return compatible


def _pick_model(models: list[dict]) -> str:
    usable = _compatible_models(models)
    if not usable:
        raise NoAvailableModelError(
            "No text-capable Gemini model available for this API key supports "
            "content generation. TTS, audio, embedding, image, robotics and "
            "experimental-only models are excluded, and no other model with "
            "'generateContent' is enabled for the key."
        )
    configured = settings.gemini_model.strip()
    if configured:
        exact = [
            model
            for model in usable
            if model.get("name") in (configured, f"models/{configured}")
        ]
        if exact:
            return exact[0]["name"]
        logger.warning(
            "GEMINI_MODEL=%r is not usable for this API key; using %r instead",
            configured,
            usable[0]["name"],
        )
    return usable[0]["name"]


def _methods_for(name: str) -> list[str]:
    """Safe metadata: supported generation methods for a cached model name."""
    for model in _model_cache._models:
        if model.get("name") == name:
            return list(model.get("supportedGenerationMethods") or [])
    return []


def _remark_active(name: str) -> None:
    """Remember the working model and log safe metadata (name + methods)."""
    _model_cache._active = name
    _model_cache._at = time.monotonic()
    logger.info(
        "AI_MODEL_SELECTED model=%s supported_generation_methods=%s",
        name,
        _methods_for(name),
    )


async def _refresh_cache() -> str:
    models = await _list_models()
    active = _pick_model(models)
    _model_cache._models = models
    _model_cache._active = active
    _model_cache._at = time.monotonic()
    logger.info(
        "AI_MODEL_SELECTED model=%s supported_generation_methods=%s",
        active,
        _methods_for(active),
    )
    return active


async def _selected_model() -> str:
    if not settings.gemini_api_key:
        raise AIUnavailableError("Gemini API key is not configured.")
    async with _model_cache._lock:
        now = time.monotonic()
        ttl = max(1, settings.ai_models_cache_ttl_seconds)
        if not _model_cache._active or now - _model_cache._at > ttl:
            return await _refresh_cache()
        return _model_cache._active


def _safe_model_metadata(models: list[dict]) -> list[dict]:
    return [
        {
            "name": model.get("name", ""),
            "supported_generation_methods": list(
                model.get("supportedGenerationMethods") or []
            ),
        }
        for model in models
    ]


async def get_available_models() -> list[dict]:
    """Safe metadata (name + generation methods) for the compatible models."""
    await _selected_model()  # refreshes/validates the cache; raises if unavailable
    return _safe_model_metadata(_compatible_models(_model_cache._models))


async def get_active_model() -> str:
    """Return the selected (pinned or first available) generation model name."""
    return await _selected_model()


async def _generate_one(prompt: str, model: str) -> tuple[bool, str]:
    """Return (True, text) on success or (False, hint) when the model is unusable.

    A model is "unusable" when the API explicitly rejects publication to it:
    404 (deprecated / not enabled for this key) or 400 (e.g. response modality
    unsupported). Hard errors (rate limit, provider outage) raise instead.
    """
    # The models list names models like "models/gemini-3.6-flash"; the
    # generateContent endpoint only accepts the bare slug "gemini-3.6-flash",
    # so the leading "models/" is removed exactly once.
    url = _GENERATE_ENDPOINT.format(model=model.removeprefix("models/"))
    headers = {"x-goog-api-key": settings.gemini_api_key}  # key only in header, never logged
    async with httpx.AsyncClient(timeout=settings.ai_request_timeout_seconds) as client:
        response = await client.post(url, headers=headers, json=_build_payload(prompt))
    # Safe metadata only: full model name, supported methods, and HTTP status.
    # Never log the API key, the URL query, or the request body.
    logger.info(
        "AI_MODEL_REQUEST model=%s supported_generation_methods=%s status=%s",
        model,
        _methods_for(model),
        response.status_code,
    )
    if response.status_code == 429:
        raise AIUnavailableError("AI provider rate limit hit.")
    if response.status_code >= 500:
        raise AIUnavailableError("AI provider returned an error.")
    if response.status_code in (400, 404):
        # Listed but not actually usable for text generation (deprecated model,
        # unsupported modalities, etc.). Return the body hint so the caller can
        # fall back to the next compatible candidate.
        return False, (response.text or "")[:200]
    if response.status_code != 200:
        logger.warning(
            "Gemini request failed with status=%s body=%s",
            response.status_code,
            (response.text or "")[:400],
        )
        raise AIUnavailableError("AI provider request failed.")

    data = response.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, TypeError):
        raise AIUnavailableError("AI provider returned an unexpected response.") from None
    if not text:
        raise AIUnavailableError("AI provider returned an empty response.")
    return True, text


async def _candidate_models() -> list[str]:
    """Names of all compatible text-generation models, in list order.

    No model names are hardcoded; the filter is based purely on the model's own
    supportedGenerationMethods field and the non-text-name blocklist.
    """
    if not _model_cache._models:
        await _refresh_cache()
    return [model["name"] for model in _compatible_models(_model_cache._models)]


async def _call_gemini(prompt: str) -> str:
    if not settings.gemini_api_key:
        raise AIUnavailableError("Gemini API key is not configured.")

    ordered = await _candidate_models()
    if not ordered:
        raise NoAvailableModelError(
            "No Gemini model available for this API key supports text "
            "content generation. TTS, audio, embedding, image, robotics and "
            "experimental-only models are excluded, and no other model with "
            "'generateContent' is enabled for the key."
        )

    # Prefer the last known-working model so we do not re-probe deprecated
    # models on every request, then cap the number of fallback attempts so we
    # never blindly retry every listed model.
    active = _model_cache._active
    if active and active in ordered:
        ordered = [active] + [m for m in ordered if m != active]
    attempts = ordered[:MAX_MODEL_PROBE_ATTEMPTS]

    hints: list[str] = []
    for model in attempts:
        ok, result = await _generate_one(prompt, model)
        if ok:
            if model != _model_cache._active:
                _remark_active(model)
            return result
        logger.debug("Gemini model %s unavailable for text generation", model)
        if result:
            hints.append(result)

    hint = hints[-1] if hints else ""
    raise NoAvailableModelError(
        "No Gemini model available for this API key is currently usable for "
        f"text content generation.{(' ' + hint) if hint else ''}"
    )


async def generate_ai_text(
    kind: str,
    *,
    service_name: str = "",
    notes: str = "",
    tone: str = "",
    text: str = "",
    business_name: str = "",
    customer_name: str = "",
    summary: str = "",
    quote_number: str = "",
    context: str = "",
) -> str:
    if kind == "service_description":
        prompt = (
            f"Write a clear, professional service description in English for the cleaning service "
            f"named '{service_name}'. Incorporate the notes below when relevant. Keep the tone "
            f"concise and do not invent prices. Output only the description.\n"
            f"Service: {service_name}\nNotes: {notes if notes else 'none'}"
        )
    elif kind == "rewrite":
        prompt = (
            f"Rewrite the following rough notes into a professional, polite description in English. "
            f"Tone: {tone or 'professional'}. Do not invent prices. Output only the rewritten text.\n"
            f"Text: {text}"
        )
    elif kind == "introduction":
        prompt = (
            "Write a short, polite quote introduction in English addressed to the customer. "
            "Do not include prices or technical claims beyond the summary provided. "
            f"Business: {business_name or 'our business'}. Customer: {customer_name or 'our customer'}.\n"
            f"Summary: {(summary or 'cleaning services for the agreed scope')}"
        )
    elif kind == "follow_up":
        prompt = (
            "Write a short, polite follow-up message in English to a customer about a quotation. "
            f"Quote number: {quote_number or '(our quote)'}. Customer: {customer_name or 'our customer'}.\n"
            f"Context: {(context or 'no additional context')}"
        )
    else:
        raise bad_request("Unknown AI task kind.")

    logger.info("AI_REQUEST kind=%s len=%d", kind, len(prompt))
    return await _call_gemini(prompt)