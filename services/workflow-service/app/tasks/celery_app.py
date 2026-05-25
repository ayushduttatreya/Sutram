# app/tasks/celery_app.py
from celery import Celery
from celery.signals import worker_process_init

from app.settings import get_settings


def create_celery_app() -> Celery:
    settings = get_settings()
    app = Celery(
        "workflow-service",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        # autodiscovery via include= (not side-effect import)
        include=["app.tasks.execute", "app.tasks.recover", "app.webhooks.tasks"],
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        result_expires=3600,
    )
    app.conf.beat_schedule = {
        "recovery-scan": {
            "task": "workflow.recover_stale_executions",
            "schedule": 60.0,
        },
    }
    return app


celery_app = create_celery_app()

# Import tasks so they are registered on the celery_app instance at import time.
# include= handles autodiscovery for running workers; this import handles test collection.
import app.tasks.execute  # noqa: E402, F401
import app.tasks.recover  # noqa: E402, F401
import app.webhooks.tasks  # noqa: F401, E402 — registers deliver_webhook with celery_app


@worker_process_init.connect  # type: ignore[untyped-decorator]
def on_worker_process_init(**kwargs: object) -> None:
    """Initialise DB and Redis connections once per worker process at startup."""
    from app.dependencies import init_db, init_redis

    init_db()
    init_redis()
