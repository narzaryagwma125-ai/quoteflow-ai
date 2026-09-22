import pytest

@pytest.mark.asyncio
async def test_brevo_smtp_transport(monkeypatch):
    from app.core.config import settings
    from app.services import email
    calls = []
    class FakeSMTP:
        def __init__(self, *args, **kwargs): calls.append(("init", args, kwargs))
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def ehlo(self): calls.append(("ehlo",))
        def starttls(self): calls.append(("starttls",))
        def login(self, user, password): calls.append(("login", user, password))
        def send_message(self, msg): calls.append(("send", msg))
    monkeypatch.setattr(email.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(settings, "smtp_username", "smtp-user")
    monkeypatch.setattr(settings, "smtp_password", "smtp-pass")
    monkeypatch.setattr(settings, "email_from", "hello@quoteflowai.in")
    await email.send_email("user@example.com","Verify","body","<p>body</p>")
    assert calls[0][1] == ("smtp-relay.brevo.com", 587)
    assert calls[3][0] == "login"
    msg = calls[4][1]
    assert msg["From"] == "hello@quoteflowai.in"
    assert msg["To"] == "user@example.com"
