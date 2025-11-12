from celery import Celery
from app.core.config import settings


def create_celery_app():
    celery_app = Celery(
        "worker",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
    )

    celery_app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=30 * 60,
        worker_hijack_root_logger=False,  # Важно для корректного логирования
        task_always_eager=False,  # Убедитесь, что это False
        imports=["app.tasks.tasks"],
        task_routes={
            'app.tasks.tasks.analyze_repository_task': {'queue': 'celery'},
            'app.tasks.tasks.analyze_zip_task': {'queue': 'celery'},
        },
    )

    return celery_app


celery_app = create_celery_app()

# Автоматически регистрируем задачи
celery_app.autodiscover_tasks(['app.tasks'], related_name='tasks')