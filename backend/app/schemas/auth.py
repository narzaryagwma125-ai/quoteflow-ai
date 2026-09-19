from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

PASSWORD_MIN = 10
PASSWORD_MAX = 200


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)


class ChangePasswordRequest(BaseModel):
    new_password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)


class SessionResponse(BaseModel):
    user: UserPublic


class MessageResponse(BaseModel):
    message: str


from app.schemas.user import UserPublic  # noqa: E402

SessionResponse.model_rebuild()
