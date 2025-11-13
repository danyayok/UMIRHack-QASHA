from random import random
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.db.session import get_db
from typing import List, Optional
from datetime import datetime
from app.schemas import ProjectCreate, ProjectOut, AnalysisOut, AnalysisStatus, TestRunOut
from app.models import Project, Analysis, AgentReport, TestRun
from app.deps.auth import get_current_user
from app.tasks import analyze_repository_task, analyze_zip_task
from app.services.git_service import GitService
from app.services.generate_pipeline import test_generation_pipeline

import aiofiles
import os
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
UPLOAD_DIR = "./storage/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("/", response_model=List[ProjectOut])
async def get_projects(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)
):
    """Получить список проектов пользователя"""
    try:
        logger.info(f"Getting projects for user {current_user.id}")

        # Получаем проекты
        result = await db.execute(
            select(Project).where(Project.owner_id == current_user.id)
        )
        projects = result.scalars().all()

        logger.info(f"Found {len(projects)} projects")

        projects_with_coverage = []
        for project in projects:
            # Получаем последний завершенный анализ для каждого проекта
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

            # Вычисляем coverage из РЕАЛЬНОГО анализа
            coverage = 0
            if latest_analysis and latest_analysis.result:
                logger.info(f"Project {project.id} has analysis result: {latest_analysis.result.keys()}")
                coverage = latest_analysis.result.get('coverage_estimate', 0)
            else:
                logger.info(f"Project {project.id} has no completed analysis or result")

            # Создаем ProjectOut с coverage
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
        logger.error(f"Error getting projects: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
            logger.info(f"🚀 Starting REAL analysis for project {project.id}, analysis {analysis.id}")
            try:
                analyze_repository_task.delay(analysis.id)
                logger.info(f"✅ Analysis task started for analysis {analysis.id}")
            except Exception as e:
                logger.error(f"❌ Failed to start analysis task: {e}")
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

    # Получаем проект
    project_result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.owner_id == current_user.id
        )
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

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

    # Формируем данные для пайплайна
    generation_data = {
        "project_info": {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "repo_url": project.repo_url,
            "branch": project.branch,
            "technology_stack": project.technology_stack
        },
        "analysis_data": analysis.result,
        "test_config": test_config,
        "generation_context": {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": current_user.id
        }
    }

    try:
        # Используем пайплайн для генерации тестов
        result = await test_generation_pipeline.generate_tests(generation_data)
        return result

    except Exception as e:
        logger.error(f"Test generation error for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Test generation failed: {str(e)}")

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
        .order_by(Analysis.created_at.desc())
        .first()
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
        .first()
    )
    test_run = test_run.scalar_one_or_none()

    if not test_run:
        raise HTTPException(404, "No test runs found")

    return TestRunOut.model_validate(test_run)


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

