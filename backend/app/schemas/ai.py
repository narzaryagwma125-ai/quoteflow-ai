from __future__ import annotations

from pydantic import BaseModel, Field

AI_MAX_PROMPT_LENGTH = 4000


class ServiceDescriptionRequest(BaseModel):
    service_name: str = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=AI_MAX_PROMPT_LENGTH)


class RewriteRequest(BaseModel):
    text: str = Field(min_length=1, max_length=AI_MAX_PROMPT_LENGTH)
    tone: str = Field(default="professional", max_length=40)


class IntroductionRequest(BaseModel):
    business_name: str = Field(default="", max_length=200)
    customer_name: str = Field(default="", max_length=200)
    summary: str = Field(default="", max_length=AI_MAX_PROMPT_LENGTH)


class FollowUpRequest(BaseModel):
    customer_name: str = Field(default="", max_length=200)
    quote_number: str = Field(default="", max_length=40)
    context: str = Field(default="", max_length=AI_MAX_PROMPT_LENGTH)


class AIContinueResponse(BaseModel):
    text: str
    generated_by_ai: bool = True


class AIGenerateResponse(AIContinueResponse):
    usage_remaining: int = 0


class AIModelInfo(BaseModel):
    name: str
    supported_generation_methods: list[str] = Field(default_factory=list)


class AIModelsResponse(BaseModel):
    models: list[AIModelInfo]
    active_model: str | None = None
