import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import auth, projects, agents, ai_route
from app.db.session import init_models
from app.services.ai_service import ai_service
from app.services.generate_pipeline import init_test_generation_pipeline

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # Используем stdout с правильной кодировкой
        logging.FileHandler('app.log', encoding='utf-8')  # Явно указываем кодировку для файла
    ]
)
logger = logging.getLogger("qa_automata")

app = FastAPI(title="QA Autopilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация пайплайна генерации тестов
test_generation_pipeline = None

from app.core.dependencies import init_app_dependencies

@app.on_event("startup")
async def on_startup():
    await init_models()
    # Инициализируем все зависимости приложения
    init_app_dependencies()
    logger.info("All app dependencies initialized")

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])
app.include_router(ai_route.router, prefix="/api/v1/ai", tags=["ai"])

@app.get("/")
async def root():
    return {"message": "QA Autopilot API is running"}

@app.get("/health")
async def health_check():
    pipeline_status = "initialized" if test_generation_pipeline else "not_initialized"
    return {
        "status": "healthy",
        "test_generation_pipeline": pipeline_status
    }