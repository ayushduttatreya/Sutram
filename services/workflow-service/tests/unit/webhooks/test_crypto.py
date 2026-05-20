import pytest
from app.webhooks.crypto import decrypt_secret, encrypt_secret, generate_webhook_secret
from cryptography.exceptions import InvalidTag


def test_generate_secret_is_64_hex_chars():
    secret = generate_webhook_secret()
    assert len(secret) == 64
    assert all(c in "0123456789abcdef" for c in secret)


def test_generate_secrets_are_unique():
    s1 = generate_webhook_secret()
    s2 = generate_webhook_secret()
    assert s1 != s2


def test_encrypt_decrypt_roundtrip():
    key = "a" * 64  # 32 bytes hex-encoded
    original = "my-super-secret-webhook-key-abc123"
    ciphertext = encrypt_secret(original, key)
    recovered = decrypt_secret(ciphertext, key)
    assert recovered == original


def test_encrypt_produces_different_ciphertexts_each_time():
    """AES-GCM uses a random nonce per encryption — same plaintext yields different ciphertext."""
    key = "b" * 64
    ct1 = encrypt_secret("same-secret", key)
    ct2 = encrypt_secret("same-secret", key)
    assert ct1 != ct2


def test_decrypt_with_wrong_key_raises():
    key = "c" * 64
    wrong_key = "d" * 64
    ciphertext = encrypt_secret("secret-value", key)
    with pytest.raises(InvalidTag):
        decrypt_secret(ciphertext, wrong_key)


def test_ciphertext_is_hex_string():
    key = "e" * 64
    ct = encrypt_secret("secret", key)
    bytes.fromhex(ct)  # raises ValueError if not valid hex


def test_ciphertext_length_is_nonce_plus_tag_plus_plaintext():
    """12-byte nonce + 16-byte GCM tag + len(plaintext) = total. Hex-encoded is 2x."""
    key = "f" * 64
    plaintext = "hello"
    ct = encrypt_secret(plaintext, key)
    expected_bytes = 12 + 16 + len(plaintext.encode())
    assert len(bytes.fromhex(ct)) == expected_bytes


def test_invalid_key_length_raises():
    """Key must be exactly 32 bytes (64 hex chars). 31-byte key is valid hex but wrong AES size."""
    with pytest.raises(ValueError):
        encrypt_secret("secret", "aa" * 31)  # 62 hex chars = 31 bytes, not a valid AES key size
