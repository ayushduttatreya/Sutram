# tests/unit/webhooks/test_url_validator.py
from unittest.mock import patch

import pytest

from app.webhooks.url_validator import WebhookURLError, validate_webhook_url


def test_valid_https_url_passes():
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]):
        validate_webhook_url("https://example.com/webhook")  # should not raise


def test_http_url_passes():
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]):
        validate_webhook_url("http://example.com/webhook")  # http allowed


def test_ftp_scheme_raises():
    with pytest.raises(WebhookURLError, match="scheme"):
        validate_webhook_url("ftp://example.com/webhook")


def test_localhost_raises():
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 0))]):
        with pytest.raises(WebhookURLError, match="private"):
            validate_webhook_url("http://localhost/webhook")


def test_aws_imds_raises():
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("169.254.169.254", 0))]):
        with pytest.raises(WebhookURLError, match="private"):
            validate_webhook_url("http://169.254.169.254/latest/meta-data/")


def test_private_10_range_raises():
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("10.0.0.1", 0))]):
        with pytest.raises(WebhookURLError, match="private"):
            validate_webhook_url("http://internal-service/webhook")


def test_private_192_168_raises():
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("192.168.1.1", 0))]):
        with pytest.raises(WebhookURLError, match="private"):
            validate_webhook_url("http://192.168.1.1/webhook")


def test_missing_hostname_raises():
    with pytest.raises(WebhookURLError, match="hostname"):
        validate_webhook_url("https:///path")


def test_unresolvable_hostname_raises():
    with patch("socket.getaddrinfo", side_effect=Exception("Name not found")):
        with pytest.raises(WebhookURLError):
            validate_webhook_url("https://this-domain-does-not-exist-xyz.invalid/webhook")
