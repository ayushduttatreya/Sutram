# services/memory-service/app/tasks/celery_app.py
from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init

from app.settings import get_settings


def create_celery_app() -> Celery:
    settings = get_settings()
    app = Celery(
        "memory-service",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=["app.tasks.compress"],
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        beat_schedule={
            "compress-old-memories": {
                "task": "memory.compress",
                "schedule": crontab(hour=2, minute=0),
            },
        },
    )
    return app


celery_app = create_celery_app()


@worker_process_init.connect  # type: ignore[untyped-decorator]
def on_worker_process_init(**kwargs: object) -> None:
    from app.dependencies import init_db, init_embedding, init_redis

    init_db()
    init_redis()
    init_embedding()


import app.tasks.compress  # noqa: E402, F401
