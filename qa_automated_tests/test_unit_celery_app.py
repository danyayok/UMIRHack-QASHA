import pytest
from unittest.mock import patch, MagicMock
from app.celery_app import create_celery_app


@patch("app.celery_app.settings")
def test_create_celery_app_success(mock_settings):
    mock_settings.CELERY_BROKER_URL = "redis://localhost:6379/0"
    mock_settings.CELERY_RESULT_BACKEND = "redis://localhost:6379/0"

    celery_app = create_celery_app()

    assert celery_app.conf.broker_url == "redis://localhost:6379/0"
    assert celery_app.conf.result_backend == "redis://localhost:6379/0"
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"
    assert celery_app.conf.accept_content == ["json"]
    assert celery_app.conf.timezone == "UTC"
    assert celery_app.conf.enable_utc is True
    assert celery_app.conf.worker_prefetch_multiplier == 1
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.worker_max_tasks_per_child == 1000
    assert celery_app.conf.worker_concurrency == 4
    assert celery_app.conf.task_default_priority == 5
    assert celery_app.conf.task_queue_max_priority == 10
    assert celery_app.conf.task_time_limit == 1800
    assert celery_app.conf.task_soft_time_limit == 1500
    assert celery_app.conf.task_retry is True
    assert celery_app.conf.task_retry_backoff is True
    assert celery_app.conf.task_retry_backoff_max == 600
    assert celery_app.conf.task_retry_jitter is True

    expected_routes = {
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
    }
    assert celery_app.conf.task_routes == expected_routes


@patch("app.celery_app.settings")
def test_create_celery_app_invalid_broker_url(mock_settings):
    mock_settings.CELERY_BROKER_URL = ""
    mock_settings.CELERY_RESULT_BACKEND = "redis://localhost:6379/0"

    celery_app = create_celery_app()

    assert celery_app.conf.broker_url == ""
    assert celery_app.conf.result_backend == "redis://localhost:6379/0"


@patch("app.celery_app.settings")
def test_create_celery_app_invalid_result_backend(mock_settings):
    mock_settings.CELERY_BROKER_URL = "redis://localhost:6379/0"
    mock_settings.CELERY_RESULT_BACKEND = ""

    celery_app = create_celery_app()

    assert celery_app.conf.broker_url == "redis://localhost:6379/0"
    assert celery_app.conf.result_backend == ""


@patch("app.celery_app.settings")
def test_create_celery_app_missing_settings(mock_settings):
    mock_settings.CELERY_BROKER_URL = None
    mock_settings.CELERY_RESULT_BACKEND = None

    celery_app = create_celery_app()

    assert celery_app.conf.broker_url is None
    assert celery_app.conf.result_backend is None