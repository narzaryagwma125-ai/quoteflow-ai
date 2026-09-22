from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str = Field(default="", max_length=40)
    address: str = Field(default="", max_length=2000)
    notes: str = Field(default="", max_length=4000)


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=4000)


class CustomerPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    phone: str
    address: str
    notes: str
    created_at: datetime
    updated_at: datetime


class CustomerListItem(CustomerPublic):
    quote_count: int = 0
    total_quoted_minor: int = 0
