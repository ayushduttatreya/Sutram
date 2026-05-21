# tests/unit/test_auth_middleware.py
import time
import uuid
from unittest.mock import patch

import pytest
from app.middleware.auth import AuthDep
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt


def make_jwt(tenant_id: str, secret: str = "test-secret", expired: bool = False) -> str:
    exp = int(time.time()) + (-10 if expired else 3600)
    return jwt.encode(
        {"tenant_id": tenant_id, "sub": tenant_id, "exp": exp},
        secret,
        algorithm="HS256",
    )


@pytest.fixture
def test_app():
    app = FastAPI()

    @app.get("/test")
    async def protected(tenant_id: AuthDep):
        return {"tenant_id": str(tenant_id)}

    return app


def test_valid_jwt_returns_tenant_id(test_app):
    tenant_id = str(uuid.uuid4())
    token = make_jwt(tenant_id)
    with patch("app.middleware.auth.get_settings") as mock:
        mock.return_value.jwt_secret = "test-secret"
        mock.return_value.jwt_algorithm = "HS256"
        client = TestClient(test_app)
        resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == tenant_id


def test_missing_auth_header_returns_401(test_app):
    client = TestClient(test_app, raise_server_exceptions=False)
    resp = client.get("/test")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "missing_token"


def test_invalid_token_returns_401(test_app):
    with patch("app.middleware.auth.get_settings") as mock:
        mock.return_value.jwt_secret = "test-secret"
        mock.return_value.jwt_algorithm = "HS256"
        client = TestClient(test_app, raise_server_exceptions=False)
        resp = client.get("/test", headers={"Authorization": "Bearer not.a.valid.token"})
    assert resp.status_code == 401


def test_expired_token_returns_401_with_token_expired_detail(test_app):
    tenant_id = str(uuid.uuid4())
    token = make_jwt(tenant_id, expired=True)
    with patch("app.middleware.auth.get_settings") as mock:
        mock.return_value.jwt_secret = "test-secret"
        mock.return_value.jwt_algorithm = "HS256"
        client = TestClient(test_app, raise_server_exceptions=False)
        resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "token_expired"


def test_token_missing_tenant_id_returns_401(test_app):
    token = jwt.encode(
        {"sub": "user123", "exp": int(time.time()) + 3600},
        "test-secret",
        algorithm="HS256",
    )
    with patch("app.middleware.auth.get_settings") as mock:
        mock.return_value.jwt_secret = "test-secret"
        mock.return_value.jwt_algorithm = "HS256"
        client = TestClient(test_app, raise_server_exceptions=False)
        resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_malformed_tenant_id_uuid_returns_401(test_app):
    """A valid JWT with a non-UUID tenant_id should return 401."""
    import time as _time

    token = jwt.encode(
        {"tenant_id": "not-a-uuid", "sub": "user", "exp": int(_time.time()) + 3600},
        "test-secret",
        algorithm="HS256",
    )
    with patch("app.middleware.auth.get_settings") as mock:
        mock.return_value.jwt_secret = "test-secret"
        mock.return_value.jwt_algorithm = "HS256"
        client = TestClient(test_app, raise_server_exceptions=False)
        resp = client.get("/test", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
