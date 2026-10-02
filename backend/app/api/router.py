from __future__ import annotations

from fastapi import APIRouter

from app.api import (
    ai,
    auth,
    billing,
    business,
    contact,
    customers,
    health,
    public_quotes,
    quotes,
    templates,
    users,
    webhooks,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(business.router)
api_router.include_router(templates.router)
api_router.include_router(customers.router)
api_router.include_router(quotes.router)
api_router.include_router(public_quotes.router)
api_router.include_router(ai.router)
api_router.include_router(billing.router)
api_router.include_router(contact.router)
api_router.include_router(webhooks.router)
