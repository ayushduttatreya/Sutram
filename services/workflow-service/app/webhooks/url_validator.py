# app/webhooks/url_validator.py
"""Webhook URL validation — prevents SSRF by blocking private/internal destinations."""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class WebhookURLError(ValueError):
    """Raised when a webhook URL fails validation."""


# RFC 1918 private ranges + loopback + link-local + metadata services
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),       # loopback
    ipaddress.ip_network("169.254.0.0/16"),     # link-local / AWS IMDS
    ipaddress.ip_network("0.0.0.0/32"),         # unspecified address → localhost on Linux
    ipaddress.ip_network("::1/128"),            # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),           # IPv6 private
    ipaddress.ip_network("fe80::/10"),          # IPv6 link-local
    ipaddress.ip_network("::ffff:0:0/96"),      # IPv4-mapped IPv6 (bypasses IPv4 checks)
]


def validate_webhook_url(url: str) -> None:
    """Validate that a webhook URL is safe to deliver to.

    Checks:
    1. Scheme must be http or https
    2. Must have a non-empty hostname
    3. Hostname must not resolve to a private/internal IP address

    Raises WebhookURLError with a user-facing message on failure.
    Does NOT make a network request — resolves hostname via getaddrinfo.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        raise WebhookURLError(f"Invalid URL: {url!r}")

    if parsed.scheme not in ("https", "http"):
        raise WebhookURLError(f"Webhook URL must use https:// scheme, got: {parsed.scheme!r}")

    hostname = parsed.hostname
    if not hostname:
        raise WebhookURLError("Webhook URL must include a hostname")

    try:
        results = socket.getaddrinfo(hostname, None)
    except Exception:
        raise WebhookURLError(f"Webhook hostname could not be resolved: {hostname!r}")

    for _family, _type, _proto, _canonname, sockaddr in results:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        for blocked in _BLOCKED_NETWORKS:
            if ip in blocked:
                raise WebhookURLError(
                    f"Webhook URL resolves to a private/internal IP address ({ip_str}) "
                    "and cannot be used as a webhook endpoint"
                )
