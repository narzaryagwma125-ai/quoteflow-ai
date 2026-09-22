from __future__ import annotations

from app.db.session import _engine_url_and_connect_args


def test_neon_libpq_tls_options_are_normalized_for_asyncpg():
    url, connect_args = _engine_url_and_connect_args(
        "postgresql+asyncpg://user:password@host.example/db"
        "?sslmode=require&channel_binding=require"
    )
    assert "sslmode" not in url.query
    assert "channel_binding" not in url.query
    assert connect_args == {"ssl": "require"}


def test_existing_asyncpg_ssl_option_is_preserved():
    url, connect_args = _engine_url_and_connect_args(
        "postgresql+asyncpg://user:password@host.example/db?ssl=require"
    )
    assert "ssl" not in url.query
    assert connect_args == {"ssl": "require"}


def test_non_postgres_urls_are_unchanged():
    url, connect_args = _engine_url_and_connect_args("sqlite+aiosqlite:///./test.db")
    assert str(url) == "sqlite+aiosqlite:///./test.db"
    assert connect_args == {}
