"""Regression tests for PostgreSQL/Neon asyncpg TLS URL normalization."""

from app.db.session import _engine_url_and_connect_args


def test_neon_url_strips_libpq_tls_options_and_enables_ssl():
    url, connect_args = _engine_url_and_connect_args(
        "postgresql+asyncpg://user:password@example.neon.tech/db"
        "?sslmode=require&channel_binding=require"
    )

    assert "sslmode" not in url.query
    assert "channel_binding" not in url.query
    assert connect_args == {"ssl": "require"}


def test_postgres_without_sslmode_defaults_to_tls():
    url, connect_args = _engine_url_and_connect_args(
        "postgresql+asyncpg://user:password@example.neon.tech/db"
    )

    assert "sslmode" not in url.query
    assert "channel_binding" not in url.query
    assert connect_args == {"ssl": True}


def test_explicit_ssl_disable_is_preserved_as_false():
    url, connect_args = _engine_url_and_connect_args(
        "postgresql+asyncpg://user:password@localhost/db?sslmode=disable"
    )

    assert "sslmode" not in url.query
    assert connect_args == {"ssl": False}


def test_non_asyncpg_urls_are_unchanged():
    url, connect_args = _engine_url_and_connect_args(
        "sqlite+aiosqlite:///./test.db"
    )

    assert str(url) == "sqlite+aiosqlite:///./test.db"
    assert connect_args == {}


def test_plain_postgresql_url_is_converted_to_asyncpg():
    url, connect_args = _engine_url_and_connect_args(
        "postgresql://user:password@example.neon.tech/db"
        "?sslmode=require&channel_binding=require"
    )

    assert url.drivername == "postgresql+asyncpg"
    assert "sslmode" not in url.query
    assert "channel_binding" not in url.query
    assert connect_args == {"ssl": "require"}
