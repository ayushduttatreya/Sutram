# tests/unit/test_main.py
from unittest.mock import patch


def test_app_creates_without_error():
    with patch("app.main.init_clients"), patch("app.main.close_clients"):
        from app.main import create_app
        application = create_app()
        assert application.title == "Sutram API Gateway"
        assert application.version == "0.1.0"


def test_health_endpoint_returns_ok():
    with patch("app.main.init_clients"), patch("app.main.close_clients"):
        from importlib import reload
        import app.main as m
        reload(m)
        application = m.create_app()
        from fastapi.testclient import TestClient
        client = TestClient(application)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "service": "api-gateway"}
