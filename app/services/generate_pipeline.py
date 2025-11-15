import os
import logging
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
import re
import pandas as pd
from docx import Document
import PyPDF2
import tempfile
import uuid
from typing import Dict, List, Any, Optional

from git import Repo, GitCommandError

from app.services.git_service import GitService

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
        """Основной метод генерации тестов с улучшенной обработкой ошибок"""
        try:
            logger.info("🎯 START: Test generation pipeline started")

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

            if not repo_path or not os.path.exists(repo_path):
                return self._create_error_response(f"Repository path not found: {repo_path}")

            logger.info(f"📁 Project: {project_info.get('name', 'Unknown')}, Path: {repo_path}")

            # 🔍 УЛУЧШЕННЫЙ АНАЛИЗ РЕПОЗИТОРИЯ
            enhanced_analysis = await self._enhance_analysis_data(analysis_data, repo_path)

            # 🔍 ГАРАНТИРУЕМ наличие endpoints
            if not enhanced_analysis.get('api_endpoints'):
                logger.warning("🔄 No API endpoints found, performing deep search...")
                from app.services.code_analyzer import CodeAnalyzer
                analyzer = CodeAnalyzer()
                analyzer.detect_api_endpoints(Path(repo_path), enhanced_analysis)
                logger.info(f"🔍 DEEP_SEARCH: Found {len(enhanced_analysis.get('api_endpoints', []))} endpoints")

            # Анализ структуры проекта
            project_analysis = self.analyze_project_structure(enhanced_analysis)

            # 🔍 ФИНАЛЬНАЯ ПРОВЕРКА ДАННЫХ
            self._validate_analysis_data(project_analysis, repo_path)

            # Определяем фреймворк тестирования
            framework = self._get_test_framework(
                project_analysis["technologies"],
                project_analysis.get("existing_test_frameworks", []),
                test_config.get("framework", "auto")
            )

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
                "coverage_details": generation_results.get("coverage_details", {}),
                "test_breakdown": generation_results.get("test_breakdown", {}),
                "framework_used": framework,
                "files_created": list(generation_results["test_files"].keys()),
                "warnings": generation_results["warnings"],
                "recommendations": generation_results["recommendations"],
                "generation_time": datetime.utcnow().isoformat(),
                "test_config_used": test_config,
                "ai_provider_used": generation_results["ai_provider"],
                "coverage_confidence": generation_results.get("coverage_details", {}).get("confidence", 0.8)
            }

        except Exception as e:
            logger.error(f"❌ PIPELINE_ERROR: {e}", exc_info=True)
            return self._create_error_response(f"Test generation failed: {str(e)}")

    async def _enhance_analysis_data(self, analysis_data: Dict, repo_path: str) -> Dict:
        """Улучшает данные анализа дополнительной информацией"""
        try:
            enhanced_data = analysis_data.copy()

            # Если структура файлов пустая, анализируем репозиторий
            if not enhanced_data.get('file_structure'):
                logger.warning("📁 Empty file structure, analyzing repository...")
                from app.services.code_analyzer import CodeAnalyzer
                analyzer = CodeAnalyzer()
                direct_analysis = await analyzer.analyze_repository(repo_path)
                enhanced_data.update(direct_analysis)

            # 🔍 ГАРАНТИРУЕМ наличие file_structure
            if not enhanced_data.get('file_structure'):
                enhanced_data['file_structure'] = self._scan_repository_files(repo_path)

            # 🔍 ОБЯЗАТЕЛЬНЫЙ поиск endpoints
            if not enhanced_data.get('api_endpoints'):
                from app.services.code_analyzer import CodeAnalyzer
                analyzer = CodeAnalyzer()
                analyzer.detect_api_endpoints(Path(repo_path), enhanced_data)

            return enhanced_data

        except Exception as e:
            logger.error(f"Error enhancing analysis data: {e}")
            return analysis_data

    def _scan_repository_files(self, repo_path: str) -> Dict:
        """Сканирует файлы репозитория если анализ пустой"""
        file_structure = {}
        try:
            repo_path_obj = Path(repo_path)
            for file_path in repo_path_obj.rglob('*'):
                if file_path.is_file():
                    relative_path = str(file_path.relative_to(repo_path))
                    file_structure[relative_path] = {
                        'path': relative_path,
                        'name': file_path.name,
                        'extension': file_path.suffix,
                        'size': file_path.stat().st_size,
                        'is_test': self._is_test_file(file_path),
                        'technology': self._detect_technology(file_path)
                    }
            logger.info(f"📁 SCANNED: Found {len(file_structure)} files in repository")
        except Exception as e:
            logger.error(f"Error scanning repository: {e}")

        return file_structure

    def _validate_analysis_data(self, project_analysis: Dict, repo_path: str):
        """Валидирует данные анализа и логирует проблемы"""
        issues = []

        if not project_analysis.get('file_structure'):
            issues.append("No file structure data")

        if not project_analysis.get('code_files'):
            issues.append("No code files identified")

        if not os.path.exists(repo_path):
            issues.append(f"Repository path does not exist: {repo_path}")

        if issues:
            logger.warning(f"⚠️ ANALYSIS_ISSUES: {', '.join(issues)}")
        else:
            logger.info("✅ ANALYSIS_VALIDATION: All checks passed")

    async def _generate_test_files(self, project_analysis: Dict, test_config: Dict,
                                   framework: str, repo_path: str) -> Dict[str, Any]:
        """Генерирует все типы тестовых файлов с РЕАЛИСТИЧНЫМ расчетом покрытия"""
        test_files = {}
        warnings = []
        recommendations = []
        ai_provider = "unknown"

        # 🔥 СЧИТАЕМ ТЕСТЫ ПО ТИПАМ ДЛЯ ТОЧНОГО РАСЧЕТА
        test_counts = {
            "unit": 0,
            "api": 0,
            "integration": 0,
            "e2e": 0,
            "total": 0
        }

        try:
            # Unit тесты
            if test_config.get("generate_unit_tests", True):
                unit_files, unit_count, provider = await self._generate_unit_tests(
                    project_analysis, framework, test_config, repo_path
                )
                test_files.update(unit_files)
                test_counts["unit"] = unit_count
                test_counts["total"] += unit_count
                ai_provider = provider
                logger.info(f"🧪 GENERATED_UNIT: {unit_count} unit tests")

            # API тесты
            if test_config.get("generate_api_tests", True):
                api_files, api_count, provider = await self._generate_api_tests(
                    project_analysis, framework, test_config, repo_path
                )
                test_files.update(api_files)
                test_counts["api"] = api_count
                test_counts["total"] += api_count
                ai_provider = provider or ai_provider
                logger.info(f"🌐 GENERATED_API: {api_count} API tests")

            # Интеграционные тесты
            if test_config.get("generate_integration_tests", True):
                integration_files, integration_count, provider = await self._generate_integration_tests(
                    project_analysis, framework, test_config, repo_path
                )
                test_files.update(integration_files)
                test_counts["integration"] = integration_count
                test_counts["total"] += integration_count
                ai_provider = provider or ai_provider
                logger.info(f"🔗 GENERATED_INTEGRATION: {integration_count} integration tests")

            # E2E тесты
            if test_config.get("generate_e2e_tests", False):
                e2e_files, e2e_count, provider = await self._generate_e2e_tests(
                    project_analysis, framework, test_config, repo_path
                )
                test_files.update(e2e_files)
                test_counts["e2e"] = e2e_count
                test_counts["total"] += e2e_count
                ai_provider = provider or ai_provider
                logger.info(f"🌐 GENERATED_E2E: {e2e_count} E2E tests")

        except Exception as e:
            error_msg = f"Error in test generation: {str(e)}"
            logger.error(f"❌ GENERATION_ERROR: {error_msg}")
            warnings.append(error_msg)

        # 🔥 УЛУЧШЕННЫЙ РАСЧЕТ ПОКРЫТИЯ
        coverage_estimate = self._calculate_realistic_coverage(
            test_counts,
            project_analysis,
            test_config
        )

        # Рекомендации
        if test_counts["total"] == 0:
            recommendations.append("Consider checking repository structure and analysis data")

        # Добавляем рекомендации по улучшению покрытия
        if coverage_estimate < 50.0:
            recommendations.append("Consider generating more unit and API tests for better coverage")
        elif coverage_estimate < 70.0:
            recommendations.append("Good start! Consider adding integration tests")
        else:
            recommendations.append("Excellent test coverage! Consider adding E2E tests for complete coverage")

        coverage_estimate = await self.ai_service.estimate_test_coverage(
            test_files,
            self._prepare_enhanced_context(project_analysis, repo_path),
            test_counts
        )


        return {
                "total_tests": test_counts["total"],
                "test_files": test_files,
                "coverage_estimate": coverage_estimate["coverage"],
                "coverage_details": coverage_estimate,
                "test_breakdown": test_counts,
                "warnings": warnings,
                "recommendations": coverage_estimate.get("improvements", []),
                "ai_provider": ai_provider
        }

    def _calculate_realistic_coverage(self, test_counts: Dict, project_analysis: Dict, test_config: Dict) -> float:
        """РАЗУМНЫЙ расчет покрытия на основе реальных метрик проекта"""

        total_tests = test_counts["total"]
        existing_tests = project_analysis.get("test_files_count", 0)
        total_files = project_analysis.get("code_files_count", 0)

        if total_files == 0:
            return 0.0

        # 🔥 БАЗОВОЕ ПОКРЫТИЕ от общего количества тестов
        base_coverage = min(70.0, (total_tests / max(1, total_files)) * 50.0)

        # 🔥 ВЕСА РАЗНЫХ ТИПОВ ТЕСТОВ
        weights = {
            "unit": 1.0,  # Unit тесты покрывают конкретные функции
            "api": 1.2,  # API тесты покрывают endpoints (важнее)
            "integration": 1.5,  # Интеграционные тесты покрывают взаимодействия
            "e2e": 2.0  # E2E тесты покрывают полные сценарии
        }

        # 🔥 ВЗВЕШЕННОЕ КОЛИЧЕСТВО ТЕСТОВ
        weighted_tests = sum(test_counts[test_type] * weights.get(test_type, 1.0)
                             for test_type in ["unit", "api", "integration", "e2e"])

        # 🔥 БОНУСЫ ЗА КАЧЕСТВО
        bonuses = 0.0

        # Бонус за разнообразие типов тестов
        test_types_used = sum(1 for test_type in ["unit", "api", "integration", "e2e"]
                              if test_counts[test_type] > 0)
        diversity_bonus = min(15.0, test_types_used * 3.0)
        bonuses += diversity_bonus

        # Бонус за E2E тесты (они покрывают много функциональности)
        if test_counts["e2e"] > 0:
            e2e_bonus = min(10.0, test_counts["e2e"] * 2.0)
            bonuses += e2e_bonus

        # Бонус за API тесты (критически важны для API проектов)
        api_endpoints = len(project_analysis.get('api_endpoints', []))
        if test_counts["api"] > 0 and api_endpoints > 0:
            api_coverage_ratio = min(1.0, test_counts["api"] / max(1, api_endpoints))
            api_bonus = min(15.0, api_coverage_ratio * 15.0)
            bonuses += api_bonus

        # 🔥 ФИНАЛЬНЫЙ РАСЧЕТ
        coverage_from_tests = min(60.0, (weighted_tests / max(1, total_files)) * 40.0)
        final_coverage = coverage_from_tests + bonuses

        # 🔥 УЧИТЫВАЕМ СУЩЕСТВУЮЩИЕ ТЕСТЫ
        if existing_tests > 0:
            existing_coverage_bonus = min(20.0, (existing_tests / max(1, total_files)) * 25.0)
            final_coverage += existing_coverage_bonus

        # Ограничиваем разумными пределами
        final_coverage = max(15.0, min(95.0, final_coverage))

        logger.info(f"🎯 REALISTIC_COVERAGE: {final_coverage:.1f}%")
        logger.info(f"📊 BREAKDOWN: {test_counts}")
        logger.info(f"📈 WEIGHTED: {weighted_tests:.1f}, BONUSES: {bonuses:.1f}")
        logger.info(f"📁 PROJECT: {total_files} files, {api_endpoints} endpoints, {existing_tests} existing tests")

        return round(final_coverage, 1)

    async def _generate_unit_tests(self, project_analysis: Dict, framework: str,
                                   config: Dict, repo_path: str) -> Tuple[Dict[str, str], int, str]:
        """Генерирует unit тесты с ГАРАНТИРОВАННЫМ доступом к файлам"""
        test_files = {}
        code_files = project_analysis.get("code_files", [])
        ai_provider = "unknown"

        # Фильтруем только существующие файлы
        valid_code_files = []
        for file_info in code_files:
            file_path = file_info.get("path", "")
            absolute_path = self._get_absolute_file_path(file_path, repo_path)
            if os.path.exists(absolute_path) and os.path.isfile(absolute_path):
                valid_code_files.append(file_info)
            else:
                logger.warning(f"⚠️ FILE_NOT_FOUND: {file_path}")

        files_to_test = valid_code_files[:config.get("max_unit_tests", 5)]

        if not files_to_test:
            logger.warning("❌ NO_VALID_FILES: No valid code files found for unit testing")
            # Создаем fallback тест
            fallback_file, fallback_content = await self._create_fallback_test(
                {"name": "fallback", "path": "fallback.py"}, framework, project_analysis
            )
            test_files[fallback_file] = fallback_content
            return test_files, 1, "fallback"

        for file_info in files_to_test:
            try:
                file_path = file_info.get("path", "")
                absolute_path = self._get_absolute_file_path(file_path, repo_path)

                if not os.path.exists(absolute_path):
                    logger.warning(f"🚫 SKIPPING_FILE: {file_path} not found")
                    continue

                # Определяем фреймворк для файла
                file_framework = self._get_test_framework_for_file(file_info, framework)

                # 🔥 УЛУЧШЕННОЕ: Получаем РЕАЛЬНОЕ содержимое файла
                file_content = self._get_file_content(absolute_path)
                if not file_content:
                    logger.warning(f"📄 EMPTY_FILE: {file_path} has no content")
                    continue

                enhanced_file_info = file_info.copy()
                enhanced_file_info.update({
                    "absolute_path": absolute_path,
                    "content": file_content,
                    "has_content": True,
                    "file_size": len(file_content),
                    "enhanced_content": {
                        "content": file_content,
                        "analysis": self._analyze_file_content(file_content, file_path)
                    }
                })

                # 🔥 УЛУЧШЕННЫЙ КОНТЕКСТ
                project_context = self._prepare_enhanced_context(project_analysis, repo_path)

                # Генерация теста
                test_content = await self.ai_service.generate_test_content(
                    file_info=enhanced_file_info,
                    project_context=project_context,
                    test_type="unit",
                    framework=file_framework,
                    config=config
                )

                if test_content and len(test_content.strip()) > 100:
                    filename = self._generate_filename(file_info, "unit", file_framework)
                    test_files[filename] = test_content
                    ai_provider = "ai_generated"
                    logger.info(f"✅ GENERATED_UNIT_TEST: {filename}")
                else:
                    # Fallback
                    filename, content = await self._create_fallback_test(file_info, file_framework, project_analysis)
                    test_files[filename] = content
                    ai_provider = "fallback"
                    logger.info(f"🔄 FALLBACK_UNIT_TEST: {filename}")

            except Exception as e:
                logger.error(f"❌ UNIT_TEST_ERROR for {file_info.get('path', 'unknown')}: {e}")
                file_framework = self._get_test_framework_for_file(file_info, framework)
                filename, content = await self._create_fallback_test(file_info, file_framework, project_analysis)
                test_files[filename] = content
                ai_provider = "fallback"

        return test_files, len(test_files), ai_provider

    async def _generate_api_tests(self, project_analysis: Dict, framework: str,
                                  config: Dict, repo_path: str) -> Tuple[Dict[str, str], int, str]:
        """Генерирует API тесты с ГАРАНТИЕЙ endpoints"""
        test_files = {}
        ai_provider = "unknown"

        api_endpoints = project_analysis.get("api_endpoints", [])
        logger.info(f"🔍 API_ENDPOINTS_FOR_GENERATION: {len(api_endpoints)} endpoints")

        if not api_endpoints:
            logger.warning("❌ NO_API_ENDPOINTS: No API endpoints found for testing")
            # Создаем общий API тест
            fallback_test = self._create_api_fallback_test(framework)
            test_files["test_api_fallback.py"] = fallback_test
            return test_files, 1, "fallback"

        # Для FastAPI/Flask используем pytest
        api_framework = "pytest" if any(
            f in project_analysis.get('frameworks', []) for f in ['fastapi', 'flask', 'django']) else framework

        endpoints_to_test = api_endpoints[:config.get("max_api_tests", 5)]

        for endpoint in endpoints_to_test:
            try:
                endpoint_file = endpoint.get('file', '')
                file_content = ""

                if endpoint_file:
                    absolute_path = self._get_absolute_file_path(endpoint_file, repo_path)
                    file_content = self._get_file_content(absolute_path) if os.path.exists(absolute_path) else ""

                # Создаем детальную информацию об endpoint
                endpoint_info = {
                    "path": f"api/{endpoint.get('method', 'GET')}_{endpoint.get('path', '').replace('/', '_')}",
                    "name": f"{endpoint.get('method', 'GET')}_{endpoint.get('path', '').replace('/', '_')}",
                    "type": "api_endpoint",
                    "extension": ".py",
                    "technology": "python",
                    "endpoint_info": endpoint,
                    "content_preview": file_content[:2000] if file_content else "No content available",
                    "has_content": bool(file_content),
                    "real_content": file_content or "No endpoint implementation found",
                    "ignored": False,
                    "is_test": False
                }

                logger.info(f"🎯 GENERATING_API_TEST: {endpoint.get('method')} {endpoint.get('path')}")

                test_content = await self.ai_service.generate_test_content(
                    file_info=endpoint_info,
                    project_context=self._prepare_enhanced_context(project_analysis, repo_path),
                    test_type="api",
                    framework=api_framework,
                    config=config
                )

                if test_content and len(test_content.strip()) > 100:
                    safe_method = endpoint.get('method', 'get').lower()
                    safe_path = endpoint.get('path', '').replace('/', '_').replace(':', '').replace('*', '').replace(
                        '<', '').replace('>', '')
                    filename = f"test_api_{safe_method}_{safe_path}.{self._get_file_ext(api_framework)}"
                    test_files[filename] = test_content
                    ai_provider = "ai_generated"
                    logger.info(f"✅ GENERATED_API_TEST: {filename}")
                else:
                    logger.warning(f"⚠️ EMPTY_API_RESPONSE for endpoint {endpoint}")

            except Exception as e:
                logger.error(f"❌ API_TEST_ERROR for endpoint {endpoint}: {e}")

        # Если не сгенерировали ни одного теста, создаем fallback
        if not test_files:
            fallback_test = self._create_api_fallback_test(api_framework)
            test_files["test_api_fallback.py"] = fallback_test
            ai_provider = "fallback"

        logger.info(f"📊 API_GENERATION_RESULT: {len(test_files)} tests generated")
        return test_files, len(test_files), ai_provider

    def _create_api_fallback_test(self, framework: str) -> str:
        """Создает fallback API тест"""
        if framework == "pytest":
            return '''
import pytest
import requests

class TestAPIFallback:
    """Fallback API tests - replace with actual endpoint tests"""

    def test_api_health_check(self):
        """Basic API health check"""
        # TODO: Replace with actual API base URL
        base_url = "http://localhost:8000"

        try:
            response = requests.get(f"{base_url}/health")
            assert response.status_code in [200, 404, 503]
        except requests.exceptions.RequestException:
            pytest.skip("API server not available")

    def test_api_endpoints_exist(self):
        """Verify that API endpoints are defined"""
        # This is a fallback test - implement actual endpoint tests
        assert True

    def test_api_response_structure(self):
        """Test basic API response structure"""
        # TODO: Implement actual API tests
        assert True
'''
        else:
            return '''
// Fallback API tests
// TODO: Implement actual API endpoint tests
'''

    def _get_absolute_file_path(self, relative_path: str, repo_path: str) -> str:
        """ГАРАНТИРОВАННО находит абсолютный путь к файлу"""
        if not relative_path or not repo_path:
            return relative_path

        # Пробуем разные варианты путей
        possible_paths = [
            os.path.join(repo_path, relative_path),
            os.path.join(repo_path, relative_path.lstrip('/')),
            os.path.join(repo_path, relative_path.lstrip('./')),
            os.path.join(repo_path, *relative_path.split('/')),
        ]

        for path in possible_paths:
            if os.path.exists(path) and os.path.isfile(path):
                return os.path.abspath(path)

        # Рекурсивный поиск по имени файла
        filename = os.path.basename(relative_path)
        if filename:
            try:
                for root, dirs, files in os.walk(repo_path):
                    if filename in files:
                        found_path = os.path.join(root, filename)
                        logger.info(f"🔍 FOUND_FILE: {filename} at {found_path}")
                        return os.path.abspath(found_path)
            except Exception as e:
                logger.error(f"Error during file search: {e}")

        logger.warning(f"🚫 FILE_NOT_FOUND: {relative_path} in {repo_path}")
        return os.path.join(repo_path, relative_path)  # Fallback

    def _get_file_content(self, file_path: str) -> str:
        """Безопасное чтение содержимого файла"""
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return ""

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if len(content) > 100000:
                    content = content[:100000] + "\n# ... [FILE TRUNCATED FOR ANALYSIS]"
                return content
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    content = f.read()
                    if len(content) > 100000:
                        content = content[:100000] + "\n# ... [FILE TRUNCATED FOR ANALYSIS]"
                    return content
            except Exception as e:
                logger.warning(f"Could not read file {file_path} with any encoding: {e}")
                return ""
        except Exception as e:
            logger.warning(f"Error reading file {file_path}: {e}")
            return ""

    def _prepare_enhanced_context(self, project_analysis: Dict, repo_path: str) -> Dict[str, Any]:
        """Создает УЛУЧШЕННЫЙ контекст с ПОЛНОЙ информацией о проекте"""
        base_context = self._prepare_context(project_analysis)

        # Добавляем информацию о репозитории
        enhanced_context = {
            **base_context,
            "repository_metadata": {
                "local_path": repo_path,
                "total_size": self._get_repository_size(repo_path),
                "file_count": len(project_analysis.get('file_structure', {})),
                "scan_timestamp": datetime.utcnow().isoformat()
            },
            "enhanced_analysis": {
                "file_structure_details": self._get_detailed_file_structure(project_analysis, repo_path),
                "api_endpoints_enhanced": self._enhance_api_endpoints(project_analysis.get('api_endpoints', [])),
                "business_context_enhanced": self._enhance_business_context(project_analysis),
                "testing_recommendations_enhanced": self._get_detailed_testing_recommendations(project_analysis)
            }
        }

        return enhanced_context

    def _get_detailed_file_structure(self, project_analysis: Dict, repo_path: str) -> Dict:
        """Получает детальную структуру файлов с реальным содержимым"""
        detailed_structure = {}
        file_structure = project_analysis.get('file_structure', {})

        for rel_path, file_info in list(file_structure.items())[:50]:  # Ограничиваем для производительности
            abs_path = self._get_absolute_file_path(rel_path, repo_path)
            if os.path.exists(abs_path):
                content_preview = self._get_file_content(abs_path)[:1000]  # Первые 1000 символов
                detailed_structure[rel_path] = {
                    **file_info,
                    "exists": True,
                    "content_preview": content_preview,
                    "content_length": len(content_preview)
                }
            else:
                detailed_structure[rel_path] = {
                    **file_info,
                    "exists": False,
                    "content_preview": "",
                    "content_length": 0
                }

        return detailed_structure

    def _enhance_api_endpoints(self, endpoints: List[Dict]) -> List[Dict]:
        """Улучшает информацию об API endpoints"""
        enhanced_endpoints = []
        for endpoint in endpoints:
            enhanced_endpoints.append({
                **endpoint,
                "test_scenarios": self._generate_endpoint_test_scenarios(endpoint),
                "priority": self._assess_endpoint_priority(endpoint),
                "authentication_required": self._check_auth_requirement(endpoint)
            })
        return enhanced_endpoints

    def _generate_endpoint_test_scenarios(self, endpoint: Dict) -> List[str]:
        """Генерирует сценарии тестирования для endpoint"""
        method = endpoint.get('method', '').upper()
        scenarios = []

        if method in ['GET', 'POST', 'PUT', 'DELETE']:
            scenarios.append(f"Test {method} request with valid data")
            scenarios.append(f"Test {method} request with invalid data")
            scenarios.append(f"Test {method} request authentication")

        if method in ['POST', 'PUT']:
            scenarios.append("Test data validation rules")
            scenarios.append("Test required fields validation")

        if method == 'GET':
            scenarios.append("Test query parameters")
            scenarios.append("Test pagination if applicable")

        return scenarios

    def _assess_endpoint_priority(self, endpoint: Dict) -> str:
        """Определяет приоритет endpoint для тестирования"""
        method = endpoint.get('method', '').upper()
        path = endpoint.get('path', '')

        if method in ['POST', 'PUT', 'DELETE']:
            return "high"
        elif '/auth/' in path or '/login' in path or '/register' in path:
            return "high"
        elif method == 'GET' and '/{id}' in path:
            return "medium"
        else:
            return "low"

    def _check_auth_requirement(self, endpoint: Dict) -> bool:
        """Проверяет требует ли endpoint аутентификации"""
        path = endpoint.get('path', '').lower()
        method = endpoint.get('method', '').upper()

        # Эндпоинты которые обычно требуют аутентификации
        auth_paths = ['/profile', '/user', '/admin', '/settings', '/dashboard']
        auth_methods = ['POST', 'PUT', 'DELETE']

        return any(auth_path in path for auth_path in auth_paths) or method in auth_methods

    def _enhance_business_context(self, project_analysis: Dict) -> Dict:
        """Улучшает бизнес-контекст проекта"""
        return {
            "domains": project_analysis.get('business_domains', ['general']),
            "core_business_functions": self._identify_business_functions(project_analysis),
            "data_entities": self._identify_data_entities(project_analysis),
            "user_roles": self._identify_user_roles(project_analysis),
            "workflows": self._identify_workflows(project_analysis)
        }

    def _identify_business_functions(self, project_analysis: Dict) -> List[str]:
        """Идентифицирует бизнес-функции на основе анализа"""
        functions = []
        endpoints = project_analysis.get('api_endpoints', [])

        for endpoint in endpoints:
            method = endpoint.get('method', '').upper()
            path = endpoint.get('path', '')

            if method == 'POST' and '/users' in path:
                functions.append("User Registration")
            elif method == 'POST' and any(x in path for x in ['/orders', '/products']):
                functions.append("Create Resource")
            elif method == 'GET' and '/{id}' in path:
                functions.append("Retrieve Resource by ID")
            elif method in ['PUT', 'PATCH']:
                functions.append("Update Resource")
            elif method == 'DELETE':
                functions.append("Delete Resource")

        return list(set(functions)) if functions else ["Data Management", "User Operations"]

    def _identify_data_entities(self, project_analysis: Dict) -> List[str]:
        """Идентифицирует сущности данных"""
        entities = []
        file_structure = project_analysis.get('file_structure', {})

        for file_path in file_structure.keys():
            if any(keyword in file_path.lower() for keyword in ['model', 'entity', 'schema']):
                entity_name = os.path.basename(file_path).replace('.py', '').title()
                if entity_name and entity_name != 'Model':
                    entities.append(entity_name)

        return entities if entities else ["User", "Data"]

    def _identify_user_roles(self, project_analysis: Dict) -> List[str]:
        """Идентифицирует роли пользователей"""
        roles = ["User"]  # Базовая роль

        endpoints = project_analysis.get('api_endpoints', [])
        for endpoint in endpoints:
            path = endpoint.get('path', '').lower()
            if 'admin' in path:
                roles.append("Admin")
                break

        return list(set(roles))

    def _identify_workflows(self, project_analysis: Dict) -> List[str]:
        """Идентифицирует рабочие процессы"""
        workflows = []
        endpoints = project_analysis.get('api_endpoints', [])

        if any(ep.get('path', '').lower().endswith('/login') for ep in endpoints):
            workflows.append("User Authentication")
        if any('/orders' in ep.get('path', '') for ep in endpoints):
            workflows.append("Order Processing")
        if any('/products' in ep.get('path', '') for ep in endpoints):
            workflows.append("Product Management")

        return workflows if workflows else ["Basic CRUD Operations"]

    def _get_detailed_testing_recommendations(self, project_analysis: Dict) -> Dict:
        """Создает детальные рекомендации по тестированию"""
        return {
            "test_priority": self._determine_test_priority(project_analysis),
            "critical_paths": self._identify_critical_test_paths(project_analysis),
            "risk_areas": self._identify_test_risk_areas(project_analysis),
            "coverage_targets": self._calculate_coverage_targets(project_analysis),
            "performance_considerations": self._identify_performance_considerations(project_analysis)
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
    def _identify_critical_test_paths(self, project_analysis: Dict) -> List[str]:
        """Идентифицирует критические пути для тестирования"""
        critical_paths = []
        endpoints = project_analysis.get('api_endpoints', [])

        # Находим основные бизнес-процессы
        auth_endpoints = [ep for ep in endpoints if any(x in ep.get('path', '').lower() for x in ['/auth', '/login'])]
        data_endpoints = [ep for ep in endpoints if
                          any(x in ep.get('path', '').lower() for x in ['/users', '/products', '/orders'])]

        if auth_endpoints:
            critical_paths.append("Authentication Flow")
        if data_endpoints:
            critical_paths.append("Data Management Flow")

        return critical_paths if critical_paths else ["Core Application Flow"]

    def _identify_test_risk_areas(self, project_analysis: Dict) -> List[str]:
        """Идентифицирует рискованные области для тестирования"""
        risk_areas = []
        endpoints = project_analysis.get('api_endpoints', [])

        for endpoint in endpoints:
            method = endpoint.get('method', '').upper()
            if method in ['POST', 'PUT', 'DELETE']:
                risk_areas.append(f"Data Modification: {method} {endpoint.get('path')}")

        return risk_areas if risk_areas else ["Data Integrity", "User Input Validation"]

    def _calculate_coverage_targets(self, project_analysis: Dict) -> Dict[str, float]:
        """Рассчитывает цели покрытия тестами"""
        current_coverage = project_analysis.get('coverage_estimate', 0)

        return {
            "unit_test_coverage": min(85.0, current_coverage + 25.0),
            "api_test_coverage": min(95.0, current_coverage + 30.0),
            "integration_test_coverage": min(75.0, current_coverage + 20.0),
            "e2e_test_coverage": min(60.0, current_coverage + 15.0)
        }

    def _identify_performance_considerations(self, project_analysis: Dict) -> List[str]:
        """Идентифицирует соображения по производительности"""
        considerations = []
        endpoints = project_analysis.get('api_endpoints', [])

        if len(endpoints) > 10:
            considerations.append("API response times under load")
        if any(ep.get('method') == 'GET' and '/list' in ep.get('path', '') for ep in endpoints):
            considerations.append("Pagination and large dataset handling")

        return considerations if considerations else ["Basic performance validation"]

    def _get_repository_size(self, repo_path: str) -> int:
        """Рассчитывает общий размер репозитория"""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(repo_path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
        except Exception as e:
            logger.warning(f"Error calculating repository size: {e}")

        return total_size

    # Существующие методы остаются без изменений
    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        return {
            "status": "error",
            "error": error_message,
            "generation_time": datetime.utcnow().isoformat()
        }

    def _is_test_file(self, file_path: Path) -> bool:
        """Определяет является ли файл тестовым"""
        name = file_path.name.lower()
        return any(pattern in name for pattern in ['test_', '_test.py', '.spec.', '.test.'])

    def _detect_technology(self, file_path: Path) -> str:
        """Определяет технологию файла"""
        extension = file_path.suffix.lower()
        tech_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.html': 'html',
            '.css': 'css'
        }
        return tech_map.get(extension, 'unknown')

    # Остальные существующие методы...
    def _get_test_framework(self, technologies: List[str], existing_frameworks: List[str], user_choice: str) -> str:
        if user_choice != "auto":
            return user_choice
        primary_language = self._get_primary_language(technologies)
        framework_map = {
            "python": "pytest", "javascript": "jest", "typescript": "jest",
            "java": "junit", "html": "cypress"
        }
        known_frameworks = [f for f in existing_frameworks if f and f != 'unknown']
        if known_frameworks:
            return known_frameworks[0]
        return framework_map.get(primary_language, "pytest")

    def _get_primary_language(self, technologies: List[str]) -> str:
        priority_languages = ["python", "java", "javascript", "typescript", "go", "ruby", "php"]
        for lang in priority_languages:
            if lang in technologies:
                return lang
        return technologies[0] if technologies else "python"

    def _calculate_coverage(self, generated_tests: int, existing_tests: int, total_files: int) -> float:
        """РАЗУМНЫЙ расчет покрытия тестами с учетом реальных метрик"""

        if total_files == 0:
            return 0.0

        total_tests = generated_tests + existing_tests

        # 🔥 УЛУЧШЕННАЯ ФОРМУЛА - учитываем разные факторы
        base_ratio = total_tests / max(1, total_files)

        # Базовое покрытие от соотношения тестов к файлам
        base_coverage = min(85.0, base_ratio * 60.0)  # Максимум 85% от этого фактора

        # 🔥 БОНУСЫ за разные типы тестов
        bonuses = 0.0

        # Бонус за E2E тесты (они покрывают много функциональности)
        if generated_tests > 0:
            e2e_bonus = min(15.0, (generated_tests / max(1, total_files)) * 25.0)
            bonuses += e2e_bonus

        # Бонус за существующие тесты
        if existing_tests > 0:
            existing_bonus = min(10.0, (existing_tests / max(1, total_files)) * 15.0)
            bonuses += existing_bonus

        # Бонус за разнообразие тестов (если есть разные типы)
        test_diversity_bonus = min(5.0, (min(generated_tests, 10) / 10.0) * 5.0)
        bonuses += test_diversity_bonus

        # 🔥 ФИНАЛЬНОЕ ПОКРЫТИЕ
        final_coverage = base_coverage + bonuses

        # Ограничиваем разумными пределами
        final_coverage = max(10.0, min(95.0, final_coverage))

        logger.info(f"📊 COVERAGE_CALC: base={base_coverage:.1f}%, bonuses={bonuses:.1f}%, final={final_coverage:.1f}%")
        logger.info(
            f"📊 COVERAGE_DETAILS: tests={total_tests}, files={total_files}, generated={generated_tests}, existing={existing_tests}")

        return round(final_coverage, 1)

    def _generate_filename(self, file_info: Dict, test_type: str, framework: str) -> str:
        base_name = file_info.get("name", "unknown").replace(file_info.get("extension", ""), "")
        safe_name = "".join(c for c in base_name if c.isalnum() or c in ('_', '-')).rstrip()
        return f"test_{test_type}_{safe_name}.{self._get_file_ext(framework)}"

    def _get_file_ext(self, framework: str) -> str:
        extensions = {
            "pytest": "py", "unittest": "py", "jest": "js", "mocha": "js",
            "jasmine": "js", "cypress": "js", "playwright": "js",
            "junit": "java", "testng": "java"
        }
        return extensions.get(framework, "py")

    async def _create_fallback_test(self, file_info: Dict, framework: str, project_analysis: Dict) -> Tuple[str, str]:
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

    def _get_test_framework_for_file(self, file_info: Dict, project_framework: str) -> str:
        file_tech = file_info.get('technology', '').lower()
        file_ext = file_info.get('extension', '').lower()

        if file_tech == 'python' or file_ext in ['.py', '.pyw']:
            return 'pytest'
        if file_tech in ['javascript', 'react'] or file_ext in ['.js', '.jsx', '.ts', '.tsx']:
            return 'jest'
        if file_tech in ['html', 'css'] or file_ext in ['.html', '.css']:
            return 'playwright'
        return project_framework

    def analyze_project_structure(self, analysis_data: Dict) -> Dict[str, Any]:
        if not analysis_data:
            return self._create_empty_project_analysis()

        technologies = analysis_data.get("technologies", [])
        frameworks = analysis_data.get("frameworks", [])
        test_analysis = analysis_data.get("test_analysis", {})
        metrics = analysis_data.get("metrics", {})
        dependencies = analysis_data.get("dependencies", {})
        file_structure = analysis_data.get("file_structure", {})

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
        return {
            "technologies": [], "frameworks": [], "file_structure": {}, "code_files": [],
            "total_files": 0, "code_files_count": 0, "test_files_count": 0, "dependencies": {},
            "test_analysis": {}, "metrics": {}, "existing_test_frameworks": [],
            "has_existing_tests": False, "test_directories": [], "architecture_patterns": [],
            "complexity_metrics": {}, "coverage_estimate": 0, "project_structure": {},
            "api_endpoints": []
        }

    def extract_code_files(self, file_structure: Dict, technologies: List[str]) -> List[Dict]:
        code_files = []
        code_extensions = self.get_code_extensions(technologies)

        for file_path, file_info in file_structure.items():
            if not isinstance(file_info, dict):
                continue

            file_ext = file_info.get('extension', '')
            file_tech = file_info.get('technology', '')
            is_test = file_info.get('is_test', False)

            if not file_ext:
                file_ext = os.path.splitext(file_path)[1].lower()

            if any(file_ext == ext for ext in code_extensions) and not is_test:
                code_file_info = {
                    "path": file_path, "name": os.path.basename(file_path),
                    "extension": file_ext, "type": self.classify_file_type(file_path, technologies),
                    "technology": file_tech, "size": file_info.get("size", 0),
                    "lines": file_info.get("lines", 0), "is_test": is_test,
                    "has_content": True, "ignored": False
                }
                code_files.append(code_file_info)

        return code_files

    def get_code_extensions(self, technologies: List[str]) -> List[str]:
        extensions = []
        tech_extensions = {
            "python": [".py", ".pyw"], "javascript": [".js", ".jsx"],
            "typescript": [".ts", ".tsx"], "java": [".java"],
            "html": [".html", ".htm"], "css": [".css", ".scss", ".less"],
            "php": [".php"], "ruby": [".rb"], "go": [".go"],
            "rust": [".rs"], "csharp": [".cs"], "cpp": [".cpp", ".h", ".hpp"],
            "c": [".c", ".h"]
        }
        for tech in technologies:
            tech_lower = tech.lower()
            if tech_lower in tech_extensions:
                extensions.extend(tech_extensions[tech_lower])
        return list(set(extensions))

    def classify_file_type(self, filename: str, technologies: List[str]) -> str:
        extension = os.path.splitext(filename)[1].lower()
        file_types = {
            ".py": "python_module", ".js": "javascript_module",
            ".jsx": "react_component", ".ts": "typescript_module",
            ".tsx": "react_typescript_component", ".java": "java_class",
            ".html": "html_template", ".css": "styles", ".scss": "styles",
            ".php": "php_script", ".rb": "ruby_script", ".go": "go_module",
            ".rs": "rust_module", ".cs": "csharp_class"
        }
        return file_types.get(extension, "unknown")

    def detect_architecture_patterns(self, file_structure: Dict, technologies: List[str]) -> List[str]:
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

    def _prepare_context(self, project_analysis: Dict) -> Dict[str, Any]:
        if not project_analysis:
            return self._create_empty_context()

        file_structure = project_analysis.get('file_structure', {})
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
        return {
            "project_metadata": {"name": "Unknown", "technologies": [], "frameworks": [], "architecture": []},
            "project_structure": {"total_files": 0, "code_files_count": 0, "test_files_count": 0, "total_lines": 0,
                                  "total_size_kb": 0, "complete_file_structure": {}},
            "testing_context": {"has_tests": False, "test_frameworks": [], "test_files_count": 0,
                                "coverage_estimate": 0},
            "dependencies": {}, "api_endpoints": [],
        }

    def _prepare_complete_file_structure(self, file_structure: Dict) -> Dict:
        structured_files = {}
        for file_path, file_info in file_structure.items():
            if isinstance(file_info, dict):
                dir_path = os.path.dirname(file_path) or "root"
                filename = os.path.basename(file_path)
                if dir_path not in structured_files:
                    structured_files[dir_path] = []
                structured_files[dir_path].append({
                    "name": filename, "path": file_path,
                    "technology": file_info.get('technology', 'unknown'),
                    "extension": file_info.get('extension', ''),
                    "is_test": file_info.get('is_test', False),
                    "size": file_info.get('size', 0),
                    "lines": file_info.get('lines', 0),
                    "type": self._classify_file_type_by_extension(file_info.get('extension', ''))
                })
        return structured_files

    def _classify_file_type_by_extension(self, extension: str) -> str:
        type_map = {
            '.py': 'python_module', '.js': 'javascript_module',
            '.jsx': 'react_component', '.ts': 'typescript_module',
            '.tsx': 'react_typescript_component', '.java': 'java_class',
            '.html': 'html_template', '.css': 'styles', '.scss': 'styles',
            '.php': 'php_script', '.rb': 'ruby_script', '.go': 'go_module',
            '.rs': 'rust_module', '.cs': 'csharp_class', '.cpp': 'cpp_source',
            '.h': 'cpp_header', '.json': 'configuration', '.yaml': 'configuration',
            '.yml': 'configuration', '.xml': 'configuration', '.md': 'documentation',
            '.txt': 'documentation'
        }
        return type_map.get(extension, 'unknown')

    def _analyze_file_content(self, content: str, file_path: str) -> Dict[str, Any]:
        if not content:
            return {
                "imports": [], "classes": [], "functions": [], "dependencies": [],
                "api_routes": [], "database_operations": [], "error_handling": [],
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
                "imports": [], "classes": [], "functions": [], "dependencies": [],
                "api_routes": [], "database_operations": [], "error_handling": [],
                "configurations": [], "analysis_error": str(e)
            }

    def _extract_imports(self, lines: List[str]) -> List[Dict]:
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
                        "type": import_type, "line": line,
                        "module": match.group(1) if match.groups() else None,
                        "imports": match.group(2).split(',') if len(match.groups()) > 1 else None
                    })
        return imports

    def _extract_classes(self, content: str) -> List[Dict]:
        classes = []
        class_patterns = [
            (r'class\s+(\w+)\(([^)]*)\):', "python_class"),
            (r'class\s+(\w+):', "python_class_simple")
        ]
        for pattern, class_type in class_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                classes.append({
                    "type": class_type, "name": match.group(1),
                    "inheritance": match.group(2) if len(match.groups()) > 1 else None,
                    "methods": self._extract_class_methods(content, match.group(1))
                })
        return classes

    def _extract_class_methods(self, content: str, class_name: str) -> List[Dict]:
        methods = []
        class_start = content.find(f"class {class_name}")
        if class_start == -1:
            return methods
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
                    "type": method_type, "name": match.group(1), "signature": match.group(0)
                })
        return methods

    def _extract_functions(self, content: str) -> List[Dict]:
        functions = []
        function_pattern = r'def\s+(\w+)\(([^)]*)\):'
        matches = re.finditer(function_pattern, content)
        for match in matches:
            functions.append({
                "name": match.group(1), "parameters": match.group(2),
                "is_async": 'async' in content[:match.start()].split('\n')[-1]
            })
        return functions

    def _extract_dependencies(self, content: str) -> List[Dict]:
        dependencies = []
        dependency_patterns = [
            (r'requests\.(get|post|put|delete)', "http_client"),
            (r'sqlalchemy', "orm"), (r'django\.', "django_framework"),
            (r'flask', "flask_framework"), (r'pandas', "data_analysis"),
            (r'numpy', "numerical_computing"), (r'redis', "cache"),
            (r'celery', "task_queue"), (r'pytest', "testing"),
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
        db_operations = []
        db_patterns = [
            (r'\.objects\.filter\(', "django_filter"),
            (r'\.objects\.get\(', "django_get"), (r'\.objects\.create\(', "django_create"),
            (r'\.save\(\)', "django_save"), (r'\.delete\(\)', "django_delete"),
            (r'session\.query\(', "sqlalchemy_query"), (r'session\.add\(', "sqlalchemy_add"),
            (r'session\.commit\(', "sqlalchemy_commit"), (r'SELECT.*FROM', "raw_sql_select"),
            (r'INSERT INTO', "raw_sql_insert"), (r'UPDATE.*SET', "raw_sql_update"),
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
        error_handling = []
        error_patterns = [
            (r'try:', "try_block"), (r'except\s+(\w+)', "except_block"),
            (r'raise\s+(\w+)', "raise_statement"), (r'assert\s+', "assert_statement"),
            (r'if\s+.*:\s*raise', "conditional_raise")
        ]
        for pattern, handler_type in error_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                error_info = {"type": handler_type, "line": match.group(0)}
                if handler_type == "except_block" and len(match.groups()) > 0:
                    error_info["exception_type"] = match.group(1)
                error_handling.append(error_info)
        return error_handling

    def _extract_configurations(self, content: str) -> List[Dict]:
        configurations = []
        config_patterns = [
            (r'DEBUG\s*=\s*(True|False)', "debug_setting"),
            (r'SECRET_KEY\s*=', "secret_key"), (r'DATABASE_URL\s*=', "database_url"),
            (r'ALLOWED_HOSTS\s*=', "allowed_hosts"), (r'INSTALLED_APPS\s*=', "installed_apps"),
            (r'MIDDLEWARE\s*=', "middleware"), (r'CORS_ORIGIN_WHITELIST\s*=', "cors_settings")
        ]
        for pattern, config_type in config_patterns:
            match = re.search(pattern, content)
            if match:
                configurations.append({"type": config_type, "setting": match.group(0)})
        return configurations

    async def _generate_integration_tests(self, project_analysis: Dict, framework: str,
                                          config: Dict, repo_path: str) -> Tuple[Dict[str, str], int, str]:
        """Генерирует интеграционные тесты с реальными данными"""
        test_files = {}
        ai_provider = "unknown"

        # Находим реальные интеграционные точки
        integration_points = self._find_real_integration_points(project_analysis, repo_path)

        for point in integration_points[:config.get("max_integration_tests", 3)]:
            try:
                test_content = await self.ai_service.generate_test_content(
                    file_info={
                        "path": f"integration/{point['name']}",
                        "name": point['name'],
                        "type": "integration_module",
                        "integration_data": point
                    },
                    project_context=self._prepare_enhanced_context(project_analysis, repo_path),
                    test_type="integration",
                    framework=framework,
                    config=config
                )

                if test_content and len(test_content.strip()) > 100:
                    filename = f"test_integration_{point['name']}.{self._get_file_ext(framework)}"
                    test_files[filename] = test_content
                    ai_provider = "ai_generated"
                else:
                    # Fallback интеграционный тест
                    fallback_content = self._create_integration_fallback_test(point, framework)
                    filename = f"test_integration_{point['name']}.{self._get_file_ext(framework)}"
                    test_files[filename] = fallback_content
                    ai_provider = "fallback"

            except Exception as e:
                logger.error(f"Error generating integration test for {point['name']}: {e}")

        return test_files, len(test_files), ai_provider

    def _find_real_integration_points(self, project_analysis: Dict, repo_path: str) -> List[Dict]:
        """Находит реальные точки интеграции в проекте"""
        integration_points = []

        # Анализируем зависимости между модулями
        endpoints = project_analysis.get('api_endpoints', [])
        file_structure = project_analysis.get('file_structure', {})

        # Точки интеграции на основе API flow
        if len(endpoints) >= 2:
            integration_points.append({
                "name": "api_workflow_integration",
                "description": "Integration between multiple API endpoints",
                "components": [f"{ep['method']} {ep['path']}" for ep in endpoints[:3]],
                "data_flow": "Request → Processing → Response"
            })

        # Интеграция с базой данных
        if any('model' in path.lower() for path in file_structure.keys()):
            integration_points.append({
                "name": "database_integration",
                "description": "Integration between services and database",
                "components": ["Service Layer", "Data Models", "Database"],
                "data_flow": "Service → Model → Database"
            })

        # Внешние интеграции
        dependencies = project_analysis.get('dependencies', {})
        if any(dep in str(dependencies) for dep in ['requests', 'httpx', 'aiohttp']):
            integration_points.append({
                "name": "external_api_integration",
                "description": "Integration with external APIs",
                "components": ["Application", "External APIs"],
                "data_flow": "App → HTTP Client → External API"
            })

        return integration_points if integration_points else [{
            "name": "basic_integration",
            "description": "Basic component integration",
            "components": ["Core Modules"],
            "data_flow": "Module A → Module B"
        }]

    def _create_integration_fallback_test(self, integration_point: Dict, framework: str) -> str:
        """Создает fallback интеграционный тест"""
        if framework == "pytest":
            return f'''
import pytest

class Test{integration_point['name'].title().replace('_', '')}Integration:
    """Integration tests for {integration_point['description']}"""

    def test_component_integration(self):
        """Test integration between {', '.join(integration_point['components'])}"""
        # TODO: Implement actual integration test
        # This should test data flow: {integration_point['data_flow']}
        assert True

    def test_error_handling(self):
        """Test error handling in integration scenario"""
        # TODO: Test how components handle errors together
        assert True

    def test_data_consistency(self):
        """Test data consistency across integrated components"""
        # TODO: Verify data remains consistent between components
        assert True
'''
        else:
            return f'''
// Integration tests for {integration_point['name']}
// TODO: Implement integration testing for: {integration_point['description']}
'''

    async def _generate_e2e_tests(self, project_analysis: Dict, framework: str,
                                  config: Dict, repo_path: str) -> Tuple[Dict[str, str], int, str]:
        """Генерирует E2E тесты с реальными пользовательскими сценариями"""
        test_files = {}
        ai_provider = "unknown"

        # Для E2E тестов используем Playwright для веб-приложений
        e2e_framework = "playwright" if any(tech in project_analysis.get('technologies', []) for tech in
                                            ['javascript', 'react', 'html', 'css']) else framework

        # Получаем реальные E2E сценарии
        e2e_scenarios = self._find_real_e2e_scenarios(project_analysis, repo_path)

        logger.info(f"🔍 E2E_SCENARIOS_FOUND: {len(e2e_scenarios)} scenarios")

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
                    project_context=self._prepare_enhanced_context(project_analysis, repo_path),
                    test_type="e2e",
                    framework=e2e_framework,
                    config=config
                )

                if test_content and len(test_content.strip()) > 100:
                    filename = f"test_e2e_{scenario['name']}.{self._get_file_ext(e2e_framework)}"
                    test_files[filename] = test_content
                    ai_provider = "ai_generated"
                    logger.info(f"✅ GENERATED_E2E_TEST: {filename}")
                else:
                    # Fallback для E2E тестов
                    fallback_content = self._create_e2e_fallback_test(scenario, e2e_framework)
                    filename = f"test_e2e_{scenario['name']}.{self._get_file_ext(e2e_framework)}"
                    test_files[filename] = fallback_content
                    ai_provider = "fallback"

            except Exception as e:
                logger.error(f"❌ E2E_TEST_ERROR for {scenario['name']}: {e}")
                # Создаем fallback тест при ошибке
                fallback_content = self._create_e2e_fallback_test(scenario, e2e_framework)
                filename = f"test_e2e_{scenario['name']}.{self._get_file_ext(e2e_framework)}"
                test_files[filename] = fallback_content
                ai_provider = "fallback"

        logger.info(f"📊 E2E_GENERATION_RESULT: {len(test_files)} tests generated")
        return test_files, len(test_files), ai_provider

    def _find_real_e2e_scenarios(self, project_analysis: Dict, repo_path: str) -> List[Dict]:
        """Находит реальные E2E сценарии на основе анализа проекта"""
        scenarios = []

        # Сценарии на основе API endpoints
        endpoints = project_analysis.get('api_endpoints', [])
        if endpoints:
            # User registration flow
            if any(ep.get('path', '').endswith('/users') and ep.get('method') == 'POST' for ep in endpoints):
                scenarios.append({
                    "name": "user_registration_flow",
                    "description": "Complete user registration process",
                    "steps": [
                        "Navigate to registration page",
                        "Fill registration form with valid data",
                        "Submit the form",
                        "Verify successful registration",
                        "Check user can login with new credentials"
                    ],
                    "user_flows": ["New User Onboarding"],
                    "pages": ["Registration", "Login", "Dashboard"],
                    "priority": "high",
                    "complexity": "medium"
                })

            # User login flow
            if any('/login' in ep.get('path', '') for ep in endpoints):
                scenarios.append({
                    "name": "user_authentication_flow",
                    "description": "User login and authentication process",
                    "steps": [
                        "Navigate to login page",
                        "Enter valid credentials",
                        "Submit login form",
                        "Verify successful authentication",
                        "Check redirect to dashboard",
                        "Verify user session is maintained"
                    ],
                    "user_flows": ["User Authentication"],
                    "pages": ["Login", "Dashboard"],
                    "priority": "high",
                    "complexity": "medium"
                })

        # Сценарии на основе бизнес-логики
        business_functions = self._identify_business_functions(project_analysis)
        for func in business_functions[:2]:
            scenarios.append({
                "name": f"{func.lower().replace(' ', '_')}_flow",
                "description": f"End-to-end test for {func}",
                "steps": [
                    f"Start {func} process",
                    "Execute main steps",
                    "Verify outcome",
                    "Check data persistence"
                ],
                "user_flows": [func],
                "pages": ["Main workflow pages"],
                "priority": "medium",
                "complexity": "high"
            })

        return scenarios if scenarios else self._create_default_e2e_scenarios(project_analysis)

    def _prepare_e2e_context(self, scenario: Dict, project_analysis: Dict, repo_path: str) -> Dict:
        """Подготавливает контекст для E2E теста"""
        return {
            "scenario": scenario,
            "application_info": {
                "technologies": project_analysis.get('technologies', []),
                "frameworks": project_analysis.get('frameworks', []),
                "api_endpoints": project_analysis.get('api_endpoints', []),
                "authentication_required": self._has_authentication(project_analysis),
                "frontend_framework": self._detect_frontend_framework(project_analysis)
            },
            "test_data": {
                "users": self._generate_test_users(scenario),
                "sample_data": self._generate_sample_data(scenario),
                "environment": "testing",
                "base_url": self._detect_base_url(project_analysis)
            },
            "navigation_flow": scenario.get('steps', []),
            "assertions": self._generate_e2e_assertions(scenario),
            "selectors": self._generate_element_selectors(scenario)
        }

    def _detect_frontend_framework(self, project_analysis: Dict) -> str:
        """Определяет фронтенд фреймворк"""
        technologies = project_analysis.get('technologies', [])
        if 'react' in technologies:
            return 'react'
        elif 'vue' in technologies:
            return 'vue'
        elif 'angular' in technologies:
            return 'angular'
        else:
            return 'unknown'

    def _detect_base_url(self, project_analysis: Dict) -> str:
        """Определяет базовый URL приложения"""
        # В реальной системе это может быть из конфигурации
        return "http://localhost:3000"

    def _generate_element_selectors(self, scenario: Dict) -> Dict[str, str]:
        """Генерирует селекторы элементов для E2E тестов"""
        selectors = {}
        scenario_name = scenario.get('name', '')

        if 'login' in scenario_name:
            selectors.update({
                "username_input": "[data-testid='username'] or input[name='username']",
                "password_input": "[data-testid='password'] or input[name='password']",
                "submit_button": "[data-testid='submit'] or button[type='submit']",
                "error_message": "[data-testid='error'] or .error-message"
            })
        elif 'registration' in scenario_name:
            selectors.update({
                "email_input": "[data-testid='email'] or input[name='email']",
                "password_input": "[data-testid='password'] or input[name='password']",
                "confirm_password_input": "[data-testid='confirm-password'] or input[name='confirmPassword']",
                "submit_button": "[data-testid='submit'] or button[type='submit']"
            })

        return selectors

    def _create_e2e_fallback_test(self, scenario: Dict, framework: str) -> str:
        """Создает fallback E2E тест"""
        test_name = scenario['name']
        description = scenario.get('description', 'E2E test scenario')
        steps = scenario.get('steps', [])

        if framework in ['pytest', 'playwright']:
            return f'''
# E2E Test: {test_name}
# Description: {description}

import pytest
import re
from playwright.sync_api import Page, expect

class Test{test_name.title().replace('_', '')}:

    def test_{test_name}(self, page: Page):
        """{description}"""

        try:
            # Test Steps:
{chr(10).join([f'            # {step}' for step in steps])}

            # TODO: Implement actual test steps based on your application
            # Example for web application:
            page.goto("http://localhost:3000")

            # Basic assertions to verify application is working
            expect(page).to_have_title(re.compile(r".+"))  # Page should have a title
            expect(page).to_have_url(re.compile(r"http://.*"))  # Valid URL

            # TODO: Add specific element interactions and assertions
            # Example for login flow:
            # page.fill('[data-testid="username"]', 'testuser')
            # page.fill('[data-testid="password"]', 'password123') 
            # page.click('[data-testid="submit"]')
            # expect(page).to_have_url(re.compile(r".*/dashboard"))

        except Exception as e:
            pytest.fail(f"E2E test failed: {{e}}")

    def test_{test_name}_steps_validation(self):
        """Verify all scenario steps are defined"""
        expected_steps = {steps}
        assert len(expected_steps) > 0, "Scenario should have defined steps"

        # Validate each step is properly defined
        for step in expected_steps:
            assert isinstance(step, str), f"Step should be string: {{step}}"
            assert len(step.strip()) > 0, "Step should not be empty"
'''
        else:
            return f'''
// E2E Test: {test_name}
// Description: {description}

// TODO: Implement E2E test for: {description}
// Steps: {', '.join(steps)}

// This is a fallback E2E test template
// Replace with actual implementation using your preferred E2E framework
'''

    def _create_default_e2e_scenarios(self, project_analysis: Dict) -> List[Dict]:
        """Создает стандартные E2E сценарии если не найдены в анализе"""
        return [
            {
                'name': 'application_smoke_test',
                'type': 'e2e',
                'description': 'Basic application smoke test',
                'steps': [
                    'Open application homepage',
                    'Verify page loads correctly',
                    'Check critical elements present',
                    'Verify no console errors',
                    'Test basic navigation'
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

    def _has_authentication(self, project_analysis: Dict) -> bool:
        """Проверяет требует ли приложение аутентификации"""
        auth_indicators = ['auth', 'login', 'jwt', 'token', 'session']
        for file_path in project_analysis.get('file_structure', {}).keys():
            if any(indicator in file_path.lower() for indicator in auth_indicators):
                return True
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

        scenario_name = scenario.get('name', '')
        if 'auth' in scenario_name:
            assertions.extend([
                "User can login successfully",
                "Protected routes are accessible after auth",
                "Logout functionality works"
            ])
        if 'api' in scenario_name:
            assertions.extend([
                "API responses are valid",
                "Error handling works for invalid requests",
                "Data consistency maintained"
            ])
        if 'registration' in scenario_name:
            assertions.extend([
                "User can register successfully",
                "Validation errors show properly",
                "Confirmation email sent (if applicable)"
            ])

        return assertions

    def _format_test_cases(self, test_cases: List[Dict], format_type: str = "markdown") -> str:
        """Форматирует тест-кейсы в указанный формат"""
        if format_type == "markdown":
            return self._format_test_cases_markdown(test_cases)
        elif format_type == "html":
            return self._format_test_cases_html(test_cases)
        elif format_type == "txt":
            return self._format_test_cases_txt(test_cases)
        else:
            return self._format_test_cases_markdown(test_cases)

    def _format_test_cases_markdown(self, test_cases: List[Dict]) -> str:
        """Форматирует тест-кейсы в Markdown"""
        content = "# Test Cases Documentation\n\n"
        content += f"*Generated on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"

        for tc in test_cases:
            content += f"## {tc['test_case_id']}: {tc['name']}\n\n"

            if tc.get('description'):
                content += f"**Description:** {tc['description']}\n\n"

            content += f"**Type:** {tc.get('test_type', 'functional')}  \n"
            content += f"**Priority:** {tc.get('priority', 'medium')}  \n"
            content += f"**Status:** {tc.get('status', 'draft')}\n\n"

            if tc.get('preconditions'):
                content += f"**Preconditions:**\n{tc['preconditions']}\n\n"

            if tc.get('steps'):
                content += "**Test Steps:**\n\n"
                for step in tc['steps']:
                    content += f"{step.get('step_number', 1)}. **Action:** {step.get('action', '')}\n"
                    if step.get('expected_result'):
                        content += f"   **Expected:** {step.get('expected_result')}\n"
                    if step.get('data'):
                        content += f"   **Data:** {step.get('data')}\n"
                    content += "\n"

            if tc.get('postconditions'):
                content += f"**Postconditions:**\n{tc['postconditions']}\n\n"

            content += "---\n\n"

        return content

    def _format_test_cases_html(self, test_cases: List[Dict]) -> str:
        """Форматирует тест-кейсы в HTML"""
        content = """<!DOCTYPE html>
    <html>
    <head>
        <title>Test Cases Documentation</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .test-case { border: 1px solid #ddd; padding: 20px; margin: 20px 0; border-radius: 5px; }
            .test-case-id { font-size: 1.5em; font-weight: bold; color: #333; }
            .priority-high { border-left: 5px solid #e74c3c; }
            .priority-medium { border-left: 5px solid #f39c12; }
            .priority-low { border-left: 5px solid #27ae60; }
            .step { margin: 10px 0; padding: 10px; background: #f8f9fa; }
        </style>
    </head>
    <body>
        <h1>Test Cases Documentation</h1>
        <p><em>Generated on: """ + datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + """</em></p>
    """

        for tc in test_cases:
            priority_class = f"priority-{tc.get('priority', 'medium')}"
            content += f"""
        <div class="test-case {priority_class}">
            <div class="test-case-id">{tc['test_case_id']}: {tc['name']}</div>
    """

            if tc.get('description'):
                content += f"        <p><strong>Description:</strong> {tc['description']}</p>\n"

            content += f"""
            <p><strong>Type:</strong> {tc.get('test_type', 'functional')}</p>
            <p><strong>Priority:</strong> {tc.get('priority', 'medium')}</p>
            <p><strong>Status:</strong> {tc.get('status', 'draft')}</p>
    """

            if tc.get('preconditions'):
                content += f"        <p><strong>Preconditions:</strong><br>{tc['preconditions']}</p>\n"

            if tc.get('steps'):
                content += "        <h3>Test Steps:</h3>\n"
                for step in tc['steps']:
                    content += f"""
            <div class="step">
                <strong>Step {step.get('step_number', 1)}:</strong> {step.get('action', '')}<br>
    """
                    if step.get('expected_result'):
                        content += f"            <strong>Expected:</strong> {step.get('expected_result')}<br>\n"
                    if step.get('data'):
                        content += f"            <strong>Data:</strong> {step.get('data')}<br>\n"
                    content += "        </div>\n"

            if tc.get('postconditions'):
                content += f"        <p><strong>Postconditions:</strong><br>{tc['postconditions']}</p>\n"

            content += "    </div>\n"

        content += """
    </body>
    </html>"""

        return content

    def _format_test_cases_txt(self, test_cases: List[Dict]) -> str:
        """Форматирует тест-кейсы в текстовый формат"""
        content = f"TEST CASES DOCUMENTATION\n"
        content += f"Generated on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n"
        content += "=" * 50 + "\n\n"

        for tc in test_cases:
            content += f"{tc['test_case_id']}: {tc['name']}\n"
            content += "-" * 50 + "\n"

            if tc.get('description'):
                content += f"Description: {tc['description']}\n\n"

            content += f"Type: {tc.get('test_type', 'functional')}\n"
            content += f"Priority: {tc.get('priority', 'medium')}\n"
            content += f"Status: {tc.get('status', 'draft')}\n\n"

            if tc.get('preconditions'):
                content += f"Preconditions:\n{tc['preconditions']}\n\n"

            if tc.get('steps'):
                content += "Test Steps:\n"
                for step in tc['steps']:
                    content += f"  {step.get('step_number', 1)}. Action: {step.get('action', '')}\n"
                    if step.get('expected_result'):
                        content += f"     Expected: {step.get('expected_result')}\n"
                    if step.get('data'):
                        content += f"     Data: {step.get('data')}\n"
                    content += "\n"

            if tc.get('postconditions'):
                content += f"Postconditions:\n{tc['postconditions']}\n\n"

            content += "\n" + "=" * 50 + "\n\n"

        return content

    async def push_to_repository(self, push_data: Dict[str, Any]) -> Dict[str, Any]:
        """Пуш тестов и тест-кейсов в репозиторий"""
        try:
            logger.info("🚀 Starting push to repository...")

            project_info = push_data["project_info"]
            tests = push_data.get("tests", [])
            test_cases = push_data.get("test_cases", [])
            push_config = push_data.get("push_config", {})

            repo_path = project_info["local_path"]
            commit_message = push_config.get("commit_message", "Add generated tests and test cases")
            branch = project_info.get("branch", "main")

            # Используем GitService для пуша
            git_service = GitService()

            # Проверяем репозиторий перед пушем
            validation = await git_service.validate_repository(repo_path)
            if not validation["valid"]:
                return {
                    "status": "error",
                    "error": f"Repository validation failed: {validation['error']}"
                }

            # Создаем файлы и пушим
            push_result = await git_service.push_tests_to_repository(
                repo_path=repo_path,
                tests=tests,
                test_cases=test_cases,
                commit_message=commit_message,
                branch=branch
            )

            if push_result["success"]:
                return {
                    "status": "success",
                    "message": f"Successfully pushed {len(tests)} tests and {len(test_cases)} test cases to repository",
                    "pushed_files": push_result.get("pushed_files", []),
                    "tests_count": push_result.get("tests_count", 0),
                    "test_cases_count": push_result.get("test_cases_count", 0),
                    "commit_hash": push_result.get("commit_hash"),
                    "branch": branch
                }
            else:
                return {
                    "status": "error",
                    "error": push_result.get("error", "Push failed"),
                    "pushed_files": push_result.get("pushed_files", [])
                }

        except Exception as e:
            logger.error(f"❌ Push to repository failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    # async def generate_test_cases(self, generation_data: Dict) -> Dict[str, Any]:
    #     """Генерация текстовых тест-кейсов на основе анализа проекта"""
    #     try:
    #         logger.info("🎯 START: Test case generation pipeline started")
    #
    #         # Валидация входных данных
    #         if not generation_data:
    #             return self._create_error_response("Empty generation data")
    #
    #         project_info = generation_data["project_info"]
    #         analysis_data = generation_data["analysis_data"]
    #         test_case_config = generation_data["test_case_config"]
    #         user_id = generation_data.get("user_id")
    #
    #         repo_path = project_info.get("local_path")
    #         if not repo_path or not os.path.exists(repo_path):
    #             return self._create_error_response(f"Repository path not found: {repo_path}")
    #
    #         # Улучшаем анализ данных
    #         enhanced_analysis = await self._enhance_analysis_data(analysis_data, repo_path)
    #
    #         # Подготавливаем контекст для генерации
    #         generation_context = self._prepare_test_case_context(enhanced_analysis, test_case_config, repo_path)
    #
    #         # Генерируем тест-кейсы
    #         test_cases = await self._generate_test_cases_content(generation_context, test_case_config)
    #
    #         return {
    #             "status": "success",
    #             "test_cases": test_cases,
    #             "test_cases_count": len(test_cases),
    #             "project_name": project_info['name'],
    #             "generation_time": datetime.utcnow().isoformat(),
    #             "coverage_estimate": self._estimate_test_case_coverage(test_cases, enhanced_analysis)
    #         }
    #
    #     except Exception as e:
    #         logger.error(f"❌ TEST_CASE_GENERATION_ERROR: {e}", exc_info=True)
    #         return self._create_error_response(f"Test case generation failed: {str(e)}")

    def _validate_test_case_response(self, response: str) -> bool:
        """Проверяет валидность ответа с тест-кейсом"""
        try:
            # Пытаемся найти JSON в ответе
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                test_case = json.loads(json_match.group())
                return all(key in test_case for key in ['name', 'steps', 'test_case_id'])
            return False
        except:
            return False

    def _parse_test_case_response(self, response: str, source: Dict, test_type: str) -> Dict:
        """Парсит ответ AI в структуру тест-кейса"""
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                test_case = json.loads(json_match.group())

                # Добавляем мета-информацию
                test_case.update({
                    "source_type": test_type,
                    "source_reference": source,
                    "created_at": datetime.utcnow().isoformat(),
                    "status": "draft"
                })

                return test_case
        except Exception as e:
            logger.error(f"Error parsing test case response: {e}")

        # Fallback тест-кейс
        return self._create_fallback_test_case(source, test_type)

    async def _parse_user_files(self, user_files: List[Dict]) -> Dict[str, Any]:
            """Парсит файлы пользователя (Excel, Word, PDF, CSV)"""
            parsed_data = {
                "excel_data": [],
                "word_data": [],
                "pdf_data": [],
                "csv_data": [],
                "requirements": [],
                "user_stories": [],
                "test_scenarios": []
            }

            if not user_files:
                return parsed_data

            for user_file in user_files:
                try:
                    file_content = user_file.get("content")
                    file_name = user_file.get("filename", "unknown")
                    file_type = user_file.get("type", "unknown")

                    logger.info(f"📁 Processing user file: {file_name} ({file_type})")

                    if file_type == "excel":
                        excel_data = await self._parse_excel_file(file_content, file_name)
                        parsed_data["excel_data"].extend(excel_data)

                    elif file_type == "word":
                        word_data = await self._parse_word_file(file_content, file_name)
                        parsed_data["word_data"].extend(word_data)

                    elif file_type == "pdf":
                        pdf_data = await self._parse_pdf_file(file_content, file_name)
                        parsed_data["pdf_data"].extend(pdf_data)

                    elif file_type == "csv":
                        csv_data = await self._parse_csv_file(file_content, file_name)
                        parsed_data["csv_data"].extend(csv_data)

                    elif file_type == "text":
                        text_data = await self._parse_text_file(file_content, file_name)
                        parsed_data["requirements"].extend(text_data.get("requirements", []))
                        parsed_data["user_stories"].extend(text_data.get("user_stories", []))

                except Exception as e:
                    logger.error(f"❌ Error parsing file {file_name}: {e}")

            # Извлекаем тестовые сценарии из всех данных
            parsed_data["test_scenarios"] = self._extract_test_scenarios_from_data(parsed_data)

            logger.info(f"📊 User files parsed: {len(parsed_data['test_scenarios'])} scenarios found")
            return parsed_data

    async def _parse_excel_file(self, file_content: bytes, filename: str) -> List[Dict]:
            """Парсит Excel файлы с тест-кейсами или требованиями"""
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                    tmp_file.write(file_content)
                    tmp_file.flush()

                    df = pd.read_excel(tmp_file.name)

                # Анализируем структуру Excel файла
                excel_data = []

                # Проверяем наличие стандартных колонок для тест-кейсов
                expected_columns = ['test_case_id', 'name', 'description', 'steps', 'expected_result']

                for sheet_name in pd.ExcelFile(tmp_file.name).sheet_names:
                    df_sheet = pd.read_excel(tmp_file.name, sheet_name=sheet_name)

                    # Преобразуем данные в структурированный формат
                    for _, row in df_sheet.iterrows():
                        test_case = {
                            "source_file": filename,
                            "source_sheet": sheet_name,
                            "row_data": row.to_dict()
                        }

                        # Пытаемся извлечь структурированную информацию
                        if 'test_case_id' in df_sheet.columns or 'Test Case ID' in df_sheet.columns:
                            test_case_id_col = 'test_case_id' if 'test_case_id' in df_sheet.columns else 'Test Case ID'
                            test_case["test_case_id"] = str(row.get(test_case_id_col, f"TC_{uuid.uuid4().hex[:8]}"))

                        if 'name' in df_sheet.columns or 'Name' in df_sheet.columns:
                            name_col = 'name' if 'name' in df_sheet.columns else 'Name'
                            test_case["name"] = str(row.get(name_col, "Unnamed Test Case"))

                        if 'description' in df_sheet.columns or 'Description' in df_sheet.columns:
                            desc_col = 'description' if 'description' in df_sheet.columns else 'Description'
                            test_case["description"] = str(row.get(desc_col, ""))

                        excel_data.append(test_case)

                os.unlink(tmp_file.name)
                logger.info(f"✅ Excel parsed: {len(excel_data)} rows from {filename}")
                return excel_data

            except Exception as e:
                logger.error(f"❌ Excel parsing error: {e}")
                return []

    async def _parse_word_file(self, file_content: bytes, filename: str) -> List[Dict]:
            """Парсит Word документы"""
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp_file:
                    tmp_file.write(file_content)
                    tmp_file.flush()

                    doc = Document(tmp_file.name)

                word_data = []
                current_section = ""

                for paragraph in doc.paragraphs:
                    text = paragraph.text.strip()
                    if not text:
                        continue

                    # Определяем тип контента по форматированию
                    if paragraph.style.name.startswith('Heading'):
                        current_section = text
                        word_data.append({
                            "type": "section_header",
                            "content": text,
                            "level": int(paragraph.style.name.split()[-1]) if paragraph.style.name.split()[
                                -1].isdigit() else 1
                        })
                    else:
                        # Анализируем текст на требования и пользовательские истории
                        requirements = self._extract_requirements_from_text(text)
                        user_stories = self._extract_user_stories_from_text(text)

                        word_data.append({
                            "type": "paragraph",
                            "section": current_section,
                            "content": text,
                            "requirements": requirements,
                            "user_stories": user_stories
                        })

                os.unlink(tmp_file.name)
                logger.info(f"✅ Word parsed: {len(word_data)} elements from {filename}")
                return word_data

            except Exception as e:
                logger.error(f"❌ Word parsing error: {e}")
                return []

    async def _parse_pdf_file(self, file_content: bytes, filename: str) -> List[Dict]:
            """Парсит PDF файлы"""
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                    tmp_file.write(file_content)
                    tmp_file.flush()

                    pdf_reader = PyPDF2.PdfReader(tmp_file.name)

                pdf_data = []

                for page_num, page in enumerate(pdf_reader.pages):
                    text = page.extract_text()
                    if text.strip():
                        # Анализируем текст страницы
                        requirements = self._extract_requirements_from_text(text)
                        user_stories = self._extract_user_stories_from_text(text)
                        test_scenarios = self._extract_test_scenarios_from_text(text)

                        pdf_data.append({
                            "page": page_num + 1,
                            "content": text,
                            "requirements": requirements,
                            "user_stories": user_stories,
                            "test_scenarios": test_scenarios
                        })

                os.unlink(tmp_file.name)
                logger.info(f"✅ PDF parsed: {len(pdf_data)} pages from {filename}")
                return pdf_data

            except Exception as e:
                logger.error(f"❌ PDF parsing error: {e}")
                return []

    async def _parse_csv_file(self, file_content: bytes, filename: str) -> List[Dict]:
            """Парсит CSV файлы"""
            try:
                # Декодируем байты в строку
                content_str = file_content.decode('utf-8')

                # Читаем CSV
                df = pd.read_csv(pd.compat.StringIO(content_str))

                csv_data = []
                for _, row in df.iterrows():
                    csv_data.append({
                        "source_file": filename,
                        "row_data": row.to_dict()
                    })

                logger.info(f"✅ CSV parsed: {len(csv_data)} rows from {filename}")
                return csv_data

            except Exception as e:
                logger.error(f"❌ CSV parsing error: {e}")
                return []

    async def _parse_text_file(self, file_content: bytes, filename: str) -> Dict[str, List]:
            """Парсит текстовые файлы"""
            try:
                content_str = file_content.decode('utf-8')

                return {
                    "requirements": self._extract_requirements_from_text(content_str),
                    "user_stories": self._extract_user_stories_from_text(content_str),
                    "test_scenarios": self._extract_test_scenarios_from_text(content_str)
                }

            except Exception as e:
                logger.error(f"❌ Text parsing error: {e}")
                return {"requirements": [], "user_stories": [], "test_scenarios": []}

    def _extract_requirements_from_text(self, text: str) -> List[str]:
            """Извлекает требования из текста"""
            requirements = []

            # Паттерны для требований
            patterns = [
                r'[Тт]ребование\s*[№#]?\s*\d*[.:]\s*(.+?)(?=\n|$)',
                r'[Rr]equirement\s*[№#]?\s*\d*[.:]\s*(.+?)(?=\n|$)',
                r'[Фф]ункционал\s*[№#]?\s*\d*[.:]\s*(.+?)(?=\n|$)',
                r'[Ss]hall\s+.+?',
                r'[Mm]ust\s+.+?',
                r'[Сс]истема\s+должна\s+.+?'
            ]

            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    requirement = match.group(1) if match.groups() else match.group(0)
                    if requirement.strip():
                        requirements.append(requirement.strip())

            return requirements

    def _extract_user_stories_from_text(self, text: str) -> List[str]:
            """Извлекает пользовательские истории из текста"""
            user_stories = []

            # Паттерны для пользовательских историй
            patterns = [
                r'[Кк]ак\s+([^,\n]+)\s+[Яя]\s+хочу\s+(.+?)(?=чтобы|$)',
                r'[Aa]s\s+a\s+([^,\n]+)\s+[Ii]\s+want\s+to\s+(.+?)(?=so that|$)',
                r'[Uu]ser\s+story\s*[№#]?\s*\d*[.:]\s*(.+?)(?=\n|$)',
                r'[Ии]стория\s+пользователя\s*[№#]?\s*\d*[.:]\s*(.+?)(?=\n|$)'
            ]

            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    if len(match.groups()) >= 2:
                        user_story = f"As {match.group(1).strip()} I want {match.group(2).strip()}"
                    else:
                        user_story = match.group(1) if match.groups() else match.group(0)

                    if user_story.strip():
                        user_stories.append(user_story.strip())

            return user_stories

    def _extract_test_scenarios_from_text(self, text: str) -> List[Dict]:
            """Извлекает тестовые сценарии из текста"""
            scenarios = []

            lines = text.split('\n')
            current_scenario = None

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Паттерны для начала сценария
                scenario_patterns = [
                    r'[Сс]ценарий\s*[№#]?\s*\d*[.:]\s*(.+)',
                    r'[Ss]cenario\s*[№#]?\s*\d*[.:]\s*(.+)',
                    r'[Тт]ест-кейс\s*[№#]?\s*\d*[.:]\s*(.+)',
                    r'[Tt]est case\s*[№#]?\s*\d*[.:]\s*(.+)'
                ]

                for pattern in scenario_patterns:
                    match = re.match(pattern, line, re.IGNORECASE)
                    if match:
                        if current_scenario:
                            scenarios.append(current_scenario)

                        current_scenario = {
                            "name": match.group(1).strip(),
                            "steps": [],
                            "type": "manual"
                        }
                        break

                # Паттерны для шагов
                step_pattern = r'^\s*(\d+)\.\s*(.+?)\s*[—–-]\s*(.+)'
                step_match = re.match(step_pattern, line)
                if step_match and current_scenario:
                    current_scenario["steps"].append({
                        "step_number": int(step_match.group(1)),
                        "action": step_match.group(2).strip(),
                        "expected_result": step_match.group(3).strip()
                    })

            if current_scenario:
                scenarios.append(current_scenario)

            return scenarios

    def _extract_test_scenarios_from_data(self, parsed_data: Dict) -> List[Dict]:
            """Извлекает тестовые сценарии из всех распарсенных данных"""
            all_scenarios = []

            # Извлекаем из всех источников
            all_scenarios.extend(parsed_data.get("test_scenarios", []))

            # Из Excel данных
            for excel_item in parsed_data.get("excel_data", []):
                if "test_case_id" in excel_item:
                    scenario = {
                        "name": excel_item.get("name", "Unnamed Scenario"),
                        "test_case_id": excel_item.get("test_case_id"),
                        "source": "excel",
                        "data": excel_item
                    }
                    all_scenarios.append(scenario)

            # Из требований создаем базовые сценарии
            for requirement in parsed_data.get("requirements", []):
                scenario = {
                    "name": f"Test: {requirement[:50]}...",
                    "description": requirement,
                    "type": "requirement_based",
                    "priority": "high"
                }
                all_scenarios.append(scenario)

            # Из пользовательских историй
            for user_story in parsed_data.get("user_stories", []):
                scenario = {
                    "name": f"User Story: {user_story[:50]}...",
                    "description": user_story,
                    "type": "user_story_based",
                    "priority": "medium"
                }
                all_scenarios.append(scenario)

            return all_scenarios

    def _prepare_test_case_context(self, enhanced_analysis: Dict, test_case_config: Dict,
                                       repo_path: str, parsed_user_data: Dict) -> Dict[str, Any]:
            """Подготавливает контекст для генерации тест-кейсов"""

            base_context = self._prepare_context(enhanced_analysis)

            # Добавляем информацию о пользовательских данных
            user_data_context = {
                "user_files_available": bool(parsed_user_data),
                "requirements_count": len(parsed_user_data.get("requirements", [])),
                "user_stories_count": len(parsed_user_data.get("user_stories", [])),
                "test_scenarios_from_files": len(parsed_user_data.get("test_scenarios", [])),
                "excel_data_count": len(parsed_user_data.get("excel_data", [])),
                "sample_requirements": parsed_user_data.get("requirements", [])[:5],
                "sample_user_stories": parsed_user_data.get("user_stories", [])[:5],
                "has_structured_data": any(parsed_user_data.get(key) for key in ["excel_data", "test_scenarios"])
            }

            return {
                **base_context,
                "user_data": user_data_context,
                "parsed_user_data": parsed_user_data,
                "test_case_config": test_case_config,
                "generation_strategy": self._determine_generation_strategy(parsed_user_data, enhanced_analysis)
            }

    def _determine_generation_strategy(self, parsed_user_data: Dict, enhanced_analysis: Dict) -> str:
            """Определяет стратегию генерации на основе доступных данных"""

            if parsed_user_data.get("test_scenarios"):
                return "enhance_existing_scenarios"
            elif parsed_user_data.get("excel_data"):
                return "structured_data_based"
            elif parsed_user_data.get("requirements") or parsed_user_data.get("user_stories"):
                return "requirements_based"
            elif enhanced_analysis.get("api_endpoints"):
                return "api_based"
            else:
                return "project_analysis_based"

    async def generate_test_cases(self, generation_data: Dict) -> Dict[str, Any]:
        """Генерация тест-кейсов для проекта"""
        try:
            logger.info("🎯 START: Test case generation pipeline started")

            # Валидация входных данных
            if not generation_data:
                return self._create_error_response("Empty generation data")

            project_info = generation_data["project_info"]
            analysis_data = generation_data["analysis_data"]
            test_case_config = generation_data["test_case_config"]
            user_files = generation_data.get("user_files", [])

            repo_path = project_info.get("local_path")

            # Улучшаем анализ данных
            enhanced_analysis = await self._enhance_analysis_data(analysis_data, repo_path)

            # 🔥 ОБРАБОТКА ФАЙЛОВ ПОЛЬЗОВАТЕЛЯ
            parsed_user_data = await self._parse_user_files(user_files)

            # Подготавливаем контекст для генерации
            generation_context = self._prepare_test_case_context(
                enhanced_analysis,
                test_case_config,
                repo_path,
                parsed_user_data
            )

            # Генерируем тест-кейсы
            test_cases = await self._generate_test_cases_content(
                generation_context,
                test_case_config,
                parsed_user_data
            )

            # Применяем конфигурацию пользователя
            filtered_test_cases = self._apply_test_case_config(test_cases, test_case_config)

            return {
                "status": "success",
                "test_cases": filtered_test_cases,
                "test_cases_count": len(filtered_test_cases),
                "project_name": project_info['name'],
                "generation_time": datetime.utcnow().isoformat(),
                "coverage_estimate": self._estimate_test_case_coverage(filtered_test_cases, enhanced_analysis),
                "user_files_processed": len(user_files),
                "parsed_user_data_summary": self._summarize_parsed_data(parsed_user_data)
            }

        except Exception as e:
            logger.error(f"❌ TEST_CASE_GENERATION_ERROR: {e}", exc_info=True)
            return self._create_error_response(f"Test case generation failed: {str(e)}")

    async def _generate_test_cases_content(self, context: Dict, config: Dict, parsed_user_data: Dict) -> List[Dict]:
        """Генерирует контент тест-кейсов с использованием AI"""
        test_cases = []

        # Определяем стратегию генерации на основе доступных данных
        strategy = context.get('generation_strategy', 'project_analysis_based')

        logger.info(f"🎯 Using generation strategy: {strategy}")

        if strategy == "enhance_existing_scenarios":
            test_cases.extend(await self._generate_from_existing_scenarios(parsed_user_data, context))
        elif strategy == "structured_data_based":
            test_cases.extend(await self._generate_from_structured_data(parsed_user_data, context))
        elif strategy == "requirements_based":
            test_cases.extend(await self._generate_from_requirements(parsed_user_data, context))
        elif strategy == "api_based":
            test_cases.extend(await self._generate_from_api_endpoints(context))
        else:
            test_cases.extend(await self._generate_from_project_analysis(context))

        # Ограничиваем количество тест-кейсов
        max_cases = config.get("max_test_cases", 50)
        if len(test_cases) > max_cases:
            test_cases = test_cases[:max_cases]

        logger.info(f"✅ Generated {len(test_cases)} test cases using {strategy} strategy")
        return test_cases

    async def _generate_from_existing_scenarios(self, parsed_user_data: Dict, context: Dict) -> List[Dict]:
        """Улучшает существующие тестовые сценарии из файлов"""
        test_cases = []

        for scenario in parsed_user_data.get("test_scenarios", [])[:20]:
            try:
                test_case_content = await self.ai_service.generate_test_content(
                    file_info={
                        "type": "test_scenario",
                        "scenario_data": scenario,
                        "name": scenario.get('name', 'Unnamed Scenario'),
                        "path": f"test_cases/{scenario.get('name', 'scenario')}"
                    },
                    project_context=context,
                    test_type="test_case",
                    framework="generic",
                    config={"priority": "high"}
                )

                if test_case_content and self._validate_test_case_response(test_case_content):
                    test_case = self._parse_test_case_response(test_case_content, scenario, "enhanced_scenario")
                    test_cases.append(test_case)

            except Exception as e:
                logger.error(f"Error enhancing scenario: {e}")
                test_cases.append(self._create_fallback_test_case(scenario, "enhanced_scenario"))

        return test_cases

    async def _generate_from_structured_data(self, parsed_user_data: Dict, context: Dict) -> List[Dict]:
            """Генерирует тест-кейсы из структурированных данных (Excel)"""
            test_cases = []

            for excel_item in parsed_user_data.get("excel_data", [])[:15]:
                try:
                    prompt = self._create_excel_based_prompt(excel_item, context)
                    test_case_content = await self.ai_service.generate_test_content(
                        file_info={"type": "excel_data", "excel_data": excel_item},
                        project_context=context,
                        test_type="test_case",
                        framework="generic",
                        config={"priority": "medium"}
                    )

                    if test_case_content and self._validate_test_case_response(test_case_content):
                        test_case = self._parse_test_case_response(test_case_content, excel_item, "excel_based")
                        test_cases.append(test_case)

                except Exception as e:
                    logger.error(f"Error generating from Excel data: {e}")
                    test_cases.append(self._create_fallback_test_case(excel_item, "excel_based"))

            return test_cases

    async def _generate_from_requirements(self, parsed_user_data: Dict, context: Dict) -> List[Dict]:
        """Генерирует тест-кейсы из требований и пользовательских историй"""
        test_cases = []

        # Из требований
        for requirement in parsed_user_data.get("requirements", [])[:10]:
            try:
                test_case_content = await self.ai_service.generate_test_content(
                    file_info={
                        "type": "requirement",
                        "requirement": requirement,
                        "name": f"Requirement: {requirement[:50]}...",
                        "path": "test_cases/requirements"
                    },
                    project_context=context,
                    test_type="test_case",
                    framework="generic",
                    config={"priority": "high"}
                )

                if test_case_content and self._validate_test_case_response(test_case_content):
                    test_case = self._parse_test_case_response(test_case_content, requirement, "requirement_based")
                    test_cases.append(test_case)

            except Exception as e:
                logger.error(f"Error generating from requirement: {e}")
                test_cases.append(self._create_fallback_test_case(requirement, "requirement_based"))

        # Из пользовательских историй
        for user_story in parsed_user_data.get("user_stories", [])[:10]:
            try:
                test_case_content = await self.ai_service.generate_test_content(
                    file_info={
                        "type": "user_story",
                        "user_story": user_story,
                        "name": f"User Story: {user_story[:50]}...",
                        "path": "test_cases/user_stories"
                    },
                    project_context=context,
                    test_type="test_case",
                    framework="generic",
                    config={"priority": "medium"}
                )

                if test_case_content and self._validate_test_case_response(test_case_content):
                    test_case = self._parse_test_case_response(test_case_content, user_story, "user_story_based")
                    test_cases.append(test_case)

            except Exception as e:
                logger.error(f"Error generating from user story: {e}")
                test_cases.append(self._create_fallback_test_case(user_story, "user_story_based"))

        return test_cases

    async def _generate_from_api_endpoints(self, context: Dict) -> List[Dict]:
        """Генерирует тест-кейсы из API endpoints"""
        test_cases = []
        api_endpoints = context.get("api_endpoints", [])

        for endpoint in api_endpoints[:15]:
            try:
                test_case_content = await self.ai_service.generate_test_content(
                    file_info={
                        "type": "api_endpoint",
                        "endpoint": endpoint,
                        "name": f"API {endpoint.get('method', 'GET')} {endpoint.get('path', '')}",
                        "path": f"test_cases/api/{endpoint.get('method', 'GET').lower()}_{endpoint.get('path', '').replace('/', '_')}"
                    },
                    project_context=context,
                    test_type="test_case",
                    framework="generic",
                    config={"priority": "high"}
                )

                if test_case_content and self._validate_test_case_response(test_case_content):
                    test_case = self._parse_test_case_response(test_case_content, endpoint, "api_based")
                    test_cases.append(test_case)

            except Exception as e:
                logger.error(f"Error generating from API endpoint: {e}")
                test_cases.append(self._create_fallback_test_case(endpoint, "api_based"))

        return test_cases

    async def _generate_from_project_analysis(self, context: Dict) -> List[Dict]:
            """Генерирует тест-кейсы из анализа проекта"""
            test_cases = []

            # Генерируем тест-кейсы для основных функциональностей
            business_functions = context.get("enhanced_analysis", {}).get("business_context_enhanced", {}).get(
                "core_business_functions", [])

            for function in business_functions[:8]:
                try:
                    prompt = self._create_business_function_prompt(function, context)
                    test_case_content = await self.ai_service.generate_test_content(
                        file_info={"type": "business_function", "function": function},
                        project_context=context,
                        test_type="test_case",
                        framework="generic",
                        config={"priority": "medium"}
                    )

                    if test_case_content and self._validate_test_case_response(test_case_content):
                        test_case = self._parse_test_case_response(test_case_content, function, "business_function")
                        test_cases.append(test_case)

                except Exception as e:
                    logger.error(f"Error generating from business function: {e}")
                    test_cases.append(self._create_fallback_test_case(function, "business_function"))

            return test_cases

    def _create_scenario_enhancement_prompt(self, scenario: Dict, context: Dict) -> str:
            """Создает промпт для улучшения существующих сценариев"""
            return f"""
    Ты - старший QA инженер. Улучши предоставленный тестовый сценарий, добавив детализацию и профессиональные практики тестирования.

    ИСХОДНЫЙ СЦЕНАРИЙ:
    {json.dumps(scenario, indent=2, ensure_ascii=False)}

    КОНТЕКСТ ПРОЕКТА:
    - Технологии: {context.get('project_metadata', {}).get('technologies', [])}
    - Бизнес-функции: {context.get('enhanced_analysis', {}).get('business_context_enhanced', {}).get('core_business_functions', [])}

    ЗАДАЧА:
    Детализируй сценарий, добавь:
    1. Четкие предусловия и постусловия
    2. Детальные шаги с ожидаемыми результатами
    3. Тестовые данные
    4. Критерии приемки
    5. Приоритет и сложность

    ФОРМАТ ОТВЕТА - ТОЛЬКО JSON:
    ```json
    {{
      "test_case_id": "уникальный_ид",
      "name": "Название тест-кейса",
      "description": "Описание",
      "test_type": "functional/regression/etc",
      "priority": "high/medium/low", 
      "preconditions": ["список предусловий"],
      "steps": [
        {{
          "step_number": 1,
          "action": "действие",
          "expected_result": "ожидаемый результат",
          "data": "тестовые данные"
        }}
      ],
      "postconditions": ["список постусловий"],
      "status": "draft"
    }}
    ```
    """

    def _create_fallback_test_case(self, source: Dict, test_type: str) -> Dict:
        """Создает fallback тест-кейс"""
        if test_type == "api_based":
            return {
                "test_case_id": f"API_{source.get('method', 'GET')}_{source.get('path', '').replace('/', '_')}",
                "name": f"Тестирование {source.get('method', 'GET')} {source.get('path', '')}",
                "description": f"Тест-кейс для endpoint {source.get('path', '')}",
                "test_type": "api",
                "priority": "medium",
                "preconditions": ["Система доступна", "Пользователь аутентифицирован"],
                "steps": [
                    {
                        "step_number": 1,
                        "action": f"Выполнить {source.get('method', 'GET')} запрос к {source.get('path', '')}",
                        "expected_result": "Получить корректный ответ от сервера",
                        "data": "Валидные тестовые данные"
                    }
                ],
                "postconditions": ["Система возвращается в исходное состояние"],
                "status": "draft",
                "source_type": test_type,
                "source_reference": source
            }
        else:
            return {
                "test_case_id": f"TC_{uuid.uuid4().hex[:8]}",
                "name": f"Тест-кейс для {test_type}",
                "description": f"Автоматически сгенерированный тест-кейс",
                "test_type": "functional",
                "priority": "medium",
                "preconditions": ["Система доступна"],
                "steps": [
                    {
                        "step_number": 1,
                        "action": "Выполнить базовую операцию",
                        "expected_result": "Операция завершена успешно",
                        "data": "Тестовые данные"
                    }
                ],
                "postconditions": ["Система в стабильном состоянии"],
                "status": "draft",
                "source_type": test_type,
                "source_reference": source
            }

    def _apply_test_case_config(self, test_cases: List[Dict], config: Dict) -> List[Dict]:
        """Применяет конфигурацию пользователя к тест-кейсам"""
        filtered_cases = test_cases

        # Фильтрация по типу
        if config.get("test_types"):
            filtered_cases = [tc for tc in filtered_cases if tc.get("test_type") in config["test_types"]]

        # Фильтрация по приоритету
        if config.get("priorities"):
            filtered_cases = [tc for tc in filtered_cases if tc.get("priority") in config["priorities"]]

        # Ограничение количества
        max_cases = config.get("max_test_cases", 50)
        if len(filtered_cases) > max_cases:
            filtered_cases = filtered_cases[:max_cases]

        return filtered_cases

    def _summarize_parsed_data(self, parsed_data: Dict) -> Dict:
        """Создает сводку по распарсенным данным"""
        return {
            "total_requirements": len(parsed_data.get("requirements", [])),
            "total_user_stories": len(parsed_data.get("user_stories", [])),
            "total_test_scenarios": len(parsed_data.get("test_scenarios", [])),
            "excel_rows": len(parsed_data.get("excel_data", [])),
            "word_elements": len(parsed_data.get("word_data", [])),
            "pdf_pages": len(parsed_data.get("pdf_data", [])),
            "csv_rows": len(parsed_data.get("csv_data", []))
        }

    def _estimate_test_case_coverage(self, test_cases: List[Dict], analysis: Dict) -> float:
        """Оценивает покрытие тест-кейсами"""
        if not test_cases:
            return 0.0

        # Базовая оценка на основе количества тест-кейсов
        base_coverage = min(80.0, len(test_cases) * 2.0)

        # Бонус за разнообразие типов тестов
        test_types = set(tc.get("test_type", "unknown") for tc in test_cases)
        diversity_bonus = min(15.0, len(test_types) * 3.0)

        # Бонус за приоритетные тесты
        high_priority_count = sum(1 for tc in test_cases if tc.get("priority") == "high")
        priority_bonus = min(10.0, high_priority_count * 1.0)

        final_coverage = base_coverage + diversity_bonus + priority_bonus
        return min(95.0, final_coverage)
# Глобальная переменная (для обратной совместимости)
test_generation_pipeline = None


def init_test_generation_pipeline(ai_service):
    """Инициализация пайплайна (для обратной совместимости)"""
    global test_generation_pipeline
    test_generation_pipeline = TestGenerationPipeline(ai_service)
    return test_generation_pipeline