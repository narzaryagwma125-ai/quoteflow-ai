from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gemini import (
    AIUnavailableError,
    NoAvailableModelError,
    generate_ai_text,
    get_active_model,
    get_available_models,
)
from app.api.deps import get_current_user, require_ai, verify_origin
from app.db.session import get_db
from app.models.user import User
from app.schemas.ai import (
    AIGenerateResponse,
    AIModelInfo,
    AIModelsResponse,
    FollowUpRequest,
    IntroductionRequest,
    RewriteRequest,
    ServiceDescriptionRequest,
)
from app.security.rate_limit import client_ip_key, enforce
from app.services.audit import audit
from app.services.subscription import get_usage_summary
from app.services.usage import increment_usage

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _service_unavailable() -> Exception:
    from fastapi import HTTPException, status

    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="The AI assistant is temporarily unavailable. You can still create quotes manually.",
    )


def _no_available_model_error(detail: str | None = None) -> Exception:
    from fastapi import HTTPException, status

    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=detail
        or (
            "No Gemini model available for this API key supports text content "
            "generation. Check that the key is valid and has at least one "
            "text-generation model enabled, or set GEMINI_MODEL."
        ),
    )


async def _run_ai(
    request: Request,
    user: User,
    db: AsyncSession,
    kind: str,
    **kwargs: str,
) -> AIGenerateResponse:
    verify_origin(request)
    await enforce(client_ip_key(request), "ai", limit=30, window_seconds=3600)
    await require_ai(user=user, db=db)

    try:
        text = await generate_ai_text(kind, **kwargs)
    except NoAvailableModelError as exc:
        # Surface the underlying message (includes the provider's hint, e.g. a
        # recommended replacement model) so operators know what to configure.
        raise _no_available_model_error(detail=str(exc)[:400]) from None
    except AIUnavailableError:
        raise _service_unavailable() from None

    await increment_usage(db, user.id, "ai")
    await audit(db, "ai.generated", user_id=user.id, entity_type="ai", entity_id=kind)
    summary = await get_usage_summary(db, user)
    await db.commit()
    return AIGenerateResponse(
        text=text,
        generated_by_ai=True,
        usage_remaining=summary["ai_remaining"],
    )


@router.post("/service-description", response_model=AIGenerateResponse)
async def service_description(
    payload: ServiceDescriptionRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIGenerateResponse:
    return await _run_ai(
        request, user, db, "service_description",
        service_name=payload.service_name,
        notes=payload.notes,
    )


@router.post("/rewrite", response_model=AIGenerateResponse)
async def rewrite(
    payload: RewriteRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIGenerateResponse:
    return await _run_ai(
        request, user, db, "rewrite", text=payload.text, tone=payload.tone
    )


@router.post("/introduction", response_model=AIGenerateResponse)
async def introduction(
    payload: IntroductionRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIGenerateResponse:
    return await _run_ai(
        request, user, db, "introduction",
        business_name=payload.business_name,
        customer_name=payload.customer_name,
        summary=payload.summary,
    )


@router.post("/follow-up-message", response_model=AIGenerateResponse)
async def follow_up_message(
    payload: FollowUpRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIGenerateResponse:
    return await _run_ai(
        request, user, db, "follow_up",
        customer_name=payload.customer_name,
        quote_number=payload.quote_number,
        context=payload.context,
    )


@router.get("/models", response_model=AIModelsResponse)
async def ai_models(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIModelsResponse:
    """List models enabled for the configured key (safe metadata only, no key)."""
    del db  # unused; auth is enforced by the dependency
    verify_origin(request)
    await enforce(client_ip_key(request), "ai_models_list", limit=10, window_seconds=3600)

    try:
        raw = await get_available_models()
        active = await get_active_model()
    except NoAvailableModelError:
        raise _no_available_model_error() from None
    except AIUnavailableError:
        raise _service_unavailable() from None

    return AIModelsResponse(
        models=[AIModelInfo(**meta) for meta in raw],
        active_model=active,
    )
