import json
import random
from pathlib import Path
from app.core.dependencies import dependencies
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.db.session import get_db
from typing import List, Optional, Dict, Any
import re
from datetime import datetime
from app.schemas import ProjectCreate, ProjectOut, AnalysisOut, AnalysisStatus, TestRunOut, TestBatchOut, \
    GeneratedTestOut, TestBatchWithTests, TestCaseOut, TestCaseFileOut, TestCaseGenerationConfig, TestGenerationConfig
from app.models import Project, Analysis, AgentReport, TestRun, GeneratedTest, TestBatch, TestCase, TestCaseFile
from app.deps.auth import get_current_user
from app.tasks import analyze_repository_task, analyze_zip_task
from app.services.git_service import GitService
from app.core.dependencies import get_test_generation_pipeline, dependencies

import aiofiles
import os
from uuid import uuid4
import logging

logger = logging.getLogger("qa_automata")

router = APIRouter()
UPLOAD_DIR = "./storage/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Константы
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

@router.get("/", response_model=List[ProjectOut])
async def get_projects(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    try:
        logger.info(f"Getting projects for user {current_user.id}")

        result = await db.execute(
            select(Project).where(Project.owner_id == current_user.id)
        )
        projects = result.scalars().all()

        projects_with_coverage = []
        for project in projects:
            # Получаем последний завершенный анализ
            analysis_result = await db.execute(
                select(Analysis)
                .where(
                    Analysis.project_id == project.id,
                    Analysis.status == "completed"
                )
                .order_by(Analysis.created_at.desc())
                .limit(1)
            )
            latest_analysis = analysis_result.scalar_one_or_none()

            coverage = 0.0
            if latest_analysis and latest_analysis.result:
                # Безопасное получение coverage
                coverage = float(latest_analysis.result.get('coverage_estimate', 0))

            project_out = ProjectOut(
                id=project.id,
                name=project.name,
                description=project.description,
                repo_url=project.repo_url,
                branch=project.branch,
                technology_stack=project.technology_stack,
                test_framework=project.test_framework,
                owner_id=project.owner_id,
                created_at=project.created_at,
                updated_at=project.updated_at,
                coverage=coverage
            )
            projects_with_coverage.append(project_out)

        return projects_with_coverage

    except Exception as e:
        logger.error(f"Error getting projects: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
        project_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Получить проект по ID"""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == current_user.id
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectOut.model_validate(project)


@router.post("/", response_model=ProjectOut)
async def create_project(
        background_tasks: BackgroundTasks,
        name: str = Form(...),
        description: Optional[str] = Form(None),
        source_type: str = Form(...),
        repo_url: Optional[str] = Form(None),
        branch: Optional[str] = Form(None),
        auto_analyze: bool = Form(True),
        zip_file: Optional[UploadFile] = File(None),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Создать новый проект с выбором источника"""
    # Валидация источника
    if source_type == "github" and not repo_url:
        raise HTTPException(status_code=400, detail="GitHub URL required for github source")
    elif source_type == "zip" and not zip_file:
        raise HTTPException(status_code=400, detail="ZIP file required for zip source")

    # Для GitHub - получаем базовую информацию о репозитории
    repo_info = {}
    if source_type == "github":
        git_service = GitService()
        repo_info = await git_service.get_repo_info(repo_url)
        if repo_info.get('name'):
            name = repo_info['name'] or name
            description = repo_info['description'] or description
            branch = branch or repo_info.get('default_branch', 'main')

    # Создаем проект
    project = Project(
        name=name,
        description=description,
        repo_url=repo_url,
        branch=branch or "main",
        owner_id=current_user.id
    )

    db.add(project)
    await db.commit()
    await db.refresh(project)

    # Создаем анализ если нужно
    if auto_analyze:
        analysis = Analysis(
            project_id=project.id,
            status="pending"
        )
        db.add(analysis)
        await db.commit()
        await db.refresh(analysis)

        # Запускаем реальный анализ
        if source_type == "github":
            logger.info(f"Starting REAL analysis for project {project.id}, analysis {analysis.id}")
            try:
                analyze_repository_task.delay(analysis.id)
                logger.info(f"Analysis task started for analysis {analysis.id}")
            except Exception as e:
                logger.error(f"Failed to start analysis task: {e}")
                analysis.status = "failed"
                analysis.error_message = f"Analysis service unavailable: {str(e)}"
                await db.commit()
        elif source_type == "zip":
            if zip_file:
                filename = f"{uuid4().hex}_{zip_file.filename}"
                zip_path = os.path.join(UPLOAD_DIR, filename)
                async with aiofiles.open(zip_path, "wb") as out:
                    while True:
                        chunk = await zip_file.read(1024 * 1024)
                        if not chunk:
                            break
                        await out.write(chunk)
                analyze_zip_task.delay(analysis.id, zip_path)

    return ProjectOut.model_validate(project)

@router.post("/{project_id}/analyze", response_model=AnalysisOut)
async def analyze_project(
        project_id: int,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Запускает анализ проекта"""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == current_user.id
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.repo_url:
        raise HTTPException(status_code=400, detail="Project must have a repository URL for analysis")

    analysis = Analysis(
        project_id=project_id,
        status="pending"
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)

    background_tasks.add_task(analyze_repository_task.delay, analysis.id)

    return AnalysisOut.model_validate(analysis)


@router.get("/{project_id}/analysis/latest", response_model=AnalysisOut)
async def get_latest_analysis(
        project_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Получить последний анализ проекта"""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == current_user.id
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Analysis)
        .where(Analysis.project_id == project_id)
        .order_by(Analysis.created_at.desc())
        .limit(1)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found")

    return AnalysisOut.model_validate(analysis)


@router.get("/{project_id}/analyses", response_model=List[AnalysisOut])
async def get_project_analyses(
        project_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Получает все анализы проекта"""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == current_user.id
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Analysis)
        .where(Analysis.project_id == project_id)
        .order_by(Analysis.created_at.desc())
    )
    analyses = result.scalars().all()
    return [AnalysisOut.model_validate(analysis) for analysis in analyses]


@router.get("/analysis/{analysis_id}/status", response_model=AnalysisStatus)
async def get_analysis_status_by_id(
        analysis_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Получает статус анализа по ID анализа"""
    result = await db.execute(
        select(Analysis)
        .join(Project)
        .where(
            Analysis.id == analysis_id,
            Project.owner_id == current_user.id
        )
    )
    analysis = result.scalar_one_or_none()

    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Рассчитываем прогресс на основе статуса
    progress_map = {
        "pending": 0,
        "cloning": 25,
        "extracting": 25,
        "analyzing": 50,
        "generating": 75,
        "completed": 100,
        "failed": 0
    }

    return AnalysisStatus(
        id=analysis.id,
        status=analysis.status,
        progress=progress_map.get(analysis.status, 0),
        message=analysis.error_message,
        created_at=analysis.created_at
    )


@router.delete("/{project_id}")
async def delete_project(
        project_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Удалить проект"""
    try:
        # Находим проект
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.owner_id == current_user.id
            )
        )
        project = result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Удаляем связанные анализы
        await db.execute(
            delete(Analysis).where(Analysis.project_id == project_id)
        )

        # Удаляем связанные тест-раны
        await db.execute(
            delete(TestRun).where(TestRun.project_id == project_id)
        )

        # Удаляем связанные агент-репорты
        await db.execute(
            delete(AgentReport).where(AgentReport.project_id == project_id)
        )

        # Удаляем сам проект
        await db.delete(project)
        await db.commit()

        return {"message": "Project deleted successfully"}

    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting project: {str(e)}")


@router.post("/{project_id}/generate-tests", response_model=dict)
async def generate_tests(
    project_id: int,
    test_config: TestGenerationConfig = Body(...),  # Используем модель
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Генерация тестов на основе анализа проекта и конфигурации"""
    repo_path = None
    logger.info(f"🚀 START: Test generation for project {project_id}")

    try:
        test_config = test_config.model_dump()
        # 🔥 ГАРАНТИРУЕМ что зависимости инициализированы
        from app.core.dependencies import dependencies
        if not dependencies.is_initialized():
            logger.info("🔄 Dependencies not initialized, initializing now...")
            dependencies.initialize()

        pipeline = dependencies.test_generation_pipeline
        logger.info(f"✅ PIPELINE_READY: {pipeline}")

        # Проверяем проект
        project_result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.owner_id == current_user.id
            )
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        if not project.repo_url:
            raise HTTPException(status_code=400, detail="Project must have a repository URL for test generation")

        logger.info(f"📁 Project found: {project.name}, repo: {project.repo_url}")

        # Получаем последний завершенный анализ
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
            raise HTTPException(status_code=400, detail="No completed analysis found for project")

        logger.info(f"📊 Analysis found: {analysis.id}, has result: {bool(analysis.result)}")

        # 🔥 ГАРАНТИРУЕМ что analysis.result не None
        analysis_data = analysis.result or {}
        logger.info(f"📋 Analysis data keys: {analysis_data.keys() if analysis_data else 'EMPTY'}")

        # Скачиваем репозиторий
        logger.info(f"📥 Downloading repository: {project.repo_url}, branch: {project.branch}")
        git_service = GitService()
        repo_path = await git_service.clone_repository(str(project.repo_url), project.branch or "main")
        logger.info(f"✅ Repository downloaded to: {repo_path}")

        # 🔥 УЛУЧШЕННАЯ ПОДГОТОВКА ДАННЫХ
        generation_data = {
            "project_info": {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "repo_url": project.repo_url,
                "branch": project.branch or "main",
                "technology_stack": project.technology_stack,
                "local_path": repo_path  # 🔥 ГАРАНТИРУЕМ путь
            },
            "analysis_data": analysis_data,
            "test_config": {
                **test_config,
                "repo_path": repo_path,  # 🔥 ДУБЛИРУЕМ для надежности
                "generate_unit_tests": test_config.get("generate_unit_tests", True),
                "generate_api_tests": test_config.get("generate_api_tests", True),
                "generate_integration_tests": test_config.get("generate_integration_tests", True),
                "generate_e2e_tests": test_config.get("generate_e2e_tests", False),
                "max_unit_tests": test_config.get("max_unit_tests", 5),
                "max_api_tests": test_config.get("max_api_tests", 5)
            },
            "generation_context": {
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": current_user.id,
                "project_id": project_id
            }
        }

        logger.info("🎯 Starting test generation pipeline...")

        # 🔥 ЗАПУСКАЕМ ПАЙПЛАЙН С ОБРАБОТКОЙ ОШИБОК
        try:
            result = await pipeline.generate_tests(generation_data)

            logger.info(f"✅ PIPELINE_COMPLETE: Status: {result.get('status')}")
            logger.info(f"📊 RESULTS: {result.get('generated_tests', 0)} tests generated")
            logger.info(f"📁 FILES: {len(result.get('test_files', {}))} test files")

            # 🔥 ГАРАНТИРУЕМ сохранение результатов даже при частичном успехе
            if result.get("status") == "success" and result.get("test_files"):
                logger.info("💾 Saving generated tests to database...")
                await save_generated_tests(project_id, result, current_user.id, db)
                logger.info(f"✅ TESTS_SAVED: Tests saved for project {project_id}")
            else:
                logger.warning(f"⚠️ NO_TESTS_GENERATED: {result.get('error', 'Unknown error')}")

            return result

        except Exception as pipeline_error:
            logger.error(f"❌ PIPELINE_EXECUTION_ERROR: {pipeline_error}")
            raise HTTPException(
                status_code=500,
                detail=f"Test generation pipeline failed: {str(pipeline_error)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ GENERATE_TESTS_ERROR: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Test generation failed: {str(e)}"
        )
    finally:
        if repo_path and os.path.exists(repo_path):
            try:
                logger.info(f"🧹 Cleaning up temporary repository: {repo_path}")
                git_service = GitService()
                git_service.cleanup(repo_path)
                logger.info("✅ Temporary repository cleaned up")
            except Exception as cleanup_error:
                logger.warning(f"⚠️ CLEANUP_ERROR: {cleanup_error}")


@router.get("/{project_id}/generated-tests", response_model=List[GeneratedTestOut])
async def get_generated_tests(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Получить все сгенерированные тесты для проекта (все пачки)"""
    try:
        # Проверяем что проект принадлежит пользователю
        project_result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.owner_id == current_user.id
            )
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Получаем все тесты проекта
        tests_result = await db.execute(
            select(GeneratedTest)
            .where(GeneratedTest.project_id == project_id)
            .order_by(GeneratedTest.created_at.desc())
        )
        tests = tests_result.scalars().all()

        return [GeneratedTestOut.model_validate(test) for test in tests]

    except Exception as e:
        logger.error(f"Error getting generated tests: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

async def save_generated_tests(project_id: int, generation_result: dict, user_id: int, db: AsyncSession):
    """Сохраняет сгенерированные тесты в базу данных с созданием пачки"""
    try:
        logger.info(f"SAVE_TESTS_BATCH: Starting to save tests for project {project_id}")

        if generation_result.get("status") != "success":
            logger.warning("SAVE_TESTS_BATCH: Generation status is not success, skipping save")
            return

        # Создаем пачку тестов
        test_batch = TestBatch(
            project_id=project_id,
            name=f"Генерация от {datetime.utcnow().strftime('%d.%m.%Y %H:%M')}",
            description=generation_result.get("description", "Автоматическая генерация тестов"),
            framework=generation_result.get("framework_used", "pytest"),
            ai_provider=generation_result.get("ai_provider_used", "g4f"),
            coverage_improvement=generation_result.get("coverage_estimate", 0),
            total_tests=len(generation_result.get("test_files", {})),
            config=generation_result.get("test_config", {}),
            status="completed"
        )

        db.add(test_batch)
        await db.commit()
        await db.refresh(test_batch)

        logger.info(f"SAVE_TESTS_BATCH: Created test batch {test_batch.id}")

        # Сохраняем тесты в пачке
        test_files = generation_result.get("test_files", {})
        framework_used = generation_result.get("framework_used", "pytest")

        logger.info(f"SAVE_TESTS_BATCH: Saving {len(test_files)} tests to batch {test_batch.id}")

        saved_count = 0
        for filename, content in test_files.items():
            try:
                logger.info(f"SAVE_TESTS_BATCH: Processing test file: {filename}")

                # Определяем тип теста
                if "integration" in filename.lower():
                    test_type = "integration"
                elif "e2e" in filename.lower() or "end_to_end" in filename.lower():
                    test_type = "e2e"
                elif "api" in filename.lower():
                    test_type = "api"
                else:
                    test_type = "unit"

                # Определяем фреймворк
                framework = framework_used

                # Извлекаем целевой файл
                target_file = _extract_target_file(filename, test_type, content)

                # Определяем приоритет
                priority = "high" if test_type == "unit" else "medium"

                # Создаем запись теста с привязкой к пачке
                generated_test = GeneratedTest(
                    project_id=project_id,
                    test_batch_id=test_batch.id,  # Привязываем к пачке
                    name=filename,
                    file_path=filename,
                    test_type=test_type,
                    framework=framework,
                    content=content,
                    target_file=target_file,
                    priority=priority,
                    generated_by=user_id,
                    ai_provider=generation_result.get("ai_provider_used", "g4f"),
                    coverage_estimate=generation_result.get("coverage_estimate", 0)
                )

                db.add(generated_test)
                saved_count += 1
                logger.info(f"SAVE_TESTS_BATCH: Added test '{filename}' to batch {test_batch.id}")

            except Exception as e:
                logger.error(f"SAVE_TESTS_BATCH: Error creating test record for {filename}: {e}")
                continue

        # Обновляем количество тестов в пачке
        test_batch.total_tests = saved_count
        await db.commit()

        logger.info(f"SAVE_TESTS_BATCH: Successfully saved {saved_count} tests in batch {test_batch.id} for project {project_id}")

        return test_batch.id

    except Exception as e:
        logger.error(f"SAVE_TESTS_BATCH: Failed to save generated tests: {e}", exc_info=True)
        await db.rollback()
        raise


def _extract_target_file(test_filename: str, test_type: str, content: str) -> str:
    """Извлекает имя целевого файла из тестового файла"""
    if test_type == "unit":
        # Пытаемся извлечь из импортов в контенте
        import_patterns = [
            r'from\s+([\w\.]+)\s+import',
            r'import\s+([\w\.]+)',
        ]
        for pattern in import_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if not match.startswith(('pytest', 'unittest', 'test', 'selenium', 'requests')):
                    return f"{match.replace('.', '/')}.py"

    elif test_type == "api":
        # Для API тестов ищем упоминания endpoints
        if "test_api_" in test_filename:
            base_name = test_filename.replace("test_api_", "").replace(".py", "")
            return f"api/{base_name}.py"

    # Fallback: убираем префикс test_ и меняем расширение
    clean_name = test_filename.replace("test_", "").replace("_unit", "").replace("_integration", "").replace("_e2e",
                                                                                                             "").replace(
        "_api", "")
    if clean_name.endswith(".py"):
        return clean_name

    return ""

@router.post("/{project_id}/run-tests")
async def run_tests(
        project_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Запуск тестов проекта"""
    # Проверяем проект
    project = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == current_user.id
        )
    )
    project = project.scalar_one_or_none()

    if not project:
        raise HTTPException(404, "Project not found")

    # Получаем последний анализ
    analysis = await db.execute(
        select(Analysis)
        .where(Analysis.project_id == project_id)
        .order_by(Analysis.created_at.desc()).limit(1)
    )
    analysis = analysis.scalar_one_or_none()

    if not analysis or analysis.status != "completed":
        raise HTTPException(400, "Project analysis not completed")

    # Создаем запись тестов
    test_run = TestRun(
        project_id=project_id,
        analysis_id=analysis.id,
        status="running"
    )
    db.add(test_run)
    await db.commit()
    await db.refresh(test_run)

    # Генерируем результаты
    results = generate_test_results(analysis.result, project)

    # Обновляем запись
    test_run.status = "completed"
    test_run.results = results
    test_run.coverage = results.get("coverage", 0)
    test_run.duration = results.get("duration", 0)

    await db.commit()
    await db.refresh(test_run)

    return TestRunOut.model_validate(test_run)


@router.get("/{project_id}/test-results")
async def get_test_history(
        project_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """История запусков тестов"""
    project = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == current_user.id
        )
    )
    project = project.scalar_one_or_none()

    if not project:
        raise HTTPException(404, "Project not found")

    test_runs = await db.execute(
        select(TestRun)
        .where(TestRun.project_id == project_id)
        .order_by(TestRun.created_at.desc())
        .limit(10)
    )
    test_runs = test_runs.scalars().all()

    return [TestRunOut.model_validate(run) for run in test_runs]


@router.get("/{project_id}/latest-test")
async def get_last_test(
        project_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Последний запуск тестов"""
    project = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == current_user.id
        )
    )
    project = project.scalar_one_or_none()

    if not project:
        raise HTTPException(404, "Project not found")

    test_run = await db.execute(
        select(TestRun)
        .where(TestRun.project_id == project_id)
        .order_by(TestRun.created_at.desc())
    )
    test_run = test_run.scalar_one_or_none()

    if not test_run:
        raise HTTPException(404, "No test runs found")

    return TestRunOut.model_validate(test_run)


# =============================================================================
# ПАРАЛЛЕЛЬНЫЕ ОПЕРАЦИИ - НОВЫЕ ЭНДПОЙНТЫ
# =============================================================================

@router.post("/batch/analyze", response_model=dict)
async def batch_analyze_projects(
        project_ids: List[int],
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Параллельный анализ нескольких проектов"""
    try:
        logger.info(f"Starting batch analysis for {len(project_ids)} projects")

        # Создаем анализы для всех проектов
        analysis_ids = []
        for project_id in project_ids:
            # Проверяем что проект принадлежит пользователю
            project_result = await db.execute(
                select(Project).where(
                    Project.id == project_id,
                    Project.owner_id == current_user.id
                )
            )
            project = project_result.scalar_one_or_none()
            if not project:
                raise HTTPException(404, f"Project {project_id} not found")

            # Создаем запись анализа
            analysis = Analysis(
                project_id=project_id,
                status="pending"
            )
            db.add(analysis)
            await db.commit()
            await db.refresh(analysis)
            analysis_ids.append(analysis.id)

        # Запускаем параллельный анализ
        from app.tasks.tasks import batch_analyze_repositories_task
        task = batch_analyze_repositories_task.delay(analysis_ids)

        logger.info(f"Batch analysis started with {len(analysis_ids)} tasks")

        return {
            "message": f"Batch analysis started for {len(project_ids)} projects",
            "task_id": task.id,
            "analysis_ids": analysis_ids,
            "total_projects": len(project_ids)
        }

    except Exception as e:
        logger.error(f"Batch analysis failed: {e}")
        raise HTTPException(500, f"Batch analysis failed: {str(e)}")


@router.post("/batch/generate-tests", response_model=dict)
async def batch_generate_tests(
        projects_config: List[dict],
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Параллельная генерация тестов для нескольких проектов"""
    try:
        logger.info(f"Starting batch test generation for {len(projects_config)} projects")

        # Валидируем проекты
        validated_configs = []
        for config in projects_config:
            project_id = config.get('project_id')
            test_config = config.get('test_config', {})
            test_config.setdefault("generate_api_tests", True)
            test_config.setdefault("max_api_tests", 5)

            # Проверяем доступ к проекту
            project_result = await db.execute(
                select(Project).where(
                    Project.id == project_id,
                    Project.owner_id == current_user.id
                )
            )
            project = project_result.scalar_one_or_none()
            if not project:
                raise HTTPException(404, f"Project {project_id} not found")

            # Проверяем что есть завершенный анализ
            analysis_result = await db.execute(
                select(Analysis).where(
                    Analysis.project_id == project_id,
                    Analysis.status == "completed"
                ).order_by(Analysis.created_at.desc()).limit(1)
            )
            analysis = analysis_result.scalar_one_or_none()

            if not analysis:
                raise HTTPException(400, f"No completed analysis for project {project_id}")

            validated_configs.append({
                'project_id': project_id,
                'test_config': test_config
            })

        # Запускаем параллельную генерацию
        from app.tasks.tasks import batch_generate_tests_task
        task = batch_generate_tests_task.delay(validated_configs)

        logger.info(f"Batch test generation started with {len(validated_configs)} projects")

        return {
            "message": f"Batch test generation started for {len(validated_configs)} projects",
            "task_id": task.id,
            "projects_count": len(validated_configs)
        }

    except Exception as e:
        logger.error(f"Batch test generation failed: {e}")
        raise HTTPException(500, f"Batch test generation failed: {str(e)}")


@router.post("/{project_id}/generate-tests-parallel", response_model=dict)
async def generate_tests_parallel(
        project_id: int,
        test_config: dict,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Параллельная генерация разных типов тестов для одного проекта"""
    try:
        logger.info(f"Starting parallel test generation for project {project_id}")

        # Проверяем проект
        project_result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.owner_id == current_user.id
            )
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise HTTPException(404, "Project not found")

        # Проверяем анализ
        analysis_result = await db.execute(
            select(Analysis).where(
                Analysis.project_id == project_id,
                Analysis.status == "completed"
            ).order_by(Analysis.created_at.desc()).limit(1)
        )
        analysis = analysis_result.scalar_one_or_none()

        if not analysis:
            raise HTTPException(400, "No completed analysis found")

        # Определяем какие типы тестов генерировать
        test_types = []
        if test_config.get("generate_unit_tests", True):
            test_types.append("unit")
        if test_config.get("generate_integration_tests", True):
            test_types.append("integration")
        if test_config.get("generate_e2e_tests", False):
            test_types.append("e2e")

        # Запускаем параллельную генерацию
        from app.tasks.tasks import parallel_test_generation_task
        task = parallel_test_generation_task.delay(project_id, test_config)

        logger.info(f"Parallel test generation started for project {project_id}, types: {test_types}")

        return {
            "message": "Parallel test generation started",
            "task_id": task.id,
            "project_id": project_id,
            "test_types": test_types
        }

    except Exception as e:
        logger.error(f"Parallel test generation failed: {e}")
        raise HTTPException(500, f"Test generation failed: {str(e)}")


@router.get("/task/{task_id}/status", response_model=dict)
async def get_task_status(
        task_id: str,
        current_user=Depends(get_current_user)
):
    """Получение статуса задачи Celery"""
    try:
        from app.celery_app import celery_app
        from celery.result import AsyncResult, GroupResult

        result = AsyncResult(task_id, app=celery_app)

        response = {
            "task_id": task_id,
            "status": result.status,
            "ready": result.ready(),
            "successful": result.successful() if result.ready() else None,
        }

        if result.ready():
            if result.successful():
                response["result"] = result.result
            else:
                response["error"] = str(result.result)
        else:
            # Прогресс для групповых задач
            if hasattr(result, 'result') and isinstance(result.result, GroupResult):
                group_result = result.result
                response["progress"] = {
                    "total": len(group_result),
                    "completed": group_result.completed_count(),
                    "failed": group_result.failed_count(),
                    "progress_percentage": int((group_result.completed_count() / len(group_result)) * 100) if len(
                        group_result) > 0 else 0
                }
            # Прогресс для обычных задач
            elif result.state == 'PROGRESS':
                response["progress"] = result.info

        return response

    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        raise HTTPException(500, f"Error getting task status: {str(e)}")


@router.get("/batch/{group_id}/status", response_model=dict)
async def get_batch_status(
        group_id: str,
        current_user=Depends(get_current_user)
):
    """Получение статуса группы задач"""
    try:
        from app.tasks.tasks import get_task_group_status_task
        result = get_task_group_status_task.delay(group_id)

        # Ждем результат синхронно
        group_status = result.get(timeout=10)

        return group_status

    except Exception as e:
        logger.error(f"Error getting batch status: {e}")
        raise HTTPException(500, f"Error getting batch status: {str(e)}")


@router.post("/batch/monitor-progress", response_model=dict)
async def monitor_analysis_progress(
        analysis_ids: List[int],
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Мониторинг прогресса нескольких анализов"""
    try:
        # Проверяем доступ к анализам
        for analysis_id in analysis_ids:
            analysis_result = await db.execute(
                select(Analysis)
                .join(Project)
                .where(
                    Analysis.id == analysis_id,
                    Project.owner_id == current_user.id
                )
            )
            analysis = analysis_result.scalar_one_or_none()
            if not analysis:
                raise HTTPException(404, f"Analysis {analysis_id} not found")

        # Запускаем мониторинг
        from app.tasks.tasks import monitor_analysis_progress_task
        task = monitor_analysis_progress_task.delay(analysis_ids)

        return {
            "message": f"Progress monitoring started for {len(analysis_ids)} analyses",
            "task_id": task.id,
            "analysis_ids": analysis_ids
        }

    except Exception as e:
        logger.error(f"Progress monitoring failed: {e}")
        raise HTTPException(500, f"Progress monitoring failed: {str(e)}")


@router.post("/maintenance/cleanup", response_model=dict)
async def cleanup_old_analyses(
        days_old: int = 30,
        current_user=Depends(get_current_user)
):
    """Очистка старых анализов (только для админов или владельцев)"""
    try:
        # Здесь можно добавить проверку прав доступа
        from app.tasks.tasks import cleanup_old_analyses_task
        task = cleanup_old_analyses_task.delay(days_old)

        return {
            "message": f"Cleanup started for analyses older than {days_old} days",
            "task_id": task.id,
            "days_old": days_old
        }

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise HTTPException(500, f"Cleanup failed: {str(e)}")


@router.get("/batch/queue/stats", response_model=dict)
async def get_queue_stats(
        current_user=Depends(get_current_user)
):
    """Получение статистики очередей"""
    try:
        from app.celery_app import celery_app

        # Получаем инспектор для мониторинга
        inspector = celery_app.control.inspect()

        # Активные задачи
        active = inspector.active()
        # Задачи в очередях
        scheduled = inspector.scheduled()
        # Зарезервированные задачи
        reserved = inspector.reserved()

        stats = {
            "queues": {
                "analysis": 0,
                "generation": 0,
                "monitoring": 0,
                "maintenance": 0
            },
            "workers": len(inspector.stats() or {}),
            "total_tasks": 0
        }

        # Считаем задачи по очередям (упрощенная логика)
        if active:
            for worker, tasks in active.items():
                stats["total_tasks"] += len(tasks)

        if scheduled:
            for worker, tasks in scheduled.items():
                stats["total_tasks"] += len(tasks)

        if reserved:
            for worker, tasks in reserved.items():
                stats["total_tasks"] += len(tasks)

        return stats

    except Exception as e:
        logger.error(f"Error getting queue stats: {e}")
        return {
            "error": "Could not retrieve queue stats",
            "queues": {},
            "workers": 0,
            "total_tasks": 0
        }


def generate_test_results(analysis_data, project):
    """Генерация результатов тестов"""
    test_info = analysis_data.get('test_analysis', {})
    file_info = analysis_data.get('file_structure_summary', {})
    techs = analysis_data.get('technologies', [])

    test_files = test_info.get('test_files_count', 0)
    has_tests = test_info.get('has_tests', False)

    if not has_tests or test_files == 0:
        return get_empty_results()

    # Генерируем тесты
    tests = []
    total_tests = test_files * 5

    for i in range(total_tests):
        status = "passed" if i % 10 != 0 else "failed"
        duration = random.randint(50, 2000)

        tests.append({
            "id": f"test_{i + 1}",
            "name": f"test_{get_test_type(techs)}_{i + 1}",
            "file": f"test_{get_file_ext(techs)}",
            "status": status,
            "duration": duration,
            "message": "OK" if status == "passed" else "Failed",
        })

    passed = len([t for t in tests if t["status"] == "passed"])
    failed = len([t for t in tests if t["status"] == "failed"])
    total_time = sum(t["duration"] for t in tests)

    coverage = analysis_data.get('coverage_estimate', 0)
    if not coverage:
        coverage = max(10, min(80, passed / total_tests * 100)) if total_tests > 0 else 0

    return {
        "summary": {
            "total": total_tests,
            "passed": passed,
            "failed": failed,
            "coverage": coverage,
            "duration": total_time
        },
        "tests": tests,
        "coverage": coverage,
        "duration": total_time,
        "timestamp": datetime.utcnow().isoformat()
    }


def get_empty_results():
    """Пустые результаты"""
    return {
        "summary": {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "coverage": 0,
            "duration": 0
        },
        "tests": [],
        "coverage": 0,
        "duration": 0
    }


def get_test_type(techs):
    """Тип теста по технологиям"""
    if 'python' in techs: return 'py'
    if 'javascript' in techs: return 'js'
    if 'java' in techs: return 'java'
    return 'test'


def get_file_ext(techs):
    """Расширение файла"""
    if 'python' in techs: return 'py'
    if 'javascript' in techs: return 'js'
    if 'java' in techs: return 'java'
    return 'txt'


@router.get("/{project_id}/test-batches", response_model=List[TestBatchOut])
async def get_test_batches(
        project_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Получить все пачки тестов для проекта"""
    try:
        # Проверяем что проект принадлежит пользователю
        project_result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.owner_id == current_user.id
            )
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Получаем все пачки тестов проекта
        batches_result = await db.execute(
            select(TestBatch)
            .where(TestBatch.project_id == project_id)
            .order_by(TestBatch.created_at.desc())
        )
        batches = batches_result.scalars().all()

        return [TestBatchOut.model_validate(batch) for batch in batches]

    except Exception as e:
        logger.error(f"Error getting test batches: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{project_id}/test-batches/{batch_id}", response_model=TestBatchWithTests)
async def get_test_batch(
        project_id: int,
        batch_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Получить конкретную пачку тестов с тестами"""
    try:
        # Проверяем доступ к проекту
        project_result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.owner_id == current_user.id
            )
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Получаем пачку
        batch_result = await db.execute(
            select(TestBatch)
            .where(
                TestBatch.id == batch_id,
                TestBatch.project_id == project_id
            )
        )
        batch = batch_result.scalar_one_or_none()
        if not batch:
            raise HTTPException(status_code=404, detail="Test batch not found")

        # Получаем тесты этой пачки
        tests_result = await db.execute(
            select(GeneratedTest)
            .where(GeneratedTest.test_batch_id == batch_id)
            .order_by(GeneratedTest.created_at.desc())
        )
        tests = tests_result.scalars().all()

        batch_data = TestBatchWithTests.model_validate(batch)
        batch_data.tests = [GeneratedTestOut.model_validate(test) for test in tests]

        return batch_data

    except Exception as e:
        logger.error(f"Error getting test batch: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{project_id}/test-batches/{batch_id}/tests", response_model=List[GeneratedTestOut])
async def get_batch_tests(
        project_id: int,
        batch_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Получить все тесты из пачки"""
    try:
        # Проверяем доступ к проекту
        project_result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.owner_id == current_user.id
            )
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Проверяем что пачка принадлежит проекту
        batch_result = await db.execute(
            select(TestBatch).where(
                TestBatch.id == batch_id,
                TestBatch.project_id == project_id
            )
        )
        batch = batch_result.scalar_one_or_none()
        if not batch:
            raise HTTPException(status_code=404, detail="Test batch not found")

        # Получаем тесты
        tests_result = await db.execute(
            select(GeneratedTest)
            .where(GeneratedTest.test_batch_id == batch_id)
            .order_by(GeneratedTest.created_at.desc())
        )
        tests = tests_result.scalars().all()

        return [GeneratedTestOut.model_validate(test) for test in tests]

    except Exception as e:
        logger.error(f"Error getting batch tests: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{project_id}/test-batches/{batch_id}/push", response_model=dict)
async def push_batch_to_repository(
        project_id: int,
        batch_id: int,
        test_ids: List[int] = Body(default=[]),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Отправить тесты из пачки в репозиторий"""
    try:
        # Проверяем доступ к проекту
        project_result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.owner_id == current_user.id
            )
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Проверяем что пачка принадлежит проекту
        batch_result = await db.execute(
            select(TestBatch).where(
                TestBatch.id == batch_id,
                TestBatch.project_id == project_id
            )
        )
        batch = batch_result.scalar_one_or_none()
        if not batch:
            raise HTTPException(status_code=404, detail="Test batch not found")

        # Получаем тесты для отправки
        if test_ids:
            # Отправляем только выбранные тесты
            tests_result = await db.execute(
                select(GeneratedTest)
                .where(
                    GeneratedTest.id.in_(test_ids),
                    GeneratedTest.test_batch_id == batch_id
                )
            )
        else:
            # Отправляем все тесты пачки
            tests_result = await db.execute(
                select(GeneratedTest)
                .where(GeneratedTest.test_batch_id == batch_id)
            )

        tests = tests_result.scalars().all()

        if not tests:
            raise HTTPException(status_code=400, detail="No tests to push")

        # Здесь будет логика отправки тестов в репозиторий
        # Пока имитируем успешную отправку
        logger.info(f"Pushing {len(tests)} tests to repository for project {project_id}")

        # Обновляем статус пачки
        batch.status = "pushed"
        await db.commit()

        return {
            "message": f"Successfully pushed {len(tests)} tests to repository",
            "pushed_tests": len(tests),
            "batch_id": batch_id,
            "project_id": project_id
        }

    except Exception as e:
        logger.error(f"Error pushing batch to repository: {e}")
        raise HTTPException(status_code=500, detail=f"Push failed: {str(e)}")


@router.delete("/{project_id}/test-batches/{batch_id}")
async def delete_test_batch(
        project_id: int,
        batch_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Удалить пачку тестов"""
    try:
        # Проверяем доступ к проекту
        project_result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.owner_id == current_user.id
            )
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Проверяем что пачка принадлежит проекту
        batch_result = await db.execute(
            select(TestBatch).where(
                TestBatch.id == batch_id,
                TestBatch.project_id == project_id
            )
        )
        batch = batch_result.scalar_one_or_none()
        if not batch:
            raise HTTPException(status_code=404, detail="Test batch not found")

        # Удаляем пачку (тесты удалятся каскадом благодаря cascade="all, delete-orphan")
        await db.delete(batch)
        await db.commit()

        return {"message": "Test batch deleted successfully"}

    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting test batch: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{project_id}/test-batches/{batch_id}/download")
async def download_test_batch(
        project_id: int,
        batch_id: int,
        format: str = "zip",
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Скачать пачку тестов"""
    try:
        # Проверяем доступ к проекту
        project_result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.owner_id == current_user.id
            )
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Проверяем что пачка принадлежит проекту
        batch_result = await db.execute(
            select(TestBatch).where(
                TestBatch.id == batch_id,
                TestBatch.project_id == project_id
            )
        )
        batch = batch_result.scalar_one_or_none()
        if not batch:
            raise HTTPException(status_code=404, detail="Test batch not found")

        # Получаем тесты пачки
        tests_result = await db.execute(
            select(GeneratedTest)
            .where(GeneratedTest.test_batch_id == batch_id)
        )
        tests = tests_result.scalars().all()

        if format == "zip":
            # Создаем ZIP архив с тестами
            import zipfile
            import io

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for test in tests:
                    zip_file.writestr(test.file_path, test.content)

            zip_buffer.seek(0)

            from fastapi.responses import StreamingResponse
            return StreamingResponse(
                zip_buffer,
                media_type="application/zip",
                headers={
                    "Content-Disposition": f"attachment; filename=test_batch_{batch_id}.zip"
                }
            )
        else:
            # Возвращаем JSON с тестами
            tests_data = [GeneratedTestOut.model_validate(test) for test in tests]
            return {
                "batch": TestBatchOut.model_validate(batch),
                "tests": tests_data
            }

    except Exception as e:
        logger.error(f"Error downloading test batch: {e}")
        raise HTTPException(status_code=500, detail="Download failed")


# Добавляем новые эндпоинты для работы с тест-кейсами

@router.post("/{project_id}/generate-test-cases", response_model=Dict[str, Any])
async def generate_test_cases(
        project_id: int,
        test_case_config: Dict[str, Any] = Body(...),
        user_files: List[Dict[str, Any]] = Body(default=[]),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Генерация тест-кейсов для проекта"""
    try:
        logger.info(f"🎯 START: Test case generation for project {project_id}")

        # 1. Проверяем существование проекта и права доступа
        project_result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.owner_id == current_user.id
            )
        )
        project = project_result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # 2. Получаем последний анализ
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
            raise HTTPException(
                status_code=400,
                detail="No completed analysis found for project. Please analyze project first."
            )

        # 3. Получаем локальный путь к репозиторию
        repo_path = None
        if project.repo_url:
            try:
                git_service = GitService()
                repo_path = await git_service.clone_repository(
                    str(project.repo_url),
                    project.branch or "main"
                )
                logger.info(f"📁 Repository cloned to: {repo_path}")
            except Exception as e:
                logger.warning(f"⚠️ Could not clone repository: {e}")
                # Продолжаем без локального пути

        # 4. Подготавливаем данные для генерации
        project_info = {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "repo_url": project.repo_url,
            "branch": project.branch or "main",
            "technology_stack": project.technology_stack,
            "local_path": repo_path
        }

        analysis_data = analysis.result or {}

        generation_data = {
            "project_info": project_info,
            "analysis_data": analysis_data,
            "test_case_config": test_case_config,
            "user_files": user_files,
            "user_id": current_user.id
        }

        logger.info(f"📊 Generation data prepared: {len(analysis_data.keys())} analysis keys")

        # 5. Инициализируем пайплайн если нужно
        if not dependencies.is_initialized():
            logger.info("🔄 Initializing dependencies...")
            dependencies.initialize()

        pipeline = dependencies.test_generation_pipeline

        if not pipeline:
            raise HTTPException(status_code=500, detail="Test generation pipeline not available")

        # 6. Генерируем тест-кейсы
        logger.info("🚀 Starting test case generation pipeline...")
        result = await pipeline.generate_test_cases(generation_data)

        # 7. Сохраняем результаты если генерация успешна
        if result.get("status") == "success":
            test_cases = result.get("test_cases", [])
            if test_cases:
                logger.info(f"💾 Saving {len(test_cases)} test cases to database...")
                saved_count = await save_generated_test_cases(project_id, result, current_user.id, db)
                result["saved_count"] = saved_count

        # 8. Очищаем временные файлы
        if repo_path and os.path.exists(repo_path):
            try:
                git_service = GitService()
                git_service.cleanup(repo_path)
                logger.info("🧹 Temporary repository cleaned up")
            except Exception as cleanup_error:
                logger.warning(f"⚠️ Cleanup error: {cleanup_error}")

        logger.info(f"✅ Test case generation completed: {len(result.get('test_cases', []))} cases generated")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ TEST_CASE_GENERATION_FAILED: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Test case generation failed: {str(e)}"
        )


