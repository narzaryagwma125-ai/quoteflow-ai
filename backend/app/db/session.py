from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def _engine_url_and_connect_args(database_url: str) -> tuple[URL, dict]:
    """Normalize PostgreSQL URLs for SQLAlchemy's asyncpg driver.

    Neon commonly provides a libpq-style URL such as ``postgresql://...``
    with ``sslmode=require`` and ``channel_binding=require``. The application
    uses async SQLAlchemy, so the URL is normalized to ``postgresql+asyncpg``
    and the libpq-only TLS options are removed before the URL reaches asyncpg.
    TLS is then enabled explicitly through ``connect_args``.
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

    # These are libpq connection-string options and must not be forwarded to
    # asyncpg as keyword arguments.
    sslmode = str(query.pop("sslmode", "") or "").lower()
    query.pop("channel_binding", None)

    # Configure TLS explicitly for asyncpg instead of through the URL.
    query.pop("ssl", None)
    connect_args["ssl"] = sslmode != "disable"

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
