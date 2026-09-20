"""Business profile + logo upload tests."""

from __future__ import annotations

import io

import pytest

from app.uploads.store import ALLOWED_TYPES, validate_logo
from tests.conftest import create_user, login


@pytest.mark.asyncio
async def test_profile_requires_auth(client):
    res = await client.get("/api/business-profile")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_create_profile_and_upsert_tax_rate(client):
    await create_user("biz@example.com")
    await login(client, "biz@example.com")

    res = await client.put(
        "/api/business-profile",
        json={
            "business_name": "Sparkle Cleaning",
            "owner_name": "Alex",
            "email": "alex@example.com",
            "country": "CA",
            "currency": "CAD",
            "tax_rate": "8.5",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["business_name"] == "Sparkle Cleaning"
    assert body["tax_rate_percent"] == "8.5"
    assert body["tax_rate_unconfigured"] is False

    res2 = await client.put("/api/business-profile", json={"tax_rate": "7.25"})
    assert res2.status_code == 200
    assert res2.json()["tax_rate_percent"] == "7.25"


@pytest.mark.asyncio
async def test_profile_default_currency_inr_and_tax_zero(client):
    await create_user("biz2@example.com")
    await login(client, "biz2@example.com")
    res = await client.put(
        "/api/business-profile",
        json={"business_name": "B", "owner_name": "O", "email": "o@example.com"},
    )
    assert res.status_code == 200
    assert res.json()["currency"] == "INR"
    assert res.json()["tax_rate_percent"] == "0"
    assert res.json()["tax_rate_unconfigured"] is True


@pytest.mark.asyncio
async def test_profile_accepts_all_supported_currencies(client):
    await create_user("currency@example.com")
    await login(client, "currency@example.com")

    for currency in ("USD", "CAD", "INR", "GBP", "AUD"):
        res = await client.put(
            "/api/business-profile",
            json={
                "business_name": "Sparkle",
                "owner_name": "Alex",
                "email": "alex@example.com",
                "currency": currency,
            },
        )
        assert res.status_code == 200, f"{currency}: {res.text}"
        assert res.json()["currency"] == currency


@pytest.mark.asyncio
async def test_profile_rejects_unsupported_currency(client):
    await create_user("currencybad@example.com")
    await login(client, "currencybad@example.com")
    res = await client.put(
        "/api/business-profile",
        json={"currency": "EUR"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_invalid_tax_rate_rejected(client):
    await create_user("biz3@example.com")
    await login(client, "biz3@example.com")
    res = await client.put(
        "/api/business-profile",
        json={"tax_rate": "55"},
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_user_cannot_access_other_profiles(client):
    await create_user("biza@example.com")
    await create_user("bizb@example.com")
    await login(client, "bizb@example.com")
    res = await client.get("/api/business-profile")
    assert res.status_code == 404  # profile is scoped per user; B has none


# --- Logo upload ---


def _png_bytes():
    # minimal 1x1 PNG
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d4944415478da63fccf000000050001000137f4f30000000049454e44ae426082"
    )


def _svg_bytes():
    return (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20">'
        b'<rect width="20" height="20" fill="#2563eb"/></svg>'
    )


class FakeFile:
    def __init__(self, data, filename="logo.png", content_type="image/png"):
        self.data = data
        self.filename = filename
        self.content_type = content_type
        self.file = io.BytesIO(data)

    def read(self, n):
        return self.data[:n]


@pytest.mark.asyncio
async def test_logo_upload_valid_png(client):
    await create_user("logo@example.com")
    await login(client, "logo@example.com")
    await client.put(
        "/api/business-profile",
        json={"business_name": "L", "owner_name": "O", "email": "o@example.com"},
    )
    files = {"file": ("logo.png", io.BytesIO(_png_bytes()), "image/png")}
    res = await client.post("/api/business-profile/logo", files=files)
    assert res.status_code == 200, res.text
    assert res.json()["content_type"] == "image/png"


@pytest.mark.asyncio
async def test_logo_upload_rejects_fake_png(client):
    await create_user("logofake@example.com")
    await login(client, "logofake@example.com")
    await client.put(
        "/api/business-profile",
        json={"business_name": "L", "owner_name": "O", "email": "o@example.com"},
    )
    files = {"file": ("logo.png", io.BytesIO(b"<svg onload=alert(1)></svg>"), "image/png")}
    res = await client.post("/api/business-profile/logo", files=files)
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_logo_upload_rejects_oversized(client):
    await create_user("logobig@example.com")
    await login(client, "logobig@example.com")
    await client.put(
        "/api/business-profile",
        json={"business_name": "L", "owner_name": "O", "email": "o@example.com"},
    )
    from app.core.config import settings

    big = _png_bytes() + (b"0" * (settings.max_logo_size_bytes + 100))
    files = {"file": ("logo.png", io.BytesIO(big), "image/png")}
    res = await client.post("/api/business-profile/logo", files=files)
    assert res.status_code == 400


def test_validate_logo_rejects_svg_content():
    with pytest.raises(Exception):  # noqa: B017
        validate_logo(FakeFile(b"<svg>evil</svg>", "logo.png", "image/png"))

    png, data, size = validate_logo(FakeFile(_png_bytes()))
    assert png == "image/png"
    assert size == len(_png_bytes())


def test_allowed_types_include_svg():
    assert set(ALLOWED_TYPES.keys()) == {
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/svg+xml",
    }


def test_validate_logo_accepts_valid_svg():
    declared, data, size = validate_logo(FakeFile(_svg_bytes(), "logo.svg", "image/svg+xml"))
    assert declared == "image/svg+xml"
    assert size == len(_svg_bytes())


def test_validate_logo_rejects_svg_with_script():
    evil = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
        b"<script>alert(1)</script></svg>"
    )
    with pytest.raises(Exception):  # noqa: B017
        validate_logo(FakeFile(evil, "logo.svg", "image/svg+xml"))


def test_validate_logo_rejects_svg_with_event_handler():
    evil = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
        b'<rect width="10" height="10" onload="alert(1)"/></svg>'
    )
    with pytest.raises(Exception):  # noqa: B017
        validate_logo(FakeFile(evil, "logo.svg", "image/svg+xml"))


def test_validate_logo_rejects_svg_external_href():
    evil = (
        b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        b'width="10" height="10"><image xlink:href="http://evil.example/x.png"/></svg>'
    )
    with pytest.raises(Exception):  # noqa: B017
        validate_logo(FakeFile(evil, "logo.svg", "image/svg+xml"))


def test_validate_logo_rejects_bad_extension():
    with pytest.raises(Exception):  # noqa: B017
        validate_logo(FakeFile(_png_bytes(), "logo.txt", "image/png"))


def test_validate_logo_accepts_jpeg_extension():
    jpeg = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffdb004300" + "00" * 64 + "ffd9")
    declared, _data, size = validate_logo(FakeFile(jpeg, "logo.jpeg", "image/jpeg"))
    assert declared == "image/jpeg"
    assert size == len(jpeg)


# --- Logo upload via API ---


@pytest.mark.asyncio
async def test_logo_upload_valid_svg(client):
    await create_user("logosvg@example.com")
    await login(client, "logosvg@example.com")
    await client.put(
        "/api/business-profile",
        json={"business_name": "L", "owner_name": "O", "email": "o@example.com"},
    )
    files = {"file": ("logo.svg", io.BytesIO(_svg_bytes()), "image/svg+xml")}
    res = await client.post("/api/business-profile/logo", files=files)
    assert res.status_code == 200, res.text
    assert res.json()["content_type"] == "image/svg+xml"

    served = await client.get("/api/business-profile/logo")
    assert served.status_code == 200
    assert served.headers["content-type"].startswith("image/svg+xml")
    assert served.headers.get("x-content-type-options") == "nosniff"


@pytest.mark.asyncio
async def test_logo_upload_rejects_svg_with_script(client):
    await create_user("logoesvg@example.com")
    await login(client, "logoesvg@example.com")
    await client.put(
        "/api/business-profile",
        json={"business_name": "L", "owner_name": "O", "email": "o@example.com"},
    )
    evil = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    files = {"file": ("logo.svg", io.BytesIO(evil), "image/svg+xml")}
    res = await client.post("/api/business-profile/logo", files=files)
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_logo_upload_rejects_bad_extension(client):
    await create_user("logoext@example.com")
    await login(client, "logoext@example.com")
    await client.put(
        "/api/business-profile",
        json={"business_name": "L", "owner_name": "O", "email": "o@example.com"},
    )
    files = {"file": ("logo.txt", io.BytesIO(_png_bytes()), "image/png")}
    res = await client.post("/api/business-profile/logo", files=files)
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_logo_delete(client):
    await create_user("logodel@example.com")
    await login(client, "logodel@example.com")
    await client.put(
        "/api/business-profile",
        json={"business_name": "L", "owner_name": "O", "email": "o@example.com"},
    )
    files = {"file": ("logo.png", io.BytesIO(_png_bytes()), "image/png")}
    assert (await client.post("/api/business-profile/logo", files=files)).status_code == 200
    assert (await client.get("/api/business-profile")).json()["has_logo"] is True

    res = await client.delete("/api/business-profile/logo")
    assert res.status_code == 200, res.text
    assert res.json()["has_logo"] is False
    assert (await client.get("/api/business-profile/logo")).status_code == 404


@pytest.mark.asyncio
async def test_logo_delete_without_logo_404(client):
    await create_user("logonone@example.com")
    await login(client, "logonone@example.com")
    await client.put(
        "/api/business-profile",
        json={"business_name": "L", "owner_name": "O", "email": "o@example.com"},
    )
    res = await client.delete("/api/business-profile/logo")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_logo_settings_defaults_and_update(client):
    await create_user("logocfg@example.com")
    await login(client, "logocfg@example.com")
    created = await client.put(
        "/api/business-profile",
        json={"business_name": "L", "owner_name": "O", "email": "o@example.com"},
    )
    body = created.json()
    assert body["logo_position"] == "left"
    assert body["logo_size"] == "medium"
    assert body["show_logo_on_quotation"] is True

    updated = await client.put(
        "/api/business-profile",
        json={"logo_position": "center", "logo_size": "large", "show_logo_on_quotation": False},
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["logo_position"] == "center"
    assert body["logo_size"] == "large"
    assert body["show_logo_on_quotation"] is False


@pytest.mark.asyncio
async def test_logo_settings_reject_invalid_values(client):
    await create_user("logocfgbad@example.com")
    await login(client, "logocfgbad@example.com")
    await client.put(
        "/api/business-profile",
        json={"business_name": "L", "owner_name": "O", "email": "o@example.com"},
    )
    res = await client.put("/api/business-profile", json={"logo_position": "middle"})
    assert res.status_code == 422
