from app.tasks.celery_app import celery_app


def test_celery_app_name():
    assert celery_app.main == "memory-service"


def test_celery_acks_late():
    assert celery_app.conf.task_acks_late is True


def test_celery_prefetch_multiplier():
    assert celery_app.conf.worker_prefetch_multiplier == 1


def test_compress_task_registered():
    assert "memory.compress" in celery_app.tasks


def test_beat_schedule_contains_compress():
    assert "compress-old-memories" in celery_app.conf.beat_schedule


def test_beat_schedule_crontab_is_daily_2am():
    sched = celery_app.conf.beat_schedule["compress-old-memories"]["schedule"]
    assert sched.hour == {2}
    assert sched.minute == {0}
