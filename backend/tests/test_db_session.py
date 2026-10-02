"""Regression tests for PostgreSQL/Neon asyncpg TLS URL normalization.

The libpq/Neon URL options must never reach asyncpg as keyword arguments, and
the requested TLS mode must be translated rather than upgraded: asyncpg maps
``ssl=True`` to ``SSLMode.verify_full``, which is stricter than the
``sslmode=require`` managed providers ask for and fails certificate validation
against providers whose CA is not in the container trust store.
"""

from app.db.session import _engine_url_and_connect_args


def test_neon_url_strips_libpq_tls_options_and_requires_tls():
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
    assert connect_args == {"ssl": "require"}


def test_explicit_ssl_disable_is_preserved_as_disable():
    url, connect_args = _engine_url_and_connect_args(
        "postgresql+asyncpg://user:password@localhost/db?sslmode=disable"
    )

    assert "sslmode" not in url.query
    assert connect_args == {"ssl": "disable"}


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