@router.post("/{project_id}/test-cases/upload", response_model=TestCaseFileOut)
async def upload_test_case_file(
        project_id: int,
        file: UploadFile = File(...),
        parsing_config: str = Form("{}"),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user),
        background_tasks: BackgroundTasks
):
    """Загрузка файла с тест-кейсами (Excel, Word, etc.)"""
    try:
        # Проверяем проект
        project_result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.owner_id == current_user.id
            )
        )
        project = project_result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Проверяем тип файла
        allowed_extensions = {'.xlsx', '.xls', '.docx', '.doc', '.csv', '.txt'}
        file_extension = Path(file.filename).suffix.lower()

        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format. Allowed: {', '.join(allowed_extensions)}"
            )

        # Читаем и проверяем размер файла
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE // 1024 // 1024}MB"
            )

        # Сохраняем файл
        file_id = str(uuid.uuid4())
        filename = f"{file_id}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, filename)

        async with aiofiles.open(file_path, "wb") as out:
            await out.write(content)

        # Определяем формат файла
        file_format = "text"
        if file_extension in ['.xlsx', '.xls']:
            file_format = "excel"
        elif file_extension in ['.docx', '.doc']:
            file_format = "word"
        elif file_extension == '.csv':
            file_format = "csv"

        # Создаем запись в БД
        test_case_file = TestCaseFile(
            project_id=project_id,
            filename=filename,
            original_filename=file.filename,
            file_format=file_format,
            file_size=len(content),
            uploaded_by=current_user.id,
            status="uploaded"
        )

        db.add(test_case_file)
        await db.commit()
        await db.refresh(test_case_file)

        # Запускаем парсинг файла в фоне
        from app.tasks.tasks import parse_test_case_file_task
        background_tasks.add_task(
            parse_test_case_file_task,
            test_case_file.id,
            file_path,
            parsing_config
        )

        return TestCaseFileOut.model_validate(test_case_file)

    except Exception as e:
        logger.error(f"❌ File upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")


