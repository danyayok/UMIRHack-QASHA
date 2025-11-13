import logging
import asyncio
import g4f
from gigachat import GigaChat
import json
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)


class HybridAIService:
    def __init__(self):
        self.giga = None
        self.giga_available = False
        self._init_gigachat()

    def _init_gigachat(self):
        """Инициализация GigaChat если доступен API ключ"""
        try:
            giga_key = os.getenv("GIGACHAT_KEY")
            if giga_key:
                self.giga = GigaChat(
                    credentials=giga_key,
                    verify_ssl_certs=False,
                    model="GigaChat"
                )
                self.giga_available = True
                logger.info("GigaChat initialized successfully")
            else:
                logger.warning("GIGACHAT_KEY not found, GigaChat will not be available")
        except Exception as e:
            logger.error(f"Failed to initialize GigaChat: {e}")
            self.giga_available = False

    async def answer_with_g4f(self, text: str, prompt: str, model: str = 'gpt-4', timeout: int = 120) -> Optional[str]:
        """Запрос к g4f с таймаутом"""
        try:
            # Создаем задачу с таймаутом
            task = asyncio.create_task(self._g4f_request(text, prompt, model))
            response = await asyncio.wait_for(task, timeout=timeout)

            if response and "Извините, я не могу" not in response and len(response) > 30:
                return response
            else:
                logger.warning(f"g4f response too short or contains refusal: {response}")
                return None

        except asyncio.TimeoutError:
            logger.warning(f"g4f request timed out after {timeout} seconds")
            return None
        except Exception as e:
            logger.error(f"g4f error: {e}")
            return None

    async def _g4f_request(self, text: str, prompt: str, model: str) -> Optional[str]:
        """Внутренний метод запроса к g4f"""
        try:
            response = await g4f.ChatCompletion.create_async(
                model=model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text}
                ],
            )
            return response
        except Exception as e:
            logger.error(f"g4f request failed: {e}")
            return None

    async def answer_with_gigachat(self, text: str, prompt: str) -> Optional[str]:
        """Запрос к GigaChat"""
        if not self.giga_available or not self.giga:
            logger.error("GigaChat not available")
            return None

        try:
            full_prompt = f"{prompt}\n\nЗапрос: {text}"
            response = self.giga.chat(full_prompt)
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"GigaChat error: {e}")
            return None

    async def generate_test_content(self, file_info: Dict, project_context: Dict, test_type: str, framework: str,
                                    config: Dict) -> Optional[str]:
        """Генерация контента теста с использованием гибридного подхода"""

        # Подготавливаем промпт для генерации тестов
        prompt = self._create_test_generation_prompt(test_type, framework, config)

        # Подготавливаем данные для запроса
        request_data = self._prepare_test_request_data(file_info, project_context, test_type, framework, config)

        # Пытаемся сначала использовать g4f с таймаутом 2 минуты
        start_time = time.time()
        g4f_response = await self.answer_with_g4f(request_data, prompt, timeout=120)
        g4f_time = time.time() - start_time

        if g4f_response:
            logger.info(f"g4f successfully generated test in {g4f_time:.2f}s")
            return g4f_response

        # Если g4f не ответил за 2 минуты или вернул ошибку, используем GigaChat
        logger.warning(f"g4f failed or timed out after {g4f_time:.2f}s, falling back to GigaChat")

        if self.giga_available:
            giga_start = time.time()
            giga_response = await self.answer_with_gigachat(request_data, prompt)
            giga_time = time.time() - giga_start

            if giga_response:
                logger.info(f"GigaChat successfully generated test in {giga_time:.2f}s")
                return giga_response

        logger.error("Both g4f and GigaChat failed to generate test")
        return None

    def _create_test_generation_prompt(self, test_type: str, framework: str, config: Dict) -> str:
        """Создание промпта для генерации тестов"""

        base_prompt = f"""
Ты - эксперт по написанию тестов для программного обеспечения. Сгенерируй качественные тесты на основе предоставленной информации о проекте.

Тип теста: {test_type}
Фреймворк: {framework}
Включить комментарии: {config.get('include_comments', True)}
Целевое покрытие: {config.get('coverage_target', 80)}%

Требования к тестам:
1. Соответствие лучшим практикам для {framework}
2. Полное покрытие критической функциональности
3. Читаемые имена тестов и комментарии
4. Правильные assertions/expectations
5. Обработка edge cases
6. Использование фикстур и моков где необходимо

{"ДЛЯ UNIT ТЕСТОВ:" if test_type == "unit" else ""}
{"ДЛЯ ИНТЕГРАЦИОННЫХ ТЕСТОВ:" if test_type == "integration" else ""}
{"ДЛЯ E2E ТЕСТОВ:" if test_type == "e2e" else ""}

Верни только код теста без дополнительных объяснений.
"""
        return base_prompt

    def _prepare_test_request_data(self, file_info: Dict, project_context: Dict, test_type: str, framework: str,
                                   config: Dict) -> str:
        """Подготовка данных для запроса к ИИ"""

        request_data = f"""
ИНФОРМАЦИЯ О ПРОЕКТЕ:
- Технологии: {', '.join(project_context.get('technologies', []))}
- Архитектура: {', '.join(project_context.get('architecture_patterns', []))}
- Всего файлов: {project_context.get('total_files', 0)}
- Файлов кода: {project_context.get('code_files_count', 0)}
- Существующие тесты: {project_context.get('has_existing_tests', False)}

ИНФОРМАЦИЯ О ЦЕЛЕВОМ ФАЙЛЕ:
- Путь: {file_info.get('path', 'N/A')}
- Тип: {file_info.get('type', 'N/A')}
- Функций: {file_info.get('functions', 0)}
- Классов: {file_info.get('classes', 0)}
- Импорты: {', '.join(file_info.get('imports', []))}

ПРЕВЬЮ СОДЕРЖИМОГО:
{file_info.get('content_preview', 'N/A')}

СТРУКТУРА ПРОЕКТА (ключевые директории):
{json.dumps(project_context.get('file_structure', {}), indent=2, ensure_ascii=False)}

ЗАВИСИМОСТИ:
{json.dumps(project_context.get('dependencies', {}), indent=2, ensure_ascii=False)}

СГЕНЕРИРУЙ {test_type.upper()} ТЕСТ ДЛЯ ЭТОГО ФАЙЛА ИСПОЛЬЗУЯ {framework.upper()}
"""
        return request_data


# Глобальный экземпляр сервиса
ai_service = HybridAIService()