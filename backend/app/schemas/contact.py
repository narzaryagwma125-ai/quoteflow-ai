from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

NAME_MAX = 120
SUBJECT_MAX = 200
MESSAGE_MIN = 10
MESSAGE_MAX = 5000


class ContactRequest(BaseModel):
    name: str = Field(min_length=1, max_length=NAME_MAX)
    email: EmailStr
    subject: str = Field(min_length=1, max_length=SUBJECT_MAX)
    message: str = Field(min_length=MESSAGE_MIN, max_length=MESSAGE_MAX)
    # Honeypot field: real users never see or fill it; bots do. If it has a
    # value the request is silently dropped as spam.
    website: str = Field(default="", max_length=500)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("name", "subject")
    @classmethod
    def strip_short_fields(cls, v: str) -> str:
        v = v.strip()
        if "\n" in v or "\r" in v:
            raise ValueError("must not contain line breaks")
        if not v:
            raise ValueError("cannot be blank")
        return v

    @field_validator("message")
    @classmethod
    def strip_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("cannot be blank")
        return v