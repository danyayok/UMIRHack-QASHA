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

        # 🔥 КРИТИЧЕСКИЕ НАСТРОЙКИ ДЛЯ ПАРАЛЛЕЛИЗМА
        worker_prefetch_multiplier=1,  # Каждый воркер берет по 1 задаче
        task_acks_late=True,  # Подтверждение после выполнения
        worker_max_tasks_per_child=1000,  # Перезапуск воркеров
        worker_concurrency=4,  # Количество процессов на воркер

        # 🔥 РАСПРЕДЕЛЕНИЕ ПО ОЧЕРЕДЯМ
        task_routes={
            'app.tasks.tasks.analyze_repository_task': {'queue': 'analysis'},
            'app.tasks.tasks.analyze_zip_task': {'queue': 'analysis'},
            'app.tasks.tasks.batch_analyze_repositories_task': {'queue': 'batch_analysis'},
            'app.tasks.tasks.batch_analyze_zips_task': {'queue': 'batch_analysis'},
            'app.tasks.tasks.parallel_test_generation_task': {'queue': 'generation'},
            'app.tasks.tasks.generate_unit_tests_task': {'queue': 'generation'},
            'app.tasks.tasks.generate_integration_tests_task': {'queue': 'generation'},
            'app.tasks.tasks.generate_e2e_tests_task': {'queue': 'generation'},
            'app.tasks.tasks.batch_generate_tests_task': {'queue': 'batch_generation'},
            'app.tasks.tasks.monitor_analysis_progress_task': {'queue': 'monitoring'},
            'app.tasks.tasks.cleanup_old_analyses_task': {'queue': 'maintenance'},
        },

        # Приоритеты задач
        task_default_priority=5,
        task_queue_max_priority=10,

        # Таймауты
        task_time_limit=30 * 60,  # 30 минут
        task_soft_time_limit=25 * 60,

        # Ретри
        task_retry=True,
        task_retry_backoff=True,
        task_retry_backoff_max=600,  # 10 минут
        task_retry_jitter=True,
    )

    return celery_app


celery_app = create_celery_app()
celery_app.autodiscover_tasks(['app.tasks'], related_name='tasks')