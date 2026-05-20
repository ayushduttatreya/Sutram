from unittest.mock import patch


def test_app_creates_without_error():
    with (
        patch("app.dependencies.init_db"),
        patch("app.dependencies.init_redis"),
        patch("app.dependencies.init_embedding"),
    ):
        from app.main import create_app
        app = create_app()
        assert app.title == "Sutram Memory Service"
        assert app.version == "0.1.0"


def test_app_openapi_accessible():
    with (
        patch("app.dependencies.init_db"),
        patch("app.dependencies.init_redis"),
        patch("app.dependencies.init_embedding"),
    ):
        from app.main import create_app
        app = create_app()
        schema = app.openapi()
        assert schema["info"]["title"] == "Sutram Memory Service"
