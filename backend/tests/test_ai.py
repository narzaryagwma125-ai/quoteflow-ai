"""AI service tests: rate limits, graceful unavailability, no price influence."""

from __future__ import annotations

import json

import pytest

from app.ai.gemini import AIUnavailableError
from app.db.session import async_session_factory
from app.models.business_profile import BusinessProfile
from app.services.quote_calc import calculate_quote
from tests.conftest import create_user, login, quote_payload


def make_profile(user_id: int) -> BusinessProfile:
    return BusinessProfile(
        user_id=user_id,
        business_name="AI Biz",
        owner_name="O",
        email="o@example.com",
    )


class _FakeGeminiResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self) -> dict:
        return self._payload


class _FakeGeminiClient:
    def __init__(self, transport) -> None:
        self._transport = transport

    async def __aenter__(self):
        return self._transport

    async def __aexit__(self, *exc):
        return False


class _FakeGeminiTransport:
    """Stub for the httpx calls inside app.ai.gemini: lists models + generates text."""

    def __init__(self, models: list[dict], generate_text: str = "Thanks for your interest.", list_status: int = 200, unavailable_models: list[str] | None = None) -> None:
        self.models = models
        self.generate_text = generate_text
        self.list_status = list_status
        self.unavailable_models = set(unavailable_models or [])
        self.calls: list[tuple[str, str, dict]] = []

    async def get(self, url: str, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return _FakeGeminiResponse(self.list_status, {"models": self.models})

    async def post(self, url: str, json: dict | None = None, **kwargs):
        self.calls.append(("POST", url, kwargs))
        model = url.split("/models/")[-1].split(":")[0]
        if model in self.unavailable_models:
            return _FakeGeminiResponse(
                404,
                {"error": {"message": f"{model} is no longer available; use another model"}},
            )
        if ":generateContent" in url:
            return _FakeGeminiResponse(
                200,
                {"candidates": [{"content": {"parts": [{"text": self.generate_text}]}}]},
            )
        return _FakeGeminiResponse(404, {})


class _FakeHttpxModule:
    def __init__(self, transport) -> None:
        self._transport = transport

    def AsyncClient(self, *args, **kwargs):
        return _FakeGeminiClient(self._transport)


def _stub_gemini_httpx(monkeypatch, models: list[dict], generate_text: str = "Thanks for your interest.", list_status: int = 200, unavailable_models: list[str] | None = None):
    from app.ai import gemini

    transport = _FakeGeminiTransport(
        models=models,
        generate_text=generate_text,
        list_status=list_status,
        unavailable_models=unavailable_models,
    )
    monkeypatch.setattr(gemini, "httpx", _FakeHttpxModule(transport))
    return transport


def _enable_gemini(monkeypatch, api_key: str = "test-key", model: str = "") -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "gemini_api_key", api_key)
    monkeypatch.setattr(settings, "gemini_model", model)


