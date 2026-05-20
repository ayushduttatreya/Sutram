# tests/unit/webhooks/test_dispatcher.py
import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.webhooks.dispatcher import WebhookDispatcher, sign_payload


def test_sign_payload_produces_valid_hmac():
    secret = "my-secret"
    payload = b'{"event": "test"}'
    signature = sign_payload(payload, secret)
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    assert signature == f"sha256={expected}"


def test_sign_payload_different_secret_different_signature():
    payload = b'{"event": "test"}'
    sig1 = sign_payload(payload, "secret-a")
    sig2 = sign_payload(payload, "secret-b")
    assert sig1 != sig2


def test_sign_payload_starts_with_sha256_prefix():
    sig = sign_payload(b"payload", "secret")
    assert sig.startswith("sha256=")


@pytest.mark.asyncio
async def test_deliver_sends_correct_headers():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "OK"

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    dispatcher = WebhookDispatcher(client=mock_client)
    status, body = await dispatcher.deliver(
        url="https://example.com/webhook",
        secret="test-secret",
        event_type="execution.completed",
        payload={"execution_id": "abc"},
    )

    assert status == 200
    assert body == "OK"

    call_kwargs = mock_client.post.call_args
    headers = call_kwargs.kwargs["headers"]
    assert headers["Content-Type"] == "application/json"
    assert headers["X-Sutram-Event"] == "execution.completed"
    assert headers["X-Sutram-Signature"].startswith("sha256=")


@pytest.mark.asyncio
async def test_deliver_signature_verifiable_by_receiver():
    """The signature sent should be verifiable with the shared secret."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "OK"

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    dispatcher = WebhookDispatcher(client=mock_client)
    secret = "shared-secret-xyz"
    await dispatcher.deliver(
        url="https://example.com/webhook",
        secret=secret,
        event_type="execution.completed",
        payload={"data": "value"},
    )

    call_kwargs = mock_client.post.call_args
    sent_body: bytes = call_kwargs.kwargs["content"]
    sent_sig: str = call_kwargs.kwargs["headers"]["X-Sutram-Signature"]

    # Receiver-side verification
    expected_digest = hmac.new(secret.encode(), sent_body, hashlib.sha256).hexdigest()
    assert sent_sig == f"sha256={expected_digest}"
