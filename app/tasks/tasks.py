import asyncio
import os
import tempfile
import zipfile
from datetime import datetime
import time
from typing import List
from sqlalchemy import select
# from pathlib import Path
# from celery import current_task
from celery import group, chord
from app.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.models import Analysis, Project
from app.services.git_service import GitService
from app.services.code_analyzer import CodeAnalyzer
from app.utils.async_utils import robust_async_to_sync
import logging
import shutil

logger = logging.getLogger(__name__)


async def update_analysis_status(analysis_id: int, status: str, error_message: str = None):
    """Обновление статуса анализа в БД"""
    async with AsyncSessionLocal() as db:
        analysis = await db.get(Analysis, analysis_id)
        if analysis:
            analysis.status = status
            if error_message:
                analysis.error_message = error_message
            await db.commit()
            logger.info(f"✅ Updated analysis {analysis_id} status to {status}")


async def update_analysis_result(analysis_id: int, status: str, result: dict):
    """Обновление результата анализа в БД"""
    async with AsyncSessionLocal() as db:
        analysis = await db.get(Analysis, analysis_id)
        if analysis:
            analysis.status = status
            analysis.result = result
            await db.commit()
            logger.info(f"✅ Analysis {analysis_id} result updated in DB")


async def get_project_info(analysis_id: int):
    """Получает информацию о проекте для анализа"""
    async with AsyncSessionLocal() as db:
        analysis = await db.get(Analysis, analysis_id)
        if analysis:
            project = await db.get(Project, analysis.project_id)
            if project:
                return (project.id, project.repo_url, project.branch)
    return None


def _filter_dependencies_from_results(analysis_result: dict) -> dict:
    """Принудительно фильтрует ВСЕ зависимости из результатов"""

    # Список всех директорий зависимостей для фильтрации
    dependency_indicators = [
        'node_modules', 'vendor', 'bower_components', 'jspm_packages',
        'elm-stuff', 'deps', '__pycache__', '.pytest_cache', '.ruff_cache',
        '.mypy_cache', '.venv', 'venv', 'env', 'virtualenv',
        '.gradle', '.npm', '.yarn', '.pnp', 'Pods', 'DerivedData',
        'build', 'dist', 'out', 'target', 'bin', 'obj',
        '.next', '.nuxt', '.output', '.svelte-kit'
    ]

    # Фильтруем test_directories
    original_test_dirs = analysis_result['test_analysis']['test_directories']
    filtered_test_dirs = [
        d for d in original_test_dirs
        if not any(dep in d.lower() for dep in dependency_indicators)
    ]

    # Фильтруем file_structure
    original_files = analysis_result['file_structure']
    filtered_files = {
        k: v for k, v in original_files.items()
        if not any(dep in k.lower() for dep in dependency_indicators)
    }

    # Фильтруем largest_file если он из зависимостей
    largest_file = analysis_result['complexity_metrics']['largest_file']
    if any(dep in largest_file['path'].lower() for dep in dependency_indicators):
        # Находим следующий по размеру файл не из зависимостей
        valid_files = [
            (info['path'], info['size'])
            for info in filtered_files.values()
            if info['size'] > 0
        ]
        if valid_files:
            valid_files.sort(key=lambda x: x[1], reverse=True)
            analysis_result['complexity_metrics']['largest_file'] = {
                'path': valid_files[0][0],
                'size': valid_files[0][1]
            }
        else:
            analysis_result['complexity_metrics']['largest_file'] = {'path': '', 'size': 0}

    # Обновляем метрики на основе отфильтрованных данных
    analysis_result['test_analysis']['test_directories'] = filtered_test_dirs
    analysis_result['file_structure'] = filtered_files

    # Пересчитываем метрики
    analysis_result['metrics']['total_files'] = len(filtered_files)
    analysis_result['metrics']['code_files'] = sum(
        1 for file_info in filtered_files.values()
        if file_info.get('technology') and not file_info.get('is_test')
    )
    analysis_result['metrics']['test_files'] = sum(
        1 for file_info in filtered_files.values()
        if file_info.get('is_test')
    )

    # Пересчитываем общее количество строк и размер
    total_lines = 0
    total_size = 0
    for file_info in filtered_files.values():
        total_lines += file_info.get('lines', 0)
        total_size += file_info.get('size', 0)

    analysis_result['metrics']['total_lines'] = total_lines
    analysis_result['metrics']['total_size_kb'] = total_size / 1024

    # Пересчитываем средний размер файла
    if analysis_result['metrics']['code_files'] > 0:
        analysis_result['complexity_metrics']['avg_file_size'] = total_size / analysis_result['metrics']['code_files']
    else:
        analysis_result['complexity_metrics']['avg_file_size'] = 0

    # Пересчитываем расширения файлов на основе отфильтрованных данных
    extension_counts = {}
    for file_info in filtered_files.values():
        ext = file_info.get('extension', '')
        if ext:
            extension_counts[ext] = extension_counts.get(ext, 0) + 1
    analysis_result['complexity_metrics']['file_extensions'] = extension_counts

    logger.info(f"🔍 After dependency filtering:")
    logger.info(f"   - Project files: {len(filtered_files)}")
    logger.info(f"   - Removed {len(original_test_dirs) - len(filtered_test_dirs)} test dirs from dependencies")
    logger.info(f"   - Code files: {analysis_result['metrics']['code_files']}")
    logger.info(f"   - Test files: {analysis_result['metrics']['test_files']}")

    return analysis_result


