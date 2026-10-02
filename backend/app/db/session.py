from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# TLS modes understood by asyncpg's ``ssl`` keyword. Anything else falls back to
# ``require`` so a typo in the database URL can never silently disable or
# downgrade TLS.
_ASYNCPG_SSL_MODES = frozenset(
    {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}
)


def _asyncpg_ssl_mode(value: object) -> str:
    """Translate a libpq/URL TLS mode into the value asyncpg expects.

    Both the libpq ``sslmode=require`` and the bare ``ssl=require`` spellings
    become the string ``"require"``, which asyncpg resolves against its own
    ``SSLMode`` enum. Boolean-ish spellings (``ssl=true``/``ssl=false``) coming
    from hand-written connection strings are accepted too.
    """
    mode = str(value or "").strip().lower().replace("_", "-")
    if mode in ("1", "true", "yes", "on"):
        mode = "require"
    elif mode in ("0", "false", "no", "off"):
        mode = "disable"
    if mode not in _ASYNCPG_SSL_MODES:
        # Managed PostgreSQL providers require TLS; never downgrade on a
        # missing or unrecognised mode.
        return "require"
    return mode


def _engine_url_and_connect_args(database_url: str) -> tuple[URL, dict]:
    """Normalize PostgreSQL URLs for SQLAlchemy's asyncpg driver.

    Neon commonly provides a libpq-style URL such as ``postgresql://...``
    with ``sslmode=require`` and ``channel_binding=require``. The application
    uses async SQLAlchemy, so the URL is normalized to ``postgresql+asyncpg``
    and the libpq-only TLS options are removed before the URL reaches asyncpg.
    TLS is then configured explicitly through ``connect_args``.
    """
    url = make_url(database_url)

    # Convert a normal PostgreSQL URL (the format Neon/Render often provides)
    # to the asyncpg driver used by this application.
    if url.get_backend_name() == "postgresql":
        url = url.set(drivername="postgresql+asyncpg")

    if url.get_backend_name() != "postgresql":
        return url, {}

    query = dict(url.query)
    connect_args: dict = {}

    # These are connection-string TLS options and must not be forwarded to
    # asyncpg as keyword arguments; ``sslmode`` and ``channel_binding`` in
    # particular are unknown to asyncpg and raise TypeError.
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)

    # asyncpg accepts the same mode spellings under ``ssl``, so both the
    # libpq-style and the bare spelling collapse into one connect argument.
    url_ssl = query.pop("ssl", None)
    connect_args["ssl"] = _asyncpg_ssl_mode(
        sslmode if sslmode not in (None, "") else url_ssl
    )

    return url.set(query=query), connect_args


_engine_url, _connect_args = _engine_url_and_connect_args(settings.database_url)
engine = create_async_engine(
    _engine_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
