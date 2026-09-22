from __future__ import annotations

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, verify_origin
from app.core.errors import not_found
from app.db.session import get_db
from app.models.business_profile import BusinessProfile, LogoFile
from app.models.user import User
from app.schemas.business import (
    BusinessProfileCreate,
    BusinessProfilePublic,
    BusinessProfileUpdate,
    LogoResponse,
)
from app.security.rate_limit import client_ip_key, enforce
from app.services.audit import audit
from app.services.quote_calc import format_percent, tax_rate_bps_from_percent
from app.uploads.store import delete_logo, read_logo, store_logo, validate_logo

router = APIRouter(prefix="/api", tags=["business"])


def _public(profile: BusinessProfile) -> BusinessProfilePublic:
    return BusinessProfilePublic(
        id=profile.id,
        business_name=profile.business_name,
        owner_name=profile.owner_name,
        email=profile.email,
        phone=profile.phone,
        address_line_1=profile.address_line_1,
        address_line_2=profile.address_line_2,
        city=profile.city,
        state_or_province=profile.state_or_province,
        postal_code=profile.postal_code,
        country=profile.country,
        currency=profile.currency,
        timezone=profile.timezone,
        tax_rate_percent=format_percent(profile.tax_rate_bps),
        tax_rate_unconfigured=(profile.tax_rate_bps == 0),
        has_logo=profile.logo_file_id is not None,
        logo_position=profile.logo_position,
        logo_size=profile.logo_size,
        show_logo_on_quotation=profile.show_logo_on_quotation,
        created_at=profile.created_at,
    )


async def _get_profile(db: AsyncSession, user_id: int) -> BusinessProfile:
    profile = (
        await db.execute(select(BusinessProfile).where(BusinessProfile.user_id == user_id))
    ).scalar_one_or_none()
    if profile is None:
        raise not_found("Business profile not found. Create one first.")
    return profile


@router.get("/business-profile", response_model=BusinessProfilePublic)
async def get_business_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BusinessProfilePublic:
    return _public(await _get_profile(db, user.id))


@router.put("/business-profile", response_model=BusinessProfilePublic)
async def upsert_business_profile(
    payload: BusinessProfileUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BusinessProfilePublic:
    verify_origin(request)
    profile = (
        await db.execute(select(BusinessProfile).where(BusinessProfile.user_id == user.id))
    ).scalar_one_or_none()
    if profile is None:
        merged = payload.model_dump(exclude_none=True)
        defaulted = {
            "business_name": merged.get("business_name") or "My Cleaning Business",
            "owner_name": merged.get("owner_name") or "Owner",
            "email": merged.get("email") or user.email,
        }
        merged.update({k: v for k, v in defaulted.items() if k not in merged})
        tax_rate = merged.pop("tax_rate", "0")
        data = {k: v for k, v in merged.items() if k in BusinessProfileCreate.model_fields}
        profile = BusinessProfile(user_id=user.id, **data, tax_rate_bps=tax_rate_bps_from_percent(tax_rate))
        db.add(profile)
        await audit(db, "business_profile.created", user_id=user.id, entity_type="business_profile")
        await db.commit()
        await db.refresh(profile)
        return _public(profile)

    data = payload.model_dump(exclude_none=True)
    if "tax_rate" in data:
        profile.tax_rate_bps = tax_rate_bps_from_percent(data.pop("tax_rate"))
    for key, value in data.items():
        if key in BusinessProfileUpdate.model_fields and key not in ("tax_rate",):
            setattr(profile, key, value)
    await audit(db, "business_profile.updated", user_id=user.id, entity_type="business_profile")
    await db.commit()
    await db.refresh(profile)
    return _public(profile)


@router.post("/business-profile/logo", response_model=LogoResponse)
async def upload_logo(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LogoResponse:
    verify_origin(request)
    await enforce(client_ip_key(request), "logo_upload", limit=10, window_seconds=3600)

    profile = await _get_profile(db, user.id)

    content_type, data, size = validate_logo(file)
    logo = LogoFile(
        user_id=user.id,
        stored_name="",  # set below
        original_name=file.filename or "logo",
        content_type=content_type,
        size_bytes=size,
    )
    db.add(logo)
    await db.flush()

    stored_path = store_logo(content_type, data)
    logo.stored_name = stored_path.name

    if profile.logo_file_id:
        old = await db.get(LogoFile, profile.logo_file_id)
        if old and old.stored_name:
            delete_logo(old.stored_name)
        await db.delete(old)
        await db.flush()

    profile.logo_file_id = logo.id
    await audit(db, "business_profile.logo_uploaded", user_id=user.id, entity_type="business_profile")
    await db.commit()
    await db.refresh(logo)
    return LogoResponse(id=logo.id, content_type=logo.content_type, size_bytes=logo.size_bytes)


@router.get("/business-profile/logo")
async def get_logo(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_profile(db, user.id)
    if not profile.logo_file_id:
        raise not_found("No logo uploaded.")
    logo = await db.get(LogoFile, profile.logo_file_id)
    if logo is None or not logo.stored_name:
        raise not_found("No logo uploaded.")
    data = read_logo(logo.stored_name)
    if data is None:
        raise not_found("Logo file is missing on disk.")
    return Response(content=data, media_type=logo.content_type, headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"})


@router.delete("/business-profile/logo", response_model=BusinessProfilePublic)
async def remove_logo(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BusinessProfilePublic:
    verify_origin(request)
    profile = await _get_profile(db, user.id)
    if profile.logo_file_id is None:
        raise not_found("No logo uploaded.")
    logo = await db.get(LogoFile, profile.logo_file_id)
    if logo is not None:
        if logo.stored_name:
            delete_logo(logo.stored_name)
        await db.delete(logo)
    profile.logo_file_id = None
    await audit(db, "business_profile.logo_removed", user_id=user.id, entity_type="business_profile")
    await db.commit()
    await db.refresh(profile)
    return _public(profile)