async def perform_repository_analysis(analysis_id: int):
    """Асинхронная функция для анализа репозитория"""
    repo_path = None
    try:
        logger.info(f"🔍 Starting REAL repository analysis for ID: {analysis_id}")

        # Обновляем статус в БД
        await update_analysis_status(analysis_id, "cloning")

        # Получаем информацию о проекте
        project_info = await get_project_info(analysis_id)
        if not project_info:
            raise Exception("Project not found")

        project_id, repo_url, branch = project_info

        logger.info(f"📦 Cloning repository: {repo_url}, branch: {branch}")

        # Клонируем репозиторий (всегда новая копия)
        git_service = GitService()
        repo_path = await git_service.clone_repository(repo_url, branch)

        logger.info(f"✅ Repository cloned to: {repo_path}")

        try:
            await update_analysis_status(analysis_id, "analyzing")

            # Анализируем код с реальным анализатором
            code_analyzer = CodeAnalyzer()
            analysis_result = await code_analyzer.analyze_repository(repo_path)

            # 🔥 ПРИНУДИТЕЛЬНАЯ ФИЛЬТРАЦИЯ ВСЕХ ЗАВИСИМОСТЕЙ
            analysis_result = _filter_dependencies_from_results(analysis_result)

            logger.info(f"📊 REAL analysis completed:")
            logger.info(f"  - Technologies: {analysis_result.get('technologies', [])}")
            logger.info(f"  - Frameworks: {analysis_result.get('frameworks', [])}")
            logger.info(f"  - Project files: {analysis_result['metrics']['total_files']}")
            logger.info(f"  - Code files: {analysis_result['metrics']['code_files']}")
            logger.info(f"  - Test files: {analysis_result['metrics']['test_files']}")

            await update_analysis_status(analysis_id, "generating")

            # Рассчитываем coverage на основе реальных данных
            coverage_estimate = _calculate_real_coverage(analysis_result)

            # Формируем финальный результат ТОЛЬКО из реальных данных проекта
            result_data = {
                "technologies": analysis_result.get('technologies', []),
                "frameworks": analysis_result.get('frameworks', []),
                "file_structure_summary": {
                    "total_files": analysis_result['metrics']['total_files'],
                    "code_files": analysis_result['metrics']['code_files'],
                    "test_files": analysis_result['metrics']['test_files'],
                    "total_lines": analysis_result['metrics']['total_lines'],
                    "total_size_kb": round(analysis_result['metrics']['total_size_kb'], 2),
                },
                "test_analysis": {
                    "has_tests": analysis_result['test_analysis']['has_tests'],
                    "test_frameworks": analysis_result['test_analysis']['test_frameworks'],
                    "test_files_count": analysis_result['test_analysis']['test_files_count'],
                    "test_directories": analysis_result['test_analysis']['test_directories'],
                },
                "project_structure": analysis_result['project_structure'],
                "dependencies": analysis_result['dependencies'],
                "complexity_metrics": analysis_result['complexity_metrics'],
                "source": repo_url,
                "branch": branch,
                "coverage_estimate": coverage_estimate,
                "analysis_timestamp": datetime.utcnow().isoformat()
            }

            # Сохраняем РЕАЛЬНЫЙ результат в БД
            await update_analysis_result(
                analysis_id,
                "completed",
                result_data
            )

            logger.info(f"✅ REAL Repository analysis {analysis_id} completed successfully")
            logger.info(f"📈 Final coverage estimate: {coverage_estimate}%")

            return {
                "status": "success",
                "analysis_id": analysis_id,
                "technologies": analysis_result.get('technologies', []),
                "has_tests": analysis_result['test_analysis']['has_tests'],
                "test_frameworks": analysis_result['test_analysis']['test_frameworks'],
                "coverage": coverage_estimate
            }

        except Exception as e:
            logger.error(f"❌ Analysis failed: {e}")
            await update_analysis_status(analysis_id, "failed", str(e))
            raise

    except Exception as e:
        logger.error(f"❌ Repository analysis {analysis_id} failed: {str(e)}")
        await update_analysis_status(analysis_id, "failed", str(e))
        raise
    finally:
        if repo_path and os.path.exists(repo_path):
            logger.info(f"🧹 Cleaning up temporary repository: {repo_path}")
            git_service = GitService()
            git_service.cleanup(repo_path)
        else:
            logger.info(f"⚠️  No temporary repository to clean up for analysis {analysis_id}")


