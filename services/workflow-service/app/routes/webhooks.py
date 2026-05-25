# app/routes/webhooks.py
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sutram_core.middleware.tenant import set_tenant_context

from app.dependencies import get_db_session, get_tenant_id_from_header
from app.models.orm import WebhookSubscriptionORM
from app.settings import get_settings
from app.webhooks.crypto import encrypt_secret, generate_webhook_secret
from app.webhooks.url_validator import WebhookURLError, validate_webhook_url

router = APIRouter(tags=["webhooks"])

DBSession = Annotated[AsyncSession, Depends(get_db_session)]
TenantID = Annotated[uuid.UUID, Depends(get_tenant_id_from_header)]


class WebhookSubscriptionCreate(BaseModel):
    url: str
    events: list[str] = ["execution.completed"]


class WebhookSubscriptionResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    tenant_id: uuid.UUID
    url: str
    events: list[str]
    active: bool


class WebhookRegistrationResponse(BaseModel):
    """Returned ONLY at registration time. Secret is shown once and never stored plaintext."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    url: str
    events: list[str]
    secret: str  # raw secret — shown once, then gone


@router.post("/webhooks", response_model=WebhookRegistrationResponse, status_code=201)
async def create_webhook(
    body: WebhookSubscriptionCreate,
    session: DBSession,
    tenant_id: TenantID,
) -> dict[str, object]:
    try:
        validate_webhook_url(body.url)
    except WebhookURLError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    await set_tenant_context(session, str(tenant_id))
    settings = get_settings()
    raw_secret = generate_webhook_secret()
    encrypted = encrypt_secret(raw_secret, settings.webhook_secret_encryption_key)

    sub = WebhookSubscriptionORM(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        url=body.url,
        secret_encrypted=encrypted,
        events=body.events,
        active=True,
    )
    session.add(sub)
    await session.flush()

    return {
        "id": sub.id,
        "tenant_id": sub.tenant_id,
        "url": sub.url,
        "events": sub.events,
        "secret": raw_secret,  # shown once only
    }


@router.get("/webhooks", response_model=list[WebhookSubscriptionResponse])
async def list_webhooks(
    session: DBSession,
    tenant_id: TenantID,
) -> list[WebhookSubscriptionORM]:
    await set_tenant_context(session, str(tenant_id))
    result = await session.execute(
        select(WebhookSubscriptionORM).where(
            WebhookSubscriptionORM.tenant_id == tenant_id,
            WebhookSubscriptionORM.active.is_(True),
        )
    )
    return list(result.scalars().all())


@router.delete("/webhooks/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: uuid.UUID,
    session: DBSession,
    tenant_id: TenantID,
) -> None:
    await set_tenant_context(session, str(tenant_id))
    result = await session.execute(
        select(WebhookSubscriptionORM).where(
            WebhookSubscriptionORM.id == webhook_id,
            WebhookSubscriptionORM.tenant_id == tenant_id,
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="Webhook subscription not found")
    sub.active = False  # soft delete
    await session.flush()
