"""Audit logging. Only safe metadata is stored — never request bodies."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.security.tokens import hash_ip


async def audit(
    db: AsyncSession,
    action: str,
    user_id: int | None = None,
    entity_type: str = "",
    entity_id: str = "",
    ip: str | None = None,
) -> None:
    safe_meta = ""
    if ip:
        safe_meta = f"ip_prefix:{hash_ip(ip)[:16]}"
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id)[:64],
            ip_hash_or_safe_metadata=safe_meta,
        )
    )
    await db.flush()