async def perform_zip_analysis(analysis_id: int, zip_path: str):
    """Асинхронная функция для анализа ZIP архива"""
    try:
        logger.info(f"📦 Starting REAL ZIP analysis for ID: {analysis_id}")

        await update_analysis_status(analysis_id, "extracting")

        # Распаковываем ZIP
        extract_path = tempfile.mkdtemp(prefix="extracted_")

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

        logger.info(f"✅ ZIP extracted to: {extract_path}")

        try:
            await update_analysis_status(analysis_id, "analyzing")

            # Анализируем код с реальным анализатором
            code_analyzer = CodeAnalyzer()
            analysis_result = await code_analyzer.analyze_repository(extract_path)

            # 🔥 ПРИНУДИТЕЛЬНАЯ ФИЛЬТРАЦИЯ ВСЕХ ЗАВИСИМОСТЕЙ
            analysis_result = _filter_dependencies_from_results(analysis_result)

            logger.info(f"📊 REAL ZIP analysis completed:")
            logger.info(f"  - Technologies: {analysis_result.get('technologies', [])}")
            logger.info(f"  - Project files: {analysis_result['metrics']['total_files']}")
            logger.info(f"  - Test files: {analysis_result['metrics']['test_files']}")

            await update_analysis_status(analysis_id, "generating")

            # Рассчитываем coverage на основе реальных данных
            coverage_estimate = _calculate_real_coverage(analysis_result)

            # Формируем результат из реальных данных
            result_data = {
                "technologies": analysis_result.get('technologies', []),
                "frameworks": analysis_result.get('frameworks', []),
                "file_structure_summary": {
                    "total_files": analysis_result['metrics']['total_files'],
                    "code_files": analysis_result['metrics']['code_files'],
                    "test_files": analysis_result['metrics']['test_files'],
                    "total_lines": analysis_result['metrics']['total_lines'],
                    "total_size_kb": round(analysis_result['metrics']['total_size_kb'], 2),
                },
                "test_analysis": {
                    "has_tests": analysis_result['test_analysis']['has_tests'],
                    "test_frameworks": analysis_result['test_analysis']['test_frameworks'],
                    "test_files_count": analysis_result['test_analysis']['test_files_count'],
                    "test_directories": analysis_result['test_analysis']['test_directories'],
                },
                "project_structure": analysis_result['project_structure'],
                "dependencies": analysis_result['dependencies'],
                "complexity_metrics": analysis_result['complexity_metrics'],
                "source": "ZIP Archive",
                "branch": "main",
                "coverage_estimate": coverage_estimate,
                "analysis_timestamp": datetime.utcnow().isoformat()
            }

            # Сохраняем в БД
            await update_analysis_result(
                analysis_id,
                "completed",
                result_data
            )

            logger.info(f"✅ ZIP analysis {analysis_id} completed")

            return {
                "status": "success",
                "analysis_id": analysis_id,
                "technologies": analysis_result.get('technologies', []),
                "has_tests": analysis_result['test_analysis']['has_tests'],
                "test_frameworks": analysis_result['test_analysis']['test_frameworks'],
                "coverage": coverage_estimate
            }

        finally:
            # Очищаем временные файлы
            shutil.rmtree(extract_path, ignore_errors=True)
            if os.path.exists(zip_path):
                os.remove(zip_path)

    except Exception as e:
        logger.error(f"❌ ZIP analysis {analysis_id} failed: {str(e)}")
        await update_analysis_status(analysis_id, "failed", str(e))
        raise