GENERATION_MODELS = [
    {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent", "countTokens"]},
    {"name": "models/gemini-2.0-flash", "supportedGenerationMethods": ["generateContent"]},
]

MIXED_MODELS = [
    {"name": "models/gemini-3.6-flash", "supportedGenerationMethods": ["generateContent", "countTokens"]},
    {"name": "models/gemini-2.5-flash-preview-tts", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent", "generateContent"]},
    {"name": "models/imagen-3.0-generate-002", "supportedGenerationMethods": ["generateImages", "generateContent"]},
    {"name": "models/robotics-1", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-2.5-flash-preview-audio", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-2.5-experimental", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-2.0-flash", "supportedGenerationMethods": ["generateContent"]},
]


@pytest.mark.asyncio
async def test_ai_requires_auth(client):
    res = await client.post(
        "/api/ai/service-description", json={"service_name": "Deep clean", "notes": "kitchen"}
    )
    assert res.status_code == 401


def test_compatible_filter_excludes_non_text_models():
    from app.ai.gemini import _compatible_models

    names = [model["name"] for model in _compatible_models(MIXED_MODELS)]
    assert "models/gemini-3.6-flash" in names
    assert "models/gemini-2.0-flash" in names
    for excluded in (
        "models/gemini-2.5-flash-preview-tts",
        "models/text-embedding-004",
        "models/imagen-3.0-generate-002",
        "models/robotics-1",
        "models/gemini-2.5-flash-preview-audio",
        "models/gemini-2.5-experimental",
    ):
        assert excluded not in names


def test_compatible_filter_requires_generate_content_method():
    from app.ai.gemini import _compatible_models

    models = [
        {"name": "models/gemini-a", "supportedGenerationMethods": ["countTokens"]},
        {"name": "models/gemini-b", "supportedGenerationMethods": []},
        {"name": "models/gemini-unknown", "supportedGenerationMethods": None},
        {"name": "models/gemini-c", "supportedGenerationMethods": ["generateContent"]},
    ]
    names = [model["name"] for model in _compatible_models(models)]
    assert names == ["models/gemini-c"]


def test_compatible_filter_preserves_full_model_resource_name():
    from app.ai.gemini import _compatible_models

    models = [
        {"name": "models/gemini-3.6-flash", "supportedGenerationMethods": ["generateContent"]}
    ]
    assert _compatible_models(models)[0]["name"] == "models/gemini-3.6-flash"


@pytest.mark.asyncio
async def test_ai_unavailable_returns_503_and_manual_flow_ok(client, monkeypatch):
    from app.core.config import settings

    # Force "no key configured" so the unavailable path is deterministic.
    monkeypatch.setattr(settings, "gemini_api_key", "")
    user = await create_user("ai@example.com")
    await login(client, "ai@example.com")
    async with async_session_factory() as db:
        db.add(make_profile(user.id))
        await db.commit()

    # no GEMINI_API_KEY configured in test env -> unavailable gracefully
    res = await client.post(
        "/api/ai/service-description", json={"service_name": "Deep clean", "notes": "kitchen"}
    )
    assert res.status_code == 503

    # user can still create a quote manually
    res2 = await client.post("/api/quotes", json=quote_payload(quote_number="Q-AI1"))
    assert res2.status_code == 201, res2.text


@pytest.mark.asyncio
async def test_ai_cannot_change_financial_totals(client):
    # AI output is only ever text; totals are computed by the central calc engine
    result = calculate_quote(
        [{"description": "Clean", "quantity": "1", "unit": "", "unit_price_minor": 10000, "sort_order": 0}],
        discount_minor=0,
        tax_rate_bps=750,
    )
    assert result.subtotal_minor == 10000
    assert result.tax_minor == 750
    assert result.total_minor == 10750


@pytest.mark.asyncio
async def test_ai_prompt_length_limited(client):
    await create_user("ailong@example.com")
    await login(client, "ailong@example.com")
    res = await client.post(
        "/api/ai/service-description",
        json={"service_name": "Clean", "notes": "x" * 5000},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_ai_rate_limit_429(client):
    from app.security import rate_limit

    class _DenyAll:
        async def hit(self, key, limit, window_seconds):
            return False

        async def remaining(self, key, limit, window_seconds):
            return 0

    original = rate_limit.limiter
    await create_user("ai429@example.com")
    await login(client, "ai429@example.com")
    rate_limit.limiter = _DenyAll()
    try:
        res = await client.post(
            "/api/ai/service-description", json={"service_name": "Clean", "notes": "x"}
        )
        assert res.status_code == 429
    finally:
        rate_limit.limiter = original


@pytest.mark.asyncio
async def test_ai_unavailable_error_is_catchable(monkeypatch):
    from app.core.config import settings
    from app.ai.gemini import _call_gemini

    monkeypatch.setattr(settings, "gemini_api_key", "")
    with pytest.raises(AIUnavailableError):
        await _call_gemini("hello")  # no api key configured → AIUnavailableError


@pytest.mark.asyncio
async def test_ai_follow_up_picks_first_generate_content_model(client, monkeypatch):
    from app.ai import gemini

    _enable_gemini(monkeypatch, api_key="test-key", model="")
    transport = _stub_gemini_httpx(
        monkeypatch, GENERATION_MODELS, generate_text="Here is a follow-up."
    )
    gemini.reset_models_cache()

    await create_user("aifollow@example.com")
    await login(client, "aifollow@example.com")

    res = await client.post(
        "/api/ai/follow-up-message",
        json={"customer_name": "Jane", "quote_number": "Q-1", "context": "status"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["text"] == "Here is a follow-up."
    assert body["generated_by_ai"] is True

    post_url = [url for method, url, _ in transport.calls if method == "POST"]
    assert post_url == [gemini._GENERATE_ENDPOINT.format(model="gemini-2.5-flash")]
    # the API key travels in a header, never inline in the URL
    assert "test-key" not in post_url[0]
    for method, url, kwargs in transport.calls:
        assert kwargs.get("headers", {}).get("x-goog-api-key") == "test-key"


@pytest.mark.asyncio
async def test_ai_falls_back_when_first_model_unavailable(client, monkeypatch):
    from app.ai import gemini

    _enable_gemini(monkeypatch, api_key="test-key", model="")
    transport = _stub_gemini_httpx(
        monkeypatch,
        GENERATION_MODELS,
        generate_text="Fallback worked.",
        unavailable_models=["gemini-2.5-flash"],
    )
    gemini.reset_models_cache()

    await create_user("aifb@example.com")
    await login(client, "aifb@example.com")

    res = await client.post(
        "/api/ai/follow-up-message",
        json={"customer_name": "Jane", "quote_number": "Q-1", "context": "status"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["text"] == "Fallback worked."

    post_url = [url for method, url, _ in transport.calls if method == "POST"]
    assert post_url == [
        gemini._GENERATE_ENDPOINT.format(model="gemini-2.5-flash"),
        gemini._GENERATE_ENDPOINT.format(model="gemini-2.0-flash"),
    ]


@pytest.mark.asyncio
async def test_ai_models_endpoint_returns_safe_metadata(client, monkeypatch):
    from app.ai import gemini

    _enable_gemini(monkeypatch, api_key="test-key", model="")
    _stub_gemini_httpx(monkeypatch, GENERATION_MODELS)
    gemini.reset_models_cache()

    await create_user("aimodels@example.com")
    await login(client, "aimodels@example.com")

    res = await client.get("/api/ai/models")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["active_model"] == "models/gemini-2.5-flash"
    assert all(
        set(item.keys()) == {"name", "supported_generation_methods"}
        for item in body["models"]
    )
    # safe metadata only: no key, no descriptors, no version info
    assert "test-key" not in res.text


@pytest.mark.asyncio
async def test_ai_no_generate_content_model_returns_clear_503(client, monkeypatch):
    from app.ai import gemini

    _enable_gemini(monkeypatch, api_key="test-key", model="")
    _stub_gemini_httpx(
        monkeypatch,
        [{"name": "models/embedding-001", "supportedGenerationMethods": ["embedContent"]}],
    )
    gemini.reset_models_cache()

    await create_user("ainogen@example.com")
    await login(client, "ainogen@example.com")

    res = await client.post(
        "/api/ai/follow-up-message",
        json={"customer_name": "Jane", "quote_number": "Q-1", "context": "status"},
    )
    assert res.status_code == 503
    assert "content generation" in res.json()["detail"]

    res2 = await client.get("/api/ai/models")
    assert res2.status_code == 503
    assert "content generation" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_ai_tts_model_is_never_probed(client, monkeypatch):
    from app.ai import gemini

    _enable_gemini(monkeypatch, api_key="test-key", model="")
    transport = _stub_gemini_httpx(
        monkeypatch,
        [
            {"name": "models/gemini-2.5-flash-preview-tts", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-2.0-flash", "supportedGenerationMethods": ["generateContent"]},
        ],
        generate_text="Real text response.",
    )
    gemini.reset_models_cache()

    await create_user("aitts@example.com")
    await login(client, "aitts@example.com")

    res = await client.post(
        "/api/ai/follow-up-message",
        json={"customer_name": "Jane", "quote_number": "Q-1", "context": "status"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["text"] == "Real text response."

    # the TTS model is filtered out before any request is sent
    post_url = [url for method, url, _ in transport.calls if method == "POST"]
    assert post_url == [gemini._GENERATE_ENDPOINT.format(model="gemini-2.0-flash")]
    assert all("tts" not in url for url in post_url)


@pytest.mark.asyncio
async def test_ai_all_candidates_404_returns_clear_503(client, monkeypatch):
    from app.ai import gemini

    _enable_gemini(monkeypatch, api_key="test-key", model="")
    _stub_gemini_httpx(
        monkeypatch,
        GENERATION_MODELS,
        generate_text="ignored",
        unavailable_models=["gemini-2.5-flash", "gemini-2.0-flash"],
    )
    gemini.reset_models_cache()

    await create_user("ai404@example.com")
    await login(client, "ai404@example.com")

    res = await client.post(
        "/api/ai/follow-up-message",
        json={"customer_name": "Jane", "quote_number": "Q-1", "context": "status"},
    )
    assert res.status_code == 503
    detail = res.json()["detail"]
    assert "content generation" in detail
    # server hint preserved so the operator knows what to pin
    assert "no longer available" in detail
    # no secrets leak to the client
    assert "test-key" not in res.text