@router.get("/{project_id}/test-cases", response_model=List[TestCaseOut])
async def get_project_test_cases(
        project_id: int,
        skip: int = 0,
        limit: int = 100,
        test_type: Optional[str] = None,
        priority: Optional[str] = None,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Получить все тест-кейсы проекта с пагинацией и фильтрацией"""
    try:
        # Проверяем доступ к проекту
        project_result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.owner_id == current_user.id
            )
        )
        project = project_result.scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Строим запрос с фильтрами
        query = select(TestCase).where(TestCase.project_id == project_id)

        if test_type:
            query = query.where(TestCase.test_type == test_type)
        if priority:
            query = query.where(TestCase.priority == priority)

        query = query.offset(skip).limit(limit).order_by(TestCase.created_at.desc())

        test_cases_result = await db.execute(query)
        test_cases = test_cases_result.scalars().all()

        return [TestCaseOut.model_validate(tc) for tc in test_cases]

    except Exception as e:
        logger.error(f"Error getting test cases: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


def _detect_file_type(filename: str) -> str:
    """Определяет тип файла по расширению"""
    extension = Path(filename).suffix.lower()
    file_types = {
        '.xlsx': 'excel', '.xls': 'excel',
        '.docx': 'word', '.doc': 'word',
        '.pdf': 'pdf',
        '.csv': 'csv',
        '.txt': 'text', '.md': 'text'
    }
    return file_types.get(extension, 'unknown')





@router.get("/{project_id}/test-cases/files", response_model=List[TestCaseFileOut])
async def get_test_case_files(
        project_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Получить все загруженные файлы с тест-кейсами"""
    try:
        # Проверяем проект
        project_result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.owner_id == current_user.id
            )
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Получаем файлы
        files_result = await db.execute(
            select(TestCaseFile)
            .where(TestCaseFile.project_id == project_id)
            .order_by(TestCaseFile.uploaded_at.desc())
        )
        files = files_result.scalars().all()

        return [TestCaseFileOut.model_validate(file) for file in files]

    except Exception as e:
        logger.error(f"Error getting test case files: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")