# =============================================================================
# ОСНОВНЫЕ ЗАДАЧИ АНАЛИЗА
# =============================================================================

@celery_app.task(bind=True, name="app.tasks.analyze_repository_task")
@robust_async_to_sync
async def analyze_repository_task(self, analysis_id: int):
    """Анализ репозитория из GitHub"""
    start_time = time.time()
    logger.info(f"🎯 Starting analyze_repository_task for analysis_id: {analysis_id}")

    try:
        # Обновляем прогресс
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 100, 'status': 'starting'}
        )

        result = await perform_repository_analysis(analysis_id)
        execution_time = time.time() - start_time

        logger.info(f"✅ Analysis {analysis_id} completed in {execution_time:.2f}s")
        return result

    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"❌ Analysis {analysis_id} failed after {execution_time:.2f}s: {e}")

        # Обновляем статус в БД при ошибке
        try:
            await update_analysis_status(analysis_id, "failed", str(e))
        except Exception as db_error:
            logger.error(f"Failed to update analysis status: {db_error}")

        return {
            "status": "error",
            "analysis_id": analysis_id,
            "error": str(e),
            "execution_time": execution_time
        }


@celery_app.task(bind=True, name="app.tasks.analyze_zip_task")
@robust_async_to_sync
async def analyze_zip_task(self, analysis_id: int, zip_path: str):
    """Анализ ZIP архива"""
    start_time = time.time()
    logger.info(f"🎯 Starting analyze_zip_task for analysis_id: {analysis_id}")

    try:
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 100, 'status': 'starting'}
        )

        result = await perform_zip_analysis(analysis_id, zip_path)
        execution_time = time.time() - start_time

        logger.info(f"✅ ZIP analysis {analysis_id} completed in {execution_time:.2f}s")
        return result

    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"❌ ZIP analysis {analysis_id} failed after {execution_time:.2f}s: {str(e)}")

        try:
            await update_analysis_status(analysis_id, "failed", str(e))
        except Exception as db_error:
            logger.error(f"Failed to update analysis status: {db_error}")

        return {
            "status": "error",
            "analysis_id": analysis_id,
            "error": str(e),
            "execution_time": execution_time
        }


# =============================================================================
# ПАРАЛЛЕЛЬНЫЕ ЗАДАЧИ ДЛЯ ГРУППОВОЙ ОБРАБОТКИ
# =============================================================================

@celery_app.task(bind=True, name="app.tasks.batch_analyze_repositories_task")
def batch_analyze_repositories_task(self, analysis_ids: List[int]):
    """Параллельный анализ нескольких репозиториев"""
    logger.info(f"🚀 Starting batch analysis for {len(analysis_ids)} repositories")

    # Создаем группу задач для параллельного выполнения
    job = group(
        analyze_repository_task.s(analysis_id)
        for analysis_id in analysis_ids
    )

    result = job.apply_async()

    return {
        "status": "started",
        "total_tasks": len(analysis_ids),
        "task_group_id": result.id,
        "analysis_ids": analysis_ids
    }


