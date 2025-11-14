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
from typing import Optional, Dict, List
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
        """Создание УЛУЧШЕННОГО промпта для генерации тестов"""

        base_prompt = f"""
        Ты - старший QA инженер и эксперт по написанию тестов. 

        ## 🎯 КРИТИЧЕСКИ ВАЖНЫЕ ПРАВИЛА:
        1. 🔥 Используй ТОЛЬКО реальные файлы и функциональность из предоставленной структуры проекта
        2. 🔥 Не выдумывай несуществующие модули, классы или функции  
        3. 🔥 Тестируй только то, что реально есть в проекте
        4. 🔥 Учитывай технологии, архитектуру и бизнес-контекст проекта

        ## 📊 КОНТЕКСТ ПРОЕКТА:
        - Архитектура: {config.get('architecture', 'Unknown')}
        - Бизнес-домены: {config.get('domains', ['General'])}
        - Ключевые компоненты: {len(config.get('key_components', []))} найдено
        - Критические пути: {config.get('critical_paths', [])}

        ## 🛠️ ТЕХНИЧЕСКИЕ ТРЕБОВАНИЯ:
        - Тип теста: {test_type}
        - Фреймворк: {framework}
        - Приоритет тестирования: {config.get('priority_focus', ['Core functionality'])}
        - Рекомендуемые сценарии: {config.get('suggested_scenarios', ['Basic functionality'])}

        ## 🎪 КАЧЕСТВО ТЕСТОВ:
        - Полное покрытие критической функциональности
        - Тестирование edge cases и boundary conditions
        - Проверка обработки ошибок
        - Соответствие лучшим практикам для {framework}
        - Использование правильных assertions/expectations
        """

        if test_type == "api":
            base_prompt += f"""
            ## 🌐 СПЕЦИФИКА ДЛЯ API ТЕСТОВ:
            - Тестируй только реальные эндпоинты из проекта
            - Проверяй статус коды ответов (200, 201, 400, 401, 404, 500)
            - Тестируй валидацию входных данных
            - Проверяй структуру JSON ответов
            - Тестируй аутентификацию и авторизацию
            - Включай тесты для ошибок и edge cases
            - Тестируй производительность для критических endpoints
            """

        elif test_type == "unit":
            base_prompt += f"""
            ## 🔧 СПЕЦИФИКА ДЛЯ UNIT ТЕСТОВ:
            - Тестируй каждую функцию/метод изолированно
            - Моки всех внешних зависимостей (API, DB, File System)  
            - Проверяй возвращаемые значения и side effects
            - Тестируй успешные сценарии AND ошибки
            - Используй параметризованные тесты для разных входных данных
            - Тестируй boundary conditions и edge cases
            - Учитывай критичность компонента: {config.get('file_criticality', 'medium')}
            """

        base_prompt += f"""

        ## 🚀 ИНСТРУКЦИИ ДЛЯ ГЕНЕРАЦИИ:
        Используй ВЕСЬ предоставленный контекст проекта для создания релевантных тестов.
        Учитывай архитектуру, бизнес-логику и критические пути.

        Сгенерируй {test_type.upper()} тест используя {framework.upper()}.

        # 🚨 ВАЖНО!!!! #
        Не пиши НИЧЕГО кроме кода - никаких уточнений, обьяснений, вопросов - только код. 
        Твой ответ будет сразу вставляться в файл.
        ЛЮБОЕ лишнее слово может СЛОМАТЬ файл, **ПИШИ ТОЛЬКО КОД**
        """

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
        """УЛУЧШЕННАЯ подготовка данных с полным контекстом"""

        enhanced_content = file_info.get('enhanced_content', {})
        file_analysis = enhanced_content.get('analysis', {})
        specific_analysis = file_info.get('specific_file_analysis', {})

        request_data = f"""
    ## 🎯 КРИТИЧЕСКАЯ ИНФОРМАЦИЯ ДЛЯ ТЕСТИРОВАНИЯ:

    ### 📁 ФАЙЛ ДЛЯ ТЕСТИРОВАНИЯ:
    - Путь: {file_info.get('path', 'unknown')}
    - Тип: {file_info.get('type', 'unknown')}
    - Технология: {file_info.get('technology', 'unknown')}

    ### 🏗️ СТРУКТУРА ФАЙЛА:
    {self._format_detailed_structure(specific_analysis)}

    ### 🔗 СВЯЗАННЫЕ API ЭНДПОИНТЫ:
    {self._format_related_endpoints(file_info.get('related_endpoints', []))}

    ### 🎪 РЕКОМЕНДУЕМЫЕ СЦЕНАРИИ ТЕСТИРОВАНИЯ:
    {self._format_test_scenarios(file_info.get('test_scenarios', []))}

    ### 🎭 ЧТО НУЖНО МОКАИТЬ:
    {self._format_mock_suggestions(file_info.get('mock_suggestions', []))}

    ### 🛠️ ТЕХНОЛОГИИ ПРОЕКТА:
    - Основные: {project_context.get('project_metadata', {}).get('technologies', [])}
    - Фреймворки: {project_context.get('project_metadata', {}).get('frameworks', [])}
    - Архитектура: {project_context.get('project_metadata', {}).get('architecture', [])}

    ## 🚀 ИНСТРУКЦИИ ДЛЯ ГЕНЕРАЦИИ ТЕСТОВ:
    Сгенерируй {test_type.upper()} тест используя {framework.upper()}.
    Используй КОНКРЕТНЫЕ функции и классы из структуры выше.
    Тестируй РЕАЛЬНУЮ логику из файла.
    """

        return request_data

    def _format_detailed_structure(self, analysis: Dict) -> str:
        """Форматирует детальную структуру файла"""
        result = []

        if analysis.get('classes'):
            result.append("### Классы:")
            for cls in analysis['classes']:
                result.append(f"  class {cls.get('name')}:")
                for method in cls.get('methods', []):
                    result.append(f"    def {method.get('name')}({method.get('parameters')})")

        if analysis.get('functions'):
            result.append("### Функции:")
            for func in analysis['functions']:
                result.append(f"  def {func.get('name')}({func.get('parameters')})")

        return '\n'.join(result) if result else "  Файл не содержит классов/функций"

    def _format_related_endpoints(self, endpoints: List[Dict]) -> str:
        """Форматирует связанные эндпоинты"""
        if not endpoints:
            return "  Нет связанных API эндпоинтов"

        result = []
        for endpoint in endpoints:
            result.append(f"  {endpoint.get('method')} {endpoint.get('path')} -> {endpoint.get('function')}")

        return '\n'.join(result)

    def _format_test_scenarios(self, scenarios: List[str]) -> str:
        """Форматирует сценарии тестирования"""
        return '\n'.join([f"  - {scenario}" for scenario in scenarios])

    def _format_mock_suggestions(self, mocks: List[Dict]) -> str:
        """Форматирует предложения по мокам"""
        if not mocks:
            return "  Нет специфических требований к мокам"

        result = []
        for mock in mocks:
            result.append(f"  - {mock.get('target')}: {mock.get('reason')}")
            for example in mock.get('examples', []):
                result.append(f"    Пример: {example}")

        return '\n'.join(result)

    def _format_file_structure_for_ai(self, file_analysis: Dict) -> str:
        """Используем СУЩЕСТВУЮЩИЕ функции форматирования"""
        result = []

        # Используем существующие методы из ai_service
        classes_str = self._format_classes(file_analysis.get('classes', []))
        functions_str = self._format_functions(file_analysis.get('functions', []))

        if classes_str:
            result.append("### Классы:")
            result.append(classes_str)

        if functions_str:
            result.append("### Функции:")
            result.append(functions_str)

        return '\n'.join(result) if result else "   Файл не содержит классов/функций"

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

    def _format_imports(self, imports: List[Dict]) -> str:
        """Форматирует импорты для отображения"""
        if not imports:
            return "   Нет импортов"

        result = []
        for imp in imports:
            if imp['type'] == 'direct_import':
                result.append(f"   import {imp['module']}")
            elif imp['type'] == 'from_import':
                result.append(f"   from {imp['module']} import ...")
            elif imp['type'] == 'multi_import':
                result.append(f"   from {imp['module']} import ({', '.join(imp['imports'])})")

        return '\n'.join(result)

    def _format_classes(self, classes: List[Dict]) -> str:
        """Форматирует классы для отображения"""
        if not classes:
            return "   Нет классов"

        result = []
        for cls in classes:
            methods = ', '.join([m['name'] for m in cls.get('methods', [])[:3]])
            result.append(f"   class {cls['name']}({cls.get('inheritance', '')}) - методы: {methods}")

        return '\n'.join(result)

    def _format_functions(self, functions: List[Dict]) -> str:
        """Форматирует функции для отображения"""
        if not functions:
            return "   Нет функций"

        result = []
        for func in functions[:5]:  # Ограничиваем количество
            async_prefix = "async " if func.get('is_async') else ""
            result.append(f"   {async_prefix}def {func['name']}({func['parameters']})")

        return '\n'.join(result)

    def _format_db_operations(self, db_ops: List[Dict]) -> str:
        """Форматирует операции с БД"""
        if not db_ops:
            return "   Нет операций с БД"

        result = []
        for op in db_ops[:5]:
            result.append(f"   {op['type']}: {op['operation']} (использовано {op['count']} раз)")

        return '\n'.join(result)

    def _format_api_routes(self, routes: List[Dict]) -> str:
        """Форматирует API routes"""
        if not routes:
            return "   Нет API endpoints"

        result = []
        for route in routes[:5]:
            result.append(f"   {route['method']} {route['path']} ({route['type']})")

        return '\n'.join(result)

    def _format_error_handling(self, error_handlers: List[Dict]) -> str:
        """Форматирует обработку ошибок"""
        if not error_handlers:
            return "   Нет явной обработки ошибок"

        result = []
        for handler in error_handlers[:3]:
            result.append(f"   {handler['type']}: {handler['line'][:50]}...")

        return '\n'.join(result)

    def _format_configurations(self, configs: List[Dict]) -> str:
        """Форматирует конфигурации"""
        if not configs:
            return "   Нет конфигураций"

        result = []
        for config in configs:
            result.append(f"   {config['type']}: {config['setting'][:30]}...")

        return '\n'.join(result)

    def _format_imports_for_tests(self, imports: List[Dict], framework: str) -> str:
        """Форматирует импорты для использования в тестах"""
        test_imports = []

        # Базовые импорты для тестов
        if framework == 'pytest':
            test_imports.append("import pytest")
        elif framework == 'unittest':
            test_imports.append("import unittest")

        # Импорты из исходного файла
        for imp in imports:
            if imp['type'] == 'direct_import':
                test_imports.append(f"import {imp['module']}")
            elif imp['type'] == 'from_import':
                # Для тестов импортируем модуль полностью или конкретные функции
                test_imports.append(f"from {imp['module']} import *  # Или конкретные функции")

        return '\n'.join([f"   {imp}" for imp in test_imports])

    def _format_components_to_test(self, file_analysis: Dict) -> str:
        """Форматирует компоненты для тестирования"""
        components = []

        # Классы для тестирования
        for cls in file_analysis.get('classes', []):
            components.append(f"   - class {cls['name']}")
            for method in cls.get('methods', [])[:2]:
                components.append(f"     * method {method['name']}")

        # Функции для тестирования
        for func in file_analysis.get('functions', [])[:3]:
            components.append(f"   - function {func['name']}")

        return '\n'.join(components) if components else "   Все основные компоненты файла"

    def _format_mandatory_scenarios(self, file_analysis: Dict, test_type: str) -> str:
        """Форматирует обязательные сценарии тестирования"""
        scenarios = []

        if test_type == 'unit':
            scenarios.extend([
                "   - Тестирование всех публичных методов",
                "   - Тестирование граничных условий",
                "   - Тестирование обработки ошибок",
                "   - Тестирование возвращаемых значений"
            ])

        elif test_type == 'api':
            scenarios.extend([
                "   - Тестирование всех endpoints",
                "   - Тестирование валидации входных данных",
                "   - Тестирование статус кодов",
                "   - Тестирование структуры ответов"
            ])

        # Добавляем специфические сценарии на основе анализа файла
        if file_analysis.get('database_operations'):
            scenarios.append("   - Тестирование операций с базой данных")

        if file_analysis.get('error_handling'):
            scenarios.append("   - Тестирование обработки исключений")

        return '\n'.join(scenarios)

    def _format_testing_utilities(self, framework: str) -> str:
        """Форматирует утилиты тестирования"""
        utilities = []

        if framework == 'pytest':
            utilities.extend([
                "   - pytest fixtures для setup/teardown",
                "   - pytest.mark для маркировки тестов",
                "   - pytest.parametrize для параметризованных тестов",
                "   - unittest.mock для мокинга"
            ])
        elif framework == 'unittest':
            utilities.extend([
                "   - unittest.TestCase как базовый класс",
                "   - setUp и tearDown методы",
                "   - assert методы для проверок",
                "   - unittest.mock для мокинга"
            ])

        return '\n'.join(utilities)

# Глобальный экземпляр сервиса
ai_service = HybridAIService()