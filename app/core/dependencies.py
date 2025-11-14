# app/core/dependencies.py
import logging
from app.services.ai_service import ai_service
from app.services.generate_pipeline import init_test_generation_pipeline

logger = logging.getLogger("qa_automata")

# Глобальная переменная для всего приложения
test_generation_pipeline = None


def init_app_dependencies():
    """Инициализация всех зависимостей приложения"""
    global test_generation_pipeline
    logger.info("🚀 INIT: Starting app dependencies initialization")

    try:
        test_generation_pipeline = init_test_generation_pipeline(ai_service)
        logger.info(f"INIT: Pipeline initialized successfully")
        logger.info(f"INIT: Pipeline object: {test_generation_pipeline}")
        logger.info(f"INIT: Pipeline type: {type(test_generation_pipeline)}")
        return test_generation_pipeline
    except Exception as e:
        logger.error(f"INIT: Failed to initialize pipeline: {e}")
        raise


def get_test_generation_pipeline():
    """Получение инициализированного пайплайна"""
    logger.info(f"GET_PIPELINE: Checking pipeline status...")

    if test_generation_pipeline is None:
        logger.error("❌ GET_PIPELINE: Pipeline is None - not initialized!")
        raise RuntimeError("Test generation pipeline not initialized. Call init_app_dependencies() first.")

    logger.info(f"GET_PIPELINE: Pipeline retrieved successfully: {test_generation_pipeline}")
    return test_generation_pipeline