@celery_app.task(bind=True, name="app.tasks.batch_analyze_zips_task")
def batch_analyze_zips_task(self, analysis_data: List[dict]):
    """Параллельный анализ нескольких ZIP архивов"""
    logger.info(f"🚀 Starting batch ZIP analysis for {len(analysis_data)} archives")

    tasks = []
    for data in analysis_data:
        task = analyze_zip_task.s(data['analysis_id'], data['zip_path'])
        tasks.append(task)

    job = group(tasks)
    result = job.apply_async()

    return {
        "status": "started",
        "total_tasks": len(analysis_data),
        "task_group_id": result.id,
        "analysis_data": analysis_data
    }


# =============================================================================
# ЗАДАЧИ ГЕНЕРАЦИИ ТЕСТОВ
# =============================================================================

@celery_app.task(bind=True, name="app.tasks.parallel_test_generation_task")
@robust_async_to_sync
async def parallel_test_generation_task(self, project_id: int, test_config: dict):
    """Параллельная генерация разных типов тестов"""
    try:
        from app.services.generate_pipeline import test_generation_pipeline

        logger.info(f"🚀 Starting parallel test generation for project {project_id}")

        # Получаем проект и анализ
        async with AsyncSessionLocal() as db:
            project = await db.get(Project, project_id)
            if not project:
                raise Exception("Project not found")

            # Получаем последний анализ
            analysis_result = await db.execute(
                select(Analysis)
                .where(
                    Analysis.project_id == project_id,
                    Analysis.status == "completed"
                )
                .order_by(Analysis.created_at.desc())
                .limit(1)
            )
            analysis = analysis_result.scalar_one_or_none()

        if not analysis:
            raise Exception("No completed analysis found")

        # Создаем задачи для разных типов тестов
        tasks = []

        if test_config.get("generate_unit_tests", True):
            unit_task = generate_unit_tests_task.s(project_id, test_config, analysis.result)
            tasks.append(unit_task)

        if test_config.get("generate_integration_tests", True):
            integration_task = generate_integration_tests_task.s(project_id, test_config, analysis.result)
            tasks.append(integration_task)

        if test_config.get("generate_e2e_tests", False):
            e2e_task = generate_e2e_tests_task.s(project_id, test_config, analysis.result)
            tasks.append(e2e_task)

        # Запускаем все задачи параллельно
        if tasks:
            job = group(tasks)
            group_result = job.apply_async()

            return {
                "status": "parallel_generation_started",
                "project_id": project_id,
                "task_group_id": group_result.id,
                "task_count": len(tasks)
            }
        else:
            return {"status": "no_tasks_created", "project_id": project_id}

    except Exception as e:
        logger.error(f"❌ Parallel test generation failed: {e}")
        raise


@celery_app.task(bind=True, name="app.tasks.generate_unit_tests_task")
@robust_async_to_sync
async def generate_unit_tests_task(self, project_id: int, test_config: dict, analysis_data: dict):
    """Генерация unit тестов - отдельная задача"""
    start_time = time.time()
    logger.info(f"🔧 Generating unit tests for project {project_id}")

    try:
        # Имитация генерации unit тестов (замените на реальную логику)
        self.update_state(state='PROGRESS', meta={'status': 'generating_unit_tests'})
        await asyncio.sleep(5)

        execution_time = time.time() - start_time

        return {
            "status": "success",
            "test_type": "unit",
            "project_id": project_id,
            "generated_tests": 15,
            "coverage_estimate": 65,
            "execution_time": execution_time
        }
    except Exception as e:
        logger.error(f"❌ Unit test generation failed: {e}")
        raise


@celery_app.task(bind=True, name="app.tasks.generate_integration_tests_task")
@robust_async_to_sync
async def generate_integration_tests_task(self, project_id: int, test_config: dict, analysis_data: dict):
    """Генерация интеграционных тестов - отдельная задача"""
    start_time = time.time()
    logger.info(f"🔧 Generating integration tests for project {project_id}")

    try:
        # Имитация генерации интеграционных тестов (замените на реальную логику)
        self.update_state(state='PROGRESS', meta={'status': 'generating_integration_tests'})
        await asyncio.sleep(3)

        execution_time = time.time() - start_time

        return {
            "status": "success",
            "test_type": "integration",
            "project_id": project_id,
            "generated_tests": 8,
            "coverage_estimate": 25,
            "execution_time": execution_time
        }
    except Exception as e:
        logger.error(f"❌ Integration test generation failed: {e}")
        raise