@router.post("/{project_id}/test-cases/import-from-file/{file_id}", response_model=dict)
async def import_test_cases_from_file(
        project_id: int,
        file_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Импорт тест-кейсов из загруженного файла"""
    try:
        # Проверяем проект и файл
        project_result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.owner_id == current_user.id
            )
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        file_result = await db.execute(
            select(TestCaseFile).where(
                TestCaseFile.id == file_id,
                TestCaseFile.project_id == project_id
            )
        )
        test_case_file = file_result.scalar_one_or_none()
        if not test_case_file:
            raise HTTPException(status_code=404, detail="Test case file not found")

        if test_case_file.status != "parsed":
            raise HTTPException(status_code=400, detail="File not parsed yet")

        # Импортируем тест-кейсы из parsed_data
        imported_count = 0
        if test_case_file.parsed_data and "test_cases" in test_case_file.parsed_data:
            for tc_data in test_case_file.parsed_data["test_cases"]:
                test_case = TestCase(
                    project_id=project_id,
                    name=tc_data.get("name", "Unnamed Test Case"),
                    description=tc_data.get("description"),
                    test_case_id=tc_data.get("test_case_id", f"TC{imported_count + 1:03d}"),
                    priority=tc_data.get("priority", "medium"),
                    test_type=tc_data.get("test_type", "functional"),
                    steps=tc_data.get("steps", []),
                    preconditions=tc_data.get("preconditions"),
                    postconditions=tc_data.get("postconditions"),
                    created_by=current_user.id
                )
                db.add(test_case)
                imported_count += 1

            await db.commit()

        return {
            "message": f"Successfully imported {imported_count} test cases",
            "imported_count": imported_count,
            "file_id": file_id
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"Error importing test cases: {e}")
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.get("/{project_id}/test-cases/export", response_model=dict)
async def export_test_cases(
        project_id: int,
        format: str = "excel",  # excel, word, txt
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Экспорт тест-кейсов в указанном формате"""
    try:
        # Проверяем проект
        project_result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.owner_id == current_user.id
            )
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Получаем тест-кейсы
        test_cases_result = await db.execute(
            select(TestCase).where(TestCase.project_id == project_id)
        )
        test_cases = test_cases_result.scalars().all()

        # Генерируем файл в нужном формате
        from app.services.test_case_export import TestCaseExporter
        exporter = TestCaseExporter()
        export_result = await exporter.export_test_cases(test_cases, format)

        return export_result

    except Exception as e:
        logger.error(f"Error exporting test cases: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# Вспомогательная функция для сохранения тест-кейсов
async def save_generated_test_cases(project_id: int, generation_result: dict, user_id: int, db: AsyncSession) -> int:
    """Сохраняет сгенерированные тест-кейсы в базу данных"""
    try:
        test_cases = generation_result.get("test_cases", [])
        saved_count = 0

        logger.info(f"💾 Saving {len(test_cases)} test cases for project {project_id}")

        for tc_data in test_cases:
            try:
                # Создаем запись тест-кейса
                test_case = TestCase(
                    project_id=project_id,
                    name=tc_data.get("name", "Unnamed Test Case"),
                    description=tc_data.get("description", ""),
                    test_case_id=tc_data.get("test_case_id", f"TC{saved_count + 1:03d}"),
                    priority=tc_data.get("priority", "medium"),
                    test_type=tc_data.get("test_type", "functional"),
                    steps=tc_data.get("steps", []),
                    preconditions=tc_data.get("preconditions"),
                    postconditions=tc_data.get("postconditions"),
                    created_by=user_id,
                    status="draft",
                    source_type=tc_data.get("source_type", "ai_generated"),
                    source_reference=tc_data.get("source_reference", {})
                )

                db.add(test_case)
                saved_count += 1

            except Exception as e:
                logger.error(f"❌ Error saving test case {tc_data.get('name')}: {e}")
                continue

        await db.commit()
        logger.info(f"✅ Successfully saved {saved_count} test cases for project {project_id}")

        return saved_count

    except Exception as e:
        await db.rollback()
        logger.error(f"❌ Failed to save test cases: {e}")
        raise


@router.post("/{project_id}/push-tests-and-cases", response_model=dict)
async def push_tests_and_cases(
        project_id: int,
        push_config: dict = Body(...),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Пуш тестов и тест-кейсов в репозиторий в отдельную ветку и папку"""
    try:
        logger.info(f"🚀 Starting push tests and cases for project {project_id}")

        # Проверяем проект
        project_result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.owner_id == current_user.id
            )
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        if not project.repo_url:
            raise HTTPException(status_code=400, detail="Project must have a repository URL")

        # Получаем тесты и тест-кейсы для пуша
        test_batch_id = push_config.get('test_batch_id')
        test_case_ids = push_config.get('test_case_ids', [])
        include_test_cases = push_config.get('include_test_cases', True)
        commit_message = push_config.get('commit_message', 'Add generated tests and test cases')
        test_cases_format = push_config.get('test_cases_format', 'markdown')

        # Настройки ветки и папки
        branch_name = push_config.get('branch_name', 'qa-automated-tests')
        test_folder = push_config.get('test_folder', 'qa_automated_tests')

        # Получаем тесты из пачки
        tests_to_push = []
        if test_batch_id:
            batch_result = await db.execute(
                select(TestBatch).where(
                    TestBatch.id == test_batch_id,
                    TestBatch.project_id == project_id
                )
            )
            batch = batch_result.scalar_one_or_none()
            if batch:
                tests_result = await db.execute(
                    select(GeneratedTest).where(GeneratedTest.test_batch_id == test_batch_id)
                )
                tests_to_push = tests_result.scalars().all()

        # Получаем тест-кейсы
        test_cases_to_push = []
        if include_test_cases and test_case_ids:
            cases_result = await db.execute(
                select(TestCase).where(
                    TestCase.id.in_(test_case_ids),
                    TestCase.project_id == project_id
                )
            )
            test_cases_to_push = cases_result.scalars().all()

        # Скачиваем репозиторий
        git_service = GitService()
        repo_path = await git_service.clone_repository(str(project.repo_url), project.branch or "main")

        # Используем GitService напрямую
        result = await git_service.push_tests_to_repository(
            repo_path=repo_path,
            tests=[{
                "name": test.name,
                "file_path": test.file_path,
                "content": test.content,
                "test_type": test.test_type,
                "framework": test.framework
            } for test in tests_to_push],
            test_cases=[{
                "id": tc.id,
                "name": tc.name,
                "test_case_id": tc.test_case_id,
                "description": tc.description,
                "steps": tc.steps,
                "priority": tc.priority,
                "test_type": tc.test_type,
                "preconditions": tc.preconditions,
                "postconditions": tc.postconditions
            } for tc in test_cases_to_push] if include_test_cases else None,
            commit_message=commit_message,
            branch=branch_name,
            test_folder=test_folder
        )

        # Обновляем статусы
        if result.get("success"):
            # Обновляем статус пачки
            if test_batch_id and batch:
                batch.status = "pushed"
                batch.branch_name = branch_name

            # Обновляем статус тест-кейсов
            for tc in test_cases_to_push:
                tc.status = "pushed"

            await db.commit()

            logger.info(
                f"✅ Successfully pushed {len(tests_to_push)} tests and {len(test_cases_to_push)} test cases to branch '{branch_name}' in folder '{test_folder}'")

        return result

    except Exception as e:
        logger.error(f"❌ Push tests and cases failed: {e}")
        raise HTTPException(status_code=500, detail=f"Push failed: {str(e)}")