# tests/unit/test_main.py
from unittest.mock import MagicMock, patch


def test_app_creates_without_error():
    with (
        patch("app.main.init_db"),
        patch("app.main.init_redis"),
        patch("app.main.get_redis_streams", return_value=MagicMock()),
    ):
        from app.main import create_app

        application = create_app()
        assert application.title == "Sutram Observability Service"
        assert application.version == "0.1.0"