@celery_app.task(bind=True, name="app.tasks.generate_e2e_tests_task")
@robust_async_to_sync
async def generate_e2e_tests_task(self, project_id: int, test_config: dict, analysis_data: dict):
    """Генерация E2E тестов - отдельная задача"""
    start_time = time.time()
    logger.info(f"🔧 Generating E2E tests for project {project_id}")

    try:
        # Имитация генерации E2E тестов (замените на реальную логику)
        self.update_state(state='PROGRESS', meta={'status': 'generating_e2e_tests'})
        await asyncio.sleep(7)

        execution_time = time.time() - start_time

        return {
            "status": "success",
            "test_type": "e2e",
            "project_id": project_id,
            "generated_tests": 5,
            "coverage_estimate": 15,
            "execution_time": execution_time
        }
    except Exception as e:
        logger.error(f"❌ E2E test generation failed: {e}")
        raise


@celery_app.task(bind=True, name="app.tasks.batch_generate_tests_task")
def batch_generate_tests_task(self, projects_config: List[dict]):
    """Пакетная генерация тестов для нескольких проектов"""
    logger.info(f"🚀 Starting batch test generation for {len(projects_config)} projects")

    tasks = []
    for config in projects_config:
        task = parallel_test_generation_task.s(
            config['project_id'],
            config.get('test_config', {})
        )
        tasks.append(task)

    job = group(tasks)
    result = job.apply_async()

    return {
        "status": "started",
        "total_projects": len(projects_config),
        "task_group_id": result.id
    }


# =============================================================================
# ЗАДАЧИ МОНИТОРИНГА И УПРАВЛЕНИЯ
# =============================================================================

@celery_app.task(bind=True, name="app.tasks.monitor_analysis_progress_task")
def monitor_analysis_progress_task(self, analysis_ids: List[int]):
    """Мониторинг прогресса анализа нескольких проектов"""
    logger.info(f"📊 Monitoring progress for {len(analysis_ids)} analyses")

    # Создаем задачи для мониторинга
    monitoring_tasks = []
    for analysis_id in analysis_ids:
        task = check_analysis_status_task.s(analysis_id)
        monitoring_tasks.append(task)

    # Запускаем мониторинг
    job = group(monitoring_tasks)
    result = job.apply_async()

    return {
        "status": "monitoring_started",
        "monitoring_group_id": result.id,
        "analysis_ids": analysis_ids
    }


@celery_app.task(bind=True, name="app.tasks.check_analysis_status_task")
@robust_async_to_sync
async def check_analysis_status_task(self, analysis_id: int):
    """Проверка статуса конкретного анализа"""
    async with AsyncSessionLocal() as db:
        analysis = await db.get(Analysis, analysis_id)
        if analysis:
            return {
                "analysis_id": analysis_id,
                "status": analysis.status,
                "progress": self._get_progress_from_status(analysis.status),
                "has_result": analysis.result is not None,
                "coverage_estimate": analysis.result.get('coverage_estimate', 0) if analysis.result else 0
            }
        return {"analysis_id": analysis_id, "status": "not_found"}


def _get_progress_from_status(self, status: str) -> int:
    """Преобразует статус в процент прогресса"""
    progress_map = {
        "pending": 0,
        "cloning": 25,
        "analyzing": 50,
        "generating": 75,
        "completed": 100,
        "failed": 0
    }
    return progress_map.get(status, 0)


@celery_app.task(bind=True, name="app.tasks.get_task_group_status_task")
def get_task_group_status_task(self, group_id: str):
    """Получение статуса группы задач"""
    try:
        from celery.result import GroupResult

        group_result = GroupResult.restore(group_id, app=celery_app)

        if group_result:
            # Получаем результаты завершенных задач
            completed = group_result.completed_count()
            total = len(group_result)

            return {
                "group_id": group_id,
                "total_tasks": total,
                "completed_tasks": completed,
                "failed_tasks": group_result.failed_count(),
                "progress_percentage": int((completed / total) * 100) if total > 0 else 0,
                "ready": group_result.ready(),
                "successful": group_result.successful(),
                "results": group_result.results if group_result.ready() else None
            }
        else:
            return {"error": "Group not found", "group_id": group_id}

    except Exception as e:
        logger.error(f"Error getting group status: {e}")
        return {"error": str(e), "group_id": group_id}


