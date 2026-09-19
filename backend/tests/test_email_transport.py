import pytest


@pytest.mark.asyncio
async def test_resend_transport_uses_https_api(monkeypatch):
    from app.core.config import settings
    from app.services import email

    calls = []

    class FakeResponse:
        status_code = 200
        is_error = False
        text = '{"id":"email-test"}'

    class FakeClient:
        def __init__(self, *args, **kwargs):
            calls.append(("client", kwargs))

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return FakeResponse()

    monkeypatch.setattr(email.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(settings, "resend_api_key", "re_test_key")
    monkeypatch.setattr(settings, "resend_api_url", "https://api.resend.com/emails")
    monkeypatch.setattr(settings, "email_from", "onboarding@example.com")

    await email.send_email(
        "user@example.com",
        "Verify your QuoteFlow AI email",
        "verify-link",
        "<p>verify-link</p>",
    )

    url, kwargs = calls[1]
    assert url == "https://api.resend.com/emails"
    assert kwargs["headers"]["Authorization"] == "Bearer re_test_key"
    assert kwargs["json"]["from"] == "onboarding@example.com"
    assert kwargs["json"]["to"] == ["user@example.com"]
    assert kwargs["json"]["subject"] == "Verify your QuoteFlow AI email"
    assert kwargs["json"]["text"] == "verify-link"
    assert kwargs["json"]["html"] == "<p>verify-link</p>"


@pytest.mark.asyncio
async def test_resend_transport_fails_clearly_when_not_configured(monkeypatch):
    from app.core.config import settings
    from app.services import email

    monkeypatch.setattr(settings, "resend_api_key", "")

    with pytest.raises(RuntimeError, match="RESEND_API_KEY is not configured"):
        await email.send_email("user@example.com", "Subject", "Body")
