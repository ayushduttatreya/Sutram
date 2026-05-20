import uuid
from unittest.mock import patch

import pytest
from sutram_core.middleware.auth import AuthError, decode_jwt
from sutram_core.middleware.internal_auth import InternalAuthError, verify_internal_token


def make_token(tenant_id: str, user_id: str, secret: str = "test-secret") -> str:
    import time

    from jose import jwt

    return jwt.encode(
        {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "sub": user_id,
            "exp": int(time.time()) + 3600,
        },
        secret,
        algorithm="HS256",
    )


def test_decode_valid_jwt():
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    token = make_token(tenant_id, user_id)

    with (
        patch("sutram_core.middleware.auth.get_jwt_secret", return_value="test-secret"),
        patch("sutram_core.middleware.auth.get_jwt_algorithm", return_value="HS256"),
    ):
        claims = decode_jwt(token, algorithm="HS256")

    assert claims["tenant_id"] == tenant_id
    assert claims["user_id"] == user_id


def test_decode_invalid_jwt_raises_auth_error():
    with (
        patch("sutram_core.middleware.auth.get_jwt_secret", return_value="test-secret"),
        pytest.raises(AuthError),
    ):
        decode_jwt("not.a.valid.token", algorithm="HS256")


def test_decode_jwt_missing_tenant_id_raises():
    from jose import jwt

    token = jwt.encode({"sub": "user123"}, "test-secret", algorithm="HS256")
    with (
        patch("sutram_core.middleware.auth.get_jwt_secret", return_value="test-secret"),
        pytest.raises(AuthError, match="Missing tenant_id"),
    ):
        decode_jwt(token, algorithm="HS256")


def test_verify_internal_token_valid():
    verify_internal_token("dev-token", expected="dev-token")


def test_verify_internal_token_invalid_raises():
    with pytest.raises(InternalAuthError):
        verify_internal_token("wrong-token", expected="dev-token")


def test_verify_internal_token_valid_and_invalid():
    # Both branches must complete without short-circuiting
    # (constant-time comparison — this just verifies it doesn't raise on equal)
    verify_internal_token("abc", expected="abc")
    with pytest.raises(InternalAuthError):
        verify_internal_token("abc", expected="xyz")


def test_decode_jwt_wrong_secret_raises():
    from jose import jwt

    token = jwt.encode(
        {"tenant_id": str(uuid.uuid4()), "sub": "user", "exp": 9999999999},
        "wrong-secret",
        algorithm="HS256",
    )
    with (
        patch("sutram_core.middleware.auth.get_jwt_secret", return_value="correct-secret"),
        patch("sutram_core.middleware.auth.get_jwt_algorithm", return_value="HS256"),
        pytest.raises(AuthError),
    ):
        decode_jwt(token)


def test_decode_jwt_expired_token_sets_expired_flag():
    import time

    from jose import jwt

    token = jwt.encode(
        {"tenant_id": str(uuid.uuid4()), "sub": "user", "exp": int(time.time()) - 10},
        "test-secret",
        algorithm="HS256",
    )
    with (
        patch("sutram_core.middleware.auth.get_jwt_secret", return_value="test-secret"),
        patch("sutram_core.middleware.auth.get_jwt_algorithm", return_value="HS256"),
        pytest.raises(AuthError) as exc_info,
    ):
        decode_jwt(token)
    assert exc_info.value.expired is True


def test_decode_jwt_uses_algorithm_from_settings():
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    token = make_token(tenant_id, user_id)  # uses HS256

    # Don't pass algorithm — should read from settings (HS256)
    with (
        patch("sutram_core.middleware.auth.get_jwt_secret", return_value="test-secret"),
        patch("sutram_core.middleware.auth.get_jwt_algorithm", return_value="HS256"),
    ):
        claims = decode_jwt(token)  # no algorithm arg
    assert claims["tenant_id"] == tenant_id


def test_decode_jwt_missing_exp_raises():
    from jose import jwt

    token = jwt.encode(
        {"tenant_id": str(uuid.uuid4()), "sub": "user"},  # no exp
        "test-secret",
        algorithm="HS256",
    )
    with (
        patch("sutram_core.middleware.auth.get_jwt_secret", return_value="test-secret"),
        patch("sutram_core.middleware.auth.get_jwt_algorithm", return_value="HS256"),
        pytest.raises(AuthError, match="Missing exp"),
    ):
        decode_jwt(token)


def test_verify_internal_token_empty_string_raises():
    with pytest.raises(InternalAuthError):
        verify_internal_token("", expected="dev-token")