# =============================================================================
# СЛУЖЕБНЫЕ И ТЕСТОВЫЕ ЗАДАЧИ
# =============================================================================

@celery_app.task(bind=True, name="app.tasks.test_dependency_filtering_task")
@robust_async_to_sync
async def test_dependency_filtering_task(self, repo_url: str, branch: str = "main"):
    """Тестовая задача для проверки фильтрации ВСЕХ зависимостей"""
    # Проверка на тестовую среду
    if os.getenv('ENVIRONMENT') not in ['testing', 'development']:
        logger.warning("Dependency filtering test should run only in test/development environment")
        return {"status": "skipped", "reason": "not_test_environment"}

    logger.info(f"🧪 Testing dependency filtering with: {repo_url}, branch: {branch}")

    try:
        git_service = GitService()
        repo_path = await git_service.clone_repository(repo_url, branch)

        code_analyzer = CodeAnalyzer()
        analysis_result = await code_analyzer.analyze_repository(repo_path)

        # Логируем критическую информацию ДО фильтрации
        logger.info(f"🧪 BEFORE DEPENDENCY FILTERING:")
        logger.info(f"🧪 Total files found: {analysis_result['metrics']['total_files']}")
        logger.info(f"🧪 Ignored dependency files: {analysis_result['metrics']['ignored_files']}")
        logger.info(f"🧪 Dependency files count: {analysis_result['metrics']['dependency_files_count']}")

        test_dirs_before = analysis_result['test_analysis']['test_directories']
        dependency_dirs_before = [
            d for d in test_dirs_before
            if any(dep in d.lower() for dep in [
                'node_modules', 'vendor', 'bower_components', '__pycache__',
                '.venv', 'venv', '.gradle', '.yarn'
            ])
        ]
        logger.info(f"🧪 Dependency test dirs before: {len(dependency_dirs_before)}")

        # Применяем фильтрацию ВСЕХ зависимостей
        analysis_result = _filter_dependencies_from_results(analysis_result)

        # Логируем ПОСЛЕ фильтрации
        logger.info(f"🧪 AFTER DEPENDENCY FILTERING:")
        logger.info(f"🧪 Clean project files: {analysis_result['metrics']['total_files']}")
        logger.info(f"🧪 Clean test files: {analysis_result['metrics']['test_files']}")

        test_dirs_after = analysis_result['test_analysis']['test_directories']
        dependency_dirs_after = [
            d for d in test_dirs_after
            if any(dep in d.lower() for dep in [
                'node_modules', 'vendor', 'bower_components', '__pycache__',
                '.venv', 'venv', '.gradle', '.yarn'
            ])
        ]
        logger.info(f"🧪 Dependency test dirs after: {len(dependency_dirs_after)}")

        if dependency_dirs_after:
            logger.error(f"❌ DEPENDENCIES STILL FOUND: {dependency_dirs_after}")
            return {
                "status": "error",
                "message": "Dependencies still present in results",
                "remaining_dependencies": dependency_dirs_after
            }
        else:
            logger.info("✅ SUCCESS: All dependencies filtered out!")
            return {
                "status": "success",
                "message": "All dependencies successfully filtered",
                "before_filtering": {
                    "total_files": analysis_result['metrics']['total_files'],
                    "ignored_files": analysis_result['metrics']['ignored_files'],
                    "dependency_test_dirs": len(dependency_dirs_before)
                },
                "after_filtering": {
                    "project_files": analysis_result['metrics']['total_files'],
                    "test_files": analysis_result['metrics']['test_files'],
                    "dependency_test_dirs": len(dependency_dirs_after)
                }
            }

    except Exception as e:
        logger.error(f"❌ Dependency filtering test failed: {e}")
        raise
    finally:
        if 'repo_path' in locals():
            git_service.cleanup(repo_path)


