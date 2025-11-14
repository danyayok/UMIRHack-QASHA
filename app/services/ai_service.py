import logging
import asyncio
import g4f
import aiohttp
import json

import requests
from gigachat import GigaChat
import os
import time
from app.core.config import settings
from typing import Optional, Dict
import ollama
from ollama import Client


logger = logging.getLogger("qa_automata")


class HybridAIService:
    def __init__(self):
        self.giga = None
        self.giga_available = False
        self.ollama_available = False
        self.ollama_model = getattr(settings, 'OLLAMA_MODEL', 'qwen3-coder:480b')
        self._init_gigachat()
        self._init_ollama()

    def _init_gigachat(self):
        """Инициализация GigaChat если доступен API ключ"""
        try:
            giga_key = settings.GIGACHAT_KEY
            if giga_key:
                self.giga = GigaChat(
                    credentials=giga_key,
                    verify_ssl_certs=False,
                    model="GigaChat"
                )
                self.giga_available = True
                logger.info("GigaChat initialized successfully")
            else:
                logger.info("GIGACHAT_KEY not found, GigaChat will not be available")
        except Exception as e:
            logger.error(f"Failed to initialize GigaChat: {e}")
            self.giga_available = False

    def _init_ollama(self):
        """Инициализация облачного Ollama"""
        try:
            # Проверяем доступность через прямое API
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {settings.OLLAMA_API_KEY}'
            }

            response = requests.get(
                f"{settings.OLLAMA_HOST}/api/tags",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                self.ollama_available = True
                logger.info(f"✅ Ollama cloud initialized successfully with model: {self.ollama_model}")
            else:
                logger.error(f"❌ Ollama initialization failed: {response.status_code} - {response.text}")
                self.ollama_available = False

        except Exception as e:
            logger.error(f"Failed to initialize Ollama cloud: {e}")
            self.ollama_available = False

    async def answer_with_ollama(self, text: str, prompt: str, timeout: int = 120) -> Optional[str]:
        """Запрос к облачному Ollama с таймаутом"""
        if not self.ollama_available:
            logger.info("Ollama not available")
            return None

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(self._sync_ollama_request, text, prompt),
                timeout=timeout
            )

            if response and self._validate_ai_response(response):
                logger.info(f"✅ Ollama response received, length: {len(response)}")
                return response
            else:
                logger.warning(f"Ollama response invalid: {response}")
                return None

        except asyncio.TimeoutError:
            logger.error(f"Ollama request timed out after {timeout} seconds")
            return None
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return None

    def _sync_ollama_request(self, text: str, prompt: str) -> Optional[str]:
        """Синхронный метод запроса к облачному Ollama"""
        try:
            # Формируем промпт
            full_prompt = f"{prompt}\n\nЗапрос: {text}"

            payload = {
                "model": self.ollama_model,
                "prompt": full_prompt,
                "stream": False
            }

            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {settings.OLLAMA_API_KEY}'
            }

            response = requests.post(
                f"{settings.OLLAMA_HOST}/api/generate",
                headers=headers,
                json=payload,
                timeout=120
            )

            if response.status_code == 200:
                data = response.json()
                return data.get('response', '').strip()
            else:
                logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"Ollama cloud request failed: {e}")
            return None

    async def answer_with_g4f(self, text: str, prompt: str, model: str = 'gpt-4', timeout: int = 60) -> Optional[str]:
        """Запрос к g4f с таймаутом"""
        try:
            task = asyncio.create_task(self._g4f_request(text, prompt, model))
            response = await asyncio.wait_for(task, timeout=timeout)

            if response and "Извините, я не могу" not in response and len(response) > 30:
                return response
            else:
                logger.warning(f"g4f response too short or contains refusal: {response}")
                return None

        except asyncio.TimeoutError:
            logger.error(f"g4f request timed out after {timeout} seconds")
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
                timeout=60
            )
            return response
        except Exception as e:
            logger.error(f"g4f request failed: {e}")
            return None

    async def answer_with_gigachat(self, text: str, prompt: str, timeout: int = 30) -> Optional[str]:
        if not self.giga_available or not self.giga:
            return None

        try:
            full_prompt = f"{prompt}\n\nЗапрос: {text}"
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.giga.chat(full_prompt)
            )
            return response.choices[0].message.content
        except asyncio.TimeoutError:
            logger.error("GigaChat request timed out")
            return None
        except Exception as e:
            logger.error(f"GigaChat error: {e}")
            return None

    async def generate_test_content(self, file_info: Dict, project_context: Dict,
                                    test_type: str, framework: str, config: Dict) -> Optional[str]:
        """Генерация контента теста с проверкой входных данных"""

        if not isinstance(file_info, dict):
            logger.error(f"AI_VALIDATION_ERROR: file_info must be dict, got {type(file_info)}")
            if isinstance(file_info, list) and file_info:
                file_info = file_info[0] if isinstance(file_info[0], dict) else {"path": "unknown"}
            else:
                file_info = {"path": "unknown", "name": "unknown", "type": "unknown"}

        if not isinstance(project_context, dict):
            logger.error(f"AI_VALIDATION_ERROR: project_context must be dict, got {type(project_context)}")
            project_context = {}

        required_fields = ['path', 'name', 'has_content', 'ignored']
        for field in required_fields:
            if field not in file_info:
                file_info[field] = field == 'ignored'

        logger.info(f"AI_RECEIVED_DATA:")
        logger.info(f"  - File: {file_info.get('path', 'unknown')}")
        logger.info(f"  - File type: {type(file_info)}")
        logger.info(f"  - File keys: {list(file_info.keys())}")
        logger.info(f"  - Project technologies: {project_context.get('project_metadata', {}).get('technologies', [])}")
        logger.info(f"  - Has content: {file_info.get('has_content', False)}")

        if not project_context.get('project_metadata', {}).get('technologies'):
            logger.warning("AI: No technologies in project context!")

        if not file_info.get('has_content', False):
            logger.warning("AI: No file content available!")

        try:
            logger.info(f"AI_START: Generating {test_type} test for {file_info.get('path', 'unknown')}")
            logger.info(f"AI_INFO: Framework: {framework}, File type: {file_info.get('type', 'unknown')}")

            prompt = self._create_test_generation_prompt(test_type, framework, config)
            request_data = self._prepare_test_request_data(file_info, project_context, test_type, framework, config)

            logger.info(f"AI_PROMPT: Prompt length: {len(prompt)} chars")
            logger.info(f"AI_DATA: Request data length: {len(request_data)} chars")
            logger.info(f"AI_DATA_SAMPLE: {request_data[:200]}...")

            # ОБНОВЛЕННАЯ СТРАТЕГИЯ: Ollama -> g4f -> GigaChat -> fallback
            ai_providers = [
                ("Ollama", self.answer_with_ollama),
                ("g4f", self.answer_with_g4f),
                ("GigaChat", self.answer_with_gigachat)
            ]

            for provider_name, provider_func in ai_providers:
                logger.info(f"AI_{provider_name.upper()}: Trying {provider_name}...")

                try:
                    if provider_name == "g4f":
                        response = await provider_func(request_data, prompt, timeout=60)
                    else:
                        response = await provider_func(request_data, prompt)

                    if response and self._validate_ai_response(response):
                        logger.info(f"AI_{provider_name.upper()}_SUCCESS: Response received, length: {len(response)}")
                        logger.info(f"AI_{provider_name.upper()}_SAMPLE: {response[:200]}...")
                        return response
                    else:
                        logger.warning(f"AI_{provider_name.upper()}: No valid response from {provider_name}")

                except Exception as e:
                    logger.error(f"AI_{provider_name.upper()}_ERROR: {e}")

            # Final fallback - базовый шаблон
            logger.info("AI_FALLBACK: Using fallback template")
            fallback_content = self._create_fallback_test(file_info, framework, test_type)
            logger.info(f"AI_FALLBACK: Generated fallback, length: {len(fallback_content)}")
            return fallback_content

        except Exception as e:
            logger.error(f"AI_ERROR: Test generation failed: {e}", exc_info=True)
            fallback_content = self._create_fallback_test(file_info, framework, test_type)
            logger.info(f"AI_ERROR_FALLBACK: Using fallback due to error")
            return fallback_content

    def _validate_ai_response(self, response: str) -> bool:
        """Проверяет валидность ответа от AI"""
        if not response or len(response.strip()) < 50:
            return False
        if any(phrase in response for phrase in ["Извините", "Sorry", "I cannot", "I can't", "как AI"]):
            return False
        return True

    def _create_fallback_test(self, file_info: Dict, framework: str, test_type: str) -> str:
        """Создание базового теста при ошибке AI"""
        return f"""
# Auto-generated {test_type} test for {file_info.get('path', 'unknown')}
# Generated as fallback (AI service unavailable)

import pytest

def test_basic_functionality():
    \"\"\"Basic test - replace with actual test logic\"\"\"
    assert True
"""

    def _create_test_generation_prompt(self, test_type: str, framework: str, config: Dict) -> str:
        """Создание промпта для генерации тестов с учетом полной структуры проекта"""

        base_prompt = f"""
        Ты - эксперт по написанию тестов для программного обеспечения. 

        ## КРИТИЧЕСКИ ВАЖНЫЕ ПРАВИЛА:
        1. 🔥 Используй ТОЛЬКО реальные файлы и функциональность из предоставленной структуры проекта
        2. 🔥 Не выдумывай несуществующие модули, классы или функции  
        3. 🔥 Тестируй только то, что реально есть в проекте
        4. 🔥 Учитывай технологии и архитектуру проекта

        ## ТЕХНИЧЕСКИЕ ТРЕБОВАНИЯ:
        - Тип теста: {test_type}
        - Фреймворк: {framework}
        - Включить комментарии: {config.get('include_comments', True)}

        ## КАЧЕСТВО ТЕСТОВ:
        - Полное покрытие критической функциональности
        - Читаемые имена тестов и комментарии  
        - Правильные assertions/expectations
        - Обработка edge cases
        - Соответствие лучшим практикам для {framework}
        """

        if test_type == "api":
            base_prompt += f"""
            ## СПЕЦИФИКА ДЛЯ API ТЕСТОВ:
            - Тестируй только реальные эндпоинты из проекта
            - Проверяй статус коды ответов (200, 201, 400, 401, 404, 500)
            - Тестируй валидацию входных данных
            - Проверяй структуру JSON ответов
            - Тестируй аутентификацию и авторизацию (если есть в проекте)
            - Включай тесты для ошибок и edge cases
            """

        elif test_type == "unit":
            base_prompt += f"""
            ## СПЕЦИФИКА ДЛЯ UNIT ТЕСТОВ:
            - Тестируй каждую функцию/метод изолированно
            - Моки всех внешних зависимостей (API, DB, File System)  
            - Проверяй возвращаемые значения и side effects
            - Тестируй успешные сценарии AND ошибки
            - Используй параметризованные тесты для разных входных данных
            """

        base_prompt += "\n\nВерни только код теста без дополнительных объяснений. Он будет сразу вставлен в файл - любое иное слово сломает его работу"
        return base_prompt

    def _get_api_test_example(self, framework: str) -> str:
        """Примеры API тестов"""
        examples = {
            "pytest": '''
    # FastAPI API Test Example
    import pytest
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)

    def test_read_main():
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "Hello World"}

    def test_create_item():
        response = client.post(
            "/items/",
            json={"name": "Test Item", "price": 10.5}
        )
        assert response.status_code == 201
        assert "id" in response.json()

    def test_invalid_input():
        response = client.post(
            "/items/",
            json={"name": ""}  # Invalid empty name
        )
        assert response.status_code == 422
    ''',
            "unittest": '''
    # Flask API Test Example
    import unittest
    from app import create_app

    class TestAPI(unittest.TestCase):
        def setUp(self):
            self.app = create_app('testing')
            self.client = self.app.test_client()

        def test_get_users(self):
            response = self.client.get('/api/users')
            self.assertEqual(response.status_code, 200)
            self.assertIn('users', response.get_json())

        def test_create_user(self):
            user_data = {
                'email': 'test@example.com',
                'password': 'password123'
            }
            response = self.client.post('/api/users', json=user_data)
            self.assertEqual(response.status_code, 201)
    '''
        }
        return examples.get(framework, "")

    def _prepare_test_request_data(self, file_info: Dict, project_context: Dict, test_type: str, framework: str,
                                   config: Dict) -> str:
        """Подготовка данных для AI с ПОЛНОЙ структурой проекта"""

        if isinstance(file_info, list):
            if file_info:
                file_info = file_info[0] if isinstance(file_info[0], dict) else {"path": "unknown", "name": "unknown",
                                                                                 "type": "unknown"}
            else:
                file_info = {"path": "unknown", "name": "unknown", "type": "unknown"}

        file_path = file_info.get('path', 'unknown')
        file_name = file_info.get('name', 'unknown')

        project_structure = project_context.get('project_structure', {})
        complete_structure = project_structure.get('complete_file_structure', {})
        file_categories = project_structure.get('file_categories', {})

        request_data = f"""
    ## 📊 ПОЛНАЯ СТРУКТУРА ПРОЕКТА:

    ### 📈 СТАТИСТИКА:
    - Всего файлов: {len(complete_structure)}
    - Исходный код: {len(file_categories.get('source_code', []))}
    - Тесты: {len(file_categories.get('tests', []))}
    - Конфиги: {len(file_categories.get('config_files', []))}
    - Документация: {len(file_categories.get('documentation', []))}

    ### 🗂️ СТРУКТУРА ПРОЕКТА:
    """

        dir_structure = {}

        for dir_path, files_data in complete_structure.items():
            if not isinstance(files_data, list):
                continue

            if dir_path not in dir_structure:
                dir_structure[dir_path] = []

            for file_data in files_data:
                if isinstance(file_data, dict):
                    dir_structure[dir_path].append(file_data)

        for directory, files in sorted(dir_structure.items()):
            request_data += f"\n📁 {directory}/:\n"

            try:
                sorted_files = sorted(
                    [f for f in files if isinstance(f, dict)],
                    key=lambda x: x.get('name', '')
                )
            except Exception as e:
                logger.warning(f"Error sorting files in {directory}: {e}")
                sorted_files = files

            for file_data in sorted_files:
                if not isinstance(file_data, dict):
                    continue

                icon = self._get_file_icon(file_data)
                file_name = file_data.get('name', 'unknown')
                request_data += f"   {icon} {file_name}"

                if file_data.get('lines'):
                    request_data += f" ({file_data['lines']} lines)"
                request_data += "\n"

        if file_categories.get('config_files'):
            request_data += f"\n### ⚙️ КОНФИГУРАЦИОННЫЕ ФАЙЛЫ:\n"
            for config_file in file_categories['config_files'][:10]:
                if isinstance(config_file, dict):
                    request_data += f"   - {config_file.get('path', 'unknown')}\n"
                else:
                    request_data += f"   - {config_file}\n"

        request_data += f"""

    ### 🎯 ТЕКУЩАЯ ЗАДАЧА:
    Тип теста: {test_type}
    Фреймворк: {framework}
    Целевой файл: {file_path}

    ### 📝 ИНСТРУКЦИИ:
    Используй информацию о структуре проекта выше для создания релевантных тестов.
    Тестируй только реально существующую функциональность из указанных файлов.

    Сгенерируй {test_type.upper()} тест используя {framework.upper()}.

    # ВАЖНО!!!! #
    Не пиши НИЧЕГО кроме кода - никаких уточнений, обьяснений, вопросов - только код. твой ответ будет сразу вставляться в файл
    ЛЮБОЕ лишнее слово может СЛОМАТЬ файл, **ПИШИ ТОЛЬКО КОД*
    """
        print(request_data, len(request_data))
        return request_data

    def _get_file_icon(self, file_info: Dict) -> str:
        """Возвращает иконку для файла"""
        if file_info.get('is_test'):
            return '🧪'

        file_type = file_info.get('type', '')
        if 'python' in file_type:
            return '🐍'
        elif 'javascript' in file_type or 'react' in file_type:
            return '📜'
        elif 'java' in file_type:
            return '☕'
        elif 'html' in file_type:
            return '🌐'
        elif 'config' in file_type:
            return '⚙️'
        elif 'documentation' in file_type:
            return '📚'
        else:
            return '📄'


# Глобальный экземпляр сервиса
ai_service = HybridAIService()