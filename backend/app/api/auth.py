"""Authentication endpoints: signup, login, logout, email verification, password reset."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, verify_origin
from app.core.config import settings
from app.core.errors import bad_request, unauthorized
from app.db.session import get_db
from app.models.token import EmailVerificationToken, PasswordResetToken
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ResetPasswordRequest,
    SessionResponse,
    SignupRequest,
    VerifyEmailRequest,
)
from app.schemas.user import UserPublic
from app.security.password import hash_password, verify_password
from app.security.rate_limit import client_ip_key, enforce
from app.security.sessions import (
    create_session_token,
    new_session_expiry,
    revoke_all_user_sessions,
    revoke_session,
    session_cookie_name,
    store_session,
)
from app.security.tokens import generate_token, hash_token
from app.services.audit import audit
from app.services.email import (
    password_reset_email_body,
    send_email,
    verification_email_body,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

EMAIL_VERIFY_TTL_MINUTES = 60 * 24  # 24h
RESET_TTL_MINUTES = 30


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=session_cookie_name(),
        value=token,
        max_age=settings.session_lifetime_days * 86400,
        httponly=True,
        secure=settings.session_cookie_secure_effective,
        samesite=settings.session_cookie_samesite,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(session_cookie_name(), path="/")


async def _send_email_or_console(email: str, subject: str, body: tuple[str, str]) -> None:
    text, html = body
    await send_email(email, subject, text, html)


@router.post("/signup", response_model=SessionResponse, status_code=201)
async def signup(
    payload: SignupRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    await enforce(client_ip_key(request), "signup", limit=5, window_seconds=3600)
    verify_origin(request)

    normalized_email = payload.email.strip().lower()
    existing = await db.execute(select(User).where(User.email == normalized_email))
    if existing.scalar_one_or_none() is not None:
        # Do not reveal that the account exists.
        raise_bad_request = bad_request("Could not create account.")
        raise raise_bad_request

    verification_required = settings.email_verification_required
    user = User(
        email=normalized_email,
        password_hash=hash_password(payload.password),
        is_active=True,
        is_email_verified=not verification_required,
    )
    db.add(user)
    await db.flush()

    verification_token: str | None = None
    if verification_required:
        verification_token = generate_token(32)
        db.add(
            EmailVerificationToken(
                user_id=user.id,
                token_hash=hash_token(verification_token),
                expires_at=datetime.now(UTC) + timedelta(minutes=EMAIL_VERIFY_TTL_MINUTES),
            )
        )
    session_token = create_session_token()
    await store_session(db, user.id, session_token, new_session_expiry())
    await audit(db, "auth.signup", user_id=user.id, ip=client_ip_key(request))
    await db.commit()

    _set_session_cookie(response, session_token)
    if verification_token is not None:
        await _send_email_or_console(
            user.email,
            "Verify your QuoteFlow AI email",
            verification_email_body(
                f"{settings.frontend_url}/verify-email?token={verification_token}"
            ),
        )
    return SessionResponse(user=UserPublic.model_validate(user))


@router.post("/login", response_model=SessionResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    await enforce(client_ip_key(request), "login", limit=10, window_seconds=900)
    verify_origin(request)

    normalized_email = payload.email.strip().lower()
    user = (await db.execute(select(User).where(User.email == normalized_email))).scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        await audit(
            db, "auth.login_failed",
            user_id=user.id if user else None,
            ip=client_ip_key(request),
        )
        await db.commit()
        raise unauthorized("Invalid email or password.")

    if not user.is_active:
        raise unauthorized("Account unavailable.")

    session_token = create_session_token()
    await store_session(db, user.id, session_token, new_session_expiry())
    user.last_login_at = datetime.now(UTC)
    await audit(db, "auth.login", user_id=user.id, ip=client_ip_key(request))
    await db.commit()

    _set_session_cookie(response, session_token)
    return SessionResponse(user=UserPublic.model_validate(user))


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    token = request.cookies.get(session_cookie_name())
    await revoke_session(db, token)
    _clear_session_cookie(response)
    return MessageResponse(message="Logged out.")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await enforce(client_ip_key(request), "forgot_password", limit=3, window_seconds=3600)
    verify_origin(request)

    normalized_email = payload.email.strip().lower()
    user = (await db.execute(select(User).where(User.email == normalized_email))).scalar_one_or_none()
    if user is not None:
        token = generate_token(32)
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=datetime.now(UTC) + timedelta(minutes=RESET_TTL_MINUTES),
            )
        )
        await audit(db, "auth.forgot_password", user_id=user.id, ip=client_ip_key(request))
        await db.commit()
        await _send_email_or_console(
            user.email,
            "Reset your QuoteFlow AI password",
            password_reset_email_body(f"{settings.frontend_url}/reset-password?token={token}"),
        )
    # Always return the same message whether the account exists or not.
    return MessageResponse(message="If that email is registered, a reset link has been sent.")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await enforce(client_ip_key(request), "reset_password", limit=3, window_seconds=3600)
    verify_origin(request)

    token_hash = hash_token(payload.token)
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    reset = result.scalar_one_or_none()

    if reset is None:
        # Single-use: also concede for unknown tokens.
        raise_bad = bad_request("This reset link is invalid or has expired.")
        raise raise_bad
    if reset.used_at is not None:
        raise bad_request("This reset link has already been used.")
    expiry = reset.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    if expiry <= datetime.now(UTC):
        raise bad_request("This reset link has expired.")

    user = await db.get(User, reset.user_id)
    if user is None:
        raise bad_request("This reset link is invalid.")
    user.password_hash = hash_password(payload.password)
    reset.used_at = datetime.now(UTC)
    await revoke_all_user_sessions(db, user.id)  # invalidate all existing sessions
    await audit(db, "auth.password_reset", user_id=user.id, ip=client_ip_key(request))
    await db.commit()
    return MessageResponse(message="Password has been reset. Please log in.")


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    payload: VerifyEmailRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await enforce(client_ip_key(request), "verify_email", limit=10, window_seconds=3600)
    verify_origin(request)

    result = await db.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == hash_token(payload.token)
        )
    )
    verify = result.scalar_one_or_none()
    if verify is None or verify.used_at is not None:
        raise bad_request("This verification link is invalid or has already been used.")
    expiry = verify.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    if expiry <= datetime.now(UTC):
        raise bad_request("This verification link has expired.")

    user = await db.get(User, verify.user_id)
    if user is None:
        raise bad_request("This verification link is invalid.")
    user.is_email_verified = True
    verify.used_at = datetime.now(UTC)
    await audit(db, "auth.email_verified", user_id=user.id, ip=client_ip_key(request))
    await db.commit()
    return MessageResponse(message="Email verified.")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await enforce(client_ip_key(request), "change_password", limit=5, window_seconds=3600)
    verify_origin(request)

    user.password_hash = hash_password(payload.new_password)
    await revoke_all_user_sessions(db, user.id)
    session_token = create_session_token()
    await store_session(db, user.id, session_token, new_session_expiry())
    await audit(db, "auth.password_changed", user_id=user.id, ip=client_ip_key(request))
    await db.commit()

    _set_session_cookie(response, session_token)
    return MessageResponse(message="Password updated.")


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await enforce(client_ip_key(request), "resend_verification", limit=3, window_seconds=3600)
    verify_origin(request)

    if user.is_email_verified:
        return MessageResponse(message="Your email is already verified.")

    token = generate_token(32)
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=datetime.now(UTC) + timedelta(minutes=EMAIL_VERIFY_TTL_MINUTES),
        )
    )
    await audit(db, "auth.verification_resent", user_id=user.id, ip=client_ip_key(request))
    await db.commit()
    await _send_email_or_console(
        user.email,
        "Verify your QuoteFlow AI email",
        verification_email_body(f"{settings.frontend_url}/verify-email?token={token}"),
    )
    return MessageResponse(message="Verification email sent.")


@router.post("/delete-account", response_model=MessageResponse)
async def delete_account(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await enforce(client_ip_key(request), "delete_account", limit=5, window_seconds=3600)
    verify_origin(request)

    await revoke_all_user_sessions(db, user.id)
    await db.delete(user)
    await db.commit()
    _clear_session_cookie(response)
    return MessageResponse(message="Account deleted.")