@celery_app.task(bind=True, name="app.tasks.diagnostic_task")
@robust_async_to_sync
async def diagnostic_task(self, test_type: str = "basic"):
    """Диагностическая задача для тестирования асинхронности"""
    logger.info(f"🔧 Starting diagnostic task: {test_type}")

    try:
        if test_type == "basic":
            logger.info("🔄 Testing asyncio.sleep...")
            await asyncio.sleep(2)
            logger.info("✅ asyncio.sleep completed")
            return {"status": "success", "test": "basic_async"}

        elif test_type == "db":
            logger.info("🔄 Testing database connection...")
            async with AsyncSessionLocal() as db:
                result = await db.execute("SELECT 1")
                value = result.scalar()
                logger.info(f"✅ Database test completed: {value}")
            return {"status": "success", "test": "database"}

        elif test_type == "git":
            logger.info("🔄 Testing Git operations...")
            git_service = GitService()
            repo_path = await git_service.clone_repository(
                "https://github.com/octocat/Hello-World",
                "main"
            )
            logger.info(f"✅ Git clone completed: {repo_path}")
            git_service.cleanup(repo_path)
            return {"status": "success", "test": "git"}

        elif test_type == "parallel":
            logger.info("🔄 Testing parallel execution...")
            # Создаем несколько задач для параллельного выполнения
            tasks = []
            for i in range(3):
                task = diagnostic_parallel_subtask.s(i)
                tasks.append(task)

            job = group(tasks)
            result = job.apply_async()

            return {
                "status": "parallel_test_started",
                "task_group_id": result.id,
                "subtask_count": 3
            }

    except Exception as e:
        logger.error(f"❌ Diagnostic task failed: {e}", exc_info=True)
        return {"status": "error", "test": test_type, "error": str(e)}


@celery_app.task(bind=True, name="app.tasks.diagnostic_parallel_subtask")
@robust_async_to_sync
async def diagnostic_parallel_subtask(self, task_id: int):
    """Вспомогательная задача для тестирования параллелизма"""
    logger.info(f"🔧 Starting parallel subtask {task_id}")
    await asyncio.sleep(2)  # Имитация работы
    return {"status": "success", "task_id": task_id, "result": f"subtask_{task_id}_completed"}


@celery_app.task(bind=True, name="app.tasks.cleanup_old_analyses_task")
@robust_async_to_sync
async def cleanup_old_analyses_task(self, days_old: int = 30):
    """Очистка старых анализов"""
    try:
        from datetime import timedelta
        from sqlalchemy import delete

        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        async with AsyncSessionLocal() as db:
            # Находим анализы для удаления
            result = await db.execute(
                select(Analysis).where(Analysis.created_at < cutoff_date)
            )
            old_analyses = result.scalars().all()

            # Удаляем их
            deleted_count = 0
            for analysis in old_analyses:
                await db.delete(analysis)
                deleted_count += 1

            await db.commit()

            logger.info(f"🧹 Cleaned up {deleted_count} analyses older than {days_old} days")
            return {
                "status": "success",
                "deleted_count": deleted_count,
                "cutoff_date": cutoff_date.isoformat()
            }

    except Exception as e:
        logger.error(f"❌ Cleanup task failed: {e}")
        return {"status": "error", "error": str(e)}


def _calculate_real_coverage(analysis_result):
    """Рассчитывает coverage на основе реальных данных о тестах"""
    if not analysis_result['test_analysis']['has_tests']:
        return 0

    total_files = analysis_result['metrics']['code_files']
    test_files = analysis_result['metrics']['test_files']

    if total_files == 0:
        return 0

    # Базовый расчет на основе соотношения тестовых файлов к общим
    file_coverage_ratio = test_files / total_files

    # Учитываем наличие тестовых фреймворков
    framework_bonus = len(analysis_result['test_analysis']['test_frameworks']) * 5

    # Учитываем тестовые директории (организованная структура тестов)
    structure_bonus = len(analysis_result['test_analysis']['test_directories']) * 3

    coverage = min(85, int(file_coverage_ratio * 70 + framework_bonus + structure_bonus))

    return max(10, coverage)  # Минимум 10% если есть тесты