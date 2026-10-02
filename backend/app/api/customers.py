from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, pagination_params, verify_origin
from app.core.errors import bad_request, not_found
from app.db.session import get_db
from app.models.customer import Customer
from app.models.quote import Quote
from app.models.user import User
from app.schemas.customer import (
    CustomerCreate,
    CustomerListItem,
    CustomerPublic,
    CustomerUpdate,
)
from app.security.rate_limit import client_ip_key, enforce
from app.services.audit import audit
from app.services.subscription import PLANS, effective_plan, get_subscription, trial_status

router = APIRouter(prefix="/api/customers", tags=["customers"])


async def _get_owned_customer(db: AsyncSession, user_id: int, customer_id: int) -> Customer:
    customer = (
        await db.execute(
            select(Customer).where(Customer.id == customer_id, Customer.user_id == user_id)
        )
    ).scalar_one_or_none()
    if customer is None:
        raise not_found("Customer not found.")
    return customer


@router.get("", response_model=list[CustomerListItem])
async def list_customers(
    pg: dict = Depends(pagination_params),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CustomerListItem]:
    page, page_size, q, sort, order = (
        pg["page"],
        pg["page_size"],
        pg["q"],
        pg["sort"],
        pg["order"],
    )
    stmt = select(Customer).where(Customer.user_id == user.id)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(Customer.name.ilike(pattern), Customer.email.ilike(pattern)))
    sort_col = {"name": Customer.name, "email": Customer.email}.get(sort, Customer.created_at)
    stmt = stmt.order_by(sort_col.asc() if order == "asc" else sort_col.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    rows = (await db.execute(stmt)).scalars().all()

    # get quote counts + totals for listed customers, scoped to the user
    count_stmt = (
        select(Quote.customer_id, func.count(Quote.id), func.coalesce(func.sum(Quote.total_minor), 0))
        .where(Quote.user_id == user.id, Quote.customer_id.isnot(None))
        .group_by(Quote.customer_id)
    )
    stats = {
        row[0]: (row[1], row[2])
        for row in (await db.execute(count_stmt)).all()
    }
    items = []
    for customer in rows:
        quote_count, total_minor = stats.get(customer.id, (0, 0))
        item = CustomerListItem(
            id=customer.id,
            name=customer.name,
            email=customer.email,
            phone=customer.phone,
            address=customer.address,
            notes=customer.notes,
            created_at=customer.created_at,
            updated_at=customer.updated_at,
            quote_count=quote_count,
            total_quoted_minor=total_minor,
        )
        items.append(item)
    return items


@router.post("", response_model=CustomerPublic, status_code=201)
async def create_customer(
    payload: CustomerCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CustomerPublic:
    verify_origin(request)
    await enforce(client_ip_key(request), "customer_create", limit=60, window_seconds=3600)

    subscription = await get_subscription(db, user.id)
    plan_name = effective_plan(subscription)
    limit = PLANS[plan_name].customers_limit
    trial = trial_status(user)
    if trial["trial_active"] and plan_name == "free":
        limit = PLANS["starter"].customers_limit
    if limit is not None:
        count = (
            await db.execute(
                select(func.count(Customer.id)).where(Customer.user_id == user.id)
            )
        ).scalar_one() or 0
        if count >= limit:
            raise bad_request(
                f"Your plan allows up to {limit} customers. Upgrade for unlimited customers."
            )

    customer = Customer(user_id=user.id, **payload.model_dump())
    db.add(customer)
    await audit(db, "customer.created", user_id=user.id, entity_type="customer")
    await db.commit()
    await db.refresh(customer)
    return CustomerPublic.model_validate(customer)


@router.get("/{customer_id}", response_model=CustomerPublic)
async def get_customer(
    customer_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CustomerPublic:
    customer = await _get_owned_customer(db, user.id, customer_id)
    return CustomerPublic.model_validate(customer)


@router.put("/{customer_id}", response_model=CustomerPublic)
async def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CustomerPublic:
    verify_origin(request)
    customer = await _get_owned_customer(db, user.id, customer_id)
    data = payload.model_dump(exclude_none=True)
    for key, value in data.items():
        setattr(customer, key, value)
    await audit(db, "customer.updated", user_id=user.id, entity_type="customer", entity_id=customer.id)
    await db.commit()
    await db.refresh(customer)
    return CustomerPublic.model_validate(customer)


@router.delete("/{customer_id}")
async def delete_customer(
    customer_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    verify_origin(request)
    customer = await _get_owned_customer(db, user.id, customer_id)
    await db.delete(customer)
    await audit(db, "customer.deleted", user_id=user.id, entity_type="customer", entity_id=customer_id)
    await db.commit()
    return {"message": "Customer deleted."}
