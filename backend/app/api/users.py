from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.business_profile import BusinessProfile
from app.models.user import User
from app.schemas.user import MeResponse
from app.services.subscription import get_usage_summary

router = APIRouter(tags=["users"])


@router.get("/api/me", response_model=MeResponse)
async def me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    usage = await get_usage_summary(db, user)
    has_profile = (
        await db.execute(select(BusinessProfile.id).where(BusinessProfile.user_id == user.id))
    ).first() is not None
    return MeResponse(
        id=user.id,
        email=user.email,
        is_email_verified=user.is_email_verified,
        plan=usage["plan"],
        subscription_status=usage["status"],
        has_business_profile=has_profile,
        trial_active=usage["trial_active"],
        trial_expired=usage["trial_expired"],
        trial_days_remaining=usage["trial_days_remaining"],
        trial_expires_at=usage["trial_expires_at"],
        trial_unlimited=usage["trial_unlimited"],
    )
