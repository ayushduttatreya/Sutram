"""HMAC-SHA256 webhook signing and HTTP delivery.

Signing: HMAC-SHA256(raw_secret, raw_request_body)
The raw secret is retrieved by decrypting the AES-GCM ciphertext stored in
webhook_subscriptions.secret_encrypted via app.webhooks.crypto.decrypt_secret().
Signature format: 'sha256={hexdigest}' in X-Sutram-Signature header.
"""
from __future__ import annotations
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any
import uuid

import httpx


def sign_payload(payload_bytes: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature. Returns 'sha256={hexdigest}'."""
    digest = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


class WebhookDispatcher:
    """Dispatches signed webhook POST requests to subscriber URLs."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def deliver(
        self,
        url: str,
        secret: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> tuple[int, str]:
        """Deliver payload to url with HMAC signature.

        Returns (status_code, response_body).
        Raises httpx.RequestError on connection failure.
        """
        payload_with_meta = {
            **payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "delivery_id": str(uuid.uuid4()),
        }
        payload_bytes = json.dumps(payload_with_meta, separators=(",", ":")).encode()
        signature = sign_payload(payload_bytes, secret)

        response = await self._client.post(
            url,
            content=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Sutram-Signature": signature,
                "X-Sutram-Event": event_type,
            },
            timeout=10.0,
        )
        return response.status_code, response.text
