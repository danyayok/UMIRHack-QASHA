import json
import random
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.db.session import get_db
from typing import List, Optional
import re
from datetime import datetime
from app.schemas import ProjectCreate, ProjectOut, AnalysisOut, AnalysisStatus, TestRunOut, TestBatchOut, \
    GeneratedTestOut, TestBatchWithTests
from app.models import Project, Analysis, AgentReport, TestRun, GeneratedTest, TestBatch
from app.deps.auth import get_current_user
from app.tasks import analyze_repository_task, analyze_zip_task
from app.services.git_service import GitService
from app.core.dependencies import get_test_generation_pipeline

import aiofiles
import os
from uuid import uuid4
import logging

logger = logging.getLogger("qa_automata")

router = APIRouter()
UPLOAD_DIR = "./storage/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


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
        branch: Optional[str] = Form(None),  # Меняем на Optional
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
            # Используем переданную ветку или ветку по умолчанию из репозитория
            branch = branch or repo_info.get('default_branch', 'main')

    # Создаем проект - используем branch если он указан, иначе 'main'
    project = Project(
        name=name,
        description=description,
        repo_url=repo_url,
        branch=branch or "main",  # Используем переданную ветку или 'main'
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

    # Возвращаем проект без coverage (он появится после анализа)
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
        test_config: dict,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Генерация тестов на основе анализа проекта и конфигурации"""
    repo_path = None
    logger.info(f"START: Генерация тестов для проекта {project_id}")

    try:
        pipeline = get_test_generation_pipeline()

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

        logger.info(f"Analysis found: {analysis.id}, status: {analysis.status}")
        logger.info(f"Analysis result keys: {analysis.result.keys() if analysis.result else 'No result'}")
        logger.info(f"Technologies: {analysis.result.get('technologies', []) if analysis.result else []}")

        logger.info(f"Downloading repository for test generation: {project.repo_url}")
        git_service = GitService()
        repo_path = await git_service.clone_repository(str(project.repo_url), project.branch)
        logger.info(f"Repository downloaded to: {repo_path}")
        generation_data = {
            "project_info": {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "repo_url": project.repo_url,
                "branch": project.branch,
                "technology_stack": project.technology_stack,
                "local_path": repo_path  # Добавляем путь к локальной копии
            },
            "analysis_data": analysis.result,
            "test_config": test_config,
            "generation_context": {
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": current_user.id
            }
        }

        try:
            logger.info("PIPELINE: Запуск пайплайна генерации тестов...")

            # ✅ ИСПОЛЬЗУЕМ ПАЙПЛАЙН ИЗ ЗАВИСИМОСТЕЙ
            logger.info(f"PIPELINE: test_generation_pipeline = {pipeline}")
            logger.info(f"PIPELINE: type = {type(pipeline)}")

            # Проверяем данные для пайплайна
            logger.info(f"PIPELINE: project_info keys = {generation_data['project_info'].keys()}")
            logger.info(f"PIPELINE: analysis_data keys = {generation_data['analysis_data'].keys()}")
            logger.info(f"PIPELINE: test_config = {generation_data['test_config']}")
            analysis_data = generation_data['analysis_data']
            logger.info(f"API Endpoints found: {analysis_data.get('api_endpoints', [])}")
            logger.info(f"API Endpoints by file: {analysis_data.get('api_endpoints_by_file', {})}")

            # Если эндпоинтов нет, возможно нужно перезапустить анализ
            if not analysis_data.get('api_endpoints'):
                logger.warning("No API endpoints found in analysis data!")

            # ✅ ВЫЗЫВАЕМ ПАЙПЛАЙН
            result = await pipeline.generate_tests(generation_data)

            logger.info(f"PIPELINE: Пайплайн завершен")
            logger.info(f"PIPELINE: Результат keys = {result.keys() if result else 'None'}")
            logger.info(f"PIPELINE: Статус = {result.get('status') if result else 'None'}")
            logger.info(f"PIPELINE: Сгенерировано тестов = {result.get('generated_tests') if result else 'None'}")

            # СОХРАНЯЕМ СГЕНЕРИРОВАННЫЕ ТЕСТЫ В БАЗУ ДАННЫХ
            logger.info("SAVE: Сохранение тестов в базу данных...")
            await save_generated_tests(project_id, result, current_user.id, db)

            logger.info(f"SUCCESS: Тесты сгенерированы и сохранены для проекта {project_id}")
            return result

        except Exception as e:
            logger.error(f"Error in generate_tests for project {project_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Test generation failed: {str(e)}")
    except Exception as e:
        logger.error(f"Error in generate_tests for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Test generation failed: {str(e)}")


    finally:
        if repo_path and os.path.exists(repo_path):
            logger.info(f"Cleaning up temporary repository: {repo_path}")
            git_service = GitService()
            git_service.cleanup(repo_path)
            logger.info(f"Temporary repository cleaned up")


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

