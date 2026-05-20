"""AES-GCM encryption for webhook secrets.

Webhook secrets must be stored in a retrievable form (not hashed) because the raw
secret is needed to compute HMAC-SHA256 signatures on outbound webhook payloads.
AES-GCM provides authenticated encryption — tampering with the ciphertext raises
InvalidTag, preventing silent decryption of corrupted data.

Key format: 64 hex characters = 32 bytes (AES-256).
Ciphertext format: hex-encoded (nonce[12] || ciphertext+tag).
"""
from __future__ import annotations
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def generate_webhook_secret() -> str:
    """Generate a cryptographically random webhook secret (64 hex chars = 32 bytes)."""
    return secrets.token_hex(32)


def encrypt_secret(plaintext: str, hex_key: str) -> str:
    """Encrypt plaintext using AES-256-GCM. Returns hex-encoded nonce+ciphertext+tag."""
    key = bytes.fromhex(hex_key)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), associated_data=None)
    return (nonce + ciphertext).hex()


def decrypt_secret(hex_ciphertext: str, hex_key: str) -> str:
    """Decrypt hex-encoded nonce+ciphertext.

    Raises InvalidTag if key is wrong or ciphertext has been tampered with.
    """
    key = bytes.fromhex(hex_key)
    raw = bytes.fromhex(hex_ciphertext)
    nonce, ciphertext = raw[:12], raw[12:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data=None)
    return plaintext.decode()
