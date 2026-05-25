# app/webhooks/tasks.py
"""Celery task for webhook delivery with exponential backoff retry schedule.

Retry delays: 1s, 5s, 30s, 5min, 30min.
After 5 failures: mark delivery as dead_lettered, stop retrying.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from celery import Task

from app.tasks.celery_app import celery_app

RETRY_DELAYS = [1, 5, 30, 300, 1800]  # seconds between attempts


@celery_app.task(  # type: ignore[untyped-decorator]
    name="webhook.deliver",
    bind=True,
    max_retries=len(RETRY_DELAYS),
    acks_late=True,
)
def deliver_webhook(self: Task, delivery_id: str) -> None:
    """Attempt delivery of a webhook. Retries with exponential-ish backoff."""
    import asyncio

    retry_delay = asyncio.run(_deliver(delivery_id, attempt=self.request.retries))
    if retry_delay is not None:
        raise self.retry(countdown=retry_delay)


async def _deliver(delivery_id: str, attempt: int) -> int | None:
    """Returns retry countdown seconds if a retry is needed, None otherwise."""
    import httpx
    from sqlalchemy import select

    from app.dependencies import get_db_session_context
    from app.models.orm import WebhookDeliveryORM, WebhookSubscriptionORM
    from app.settings import get_settings
    from app.webhooks.crypto import decrypt_secret
    from app.webhooks.dispatcher import WebhookDispatcher

    settings = get_settings()

    async with get_db_session_context() as session:
        result = await session.execute(
            select(WebhookDeliveryORM).where(WebhookDeliveryORM.id == delivery_id)
        )
        delivery = result.scalar_one_or_none()
        if delivery is None or delivery.status in ("delivered", "dead_lettered"):
            return None

        sub_result = await session.execute(
            select(WebhookSubscriptionORM).where(
                WebhookSubscriptionORM.id == delivery.subscription_id
            )
        )
        subscription = sub_result.scalar_one_or_none()
        if subscription is None or not subscription.active:
            delivery.status = "failed"
            return None

        secret = decrypt_secret(
            subscription.secret_encrypted, settings.webhook_secret_encryption_key
        )

        async with httpx.AsyncClient() as client:
            dispatcher = WebhookDispatcher(client=client)
            try:
                status_code, response_body = await dispatcher.deliver(
                    url=subscription.url,
                    secret=secret,
                    event_type=delivery.event_type,
                    payload=delivery.payload,
                )
            except httpx.RequestError as e:
                status_code, response_body = 0, str(e)

        delivery.attempt_count += 1
        delivery.last_attempt_at = datetime.now(UTC)
        delivery.response_code = status_code
        delivery.response_body = response_body[:1000]

        if 200 <= status_code < 300:
            delivery.status = "delivered"
            return None
        elif attempt >= len(RETRY_DELAYS) - 1:
            delivery.status = "dead_lettered"
            return None
        else:
            delivery.status = "pending"
            delivery.next_retry_at = datetime.now(UTC) + timedelta(seconds=RETRY_DELAYS[attempt])
            return RETRY_DELAYS[attempt]
