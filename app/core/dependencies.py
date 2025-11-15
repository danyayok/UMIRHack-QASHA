import logging
from app.services.ai_service import ai_service
from app.services.generate_pipeline import TestGenerationPipeline

logger = logging.getLogger("qa_automata")


class DependencyContainer:
    def __init__(self):
        self._test_generation_pipeline = None
        self._initialized = False

    def initialize(self):
        """Инициализация всех зависимостей приложения"""
        try:
            logger.info("🚀 INIT: Starting app dependencies initialization")

            # Инициализируем AI service если нужно
            if not hasattr(ai_service, 'initialized'):
                # Инициализируем AI сервис
                ai_service._init_gigachat()
                ai_service._init_ollama()
                ai_service.initialized = True

            # Создаем пайплайн
            self._test_generation_pipeline = TestGenerationPipeline(ai_service)
            self._initialized = True

            logger.info("✅ INIT: Dependencies initialized successfully")
            logger.info(f"✅ INIT: Pipeline: {self._test_generation_pipeline}")
            return True

        except Exception as e:
            logger.error(f"❌ INIT: Failed to initialize dependencies: {e}")
            self._initialized = False
            return False

    @property
    def test_generation_pipeline(self):
        if not self._initialized or self._test_generation_pipeline is None:
            raise RuntimeError(
                "Dependencies not initialized. Call dependencies.initialize() first."
            )
        return self._test_generation_pipeline

    def is_initialized(self):
        return self._initialized and self._test_generation_pipeline is not None


# Глобальный контейнер зависимостей
dependencies = DependencyContainer()


def init_app_dependencies():
    """Инициализация зависимостей приложения (для main.py)"""
    return dependencies.initialize()


def get_test_generation_pipeline():
    """Получение инициализированного пайплайна"""
    return dependencies.test_generation_pipeline


def get_ai_service():
    """Получение AI сервиса"""
    return ai_service