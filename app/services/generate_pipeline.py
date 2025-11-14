import os
import logging
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
import re
logger = logging.getLogger("qa_automata")


class TestGenerationPipeline:
    """Пайплайн для генерации тестов на основе анализа проекта"""

    def __init__(self, ai_service):
        self.ai_service = ai_service
        self.supported_frameworks = {
            'python': ['pytest', 'unittest', 'nose'],
            'javascript': ['jest', 'mocha', 'jasmine', 'cypress', 'playwright'],
            'typescript': ['jest', 'mocha', 'jasmine', 'cypress', 'playwright'],
            'java': ['junit', 'testng', 'selenium'],
            'html': ['cypress', 'playwright', 'selenium']
        }

    async def generate_tests(self, generation_data: Dict) -> Dict[str, Any]:
        """Основной метод генерации тестов"""
        try:
            # Валидация входных данных
            if not generation_data:
                return self._create_error_response("Empty generation data")

            required_keys = ["project_info", "analysis_data", "test_config"]
            for key in required_keys:
                if key not in generation_data:
                    return self._create_error_response(f"Missing required key: {key}")

            project_info = generation_data["project_info"]
            analysis_data = generation_data["analysis_data"]
            test_config = generation_data["test_config"]
            repo_path = project_info.get("local_path")

            logger.info(f"Starting test generation for project: {project_info.get('name', 'Unknown')}")

            # 🔍 ДИАГНОСТИКА: Проверяем наличие эндпоинтов ДО анализа
            logger.info(
                f"🔍 INITIAL_API_CHECK: API endpoints in analysis: {len(analysis_data.get('api_endpoints', []))}")

            # Если структура файлов пустая, анализируем репозиторий напрямую
            if not analysis_data.get('file_structure'):
                logger.warning("File structure is empty, analyzing repository directly")
                analysis_data = await self.analyze_repository_directly(repo_path, analysis_data)

            # 🔍 ДИАГНОСТИКА: Проверяем наличие эндпоинтов ПОСЛЕ анализа
            logger.info(f"🔍 AFTER_ANALYSIS_API_CHECK: API endpoints: {len(analysis_data.get('api_endpoints', []))}")

            # Продолжаем обычную обработку
            project_analysis = self.analyze_project_structure(analysis_data)

            # 🔍 УЛУЧШЕННАЯ ДИАГНОСТИКА ЭНДПОИНТОВ
            if not analysis_data.get('api_endpoints'):
                logger.warning("⚠️  No API endpoints found in analysis data, performing emergency search...")
                from app.services.code_analyzer import CodeAnalyzer
                emergency_analyzer = CodeAnalyzer()

                # Создаем временный анализ результат для emergency поиска
                emergency_analysis = {'api_endpoints': [], 'api_endpoints_by_file': {}}
                emergency_analyzer.detect_api_endpoints(Path(repo_path), emergency_analysis)

                # Объединяем результаты
                if emergency_analysis['api_endpoints']:
                    analysis_data['api_endpoints'] = emergency_analysis['api_endpoints']
                    analysis_data['api_endpoints_by_file'] = emergency_analysis['api_endpoints_by_file']
                    logger.info(
                        f"✅ EMERGENCY_SEARCH_SUCCESS: Found {len(emergency_analysis['api_endpoints'])} endpoints")
                else:
                    logger.error("❌ EMERGENCY_SEARCH_FAILED: No endpoints found even with emergency search")

                    # Дополнительная диагностика: какие файлы анализируются?
                    python_files = list(Path(repo_path).rglob("*.py"))
                    logger.info(f"🔍 DIAGNOSTIC: Total Python files: {len(python_files)}")

                    # Покажем несколько файлов для отладки
                    for i, py_file in enumerate(python_files[:10]):
                        logger.info(f"🔍 DIAGNOSTIC: Python file {i + 1}: {py_file}")

            # Обновляем project_analysis с новыми данными об эндпоинтах
            project_analysis['api_endpoints'] = analysis_data.get('api_endpoints', [])
            project_analysis['api_endpoints_by_file'] = analysis_data.get('api_endpoints_by_file', {})

            # Определяем фреймворк тестирования
            framework = self._get_test_framework(
                project_analysis["technologies"],
                project_analysis.get("existing_test_frameworks", []),
                test_config.get("framework", "auto")
            )

            # 🔍 ФИНАЛЬНАЯ ПРОВЕРКА
            logger.info(f"🔍 FINAL_API_CHECK: {len(project_analysis.get('api_endpoints', []))} endpoints for generation")

            # Генерируем тесты
            generation_results = await self._generate_test_files(
                project_analysis, test_config, framework, repo_path
            )

            # Формируем финальный ответ
            return {
                "status": "success",
                "project_name": project_info['name'],
                "generated_tests": generation_results["total_tests"],
                "test_files": generation_results["test_files"],
                "coverage_estimate": generation_results["coverage_estimate"],
                "framework_used": framework,
                "files_created": list(generation_results["test_files"].keys()),
                "warnings": generation_results["warnings"],
                "recommendations": generation_results["recommendations"],
                "generation_time": datetime.utcnow().isoformat(),
                "test_config_used": test_config,
                "ai_provider_used": generation_results["ai_provider"],
                "project_context": self._prepare_context(project_analysis)
            }
        except Exception as e:
            logger.error(f"Error in generate_tests: {e}")
            return {
                "status": "error",
                "error": str(e),
                "generation_time": datetime.utcnow().isoformat()
            }

    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """Создает стандартный ответ об ошибке"""
        return {
            "status": "error",
            "error": error_message,
            "generation_time": datetime.utcnow().isoformat()
        }

    async def analyze_repository_directly(self, repo_path: str, existing_analysis: Dict) -> Dict:
        """Прямой анализ репозитория если данные анализа неполные"""
        try:
            from app.services.code_analyzer import CodeAnalyzer

            analyzer = CodeAnalyzer()
            direct_analysis = await analyzer.analyze_repository(repo_path)

            # 🔍 ПРИНУДИТЕЛЬНЫЙ ПОИСК ЭНДПОИНТОВ
            if not direct_analysis.get('api_endpoints'):
                logger.warning("🔄 DIRECT_ANALYSIS: No endpoints found, performing forced search...")
                analyzer.detect_api_endpoints(Path(repo_path), direct_analysis)

            # Объединяем с существующим анализом
            existing_analysis.update(direct_analysis)
            return existing_analysis
        except Exception as e:
            logger.error(f"Error in analyze_repository_directly: {e}")
            return existing_analysis

    async def _generate_test_files(self, project_analysis: Dict, test_config: Dict,
                                   framework: str, repo_path: str) -> Dict[str, Any]:
        """Генерирует все типы тестовых файлов"""
        test_files = {}
        warnings = []
        recommendations = []
        ai_provider = "unknown"
        total_tests = 0

        try:
            if test_config.get("generate_unit_tests", True):
                unit_files, unit_count, provider = await self._generate_unit_tests(
                    project_analysis, framework, test_config, repo_path
                )
                test_files.update(unit_files)
                total_tests += unit_count  # ✅ Используем возвращаемое значение
                ai_provider = provider

            # API тесты
            if test_config.get("generate_api_tests", True):
                api_files, api_count, provider = await self._generate_api_tests(
                    project_analysis, framework, test_config, repo_path
                )
                test_files.update(api_files)
                total_tests += api_count  # ✅ Используем возвращаемое значение
                ai_provider = provider or ai_provider

            # Интеграционные тесты
            if test_config.get("generate_integration_tests", True):
                integration_files, integration_count, provider = await self._generate_integration_tests(
                    project_analysis, framework, test_config
                )
                test_files.update(integration_files)
                total_tests += len(integration_files)
                ai_provider = provider or ai_provider

            # E2E тесты
            if test_config.get("generate_e2e_tests", False):
                e2e_files, e2e_count, provider = await self._generate_e2e_tests(
                    project_analysis, framework, test_config
                )
                test_files.update(e2e_files)
                total_tests += len(e2e_files)
                ai_provider = provider or ai_provider

        except Exception as e:
            logger.error(f"Error in _generate_test_files: {e}")
            warnings.append(f"Error during test generation: {str(e)}")

        # Расчет покрытия
        coverage_estimate = self._calculate_coverage(
            total_tests,
            project_analysis.get("test_files_count", 0),
            project_analysis.get("code_files_count", 0)
        )

        return {
            "total_tests": total_tests,
            "test_files": test_files,
            "coverage_estimate": coverage_estimate,
            "warnings": warnings,
            "recommendations": recommendations,
            "ai_provider": ai_provider
        }

    async def _generate_unit_tests(self, project_analysis: Dict, framework: str,
                                   config: Dict, repo_path: str) -> Tuple[Dict[str, str], int, str]:
        """Генерирует unit тесты с правильным фреймворком для каждого файла"""
        test_files = {}
        code_files = project_analysis.get("code_files", [])
        ai_provider = "unknown"

        files_to_test = code_files[:config.get("max_unit_tests", 5)]

        for file_info in files_to_test:
            try:
                # Определяем фреймворк для конкретного файла
                file_framework = self._get_test_framework_for_file(file_info, framework)

                if not isinstance(file_info, dict):
                    continue

                file_info_copy = file_info.copy()

                # Получаем расширенное содержимое файла
                enhanced_content = self._get_enhanced_file_content(file_info_copy.get("path", ""), repo_path)
                file_info_copy["enhanced_content"] = enhanced_content
                file_info_copy["has_content"] = bool(enhanced_content.get("content"))

                # Подготавливаем контекст проекта
                project_context = self._prepare_context(project_analysis)

                # Добавляем специфическую информацию для тестирования
                file_specific_context = {
                    "file_criticality": self._assess_criticality(file_info_copy),
                    "is_core_component": self._is_critical_file(file_info_copy),
                    "suggested_test_scenarios": self._suggest_test_scenarios(file_info_copy, project_analysis),
                    "required_imports": self._get_required_test_imports(enhanced_content.get("analysis", {}),
                                                                        file_framework)
                }

                enhanced_file_info = {
                    **file_info_copy,
                    "context_hints": file_specific_context
                }
                enhanced_context = {
                    **project_context,
                    "specific_file_analysis": self._get_detailed_file_analysis(file_info_copy, repo_path),
                    "related_endpoints": self._find_related_endpoints(file_info_copy, project_analysis),
                    "test_scenarios": self._suggest_test_scenarios(file_info_copy, project_analysis),
                    "mock_suggestions": self._suggest_mocks(file_info_copy, project_analysis)
                }

                test_content = await self.ai_service.generate_test_content(
                    file_info=enhanced_file_info,
                    project_context=enhanced_context,
                    test_type="unit",
                    framework=file_framework,  # ✅ Используем фреймворк для конкретного файла
                    config=config
                )

                if test_content:
                    filename = self._generate_filename(file_info_copy, "unit", file_framework)
                    test_files[filename] = test_content
                    ai_provider = "ai_generated"
                else:
                    filename, content = await self._create_fallback_test(file_info_copy, file_framework,
                                                                         project_analysis)
                    test_files[filename] = content
                    ai_provider = "fallback"

            except Exception as e:
                logger.error(f"Error generating unit test for {file_info.get('path', 'unknown')}: {e}")
                file_framework = self._get_test_framework_for_file(file_info, framework)
                filename, content = await self._create_fallback_test(file_info, file_framework, project_analysis)
                test_files[filename] = content
                ai_provider = "fallback"

        return test_files, len(test_files), ai_provider

    def _get_required_test_imports(self, file_analysis: Dict, framework: str) -> List[str]:
        """Определяет необходимые импорты для тестов"""
        required_imports = []

        # Базовые импорты для фреймворка
        if framework == 'pytest':
            required_imports.extend(['pytest', 'unittest.mock'])
        elif framework == 'unittest':
            required_imports.extend(['unittest', 'unittest.mock'])

        # Импорты из исходного файла
        for imp in file_analysis.get('imports', []):
            if imp['type'] == 'direct_import':
                required_imports.append(imp['module'])

        return required_imports

    async def _generate_api_tests(self, project_analysis: Dict, framework: str,
                                  config: Dict, repo_path: str) -> Tuple[Dict[str, str], int, str]:
        """Генерирует API тесты с правильным фреймворком (pytest для FastAPI)"""
        test_files = {}
        ai_provider = "unknown"

        api_endpoints = project_analysis.get("api_endpoints", [])
        logger.info(f"GENERATE_API: Found {len(api_endpoints)} API endpoints")

        # Для FastAPI используем pytest
        api_framework = "pytest" if any(
            f in project_analysis.get('frameworks', []) for f in ['fastapi', 'flask', 'django']) else framework

        for endpoint in api_endpoints[:config.get("max_api_tests", 5)]:
            try:
                endpoint_file = endpoint.get('file', '')
                endpoint_file_content = self._get_file_content(endpoint_file, repo_path)

                # Создаем правильный file_info словарь
                mock_file_info = {
                    "path": f"api/{endpoint.get('method', 'GET')}_{endpoint.get('path', '').replace('/', '_')}",
                    "name": f"{endpoint.get('method', 'GET')}_{endpoint.get('path', '').replace('/', '_')}",
                    "type": "api_endpoint",
                    "extension": ".py",  # ✅ Для API тестов используем Python
                    "technology": "python",
                    "endpoint_info": endpoint,
                    "content_preview": endpoint_file_content[:2000] if endpoint_file_content else "No content",
                    "has_content": bool(endpoint_file_content),
                    "ignored": False,
                    "is_test": False,
                    "real_content": endpoint_file_content or "No endpoint implementation found"
                }

                logger.info(f"GENERATE_API: Generating test for {endpoint.get('method')} {endpoint.get('path')}")

                test_content = await self.ai_service.generate_test_content(
                    file_info=mock_file_info,
                    project_context=self._prepare_context(project_analysis),
                    test_type="api",
                    framework=api_framework,  # ✅ Используем правильный фреймворк для API
                    config=config
                )

                if test_content and len(test_content.strip()) > 50:
                    # Создаем безопасное имя файла
                    safe_method = endpoint.get('method', 'get').lower()
                    safe_path = endpoint.get('path', '').replace('/', '_').replace(':', '').replace('*', '')
                    filename = f"test_api_{safe_method}_{safe_path}.{self._get_file_ext(api_framework)}"
                    test_files[filename] = test_content
                    ai_provider = "ai_generated"
                    logger.info(f"GENERATE_API: Successfully generated API test: {filename}")
                else:
                    logger.warning(f"GENERATE_API: Empty response for endpoint {endpoint}")

            except Exception as e:
                logger.error(f"GENERATE_API: Error generating API test for endpoint {endpoint}: {e}")

        logger.info(f"GENERATE_API: Generated {len(test_files)} API test files")
        return test_files, len(test_files), ai_provider

    async def _generate_integration_tests(self, project_analysis: Dict, framework: str,
                                          config: Dict) -> Tuple[Dict[str, str], int, str]:
        """Генерирует интеграционные тесты"""
        test_files = {}
        ai_provider = "unknown"

        modules = self._find_integration_modules(project_analysis)

        for module in modules[:config.get("max_integration_tests", 3)]:
            try:
                mock_file_info = {
                    "path": f"integration/{module}",
                    "name": module,
                    "type": "integration_module"
                }

                test_content = await self.ai_service.generate_test_content(
                    file_info=mock_file_info,
                    project_context=self._prepare_context(project_analysis),
                    test_type="integration",
                    framework=framework,
                    config=config
                )

                if test_content:
                    filename = f"test_integration_{module}.{self._get_file_ext(framework)}"
                    test_files[filename] = test_content
                    ai_provider = "ai_generated"

            except Exception as e:
                logger.error(f"Error generating integration test for {module}: {e}")

        return test_files, len(test_files), ai_provider

    async def _generate_e2e_tests(self, project_analysis: Dict, framework: str, config: Dict, repo_path: str) -> Tuple[
        Dict[str, str], int, str]:
        """Генерация E2E тестов с правильным фреймворком"""
        test_files = {}
        ai_provider = "unknown"

        # Для E2E тестов используем Playwright для веб-приложений
        e2e_framework = "playwright" if any(tech in project_analysis.get('technologies', []) for tech in
                                            ['javascript', 'react', 'html', 'css']) else framework

        # Получаем E2E сценарии из анализа
        e2e_scenarios = project_analysis.get('e2e_scenarios', [])

        # Если сценариев нет, создаем базовые
        if not e2e_scenarios:
            e2e_scenarios = self._create_default_e2e_scenarios(project_analysis)

        logger.info(f"GENERATE_E2E: Found {len(e2e_scenarios)} E2E scenarios, using framework: {e2e_framework}")

        for scenario in e2e_scenarios[:config.get("max_e2e_tests", 5)]:
            try:
                # Создаем расширенный контекст для E2E теста
                e2e_context = self._prepare_e2e_context(scenario, project_analysis, repo_path)

                test_content = await self.ai_service.generate_test_content(
                    file_info={
                        "path": f"e2e/{scenario['name']}",
                        "name": scenario['name'],
                        "type": "e2e_scenario",
                        "scenario_data": scenario,
                        "e2e_context": e2e_context
                    },
                    project_context=self._prepare_context(project_analysis),
                    test_type="e2e",
                    framework=e2e_framework,  # ✅ Используем правильный E2E фреймворк
                    config=config
                )

                if test_content and len(test_content.strip()) > 100:
                    filename = f"test_e2e_{scenario['name']}.{self._get_file_ext(e2e_framework)}"
                    test_files[filename] = test_content
                    ai_provider = "ai_generated"
                    logger.info(f"GENERATE_E2E: Successfully generated E2E test: {filename}")
                else:
                    # Fallback для E2E тестов
                    fallback_content = self._create_e2e_fallback_test(scenario, e2e_framework)
                    filename = f"test_e2e_{scenario['name']}.{self._get_file_ext(e2e_framework)}"
                    test_files[filename] = fallback_content
                    ai_provider = "fallback"

            except Exception as e:
                logger.error(f"GENERATE_E2E: Error generating E2E test for {scenario['name']}: {e}")
                # Создаем fallback тест при ошибке
                fallback_content = self._create_e2e_fallback_test(scenario, e2e_framework)
                filename = f"test_e2e_{scenario['name']}.{self._get_file_ext(e2e_framework)}"
                test_files[filename] = fallback_content
                ai_provider = "fallback"

        logger.info(f"GENERATE_E2E: Generated {len(test_files)} E2E test files")
        return test_files, len(test_files), ai_provider

    def _prepare_e2e_context(self, scenario: Dict, project_analysis: Dict, repo_path: str) -> Dict:
        """Подготавливает контекст для E2E теста"""
        return {
            "scenario": scenario,
            "application_info": {
                "technologies": project_analysis.get('technologies', []),
                "frameworks": project_analysis.get('frameworks', []),
                "api_endpoints": project_analysis.get('api_endpoints', []),
                "authentication_required": self._has_authentication(project_analysis)
            },
            "test_data": {
                "users": self._generate_test_users(scenario),
                "sample_data": self._generate_sample_data(scenario),
                "environment": "testing"
            },
            "navigation_flow": scenario.get('steps', []),
            "assertions": self._generate_e2e_assertions(scenario)
        }

    def _create_e2e_fallback_test(self, scenario: Dict, framework: str) -> str:
        """Создает fallback E2E тест при ошибке AI"""
        test_name = scenario['name']
        description = scenario.get('description', 'E2E test scenario')
        steps = scenario.get('steps', [])

        if framework in ['pytest', 'playwright']:
            return f'''
    # E2E Test: {test_name}
    # Description: {description}

    import pytest
    from playwright.sync_api import sync_playwright

    class Test{test_name.title().replace('_', '')}:

        def test_{test_name}(self):
            """{description}"""

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                try:
                    # Test Steps:
    {chr(10).join([f'                # {step}' for step in steps])}

                    # TODO: Implement actual test steps
                    page.goto("http://localhost:3000")

                    # Basic assertions
                    assert page.title() is not None
                    assert page.url is not None

                finally:
                    browser.close()

        def test_{test_name}_steps(self):
            """Verify all scenario steps"""
            expected_steps = {steps}
            assert len(expected_steps) > 0, "Scenario should have defined steps"

            # Add specific step validations here
            for step in expected_steps:
                assert isinstance(step, str), f"Step should be string: {{step}}"
    '''
        else:
            return f'''
    # E2E Test: {test_name}
    # Description: {description}

    // TODO: Implement E2E test for: {description}
    // Steps: {', '.join(steps)}

    // This is a fallback E2E test template
    // Replace with actual implementation using your preferred E2E framework
    '''

    def _create_default_e2e_scenarios(self, project_analysis: Dict) -> List[Dict]:
        """Создает стандартные E2E сценарии если не найдены в анализе"""
        default_scenarios = [
            {
                'name': 'application_smoke_test',
                'type': 'e2e',
                'description': 'Basic application smoke test',
                'steps': [
                    'Open application homepage',
                    'Verify page loads correctly',
                    'Check critical elements present',
                    'Verify no console errors'
                ],
                'expected_outcome': 'Application starts without critical errors',
                'priority': 'high',
                'complexity': 'simple'
            },
            {
                'name': 'user_journey_flow',
                'type': 'e2e',
                'description': 'Complete user journey through main features',
                'steps': [
                    'Access application',
                    'Navigate through main sections',
                    'Perform key user actions',
                    'Verify data persistence',
                    'Check error handling'
                ],
                'expected_outcome': 'User can complete main journey without issues',
                'priority': 'high',
                'complexity': 'medium'
            }
        ]

        # Добавляем сценарии на основе API endpoints
        api_endpoints = project_analysis.get('api_endpoints', [])
        if api_endpoints:
            default_scenarios.append({
                'name': 'api_integration_flow',
                'type': 'e2e',
                'description': 'End-to-end API integration test',
                'steps': [
                    'Start application backend',
                    'Initialize test database',
                    'Execute key API calls',
                    'Verify API responses',
                    'Check data consistency'
                ],
                'expected_outcome': 'All critical APIs function correctly',
                'priority': 'high',
                'complexity': 'high'
            })

        return default_scenarios

    def _has_authentication(self, project_analysis: Dict) -> bool:
        """Проверяет требует ли приложение аутентификации"""
        auth_indicators = ['auth', 'login', 'jwt', 'token', 'session']

        # Проверяем файлы
        for file_path in project_analysis.get('file_structure', {}).keys():
            if any(indicator in file_path.lower() for indicator in auth_indicators):
                return True

        # Проверяем API endpoints
        for endpoint in project_analysis.get('api_endpoints', []):
            if any(indicator in endpoint.get('path', '').lower() for indicator in auth_indicators):
                return True

        return False

    def _generate_test_users(self, scenario: Dict) -> List[Dict]:
        """Генерирует тестовых пользователей для E2E сценария"""
        return [
            {
                "username": "test_user",
                "password": "test_password123",
                "role": "user",
                "email": "test@example.com"
            },
            {
                "username": "admin_user",
                "password": "admin_password123",
                "role": "admin",
                "email": "admin@example.com"
            }
        ]

    def _generate_sample_data(self, scenario: Dict) -> Dict:
        """Генерирует примеры данных для E2E теста"""
        return {
            "sample_input": "test_data",
            "expected_output": "expected_result",
            "validation_rules": {
                "required_fields": ["id", "name"],
                "data_types": {"id": "integer", "name": "string"}
            }
        }

    def _generate_e2e_assertions(self, scenario: Dict) -> List[str]:
        """Генерирует утверждения для E2E теста"""
        assertions = [
            "Page loads without errors",
            "Critical elements are visible",
            "User interactions work correctly",
            "Data validation passes",
            "Navigation works as expected"
        ]

        # Добавляем специфичные утверждения на основе сценария
        if 'auth' in scenario['name']:
            assertions.extend([
                "User can login successfully",
                "Protected routes are accessible after auth",
                "Logout functionality works"
            ])

        if 'api' in scenario['name']:
            assertions.extend([
                "API responses are valid",
                "Error handling works for invalid requests",
                "Data consistency maintained"
            ])

        return assertions

    def _get_primary_language(self, technologies: List[str]) -> str:
        """Определяет основной язык проекта с приоритетом бэкенда"""
        priority_languages = ["python", "java", "javascript", "typescript", "go", "ruby", "php"]

        for lang in priority_languages:
            if lang in technologies:
                return lang

        return technologies[0] if technologies else "python"
    def _get_test_framework(self, technologies: List[str], existing_frameworks: List[str],
                            user_choice: str) -> str:
        """Определяет фреймворк тестирования с приоритетом по основному языку"""
        if user_choice != "auto":
            return user_choice

        # Определяем основной язык проекта
        primary_language = self._get_primary_language(technologies)

        # Сопоставляем язык с фреймворком
        framework_map = {
            "python": "pytest",
            "javascript": "jest",
            "typescript": "jest",
            "java": "junit",
            "html": "cypress",
            "cpp": "gtest",
            "csharp": "nunit",
            "go": "testing",
            "ruby": "rspec",
            "php": "phpunit"
        }

        known_frameworks = [f for f in existing_frameworks if f and f != 'unknown']
        if known_frameworks:
            return known_frameworks[0]

        return framework_map.get(primary_language, "pytest")

    def _calculate_coverage(self, generated_tests: int, existing_tests: int, total_files: int) -> float:
        """Рассчитывает оценку покрытия"""
        if total_files == 0:
            return 0.0

        total_tests = generated_tests + existing_tests
        base_coverage = min(95.0, (total_tests / max(1, total_files)) * 100)
        return round(base_coverage, 1)

    def _generate_filename(self, file_info: Dict, test_type: str, framework: str) -> str:
        """Генерирует имя тестового файла"""
        base_name = file_info.get("name", "unknown").replace(file_info.get("extension", ""), "")
        safe_name = "".join(c for c in base_name if c.isalnum() or c in ('_', '-')).rstrip()
        return f"test_{test_type}_{safe_name}.{self._get_file_ext(framework)}"

    def _get_file_ext(self, framework: str) -> str:
        """Возвращает правильное расширение файла для фреймворка"""
        extensions = {
            "pytest": "py", "unittest": "py", "nose": "py", "doctest": "py",
            "jest": "js", "mocha": "js", "jasmine": "js", "cypress": "js", "playwright": "js",
            "junit": "java", "testng": "java",
            "nunit": "cs", "xunit": "cs", "mstest": "cs",
            "gtest": "cpp", "catch2": "cpp",
            "testing": "go", "testify": "go",
            "rspec": "rb", "minitest": "rb",
            "phpunit": "php",
            "xctest": "swift",
            "unknown": "py"
        }
        return extensions.get(framework, "py")

    def _get_file_content(self, file_path: str, repo_path: str = "") -> str:
        """Безопасное получение содержимого файла - ДОПОЛНЕННАЯ ВЕРСИЯ"""
        if not file_path:
            return ""
        absolute_path = self._find_absolute_file_path(file_path, repo_path)
        logger.info(f"Looking for file: {file_path} -> {absolute_path}")
        if not os.path.exists(absolute_path) or not os.path.isfile(absolute_path):
            logger.warning(f"File not found: {absolute_path}")
            return ""
        try:
            with open(absolute_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if len(content) > 100000:
                    content = content[:100000] + "\n# ... [FILE TRUNCATED FOR ANALYSIS]"
                logger.info(f"GET_FILE_CONTENT: Successfully read {len(content)} chars from {absolute_path}")
                return content
        except UnicodeDecodeError:
            try:
                with open(absolute_path, 'r', encoding='latin-1') as f:
                    content = f.read()
                    if len(content) > 100000:
                        content = content[:100000] + "\n# ... [FILE TRUNCATED FOR ANALYSIS]"
                    logger.info(f"GET_FILE_CONTENT: Successfully read with latin-1: {len(content)} chars")
                    return content
            except Exception as e:
                logger.warning(f"Could not read file {absolute_path} with any encoding: {e}")
                return ""
        except Exception as e:
            logger.warning(f"Error reading file {absolute_path}: {e}")
            return ""

    async def _create_fallback_test(self, file_info: Dict, framework: str,
                                    project_analysis: Dict) -> Tuple[str, str]:
        """Создает fallback тест с правильным фреймворком"""
        file_name = file_info.get('name', 'unknown').replace('.', '').title()

        if framework == "pytest":
            content = f'''
    # Fallback test for {file_info.get('path', 'unknown')}

    import pytest

    class Test{file_name}:
        def test_basic_functionality(self):
            """Basic test - replace with actual test logic"""
            assert True

        def test_edge_cases(self):
            """Test edge cases"""
            assert 1 == 1
    '''
        elif framework == "jest":
            content = f'''
    // Fallback test for {file_info.get('path', 'unknown')}

    describe('{file_name}', () => {{
        test('basic functionality', () => {{
            expect(true).toBe(true);
        }});

        test('edge cases', () => {{
            expect(1).toBe(1);
        }});
    }});
    '''
        else:
            content = f'''
    # Fallback test for {file_info.get('path', 'unknown')}
    # Framework: {framework}

    // TODO: Implement actual tests for {file_info.get('path', 'unknown')}
    '''

        filename = self._generate_filename(file_info, "unit", framework)
        return filename, content

    def _find_integration_modules(self, project_analysis: Dict) -> List[str]:
        """Находит модули для интеграционного тестирования"""
        modules = []
        for file_info in project_analysis.get("code_files", []):
            path_lower = file_info.get("path", "").lower()
            if any(keyword in path_lower for keyword in ["api", "service", "controller"]):
                modules.append(file_info.get("name", "unknown"))
        return modules[:10]

    def _find_e2e_scenarios(self, project_analysis: Dict) -> List[str]:
        """Находит сценарии для E2E тестирования"""
        scenarios = ["user_authentication", "main_workflow"]
        technologies = [tech.lower() for tech in project_analysis.get("technologies", [])]

        if "react" in technologies:
            scenarios.append("component_rendering")
        if any("api" in file_info.get("path", "").lower() for file_info in project_analysis.get("code_files", [])):
            scenarios.append("api_endpoints")
        return scenarios

    def _prepare_context(self, project_analysis: Dict) -> Dict[str, Any]:
        """Подготавливает РАСШИРЕННЫЙ контекст проекта для AI"""
        if not project_analysis:
            return self._create_empty_context()

        file_structure = project_analysis.get('file_structure', {})

        # Формируем полную структуру файлов проекта
        complete_file_structure = self._prepare_complete_file_structure(file_structure)

        # Базовый контекст
        base_context = {
            "project_metadata": {
                "name": project_analysis.get('project_name', 'Unknown'),
                "technologies": project_analysis.get('technologies', []),
                "frameworks": project_analysis.get('frameworks', []),
                "architecture": project_analysis.get('architecture_patterns', []),
            },
            "project_structure": {
                "total_files": project_analysis.get('total_files', 0),
                "code_files_count": project_analysis.get('code_files_count', 0),
                "test_files_count": project_analysis.get('test_files_count', 0),
                "total_lines": project_analysis.get('total_lines', 0),
                "total_size_kb": project_analysis.get('total_size_kb', 0),
                "complete_file_structure": complete_file_structure,
            },
            "testing_context": {
                "has_tests": project_analysis.get('has_existing_tests', False),
                "test_frameworks": project_analysis.get('existing_test_frameworks', []),
                "test_files_count": project_analysis.get('test_files_count', 0),
                "coverage_estimate": project_analysis.get('coverage_estimate', 0),
            },
            "dependencies": project_analysis.get('dependencies', {}),
            "api_endpoints": project_analysis.get('api_endpoints', []),
        }

        # ДОБАВЛЯЕМ РАСШИРЕННЫЙ КОНТЕКСТ
        enhanced_context = {
            **base_context,
            "semantic_analysis": {
                "key_components": self._identify_key_components(project_analysis, ""),
                "critical_paths": self._find_critical_paths(project_analysis),
                "error_handling_patterns": self._analyze_error_handling(project_analysis)
            },
            "business_context": {
                "domains": self._detect_business_domains(project_analysis),
                "core_functions": self._identify_core_functions(project_analysis),
                "data_entities": self._identify_data_entities(project_analysis)
            },
            "testing_recommendations": {
                "priority_focus": self._determine_test_priority(project_analysis),
                "recommended_test_types": self._recommend_test_types(project_analysis),
                "risk_areas": self._identify_risk_areas(project_analysis)
            }
        }

        logger.info(
            f"Enhanced context prepared with {len(enhanced_context['semantic_analysis']['key_components'])} key components")
        return enhanced_context

    def _get_test_framework_for_file(self, file_info: Dict, project_framework: str) -> str:
        """Определяет фреймворк тестирования для конкретного файла"""
        file_tech = file_info.get('technology', '').lower()
        file_ext = file_info.get('extension', '').lower()

        # Для Python файлов используем pytest
        if file_tech == 'python' or file_ext in ['.py', '.pyw']:
            return 'pytest'

        # Для JavaScript/React файлов используем jest
        if file_tech in ['javascript', 'react'] or file_ext in ['.js', '.jsx', '.ts', '.tsx']:
            return 'jest'

        # Для HTML/CSS файлов используем playwright для E2E
        if file_tech in ['html', 'css'] or file_ext in ['.html', '.css']:
            return 'playwright'

        return project_framework
    def _create_empty_context(self) -> Dict[str, Any]:
        """Создает пустой контекст при отсутствии данных"""
        return {
            "project_metadata": {
                "name": "Unknown",
                "technologies": [],
                "frameworks": [],
                "architecture": [],
            },
            "project_structure": {
                "total_files": 0,
                "code_files_count": 0,
                "test_files_count": 0,
                "total_lines": 0,
                "total_size_kb": 0,
                "complete_file_structure": {},
            },
            "testing_context": {
                "has_tests": False,
                "test_frameworks": [],
                "test_files_count": 0,
                "coverage_estimate": 0,
            },
            "dependencies": {},
            "api_endpoints": [],
        }

    def _prepare_complete_file_structure(self, file_structure: Dict) -> Dict:
        """Подготавливает полную структуру файлов для AI"""
        if not file_structure:
            return {}

        structured_files = {}

        for file_path, file_info in file_structure.items():
            if isinstance(file_info, dict):
                # Группируем файлы по директориям
                dir_path = os.path.dirname(file_path) or "root"
                filename = os.path.basename(file_path)

                if dir_path not in structured_files:
                    structured_files[dir_path] = []

                structured_files[dir_path].append({
                    "name": filename,
                    "path": file_path,
                    "technology": file_info.get('technology', 'unknown'),
                    "extension": file_info.get('extension', ''),
                    "is_test": file_info.get('is_test', False),
                    "size": file_info.get('size', 0),
                    "lines": file_info.get('lines', 0),
                    "type": self._classify_file_type_by_extension(file_info.get('extension', ''))
                })

        return structured_files

    def _classify_file_type_by_extension(self, extension: str) -> str:
        """Классифицирует файлы по расширению"""
        type_map = {
            '.py': 'python_module',
            '.js': 'javascript_module',
            '.jsx': 'react_component',
            '.ts': 'typescript_module',
            '.tsx': 'react_typescript_component',
            '.java': 'java_class',
            '.html': 'html_template',
            '.css': 'styles',
            '.scss': 'styles',
            '.php': 'php_script',
            '.rb': 'ruby_script',
            '.go': 'go_module',
            '.rs': 'rust_module',
            '.cs': 'csharp_class',
            '.cpp': 'cpp_source',
            '.h': 'cpp_header',
            '.json': 'configuration',
            '.yaml': 'configuration',
            '.yml': 'configuration',
            '.xml': 'configuration',
            '.md': 'documentation',
            '.txt': 'documentation'
        }
        return type_map.get(extension, 'unknown')

    def _format_api_routes(self, routes: List[Dict]) -> str:
        """Форматирует API routes"""
        if not routes:
            return "   Нет API endpoints"

        result = []
        for route in routes[:5]:
            result.append(f"   {route['method']} {route['path']} ({route['type']})")

        return '\n'.join(result)
    def _get_language_from_framework(self, framework: str) -> str:
        """Определение языка по фреймворку"""
        lang_map = {
            # Python
            'pytest': 'python', 'unittest': 'python', 'nose': 'python', 'nose2': 'python',
            'doctest': 'python', 'robot': 'python', 'behave': 'python', 'lettuce': 'python',
            'selenium-python': 'python', 'requests': 'python', 'zap': 'python',

            # JavaScript/TypeScript
            'jest': 'javascript', 'mocha': 'javascript', 'jasmine': 'javascript', 'karma': 'javascript',
            'ava': 'javascript', 'tape': 'javascript', 'qunit': 'javascript', 'vitest': 'javascript',
            'cypress': 'javascript', 'playwright': 'javascript', 'puppeteer': 'javascript',
            'selenium': 'javascript', 'testcafe': 'javascript', 'webdriverio': 'javascript',
            'protractor': 'javascript', 'vue-test-utils': 'javascript', 'react-testing-library': 'javascript',
            'enzyme': 'javascript', 'selenium-javascript': 'javascript', 'supertest': 'javascript',
            'appium': 'javascript', 'detox': 'javascript', 'k6': 'javascript',

            # Java
            'junit': 'java', 'testng': 'java', 'mockito2': 'java', 'spock2': 'java',
            'assertj': 'java', 'rest-assured': 'java', 'selenium-java': 'java', 'http-client': 'java',
            'espresso': 'java', 'jmeter': 'java', 'burp': 'java',

            # C#
            'nunit': 'csharp', 'xunit': 'csharp', 'mstest': 'csharp', 'moq': 'csharp',
            'fakeiteasy': 'csharp', 'specflow': 'csharp', 'selenium-csharp': 'csharp',

            # C++
            'gtest': 'cpp', 'catch2': 'cpp', 'boost.test': 'cpp', 'doctest2': 'cpp', 'cppunit': 'cpp',

            # Go
            'testing': 'go', 'testify': 'go', 'ginkgo': 'go', 'goconvey': 'go', 'httpexpect': 'go',

            # Ruby
            'rspec': 'ruby', 'minitest': 'ruby', 'test-unit': 'ruby', 'cucumber-ruby': 'ruby', 'selenium-ruby': 'ruby',

            # PHP
            'phpunit': 'php', 'codeception': 'php', 'phpspec': 'php', 'behat': 'php',

            # Swift
            'xctest': 'swift', 'quick': 'swift', 'nimble': 'swift', 'xcuitest': 'swift',

            # Kotlin
            'kotlintest': 'kotlin', 'spek': 'kotlin', 'mockk': 'kotlin',

            # Rust
            'rust-test': 'rust', 'proptest': 'rust', 'mockall': 'rust',

            # Dart/Flutter
            'flutter_test': 'dart', 'test': 'dart', 'mockito': 'dart',

            # R
            'testthat': 'r',

            # Scala
            'scalatest': 'scala', 'specs2': 'scala', 'scalacheck': 'scala', 'gatling': 'scala',

            # Groovy
            'spock': 'groovy',

            # Perl
            'test-simple': 'perl', 'test-more': 'perl',

            # Haskell
            'hspec': 'haskell', 'hunit': 'haskell', 'quickcheck': 'haskell',

            # Elixir
            'exunit': 'elixir',

            # Clojure
            'clojure.test': 'clojure', 'midje': 'clojure',

            # Shell/Bash
            'bats': 'bash', 'shunit2': 'bash',

            # SQL
            'tsqlt': 'sql', 'utplsql': 'sql',
        }

        framework_lower = framework.lower()

        # Прямое сопоставление
        if framework_lower in lang_map:
            return lang_map[framework_lower]

        # Частичное сопоставление
        for key, language in lang_map.items():
            if framework_lower in key or key in framework_lower:
                return language

        # Определение по ключевым словам
        if any(word in framework_lower for word in ['py', 'python']):
            return 'python'
        elif any(word in framework_lower for word in
                 ['js', 'javascript', 'node', 'react', 'vue', 'angular', 'ts', 'typescript']):
            return 'javascript'
        elif any(word in framework_lower for word in ['java', 'junit', 'testng']):
            return 'java'
        elif any(word in framework_lower for word in ['c#', 'csharp', 'dotnet', 'nunit']):
            return 'csharp'
        elif any(word in framework_lower for word in ['cpp', 'c++', 'gtest']):
            return 'cpp'
        elif any(word in framework_lower for word in ['go', 'golang']):
            return 'go'
        elif any(word in framework_lower for word in ['ruby', 'rails', 'rspec']):
            return 'ruby'
        elif any(word in framework_lower for word in ['php']):
            return 'php'
        elif any(word in framework_lower for word in ['swift']):
            return 'swift'
        elif any(word in framework_lower for word in ['kotlin']):
            return 'kotlin'
        elif any(word in framework_lower for word in ['rust']):
            return 'rust'
        elif any(word in framework_lower for word in ['dart', 'flutter']):
            return 'dart'
        elif any(word in framework_lower for word in ['r', 'rlang']):
            return 'r'
        elif any(word in framework_lower for word in ['scala']):
            return 'scala'
        elif any(word in framework_lower for word in ['groovy']):
            return 'groovy'
        elif any(word in framework_lower for word in ['perl']):
            return 'perl'
        elif any(word in framework_lower for word in ['haskell']):
            return 'haskell'
        elif any(word in framework_lower for word in ['elixir']):
            return 'elixir'
        elif any(word in framework_lower for word in ['clojure']):
            return 'clojure'
        elif any(word in framework_lower for word in ['bash', 'shell', 'sh']):
            return 'bash'
        elif any(word in framework_lower for word in ['sql']):
            return 'sql'

        return 'python'

    def analyze_project_structure(self, analysis_data: Dict) -> Dict[str, Any]:
        """Анализ структуры проекта для генерации тестов с полными данными"""
        if not analysis_data:
            return self._create_empty_project_analysis()

        logger.info(f"ANALYSIS_DATA_KEYS: {analysis_data.keys()}")

        # Извлекаем все необходимые данные
        technologies = analysis_data.get("technologies", [])
        frameworks = analysis_data.get("frameworks", [])
        test_analysis = analysis_data.get("test_analysis", {})
        metrics = analysis_data.get("metrics", {})
        dependencies = analysis_data.get("dependencies", {})
        file_structure = analysis_data.get("file_structure", {})

        # Извлекаем файлы кода
        code_files = self.extract_code_files(file_structure, technologies)

        return {
            "technologies": technologies,
            "frameworks": frameworks,
            "file_structure": file_structure,
            "code_files": code_files,
            "total_files": metrics.get('total_files', 0),
            "code_files_count": metrics.get('code_files', 0),
            "test_files_count": metrics.get('test_files', 0),
            "dependencies": dependencies,
            "test_analysis": test_analysis,
            "metrics": metrics,
            "existing_test_frameworks": test_analysis.get("test_frameworks", []),
            "has_existing_tests": test_analysis.get("has_tests", False),
            "test_directories": test_analysis.get("test_directories", []),
            "architecture_patterns": self.detect_architecture_patterns(file_structure, technologies),
            "complexity_metrics": analysis_data.get("complexity_metrics", {}),
            "coverage_estimate": analysis_data.get("coverage_estimate", 0),
            "project_structure": analysis_data.get("project_structure", {}),
            "api_endpoints": analysis_data.get("api_endpoints", [])
        }

    def _create_empty_project_analysis(self) -> Dict[str, Any]:
        """Создает пустой анализ проекта"""
        return {
            "technologies": [],
            "frameworks": [],
            "file_structure": {},
            "code_files": [],
            "total_files": 0,
            "code_files_count": 0,
            "test_files_count": 0,
            "dependencies": {},
            "test_analysis": {},
            "metrics": {},
            "existing_test_frameworks": [],
            "has_existing_tests": False,
            "test_directories": [],
            "architecture_patterns": [],
            "complexity_metrics": {},
            "coverage_estimate": 0,
            "project_structure": {},
            "api_endpoints": []
        }

    def extract_code_files(self, file_structure: Dict, technologies: List[str]) -> List[Dict]:
        """Извлечение файлов с кодом и их метаданными"""
        logger.info("EXTRACT_START: Extracting code files")

        if not file_structure:
            logger.warning("Empty file structure provided")
            return []

        code_files = []
        code_extensions = self.get_code_extensions(technologies)

        for file_path, file_info in file_structure.items():
            if not isinstance(file_info, dict):
                logger.warning(f"Invalid file info for {file_path}: {type(file_info)}")
                continue

            file_ext = file_info.get('extension', '')
            file_tech = file_info.get('technology', '')
            is_test = file_info.get('is_test', False)

            # Если расширение не указано, определяем по пути
            if not file_ext:
                file_ext = os.path.splitext(file_path)[1].lower()

            # Проверяем расширение файла и что это не тестовый файл
            if any(file_ext == ext for ext in code_extensions) and not is_test:
                code_file_info = {
                    "path": file_path,
                    "name": os.path.basename(file_path),
                    "extension": file_ext,
                    "type": self.classify_file_type(file_path, technologies),
                    "technology": file_tech,
                    "size": file_info.get("size", 0),
                    "lines": file_info.get("lines", 0),
                    "is_test": is_test,
                    "has_content": True,
                    "ignored": False
                }
                code_files.append(code_file_info)
                logger.info(f"EXTRACT_ADDED: {file_path}")

        logger.info(f"EXTRACT_COMPLETE: Found {len(code_files)} code files")
        return code_files

    def get_code_extensions(self, technologies: List[str]) -> List[str]:
        """Получение расширений файлов для разных технологий"""
        extensions = []

        tech_extensions = {
            "python": [".py", ".pyw"],
            "javascript": [".js", ".jsx"],
            "typescript": [".ts", ".tsx"],
            "java": [".java"],
            "html": [".html", ".htm"],
            "css": [".css", ".scss", ".less"],
            "php": [".php"],
            "ruby": [".rb"],
            "go": [".go"],
            "rust": [".rs"],
            "csharp": [".cs"],
            "cpp": [".cpp", ".h", ".hpp"],
            "c": [".c", ".h"]
        }

        for tech in technologies:
            tech_lower = tech.lower()
            if tech_lower in tech_extensions:
                extensions.extend(tech_extensions[tech_lower])

        # Убираем дубликаты
        unique_extensions = list(set(extensions))
        logger.info(f"EXTENSIONS_RESULT: Final extensions: {unique_extensions}")
        return unique_extensions

    def classify_file_type(self, filename: str, technologies: List[str]) -> str:
        """Классификация типа файла"""
        extension = os.path.splitext(filename)[1].lower()

        file_types = {
            ".py": "python_module",
            ".js": "javascript_module",
            ".jsx": "react_component",
            ".ts": "typescript_module",
            ".tsx": "react_typescript_component",
            ".java": "java_class",
            ".html": "html_template",
            ".css": "styles",
            ".scss": "styles",
            ".php": "php_script",
            ".rb": "ruby_script",
            ".go": "go_module",
            ".rs": "rust_module",
            ".cs": "csharp_class"
        }

        return file_types.get(extension, "unknown")

    def detect_architecture_patterns(self, file_structure: Dict, technologies: List[str]) -> List[str]:
        """Обнаружение архитектурных паттернов в проекте"""
        patterns = []
        structure_keys = list(file_structure.keys())

        if "src" in structure_keys and "tests" in structure_keys:
            patterns.append("standard_src_tests")

        if "app" in structure_keys and "spec" in structure_keys:
            patterns.append("rails_like")

        if "components" in structure_keys and "pages" in structure_keys:
            patterns.append("react_nextjs")

        if "controllers" in structure_keys and "models" in structure_keys:
            patterns.append("mvc_pattern")

        return patterns

    def _prepare_enhanced_context(self, project_analysis: Dict, repo_path: str) -> Dict[str, Any]:
        """Расширенный контекст проекта с семантическим анализом"""

        # Используем существующий метод как основу
        base_context = self._prepare_context(project_analysis)

        # Дополняем расширенной информацией
        enhanced_context = {
            **base_context,
            "semantic_analysis": self._perform_semantic_analysis(project_analysis, repo_path),
            "code_patterns": self._extract_code_patterns(project_analysis, repo_path),
            "business_logic": self._infer_business_logic(project_analysis),
            "testing_strategy": self._derive_testing_strategy(project_analysis)
        }

        return enhanced_context

    def _perform_semantic_analysis(self, project_analysis: Dict, repo_path: str) -> Dict[str, Any]:
        """Семантический анализ кода для понимания логики"""
        semantic_data = {
            "key_components": self._identify_key_components(project_analysis, repo_path),
            "data_flow": self._analyze_data_flow(project_analysis),
            "critical_paths": self._find_critical_paths(project_analysis),
            "error_handling": self._analyze_error_handling(project_analysis)
        }

        logger.info(f"Semantic analysis completed: {len(semantic_data['key_components'])} key components found")
        return semantic_data

    def _identify_key_components(self, project_analysis: Dict, repo_path: str) -> List[Dict]:
        """Идентификация ключевых компонентов системы"""
        key_components = []

        # Анализ API endpoints как ключевых компонентов
        for endpoint in project_analysis.get('api_endpoints', [])[:10]:
            key_components.append({
                "type": "api_endpoint",
                "name": f"{endpoint.get('method', 'GET')} {endpoint.get('path', '')}",
                "file": endpoint.get('file', ''),
                "function": endpoint.get('function_name', 'unknown'),
                "criticality": "high" if endpoint.get('method') in ['POST', 'PUT', 'DELETE'] else "medium"
            })

        # Анализ основных модулей
        for file_info in project_analysis.get('code_files', [])[:20]:
            if self._is_critical_file(file_info):
                key_components.append({
                    "type": "core_module",
                    "name": file_info.get('name', ''),
                    "path": file_info.get('path', ''),
                    "technology": file_info.get('technology', ''),
                    "criticality": self._assess_criticality(file_info)
                })

        return key_components

    def _is_critical_file(self, file_info: Dict) -> bool:
        """Определяет критичность файла"""
        path = file_info.get('path', '').lower()
        name = file_info.get('name', '').lower()

        critical_indicators = [
            'controller', 'service', 'model', 'handler',
            'api', 'endpoint', 'route', 'view',
            'core', 'main', 'app', 'application',
            'business', 'logic', 'manager'
        ]

        return any(indicator in path or indicator in name for indicator in critical_indicators)

    def _assess_criticality(self, file_info: Dict) -> str:
        """Оценивает критичность файла"""
        path = file_info.get('path', '').lower()

        if any(term in path for term in ['controller', 'api', 'endpoint']):
            return "high"
        elif any(term in path for term in ['service', 'business', 'logic']):
            return "high"
        elif any(term in path for term in ['model', 'data', 'database']):
            return "medium"
        else:
            return "low"

    def _analyze_data_flow(self, project_analysis: Dict) -> List[Dict]:
        """Анализ потоков данных между компонентами"""
        data_flows = []

        # На основе API endpoints определяем потенциальные потоки данных
        endpoints = project_analysis.get('api_endpoints', [])
        for i, endpoint in enumerate(endpoints[:5]):
            for j, next_endpoint in enumerate(endpoints[i + 1:i + 3]):
                if self._are_endpoints_related(endpoint, next_endpoint):
                    data_flows.append({
                        "source": f"{endpoint.get('method')} {endpoint.get('path')}",
                        "target": f"{next_endpoint.get('method')} {next_endpoint.get('path')}",
                        "data_type": "request/response",
                        "relationship": "sequential"
                    })

        return data_flows

    def _are_endpoints_related(self, endpoint1: Dict, endpoint2: Dict) -> bool:
        """Определяет связаны ли эндпоинты"""
        path1 = endpoint1.get('path', '')
        path2 = endpoint2.get('path', '')

        # Эндпоинты связаны если они в одном файле или имеют общий префикс пути
        return (endpoint1.get('file') == endpoint2.get('file') or
                path1.split('/')[0] == path2.split('/')[0])

    def _find_critical_paths(self, project_analysis: Dict) -> List[List[str]]:
        """Находит критические пути в приложении"""
        critical_paths = []

        # Создаем типичные критические пути на основе архитектуры
        frameworks = project_analysis.get('frameworks', [])

        if 'django' in frameworks:
            critical_paths.append(['URL → View → Model → Database → Response'])
        elif 'flask' in frameworks:
            critical_paths.append(['Route → View Function → Business Logic → Response'])
        elif 'fastapi' in frameworks:
            critical_paths.append(['Endpoint → Dependency → Service → Model → Response'])

        # Добавляем общие критические пути
        critical_paths.extend([
            ['User Input → Validation → Processing → Storage → Response'],
            ['API Request → Authentication → Authorization → Business Logic → Response'],
            ['Data Query → Processing → Transformation → Response']
        ])

        return critical_paths

    def _analyze_error_handling(self, project_analysis: Dict) -> Dict[str, Any]:
        """Анализ обработки ошибок в проекте"""
        error_patterns = {
            "common_error_scenarios": [
                "Invalid input validation",
                "Database connection errors",
                "Authentication failures",
                "Authorization violations",
                "Resource not found",
                "External API failures"
            ],
            "recommended_error_tests": [
                "Test invalid input formats",
                "Test boundary conditions",
                "Test authentication edge cases",
                "Test database rollback scenarios",
                "Test concurrent access issues"
            ]
        }

        return error_patterns

    def _extract_code_patterns(self, project_analysis: Dict, repo_path: str) -> Dict[str, Any]:
        """Извлекает паттерны кода из проекта"""
        patterns = {
            "architectural_patterns": self._detect_architectural_patterns(project_analysis),
            "design_patterns": self._detect_design_patterns(project_analysis),
            "conventions": self._detect_code_conventions(project_analysis)
        }

        return patterns

    def _detect_architectural_patterns(self, project_analysis: Dict) -> List[str]:
        """Обнаруживает архитектурные паттерны"""
        patterns = []
        frameworks = [f.lower() for f in project_analysis.get('frameworks', [])]
        file_structure = project_analysis.get('file_structure', {})

        if any(f in ['django', 'flask', 'fastapi'] for f in frameworks):
            patterns.append("MVC/MVT Pattern")

        if any(f in ['react', 'vue', 'angular'] for f in frameworks):
            patterns.append("Component-Based Architecture")

        # Анализ структуры файлов для определения паттернов
        if any('microservice' in path.lower() for path in file_structure.keys()):
            patterns.append("Microservices Architecture")
        elif any('monolith' in path.lower() for path in file_structure.keys()):
            patterns.append("Monolithic Architecture")

        return patterns

    def _detect_design_patterns(self, project_analysis: Dict) -> List[str]:
        """Обнаруживает паттерны проектирования"""
        patterns = []
        file_structure = project_analysis.get('file_structure', {})

        # Простой анализ на основе имен файлов и структуры
        if any('factory' in path.lower() for path in file_structure.keys()):
            patterns.append("Factory Pattern")
        if any('singleton' in path.lower() for path in file_structure.keys()):
            patterns.append("Singleton Pattern")
        if any('adapter' in path.lower() for path in file_structure.keys()):
            patterns.append("Adapter Pattern")
        if any('observer' in path.lower() for path in file_structure.keys()):
            patterns.append("Observer Pattern")

        return patterns

    def _detect_code_conventions(self, project_analysis: Dict) -> Dict[str, Any]:
        """Определяет соглашения по коду"""
        conventions = {
            "naming_conventions": self._analyze_naming_conventions(project_analysis),
            "testing_conventions": self._analyze_testing_conventions(project_analysis),
            "project_structure": self._analyze_project_structure(project_analysis)
        }

        return conventions

    def _analyze_naming_conventions(self, project_analysis: Dict) -> Dict[str, str]:
        """Анализирует соглашения по именованию"""
        conventions = {}
        file_structure = project_analysis.get('file_structure', {})

        # Анализ имен файлов
        filenames = list(file_structure.keys())[:50]  # Берем первые 50 файлов для анализа

        if any('test_' in fname for fname in filenames):
            conventions["test_files"] = "test_*.py"
        if any('_test.py' in fname for fname in filenames):
            conventions["test_files"] = "*_test.py"

        return conventions

    def _analyze_testing_conventions(self, project_analysis: Dict) -> Dict[str, Any]:
        """Анализирует соглашения по тестированию"""
        test_analysis = project_analysis.get('test_analysis', {})

        return {
            "test_frameworks": test_analysis.get('test_frameworks', []),
            "test_structure": test_analysis.get('test_directories', []),
            "has_unit_tests": test_analysis.get('has_tests', False),
            "test_coverage": project_analysis.get('coverage_estimate', 0)
        }

    def _analyze_project_structure(self, project_analysis: Dict) -> Dict[str, Any]:
        """Анализирует структуру проекта"""
        structure = {
            "architecture_type": "unknown",
            "has_separate_tests": False,
            "module_organization": "flat"
        }

        file_structure = project_analysis.get('file_structure', {})
        paths = list(file_structure.keys())

        # Определяем тип архитектуры
        if any('/src/' in path for path in paths):
            structure["architecture_type"] = "standard_src"
        if any('/app/' in path for path in paths):
            structure["architecture_type"] = "application_folders"

        # Проверяем наличие отдельной тестовой директории
        structure["has_separate_tests"] = any('/test' in path.lower() or '/tests' in path.lower() for path in paths)

        return structure

    def _infer_business_logic(self, project_analysis: Dict) -> Dict[str, Any]:
        """Выводит бизнес-логику на основе анализа проекта"""
        business_domains = self._detect_business_domains(project_analysis)

        return {
            "domains": business_domains,
            "core_functions": self._identify_core_functions(project_analysis),
            "data_entities": self._identify_data_entities(project_analysis)
        }

    def _detect_business_domains(self, project_analysis: Dict) -> List[str]:
        """Определяет бизнес-домены проекта"""
        domains = []
        file_structure = project_analysis.get('file_structure', {})

        # Анализ путей файлов для определения доменов
        paths = list(file_structure.keys())

        domain_indicators = {
            'user': ['user', 'auth', 'account', 'profile'],
            'product': ['product', 'item', 'catalog', 'inventory'],
            'order': ['order', 'cart', 'checkout', 'payment'],
            'content': ['content', 'article', 'blog', 'post'],
            'notification': ['notification', 'message', 'email', 'alert']
        }

        for domain, indicators in domain_indicators.items():
            if any(indicator in path.lower() for path in paths for indicator in indicators):
                domains.append(domain)

        return domains if domains else ["general_application"]

    def _identify_core_functions(self, project_analysis: Dict) -> List[str]:
        """Определяет основные функции системы"""
        core_functions = []
        endpoints = project_analysis.get('api_endpoints', [])

        # На основе API endpoints определяем основные функции
        for endpoint in endpoints[:10]:
            method = endpoint.get('method', '').upper()
            path = endpoint.get('path', '')

            if method == 'GET' and '/{id}' in path:
                core_functions.append(f"Retrieve {path.split('/')[1]} by ID")
            elif method == 'POST':
                core_functions.append(f"Create new {path.split('/')[-1]}")
            elif method == 'PUT' or method == 'PATCH':
                core_functions.append(f"Update {path.split('/')[1]}")
            elif method == 'DELETE':
                core_functions.append(f"Delete {path.split('/')[1]}")

        return list(set(core_functions))  # Убираем дубликаты

    def _identify_data_entities(self, project_analysis: Dict) -> List[str]:
        """Определяет основные сущности данных"""
        entities = []
        file_structure = project_analysis.get('file_structure', {})

        # Ищем файлы моделей
        for path in file_structure.keys():
            if any(indicator in path.lower() for indicator in ['model', 'entity', 'schema']):
                # Извлекаем имя сущности из пути
                entity_name = path.split('/')[-1].replace('.py', '').replace('_', ' ').title()
                if entity_name and entity_name != 'Model':
                    entities.append(entity_name)

        return entities if entities else ["User", "Data"]

    def _derive_testing_strategy(self, project_analysis: Dict) -> Dict[str, Any]:
        """Формирует стратегию тестирования на основе анализа проекта"""
        return {
            "priority_focus": self._determine_test_priority(project_analysis),
            "test_types_needed": self._recommend_test_types(project_analysis),
            "coverage_goals": self._set_coverage_goals(project_analysis),
            "risk_areas": self._identify_risk_areas(project_analysis)
        }

    def _determine_test_priority(self, project_analysis: Dict) -> List[str]:
        """Определяет приоритеты тестирования"""
        priorities = []

        # Критические API endpoints
        if project_analysis.get('api_endpoints'):
            priorities.append("API endpoints (especially POST/PUT/DELETE)")

        # Основные бизнес-функции
        priorities.append("Core business logic")

        # Обработка ошибок
        priorities.append("Error handling and edge cases")

        # Интеграционные точки
        priorities.append("Data validation and integration points")

        return priorities

    def _recommend_test_types(self, project_analysis: Dict) -> Dict[str, bool]:
        """Рекомендует типы тестов на основе проекта"""
        frameworks = [f.lower() for f in project_analysis.get('frameworks', [])]
        has_api = bool(project_analysis.get('api_endpoints'))

        return {
            "unit_tests": True,  # Всегда рекомендуем unit тесты
            "integration_tests": has_api or any(f in ['django', 'flask', 'fastapi'] for f in frameworks),
            "api_tests": has_api,
            "e2e_tests": any(f in ['react', 'vue', 'angular'] for f in frameworks),
            "performance_tests": has_api and len(project_analysis.get('api_endpoints', [])) > 5
        }

    def _set_coverage_goals(self, project_analysis: Dict) -> Dict[str, float]:
        """Устанавливает цели покрытия"""
        current_coverage = project_analysis.get('coverage_estimate', 0)

        return {
            "unit_test_coverage": min(80.0, current_coverage + 20.0),
            "integration_test_coverage": min(70.0, current_coverage + 15.0),
            "api_test_coverage": min(90.0, current_coverage + 25.0) if project_analysis.get('api_endpoints') else 0.0
        }

    def _identify_risk_areas(self, project_analysis: Dict) -> List[str]:
        """Определяет рискованные области для тестирования"""
        risk_areas = []

        # API endpoints с модифицирующими операциями
        endpoints = project_analysis.get('api_endpoints', [])
        for endpoint in endpoints:
            if endpoint.get('method') in ['POST', 'PUT', 'DELETE']:
                risk_areas.append(f"Data modification: {endpoint.get('method')} {endpoint.get('path')}")

        # Сложные бизнес-процессы
        if len(project_analysis.get('api_endpoints', [])) > 10:
            risk_areas.append("Complex business workflows")

        # Интеграции с внешними системами
        if project_analysis.get('dependencies'):
            risk_areas.append("External dependencies and integrations")

        return risk_areas if risk_areas else ["Core application functionality"]

    def _find_related_endpoints(self, file_info: Dict, project_analysis: Dict) -> List[Dict]:
        """Находит эндпоинты связанные с файлом"""
        related = []
        file_path = file_info.get('path', '')

        for endpoint in project_analysis.get('api_endpoints', []):
            if endpoint.get('file') == file_path:
                related.append({
                    "method": endpoint.get('method'),
                    "path": endpoint.get('path'),
                    "function": endpoint.get('function_name')
                })

        return related

    def _suggest_test_scenarios(self, file_info: Dict, project_analysis: Dict) -> List[str]:
        """Предлагает сценарии тестирования для файла"""
        scenarios = []
        file_path = file_info.get('path', '').lower()

        # Базовые сценарии для всех файлов
        scenarios.extend([
            "Test basic functionality with valid inputs",
            "Test edge cases and boundary conditions",
            "Test error handling with invalid inputs",
            "Test performance with typical workloads"
        ])

        # Специфические сценарии на основе типа файла
        if 'model' in file_path:
            scenarios.extend([
                "Test data validation rules",
                "Test database operations (CRUD)",
                "Test relationships with other models"
            ])
        elif 'service' in file_path or 'business' in file_path:
            scenarios.extend([
                "Test business logic with various inputs",
                "Test integration with dependencies",
                "Test transaction rollback scenarios"
            ])
        elif 'api' in file_path or 'endpoint' in file_path:
            scenarios.extend([
                "Test HTTP status codes for different scenarios",
                "Test request/response payload validation",
                "Test authentication and authorization"
            ])

        return scenarios

    def _get_enhanced_file_content(self, file_path: str, repo_path: str) -> Dict[str, Any]:
        """Получает расширенное содержимое файла с анализом"""
        content = self._get_file_content(file_path, repo_path)
        if not content:
            return {"content": "", "analysis": {}}

        return {
            "content": content,
            "analysis": self._analyze_file_content(content, file_path)
        }

    def _analyze_file_content(self, content: str, file_path: str) -> Dict[str, Any]:
        """Анализирует содержимое файла для извлечения ключевой информации - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        if not content:
            return {
                "imports": [],
                "classes": [],
                "functions": [],
                "dependencies": [],
                "api_routes": [],
                "database_operations": [],
                "error_handling": [],
                "configurations": []
            }

        try:
            lines = content.split('\n')

            return {
                "imports": self._extract_imports(lines),
                "classes": self._extract_classes(content),
                "functions": self._extract_functions(content),
                "dependencies": self._extract_dependencies(content),
                "api_routes": self._extract_api_routes(content),
                "database_operations": self._extract_database_operations(content),
                "error_handling": self._extract_error_handling(content),
                "configurations": self._extract_configurations(content)
            }
        except Exception as e:
            logger.error(f"Error analyzing file content for {file_path}: {e}")
            return {
                "imports": [],
                "classes": [],
                "functions": [],
                "dependencies": [],
                "api_routes": [],
                "database_operations": [],
                "error_handling": [],
                "configurations": [],
                "analysis_error": str(e)
            }

    def _extract_imports(self, lines: List[str]) -> List[Dict]:
        """Извлекает все импорты из файла"""
        imports = []
        import_patterns = [
            (r'^import\s+(\w+)', "direct_import"),
            (r'^from\s+([\w\.]+)\s+import', "from_import"),
            (r'^from\s+([\w\.]+)\s+import\s+\(([^)]+)\)', "multi_import")
        ]

        for line in lines:
            line = line.strip()
            for pattern, import_type in import_patterns:
                match = re.search(pattern, line)
                if match:
                    imports.append({
                        "type": import_type,
                        "line": line,
                        "module": match.group(1) if match.groups() else None,
                        "imports": match.group(2).split(',') if len(match.groups()) > 1 else None
                    })

        return imports

    def _extract_classes(self, content: str) -> List[Dict]:
        """Извлекает классы из файла"""
        classes = []
        class_patterns = [
            (r'class\s+(\w+)\(([^)]*)\):', "python_class"),
            (r'class\s+(\w+):', "python_class_simple")
        ]

        for pattern, class_type in class_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                classes.append({
                    "type": class_type,
                    "name": match.group(1),
                    "inheritance": match.group(2) if len(match.groups()) > 1 else None,
                    "methods": self._extract_class_methods(content, match.group(1))
                })

        return classes

    def _extract_class_methods(self, content: str, class_name: str) -> List[Dict]:
        """Извлекает методы класса"""
        methods = []
        # Ищем методы после объявления класса
        class_start = content.find(f"class {class_name}")
        if class_start == -1:
            return methods

        # Ищем следующий класс или конец файла
        next_class = re.search(r'class\s+\w+', content[class_start + 1:])
        class_content = content[class_start:class_start + next_class.start()] if next_class else content[class_start:]

        method_patterns = [
            (r'def\s+(\w+)\(self[^)]*\):', "instance_method"),
            (r'def\s+(\w+)\(cls[^)]*\):', "class_method"),
            (r'def\s+(\w+)\([^)]*\):', "static_method")
        ]

        for pattern, method_type in method_patterns:
            matches = re.finditer(pattern, class_content)
            for match in matches:
                methods.append({
                    "type": method_type,
                    "name": match.group(1),
                    "signature": match.group(0)
                })

        return methods

    def _extract_functions(self, content: str) -> List[Dict]:
        """Извлекает функции из файла"""
        functions = []
        function_pattern = r'def\s+(\w+)\(([^)]*)\):'

        matches = re.finditer(function_pattern, content)
        for match in matches:
            functions.append({
                "name": match.group(1),
                "parameters": match.group(2),
                "is_async": 'async' in content[:match.start()].split('\n')[-1]
            })

        return functions

    def _extract_dependencies(self, content: str) -> List[Dict]:
        """Извлекает зависимости из файла"""
        dependencies = []

        # Паттерны для различных зависимостей
        dependency_patterns = [
            (r'requests\.(get|post|put|delete)', "http_client"),
            (r'sqlalchemy', "orm"),
            (r'django\.', "django_framework"),
            (r'flask', "flask_framework"),
            (r'pandas', "data_analysis"),
            (r'numpy', "numerical_computing"),
            (r'redis', "cache"),
            (r'celery', "task_queue"),
            (r'pytest', "testing"),
            (r'unittest', "testing")
        ]

        for pattern, dep_type in dependency_patterns:
            if re.search(pattern, content):
                dependencies.append({
                    "type": dep_type,
                    "name": pattern.replace(r'\.', '').replace(r'\([^)]*\)', ''),
                    "usage_count": len(re.findall(pattern, content))
                })

        return dependencies


    def _extract_api_routes(self, content: str) -> List[Dict]:
        """Извлекает API routes из файла"""
        routes = []

        route_patterns = [
            (r'@app\.route\(["\']([^"\']+)["\']', "flask_route"),
            (r'@router\.(get|post|put|delete)\(["\']([^"\']+)["\']', "fastapi_route"),
            (r'path\(["\']([^"\']+)["\']', "django_route"),
            (r'url\(["\']([^"\']+)["\']', "django_route_alt")
        ]

        for pattern, route_type in route_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                routes.append({
                    "type": route_type,
                    "path": match.group(1) if route_type == "flask_route" else match.group(2),
                    "method": match.group(1).upper() if route_type == "fastapi_route" else "GET"
                })

        return routes


    def _extract_database_operations(self, content: str) -> List[Dict]:
        """Извлекает операции с базой данных"""
        db_operations = []

        db_patterns = [
            (r'\.objects\.filter\(', "django_filter"),
            (r'\.objects\.get\(', "django_get"),
            (r'\.objects\.create\(', "django_create"),
            (r'\.save\(\)', "django_save"),
            (r'\.delete\(\)', "django_delete"),
            (r'session\.query\(', "sqlalchemy_query"),
            (r'session\.add\(', "sqlalchemy_add"),
            (r'session\.commit\(', "sqlalchemy_commit"),
            (r'SELECT.*FROM', "raw_sql_select"),
            (r'INSERT INTO', "raw_sql_insert"),
            (r'UPDATE.*SET', "raw_sql_update"),
            (r'DELETE FROM', "raw_sql_delete")
        ]

        for pattern, op_type in db_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                db_operations.append({
                    "type": op_type,
                    "operation": pattern.replace(r'\([^)]*\)', '').replace(r'\.', ''),
                    "count": len(re.findall(pattern, content, re.IGNORECASE))
                })

        return db_operations


    def _extract_error_handling(self, content: str) -> List[Dict]:
        """Извлекает обработку ошибок"""
        error_handling = []

        error_patterns = [
            (r'try:', "try_block"),
            (r'except\s+(\w+)', "except_block"),
            (r'raise\s+(\w+)', "raise_statement"),
            (r'assert\s+', "assert_statement"),
            (r'if\s+.*:\s*raise', "conditional_raise")
        ]

        for pattern, handler_type in error_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                error_info = {
                    "type": handler_type,
                    "line": match.group(0)
                }
                if handler_type == "except_block" and len(match.groups()) > 0:
                    error_info["exception_type"] = match.group(1)
                error_handling.append(error_info)

        return error_handling


    def _extract_configurations(self, content: str) -> List[Dict]:
        """Извлекает конфигурации и настройки"""
        configurations = []

        config_patterns = [
            (r'DEBUG\s*=\s*(True|False)', "debug_setting"),
            (r'SECRET_KEY\s*=', "secret_key"),
            (r'DATABASE_URL\s*=', "database_url"),
            (r'ALLOWED_HOSTS\s*=', "allowed_hosts"),
            (r'INSTALLED_APPS\s*=', "installed_apps"),
            (r'MIDDLEWARE\s*=', "middleware"),
            (r'CORS_ORIGIN_WHITELIST\s*=', "cors_settings")
        ]

        for pattern, config_type in config_patterns:
            match = re.search(pattern, content)
            if match:
                configurations.append({
                    "type": config_type,
                    "setting": match.group(0)
                })

        return configurations

    def _get_detailed_file_analysis(self, file_info: Dict, repo_path: str) -> Dict:
        """Детальный анализ конкретного файла"""
        file_path = file_info.get('path', '')
        content = self._get_file_content(file_path, repo_path)

        return {
            "content": content,
            "imports": self._extract_imports(content.split('\n')),
            "classes": self._extract_classes(content),
            "functions": self._extract_functions(content),
            "api_calls": self._extract_api_calls(content),
            "database_operations": self._extract_database_operations(content),
            "error_handling": self._extract_error_handling(content),
            "complexity_metrics": self._calculate_complexity(content)
        }

    def _find_related_endpoints(self, file_info: Dict, project_analysis: Dict) -> List[Dict]:
        """Находит эндпоинты связанные с файлом"""
        related = []
        file_path = file_info.get('path', '')

        for endpoint in project_analysis.get('api_endpoints', []):
            if endpoint.get('file') == file_path:
                related.append({
                    "method": endpoint.get('method'),
                    "path": endpoint.get('path'),
                    "function": endpoint.get('function_name'),
                    "parameters": endpoint.get('parameters', [])
                })

        return related

    def _suggest_test_scenarios(self, file_info: Dict, project_analysis: Dict) -> List[str]:
        """Предлагает сценарии тестирования для файла"""
        scenarios = []
        file_path = file_info.get('path', '').lower()

        # Базовые сценарии
        scenarios.extend([
            "Test basic functionality with valid inputs",
            "Test edge cases and boundary conditions",
            "Test error handling with invalid inputs",
            "Test performance with typical workloads"
        ])

        # Специфические сценарии на основе типа файла
        if 'model' in file_path:
            scenarios.extend([
                "Test data validation rules",
                "Test database operations (CRUD)",
                "Test relationships with other models"
            ])
        elif 'service' in file_path or 'business' in file_path:
            scenarios.extend([
                "Test business logic with various inputs",
                "Test integration with dependencies",
                "Test transaction rollback scenarios"
            ])
        elif 'api' in file_path or 'endpoint' in file_path:
            scenarios.extend([
                "Test HTTP status codes for different scenarios",
                "Test request/response payload validation",
                "Test authentication and authorization"
            ])

        return scenarios

    def _suggest_mocks(self, file_info: Dict, project_analysis: Dict) -> List[Dict]:
        """Предлагает что нужно мокать в тестах"""
        mocks = []
        file_path = file_info.get('path', '').lower()

        # Анализ зависимостей для мокинга
        dependencies = project_analysis.get('dependencies', {})

        if 'requests' in str(dependencies):
            mocks.append({
                "target": "requests",
                "reason": "HTTP calls to external APIs",
                "examples": ["mock.get()", "mock.post()"]
            })

        if any(db in str(dependencies) for db in ['sqlalchemy', 'django.db', 'psycopg2']):
            mocks.append({
                "target": "database",
                "reason": "Database operations",
                "examples": ["mock_session.query()", "mock_connection.execute()"]
            })

        return mocks

    def _extract_api_calls(self, content: str) -> List[Dict]:
        """Извлекает API вызовы из файла"""
        api_calls = []

        patterns = [
            (r'requests\.(get|post|put|delete|patch)\([^)]*\)', 'requests'),
            (r'httpx\.(get|post|put|delete|patch)\([^)]*\)', 'httpx'),
            (r'aiohttp\.(get|post|put|delete|patch)\([^)]*\)', 'aiohttp'),
            (r'urllib\.request\.(urlopen|Request)\([^)]*\)', 'urllib')
        ]

        for pattern, lib in patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                api_calls.append({
                    "library": lib,
                    "call": match.group(0),
                    "method": match.group(1) if match.groups() else 'unknown'
                })

        return api_calls

    def _calculate_complexity(self, content: str) -> Dict[str, Any]:
        """Рассчитывает метрики сложности кода"""
        lines = content.split('\n')

        # Простые метрики сложности
        total_lines = len(lines)
        code_lines = len([line for line in lines if line.strip() and not line.strip().startswith('#')])
        function_count = len(re.findall(r'def\s+\w+\(', content))
        class_count = len(re.findall(r'class\s+\w+', content))

        # Подсчет условий и циклов для цикломатической сложности
        conditions = len(re.findall(r'\b(if|elif|for|while|and|or)\b', content))

        return {
            "total_lines": total_lines,
            "code_lines": code_lines,
            "function_count": function_count,
            "class_count": class_count,
            "condition_count": conditions,
            "complexity_score": min(10, (conditions + function_count) / max(1, code_lines / 100))
        }

    def _find_real_e2e_scenarios(self, project_analysis: Dict) -> List[Dict]:
        """Находит реальные E2E сценарии на основе анализа проекта"""
        scenarios = []

        # Сценарии на основе API endpoints
        endpoints = project_analysis.get('api_endpoints', [])
        if endpoints:
            scenarios.append({
                "name": "api_workflow",
                "description": "Complete API workflow testing",
                "user_flows": ["Authentication → Data retrieval → Data modification"],
                "pages": ["Login", "Dashboard", "Details"]
            })

        # Сценарии на основе бизнес-логики
        business_functions = project_analysis.get('business_context', {}).get('core_functions', [])
        for func in business_functions[:3]:
            scenarios.append({
                "name": f"{func.lower().replace(' ', '_')}_flow",
                "description": f"End-to-end test for {func}",
                "user_flows": [func],
                "pages": ["Main workflow pages"]
            })

        return scenarios

    def _find_absolute_file_path(self, relative_path: str, repo_path: str) -> str:
        if not relative_path or not repo_path:
            return relative_path

        # Пробуем разные варианты путей
        possible_paths = [
            os.path.join(repo_path, relative_path),
            os.path.join(repo_path, relative_path.lstrip('/')),
            os.path.join(repo_path, relative_path.lstrip('./'))
        ]

        for path in possible_paths:
            if os.path.exists(path) and os.path.isfile(path):
                return path

        # Рекурсивный поиск по имени файла
        filename = os.path.basename(relative_path)
        if filename:
            for root, dirs, files in os.walk(repo_path):
                if filename in files:
                    found_path = os.path.join(root, filename)
                    logger.info(f"Found file {filename} at {found_path}")
                    return found_path

        logger.warning(f"File not found: {relative_path} in {repo_path}")
        return relative_path  # fallback
test_generation_pipeline = None


def init_test_generation_pipeline(ai_service):
    """Инициализация глобального экземпляра пайплайна"""
    global test_generation_pipeline
    test_generation_pipeline = TestGenerationPipeline(ai_service)
    return test_generation_pipeline