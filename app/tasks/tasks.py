import asyncio
import os
import tempfile
import zipfile
from datetime import datetime
from celery import current_task
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

async def perform_repository_analysis(analysis_id: int):
    """Асинхронная функция для анализа репозитория"""
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

        # Клонируем репозиторий
        git_service = GitService()
        repo_path = await git_service.clone_repository(repo_url, branch)

        logger.info(f"✅ Repository cloned to: {repo_path}")

        try:
            await update_analysis_status(analysis_id, "analyzing")

            # Анализируем код с реальным анализатором
            code_analyzer = CodeAnalyzer()
            analysis_result = await code_analyzer.analyze_repository(repo_path)

            logger.info(f"📊 REAL analysis completed:")
            logger.info(f"  - Technologies: {analysis_result.get('technologies', [])}")
            logger.info(f"  - Frameworks: {analysis_result.get('frameworks', [])}")
            logger.info(f"  - Total files: {analysis_result['metrics']['total_files']}")
            logger.info(f"  - Code files: {analysis_result['metrics']['code_files']}")
            logger.info(f"  - Test files: {analysis_result['metrics']['test_files']}")

            await update_analysis_status(analysis_id, "generating")

            # Рассчитываем coverage на основе реальных данных
            coverage_estimate = _calculate_real_coverage(analysis_result)

            # Формируем финальный результат ТОЛЬКО из реальных данных
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
        finally:
            # Очищаем временные файлы
            git_service.cleanup(repo_path)

    except Exception as e:
        logger.error(f"❌ Repository analysis {analysis_id} failed: {str(e)}")
        await update_analysis_status(analysis_id, "failed", str(e))
        raise

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

            logger.info(f"📊 REAL ZIP analysis completed:")
            logger.info(f"  - Technologies: {analysis_result.get('technologies', [])}")
            logger.info(f"  - Total files: {analysis_result['metrics']['total_files']}")
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

@celery_app.task(bind=True, name="app.tasks.analyze_repository_task")
@robust_async_to_sync
async def analyze_repository_task(self, analysis_id: int):
    """Анализ репозитория из GitHub"""
    logger.info(f"🎯 Starting analyze_repository_task for analysis_id: {analysis_id}")
    try:
        result = await perform_repository_analysis(analysis_id)
        logger.info(f"✅ analyze_repository_task completed for analysis_id: {analysis_id}")
        return result
    except Exception as e:
        logger.error(f"❌ analyze_repository_task failed for analysis_id {analysis_id}: {str(e)}")
        return {
            "status": "error",
            "analysis_id": analysis_id,
            "error": str(e)
        }

@celery_app.task(bind=True, name="app.tasks.analyze_zip_task")
@robust_async_to_sync
async def analyze_zip_task(self, analysis_id: int, zip_path: str):
    """Анализ ZIP архива"""
    logger.info(f"🎯 Starting analyze_zip_task for analysis_id: {analysis_id}")
    try:
        result = await perform_zip_analysis(analysis_id, zip_path)
        logger.info(f"✅ analyze_zip_task completed for analysis_id: {analysis_id}")
        return result
    except Exception as e:
        logger.error(f"❌ analyze_zip_task failed for analysis_id {analysis_id}: {str(e)}")
        return {
            "status": "error",
            "analysis_id": analysis_id,
            "error": str(e)
        }


@celery_app.task(bind=True, name="app.tasks.diagnostic_task")
@robust_async_to_sync
async def diagnostic_task(self, test_type: str = "basic"):
    """Диагностическая задача для тестирования асинхронности"""
    logger.info(f"🔧 Starting diagnostic task: {test_type}")

    try:
        if test_type == "basic":
            # Тест базовой асинхронности
            logger.info("🔄 Testing asyncio.sleep...")
            await asyncio.sleep(2)
            logger.info("✅ asyncio.sleep completed")

            return {"status": "success", "test": "basic_async"}

        elif test_type == "db":
            # Тест работы с БД
            logger.info("🔄 Testing database connection...")
            async with AsyncSessionLocal() as db:
                result = await db.execute("SELECT 1")
                value = result.scalar()
                logger.info(f"✅ Database test completed: {value}")

            return {"status": "success", "test": "database"}

        elif test_type == "git":
            # Тест Git операций
            logger.info("🔄 Testing Git operations...")
            git_service = GitService()
            repo_path = await git_service.clone_repository(
                "https://github.com/octocat/Hello-World",
                "main"
            )
            logger.info(f"✅ Git clone completed: {repo_path}")

            # Очистка
            git_service.cleanup(repo_path)
            return {"status": "success", "test": "git"}

    except Exception as e:
        logger.error(f"❌ Diagnostic task failed: {e}", exc_info=True)
        return {"status": "error", "test": test_type, "error": str(e)}

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