from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.db.session import get_db
from typing import List, Optional
from app.schemas import ProjectCreate, ProjectOut, AnalysisOut, AnalysisStatus
from app.models import Project, Analysis, AgentReport, TestRun
from app.deps.auth import get_current_user
from app.tasks import analyze_repository_task, analyze_zip_task
from app.services.git_service import GitService
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
        branch: Optional[str] = Form("main"),
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
            branch = repo_info.get('default_branch', branch)

    # Создаем проект
    project = Project(
        name=name,
        description=description,
        repo_url=repo_url,
        branch=branch if branch else "main",
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