"""Diagnose which Gemini models the configured key can actually use.

Safe to run: prints model names and supported generation methods only. The API
key and any other secrets are never printed.

Usage:
    python -m app.ai.diagnose
"""

from __future__ import annotations

import asyncio
import sys

from app.ai.gemini import (
    AIUnavailableError,
    NoAvailableModelError,
    get_active_model,
    get_available_models,
    reset_models_cache,
)


async def main() -> int:
    from app.core.config import settings

    if not settings.gemini_api_key:
        print("GEMINI_API_KEY is not set; nothing to diagnose.", file=sys.stderr)
        return 1

    reset_models_cache()
    try:
        models = await get_available_models()
        active = await get_active_model()
    except NoAvailableModelError as exc:
        print(f"[ERROR] No compatible text-generation model: {exc}", file=sys.stderr)
        return 2
    except AIUnavailableError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    if not models:
        print("No compatible text-generating model returned by the API.")
    for model in models:
        methods = ", ".join(model["supported_generation_methods"])
        marker = "  <-- selected" if model["name"] == active else ""
        print(f"{model['name']}  supported={methods}{marker}")
    print(f"active_model={active}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))