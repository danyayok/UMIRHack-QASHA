import os
import logging
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path

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
        """Генерирует unit тесты"""
        test_files = {}
        code_files = project_analysis.get("code_files", [])
        ai_provider = "unknown"

        files_to_test = code_files[:config.get("max_unit_tests", 5)]

        for file_info in files_to_test:
            try:
                # 🔥 ИСПРАВЛЕНИЕ: Убедимся что file_info - словарь
                if not isinstance(file_info, dict):
                    logger.warning(f"Invalid file_info type: {type(file_info)}, skipping")
                    continue

                # Создаем копию чтобы не модифицировать исходные данные
                file_info_copy = file_info.copy()

                # Получаем реальное содержимое файла
                real_content = self._get_file_content(file_info_copy.get("path", ""), repo_path)
                if real_content:
                    file_info_copy["real_content"] = real_content
                    file_info_copy["has_content"] = True
                else:
                    file_info_copy["has_content"] = False

                # Подготавливаем контекст
                project_context = self._prepare_context(project_analysis)

                test_content = await self.ai_service.generate_test_content(
                    file_info=file_info_copy,  # 🔥 Теперь передаем словарь, а не список
                    project_context=project_context,
                    test_type="unit",
                    framework=framework,
                    config=config
                )

                if test_content:
                    filename = self._generate_filename(file_info_copy, "unit", framework)
                    test_files[filename] = test_content
                    ai_provider = "ai_generated"
                else:
                    filename, content = await self._create_fallback_test(file_info_copy, framework, project_analysis)
                    test_files[filename] = content
                    ai_provider = "fallback"

            except Exception as e:
                logger.error(f"Error generating unit test for {file_info.get('path', 'unknown')}: {e}")
                filename, content = await self._create_fallback_test(file_info, framework, project_analysis)
                test_files[filename] = content
                ai_provider = "fallback"

        return test_files, len(test_files), ai_provider

    async def _generate_api_tests(self, project_analysis: Dict, framework: str,
                                  config: Dict, repo_path: str) -> Tuple[Dict[str, str], int, str]:
        """Генерирует API тесты с реальным кодом эндпоинтов"""
        test_files = {}
        ai_provider = "unknown"

        api_endpoints = project_analysis.get("api_endpoints", [])
        logger.info(f"GENERATE_API: Found {len(api_endpoints)} API endpoints")

        for endpoint in api_endpoints[:config.get("max_api_tests", 5)]:
            try:
                endpoint_file = endpoint.get('file', '')
                endpoint_file_content = self._get_file_content(endpoint_file, repo_path)

                # Создаем правильный file_info словарь
                mock_file_info = {
                    "path": f"api/{endpoint.get('method', 'GET')}_{endpoint.get('path', '').replace('/', '_')}",
                    "name": f"{endpoint.get('method', 'GET')}_{endpoint.get('path', '').replace('/', '_')}",
                    "type": "api_endpoint",
                    "extension": ".py",
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
                    framework=framework,
                    config=config
                )

                if test_content and len(test_content.strip()) > 50:
                    # Создаем безопасное имя файла
                    safe_method = endpoint.get('method', 'get').lower()
                    safe_path = endpoint.get('path', '').replace('/', '_').replace(':', '').replace('*', '')
                    filename = f"test_api_{safe_method}_{safe_path}.{self._get_file_ext(framework)}"
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

    async def _generate_e2e_tests(self, project_analysis: Dict, framework: str,
                                  config: Dict) -> Tuple[Dict[str, str], int, str]:
        """Генерирует E2E тесты"""
        test_files = {}
        ai_provider = "unknown"

        scenarios = self._find_e2e_scenarios(project_analysis)

        for scenario in scenarios[:config.get("max_e2e_tests", 2)]:
            try:
                mock_file_info = {
                    "path": f"e2e/{scenario}",
                    "name": scenario,
                    "type": "e2e_scenario"
                }

                test_content = await self.ai_service.generate_test_content(
                    file_info=mock_file_info,
                    project_context=self._prepare_context(project_analysis),
                    test_type="e2e",
                    framework=framework,
                    config=config
                )

                if test_content:
                    filename = f"test_e2e_{scenario}.{self._get_file_ext(framework)}"
                    test_files[filename] = test_content
                    ai_provider = "ai_generated"

            except Exception as e:
                logger.error(f"Error generating E2E test for {scenario}: {e}")

        return test_files, len(test_files), ai_provider

    def _get_test_framework(self, technologies: List[str], existing_frameworks: List[str],
                            user_choice: str) -> str:
        """Определяет фреймворк тестирования"""
        if user_choice != "auto":
            return user_choice

        # Фильтруем неизвестные фреймворки
        known_frameworks = [f for f in existing_frameworks if f and f != 'unknown']
        if known_frameworks:
            return known_frameworks[0]

        # Определяем по основным технологиям проекта
        primary_tech = technologies[0].lower() if technologies else "python"

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

        return framework_map.get(primary_tech, "pytest")

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
        """Безопасное получение содержимого файла с улучшенной обработкой путей"""
        if not file_path:
            return ""

        # Нормализуем пути
        file_path = file_path.strip()
        if repo_path:
            repo_path = repo_path.strip()

        # Пробуем разные варианты путей
        possible_paths = [file_path]

        if repo_path:
            possible_paths.extend([
                os.path.join(repo_path, file_path),
                os.path.join(repo_path, file_path.lstrip('/')),
                os.path.join(repo_path, file_path.lstrip('./'))
            ])

        for full_path in possible_paths:
            if os.path.exists(full_path) and os.path.isfile(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        logger.info(f"GET_FILE_CONTENT: Successfully read {len(content)} chars from {full_path}")
                        return content
                except UnicodeDecodeError:
                    try:
                        with open(full_path, 'r', encoding='latin-1') as f:
                            content = f.read()
                            logger.info(f"GET_FILE_CONTENT: Successfully read with latin-1: {len(content)} chars")
                            return content
                    except Exception as e:
                        logger.warning(f"Could not read file {full_path} with any encoding: {e}")
                        continue
                except Exception as e:
                    logger.warning(f"Error reading file {full_path}: {e}")
                    continue

        logger.warning(f"File not found at any path: {file_path}")
        return ""

    async def _create_fallback_test(self, file_info: Dict, framework: str,
                                    project_analysis: Dict) -> Tuple[str, str]:
        """Создает fallback тест при ошибке AI"""
        file_name = file_info.get('name', 'unknown').replace('.', '').title()
        content = f"""
# Fallback test for {file_info.get('path', 'unknown')}

import pytest

class Test{file_name}:
    def test_basic_functionality(self):
        assert True

    def test_edge_cases(self):
        assert 1 == 1
"""
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
        """Подготавливает полный контекст проекта для AI со всей структурой файлов"""
        if not project_analysis:
            return self._create_empty_context()

        file_structure = project_analysis.get('file_structure', {})

        # Формируем полную структуру файлов проекта
        complete_file_structure = self._prepare_complete_file_structure(file_structure)

        return {
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


test_generation_pipeline = None


def init_test_generation_pipeline(ai_service):
    """Инициализация глобального экземпляра пайплайна"""
    global test_generation_pipeline
    test_generation_pipeline = TestGenerationPipeline(ai_service)
    return test_generation_pipeline