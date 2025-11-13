import os
import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from app.services.ai_service import ai_service

logger = logging.getLogger(__name__)


class TestGenerationPipeline:
    """Пайплайн для генерации тестов на основе анализа проекта"""

    def __init__(self):
        self.supported_frameworks = {
            'python': ['pytest', 'unittest', 'nose'],
            'javascript': ['jest', 'mocha', 'jasmine', 'cypress', 'playwright'],
            'typescript': ['jest', 'mocha', 'jasmine', 'cypress', 'playwright'],
            'java': ['junit', 'testng', 'selenium'],
            'html': ['cypress', 'playwright', 'selenium']
        }

    async def generate_tests(self, generation_data: Dict) -> Dict[str, Any]:
        """Основной метод генерации тестов"""

        project_info = generation_data["project_info"]
        analysis_data = generation_data["analysis_data"]
        test_config = generation_data["test_config"]

        logger.info(f"Starting test generation for project: {project_info['name']}")

        # Анализируем проект с полной структурой
        project_analysis = self.analyze_project_structure(analysis_data)

        # Определяем фреймворк тестирования
        framework = self.determine_test_framework(
            project_analysis["technologies"],
            project_analysis.get("existing_test_frameworks", []),
            test_config.get("framework", "auto")
        )

        # Генерируем тесты с использованием ИИ
        generation_results = await self.generate_test_suite_with_ai(
            project_analysis,
            test_config,
            framework
        )

        # Формируем финальный ответ
        return {
            "status": "success",
            "project_name": project_info['name'],
            "generated_tests": generation_results["total_tests"],
            "tests": generation_results["tests"],
            "coverage_estimate": generation_results["coverage_estimate"],
            "framework_used": framework,
            "files_created": generation_results["files_created"],
            "warnings": generation_results["warnings"],
            "recommendations": generation_results["recommendations"],
            "generation_time": datetime.utcnow().isoformat(),
            "test_config_used": test_config,
            "ai_provider_used": generation_results["ai_provider"],
            "project_context": self.prepare_project_context(project_analysis)
        }

    def _create_test_generation_prompt(self, test_type: str, framework: str, config: Dict, file_info: Dict,
                                       project_context: Dict) -> str:
        """Создание максимально эффективного промпта для генерации тестов"""

        language = self._get_language_from_framework(framework)

        prompt = f"""
# ROLE: Senior Test Automation Engineer
Ты эксперт по написанию качественных тестов. Сгенерируй профессиональные тесты на основе предоставленного кода и контекста проекта.

## ТЕХНИЧЕСКИЕ ТРЕБОВАНИЯ:
- Язык: {language}
- Фреймворк: {framework}
- Тип теста: {test_type}
- Целевое покрытие: {config.get('coverage_target', 80)}%
- Включить комментарии: {config.get('include_comments', True)}

## КОНТЕКСТ ПРОЕКТА:
- Технологии: {', '.join(project_context.get('project_metadata', {}).get('technologies', []))}
- Архитектура: {project_context.get('project_metadata', {}).get('architecture', [])}
- Тип проекта: {project_context.get('project_metadata', {}).get('type', 'unknown')}
- Сложность: {project_context.get('project_metadata', {}).get('complexity', 'unknown')}

## АНАЛИЗИРУЕМЫЙ ФАЙЛ:
- Путь: {file_info.get('path', 'N/A')}
- Тип: {file_info.get('type', 'N/A')}
- Функции: {file_info.get('functions', 0)}
- Классы: {file_info.get('classes', 0)}

## СТРУКТУРА ПРОЕКТА:
{self._format_project_structure(project_context.get('project_structure', {}))}

## СПЕЦИФИЧЕСКИЕ ТРЕБОВАНИЯ ДЛЯ {test_type.upper()} ТЕСТОВ:

{self._get_test_type_specific_instructions(test_type, framework, language)}

## КРИТЕРИИ КАЧЕСТВА ТЕСТОВ:
1. **Полное покрытие** - тестируй все публичные методы и основные сценарии
2. **Читаемость** - понятные имена тестов, структура AAA (Arrange-Act-Assert)
3. **Изоляция** - моки для внешних зависимостей
4. **Edge cases** - граничные значения, ошибки, исключения
5. **Производительность** - быстрые, независимые тесты
6. **Поддержка** - легко изменять и расширять

## ФОРМАТ ОТВЕТА:
Верни ТОЛЬКО код теста без дополнительных объяснений, комментариев вне кода или markdown разметки.

Начинай сразу с импортов/зависимостей.
"""
        return prompt

    def _get_test_type_specific_instructions(self, test_type: str, framework: str, language: str) -> str:
        """Специфичные инструкции для разных типов тестов"""

        instructions = {
            "unit": f"""
### UNIT ТЕСТЫ ({framework.upper()}):
- Тестируй КАЖДУЮ функцию/метод изолированно
- Моки ВСЕХ внешних зависимостей (API, DB, File System)
- Проверяй возвращаемые значения и side effects
- Тестируй успешные сценарии AND ошибки
- Используй параметризованные тесты для разных входных данных
- Включай тесты для граничных значений и исключений

Пример структуры для {language}:
{self._get_unit_test_example(language, framework)}
""",

            "integration": f"""
### ИНТЕГРАЦИОННЫЕ ТЕСТЫ ({framework.upper()}):
- Тестируй взаимодействие между модулями
- Используй реальные базы данных/сервисы ИЛИ реалистичные моки
- Проверяй корректность данных на всех уровнях
- Тестируй сценарии "счастливого пути" AND ошибки
- Включай тесты на производительность при необходимости

Пример структуры для {language}:
{self._get_integration_test_example(language, framework)}
""",

            "e2e": f"""
### E2E ТЕСТЫ ({framework.upper()}):
- Тестируй полные пользовательские сценарии
- Используй стабильные селекторы (data-testid, role, aria-label)
- Добавляй ожидания для асинхронных операций
- Тестируй UI состояния (загрузка, ошибки, успех)
- Включай проверки accessibility при возможности
- Симулируй реальное поведение пользователя

Пример структуры для {language}:
{self._get_e2e_test_example(language, framework)}
"""
        }

        return instructions.get(test_type, "")

    def _get_unit_test_example(self, language: str, framework: str) -> str:
        """Примеры структуры unit тестов"""

        examples = {
            "python": '''
# pytest пример структуры:
import pytest
from unittest.mock import Mock, patch
from mymodule import Calculator

class TestCalculator:
    def test_add_positive_numbers(self):
        # Arrange
        calc = Calculator()

        # Act
        result = calc.add(2, 3)

        # Assert
        assert result == 5

    def test_add_negative_numbers(self):
        # Arrange
        calc = Calculator()

        # Act
        result = calc.add(-2, -3)

        # Assert
        assert result == -5

    @pytest.mark.parametrize("a,b,expected", [
        (0, 0, 0),
        (1, 0, 1),
        (0, 1, 1),
    ])
    def test_add_edge_cases(self, a, b, expected):
        calc = Calculator()
        assert calc.add(a, b) == expected
''',
            "javascript": '''
// Jest пример структуры:
const { Calculator } = require('./calculator');

describe('Calculator', () => {
  let calculator;

  beforeEach(() => {
    calculator = new Calculator();
  });

  test('should add positive numbers correctly', () => {
    // Arrange
    const a = 2, b = 3;

    // Act
    const result = calculator.add(a, b);

    // Assert
    expect(result).toBe(5);
  });

  test('should handle negative numbers', () => {
    expect(calculator.add(-2, -3)).toBe(-5);
  });

  test.each([
    [0, 0, 0],
    [1, 0, 1],
    [0, 1, 1],
  ])('should add edge cases %i + %i = %i', (a, b, expected) => {
    expect(calculator.add(a, b)).toBe(expected);
  });
});
'''
        }
        return examples.get(language, "")

    def _format_project_structure(self, structure: Dict) -> str:
        """Форматирование структуры проекта для промпта"""

        def format_tree(data, indent=0):
            result = ""
            for key, value in data.items():
                result += "  " * indent + f"📁 {key}\n"
                if isinstance(value, dict):
                    result += format_tree(value, indent + 1)
                else:
                    result += "  " * (indent + 1) + f"📄 {value}\n"
            return result

        return format_tree(structure.get('file_structure', {}))

    def _get_language_from_framework(self, framework: str) -> str:
        """Определение языка по фреймворку"""
        lang_map = {
            'pytest': 'python', 'unittest': 'python',
            'jest': 'javascript', 'mocha': 'javascript', 'jasmine': 'javascript',
            'junit': 'java', 'testng': 'java',
            'cypress': 'javascript', 'playwright': 'javascript', 'selenium': 'python'
        }
        return lang_map.get(framework, 'unknown')

    def _prepare_test_request_data(self, file_info: Dict, project_context: Dict, test_type: str, framework: str,
                                   config: Dict) -> str:
        """Улучшенная подготовка данных для AI"""

        # Получаем реальное содержимое файла если доступно
        file_content = self._get_file_content(file_info.get('path', ''))

        request_data = f"""
## КОД ДЛЯ ТЕСТИРОВАНИЯ:
```{self._get_language_from_framework(framework)}
{file_content if file_content else file_info.get('content_preview', 'N/A')}
```

## МЕТАДАННЫЕ ФАЙЛА:
- Путь: {file_info.get('path', 'N/A')}
- Тип файла: {file_info.get('type', 'N/A')}
- Количество функций: {file_info.get('functions', 0)}
- Количество классов: {file_info.get('classes', 0)}
- Импорты: {', '.join(file_info.get('imports', []))}

## АРХИТЕКТУРНЫЕ ИНСАЙТЫ:
{json.dumps(project_context.get('architecture_insights', {}), indent=2, ensure_ascii=False)}

## СУЩЕСТВУЮЩИЕ ТЕСТЫ:
{json.dumps(project_context.get('testing_context', {}).get('existing_tests', {}), indent=2, ensure_ascii=False)}

## РЕКОМЕНДАЦИИ ПО ТЕСТИРОВАНИЮ:
{chr(10).join(project_context.get('generation_guidelines', {}).get('test_style_recommendations', []))}

## ОБЛАСТИ ФОКУСА ТЕСТИРОВАНИЯ:
{chr(10).join(project_context.get('testing_context', {}).get('potential_test_focus_areas', []))}

## ГЕНЕРИРУЙ {test_type.upper()} ТЕСТ ДЛЯ ПРЕДОСТАВЛЕННОГО КОДА
Используй {framework.upper()} и учитывай контекст проекта.
"""
        return request_data

    def _get_file_content(self, file_path: str) -> str:
        """Получение реального содержимого файла"""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception as e:
            logger.warning(f"Could not read file {file_path}: {e}")

        return ""

    def _get_integration_test_example(self, language: str, framework: str) -> str:
        """Примеры интеграционных тестов"""
        examples = {
            "python": '''
# pytest интеграционные тесты:
import pytest
from myapp import create_app
from myapp.database import db

class TestUserIntegration:
    @pytest.fixture
    def app(self):
        app = create_app('testing')
        with app.app_context():
            db.create_all()
            yield app
            db.drop_all()

    def test_user_registration_flow(self, app):
        # Тестируем полный flow регистрации
        with app.test_client() as client:
            response = client.post('/register', json={
                'email': 'test@example.com',
                'password': 'password123'
            })
            assert response.status_code == 201
            assert 'user_id' in response.json
''',
            "javascript": '''
// Jest интеграционные тесты:
const request = require('supertest');
const app = require('../app');
const db = require('../database');

describe('User API Integration', () => {
  beforeAll(async () => {
    await db.connect();
  });

  afterAll(async () => {
    await db.disconnect();
  });

  test('should create user and return token', async () => {
    const response = await request(app)
      .post('/api/users')
      .send({
        email: 'test@example.com',
        password: 'password123'
      });

    expect(response.status).toBe(201);
    expect(response.body).toHaveProperty('token');
    expect(response.body.user.email).toBe('test@example.com');
  });
});
'''
        }
        return examples.get(language, "")

    def _get_e2e_test_example(self, language: str, framework: str) -> str:
        """Примеры E2E тестов"""
        examples = {
            "python": '''
# Selenium E2E тесты:
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class TestUserJourney:
    def setUp(self):
        self.driver = webdriver.Chrome()
        self.wait = WebDriverWait(self.driver, 10)

    def test_complete_user_registration(self):
        driver = self.driver
        driver.get("http://localhost:3000")

        # Шаг 1: Переход на страницу регистрации
        register_link = self.wait.until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Register"))
        )
        register_link.click()

        # Шаг 2: Заполнение формы
        email_input = driver.find_element(By.ID, "email")
        email_input.send_keys("test@example.com")

        password_input = driver.find_element(By.ID, "password")
        password_input.send_keys("password123")

        # Шаг 3: Отправка формы
        submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_btn.click()

        # Шаг 4: Проверка успешной регистрации
        success_message = self.wait.until(
            EC.visibility_of_element_located((By.CLASS_NAME, "alert-success"))
        )
        assert "Registration successful" in success_message.text
''',
            "javascript": '''
// Playwright E2E тесты:
const { test, expect } = require('@playwright/test');

test('complete user registration flow', async ({ page }) => {
  // Шаг 1: Переход на сайт
  await page.goto('http://localhost:3000');

  // Шаг 2: Навигация к регистрации
  await page.click('text=Register');
  await expect(page).toHaveURL(/.*\/register/);

  // Шаг 3: Заполнение формы
  await page.fill('[data-testid="email-input"]', 'test@example.com');
  await page.fill('[data-testid="password-input"]', 'password123');

  // Шаг 4: Отправка формы
  await page.click('[data-testid="submit-button"]');

  // Шаг 5: Проверка успеха
  await expect(page.locator('[data-testid="success-message"]')).toBeVisible();
  await expect(page).toHaveURL(/.*\/dashboard/);
});
'''
        }
        return examples.get(language, "")

    def assess_python_style(self, project_analysis: Dict) -> Dict[str, Any]:
        """Анализ стиля Python кода"""
        style_insights = {
            "probable_style": "unknown",
            "conventions_followed": [],
            "package_structure": "unknown"
        }

        code_files = project_analysis["code_files"]
        file_structure = project_analysis.get("file_structure", {})

        # Анализируем структуру проекта
        if "src" in file_structure:
            style_insights["package_structure"] = "src_layout"
            style_insights["conventions_followed"].append("src-based layout")
        elif any(file_info["path"].startswith("package") for file_info in code_files):
            style_insights["package_structure"] = "flat_layout"
        else:
            style_insights["package_structure"] = "mixed_layout"

        # Анализируем файлы на предмет стиля
        class_files = sum(1 for file_info in code_files if file_info.get("classes", 0) > 0)
        function_files = sum(1 for file_info in code_files if file_info.get("functions", 0) > 0)

        # Определяем вероятный стиль
        if class_files > function_files * 2:
            style_insights["probable_style"] = "OOP_heavy"
            style_insights["conventions_followed"].append("object-oriented programming")
        elif function_files > class_files * 2:
            style_insights["probable_style"] = "procedural"
            style_insights["conventions_followed"].append("procedural programming")
        else:
            style_insights["probable_style"] = "mixed"
            style_insights["conventions_followed"].append("mixed programming paradigm")

        # Проверяем наличие common Python patterns
        if any("test" in file_info["path"] for file_info in code_files):
            style_insights["conventions_followed"].append("test directory structure")

        if any("utils" in file_info["path"] or "helpers" in file_info["path"] for file_info in code_files):
            style_insights["conventions_followed"].append("utility modules")

        if any("__init__.py" in file_info["path"] for file_info in code_files):
            style_insights["conventions_followed"].append("package initialization")

        # Анализируем зависимости для определения фреймворков
        dependencies = project_analysis.get("dependencies", {})
        python_deps = dependencies.get("python", [])

        if any("django" in dep.lower() for dep in python_deps):
            style_insights["probable_style"] = "django_framework"
            style_insights["conventions_followed"].append("Django project structure")
        elif any("flask" in dep.lower() for dep in python_deps):
            style_insights["probable_style"] = "flask_framework"
            style_insights["conventions_followed"].append("Flask application structure")
        elif any("fastapi" in dep.lower() for dep in python_deps):
            style_insights["probable_style"] = "fastapi_framework"
            style_insights["conventions_followed"].append("FastAPI application structure")

        return style_insights

    def assess_javascript_style(self, project_analysis: Dict) -> Dict[str, Any]:
        """Анализ стиля JavaScript/TypeScript кода"""
        style_insights = {
            "probable_style": "unknown",
            "module_system": "unknown",
            "framework": "none",
            "conventions_followed": []
        }

        code_files = project_analysis["code_files"]
        file_structure = project_analysis.get("file_structure", {})
        technologies = [tech.lower() for tech in project_analysis["technologies"]]

        # Определяем TypeScript vs JavaScript
        if "typescript" in technologies:
            style_insights["conventions_followed"].append("TypeScript usage")
            style_insights["probable_style"] = "typescript"
        else:
            style_insights["probable_style"] = "javascript"

        # Анализируем структуру проекта
        if "src" in file_structure and "public" in file_structure:
            style_insights["conventions_followed"].append("standard frontend structure")

        # Определяем модульную систему
        import_patterns = self.analyze_js_import_patterns(code_files)
        if import_patterns["has_es6_imports"]:
            style_insights["module_system"] = "ES6_modules"
            style_insights["conventions_followed"].append("ES6 module syntax")
        elif import_patterns["has_commonjs_requires"]:
            style_insights["module_system"] = "CommonJS"
            style_insights["conventions_followed"].append("CommonJS require syntax")

        # Определяем фреймворк
        dependencies = project_analysis.get("dependencies", {})
        js_deps = dependencies.get("javascript", []) + dependencies.get("npm", [])

        if any("react" in dep.lower() for dep in js_deps):
            style_insights["framework"] = "react"
            style_insights["conventions_followed"].append("React component structure")

            # Проверяем структуру React
            if any("components" in file_info["path"] for file_info in code_files):
                style_insights["conventions_followed"].append("components directory")
            if any("hooks" in file_info["path"] for file_info in code_files):
                style_insights["conventions_followed"].append("React hooks usage")

        elif any("vue" in dep.lower() for dep in js_deps):
            style_insights["framework"] = "vue"
            style_insights["conventions_followed"].append("Vue.js structure")
        elif any("angular" in dep.lower() for dep in js_deps):
            style_insights["framework"] = "angular"
            style_insights["conventions_followed"].append("Angular structure")
        elif any("express" in dep.lower() for dep in js_deps):
            style_insights["framework"] = "express"
            style_insights["conventions_followed"].append("Express.js application structure")
        elif any("next" in dep.lower() for dep in js_deps):
            style_insights["framework"] = "nextjs"
            style_insights["conventions_followed"].append("Next.js application structure")

        # Анализируем стиль компонентов/функций
        component_files = sum(
            1 for file_info in code_files if any(ext in file_info["name"] for ext in [".jsx", ".tsx", ".vue"]))
        regular_js_files = sum(1 for file_info in code_files if
                               file_info["extension"] in [".js", ".ts"] and "component" not in file_info[
                                   "path"].lower())

        if component_files > regular_js_files:
            style_insights["probable_style"] = "component_based"
        elif regular_js_files > component_files:
            style_insights["probable_style"] = "module_based"

        # Проверяем наличие common patterns
        if any("utils" in file_info["path"] or "helpers" in file_info["path"] for file_info in code_files):
            style_insights["conventions_followed"].append("utility modules")

        if any("services" in file_info["path"] or "api" in file_info["path"] for file_info in code_files):
            style_insights["conventions_followed"].append("service layer")

        if any("styles" in file_info["path"] or "css" in file_info["path"] for file_info in code_files):
            style_insights["conventions_followed"].append("styling organization")

        return style_insights

    def analyze_js_import_patterns(self, code_files: List[Dict]) -> Dict[str, bool]:
        """Анализ паттернов импорта в JavaScript/TypeScript"""
        patterns = {
            "has_es6_imports": False,
            "has_commonjs_requires": False,
            "has_dynamic_imports": False
        }

        for file_info in code_files:
            content_preview = file_info.get("content_preview", "").lower()

            if "import" in content_preview and "from" in content_preview:
                patterns["has_es6_imports"] = True

            if "require(" in content_preview:
                patterns["has_commonjs_requires"] = True

            if "import(" in content_preview:
                patterns["has_dynamic_imports"] = True

        return patterns

    def assess_java_style(self, project_analysis: Dict) -> Dict[str, Any]:
        """Анализ стиля Java кода"""
        style_insights = {
            "probable_style": "unknown",
            "build_system": "unknown",
            "framework": "none",
            "conventions_followed": []
        }

        code_files = project_analysis["code_files"]
        file_structure = project_analysis.get("file_structure", {})

        # Определяем систему сборки
        if "pom.xml" in str(file_structure):
            style_insights["build_system"] = "maven"
            style_insights["conventions_followed"].append("Maven project structure")
        elif "build.gradle" in str(file_structure):
            style_insights["build_system"] = "gradle"
            style_insights["conventions_followed"].append("Gradle project structure")

        # Анализируем структуру пакетов
        if "src/main/java" in str(file_structure):
            style_insights["conventions_followed"].append("standard Maven/Gradle source layout")
            style_insights["probable_style"] = "enterprise_java"

        # Определяем фреймворк
        dependencies = project_analysis.get("dependencies", {})
        java_deps = dependencies.get("java", []) + dependencies.get("maven", [])

        if any("spring-boot" in dep.lower() for dep in java_deps):
            style_insights["framework"] = "spring_boot"
            style_insights["conventions_followed"].append("Spring Boot application structure")
        elif any("spring" in dep.lower() for dep in java_deps):
            style_insights["framework"] = "spring_framework"
            style_insights["conventions_followed"].append("Spring Framework structure")

        # Анализируем использование классов
        class_files = sum(1 for file_info in code_files if file_info.get("classes", 0) > 0)
        if class_files > 0:
            style_insights["conventions_followed"].append("object-oriented design")
            style_insights["probable_style"] = "OOP"

        return style_insights

    def prepare_project_context(self, project_analysis: Dict) -> Dict[str, Any]:
        """Подготовка полного контекста проекта для нейросети"""

        # Добавляем детальную информацию о файлах
        detailed_files = []
        for file_info in project_analysis["code_files"][:15]:  # Ограничиваем для размера
            detailed_files.append({
                "path": file_info["path"],
                "name": file_info["name"],
                "type": file_info["type"],
                "extension": file_info["extension"],
                "directory": os.path.dirname(file_info["path"]) or "root",
                "size_estimate": "small" if file_info.get("size", 0) < 1000 else "medium" if file_info.get("size",
                                                                                                           0) < 10000 else "large"
            })

        # Анализируем структуру для понимания архитектуры
        architecture_insights = self.analyze_architecture_insights(project_analysis)

        # Определяем тип проекта
        project_type = self.determine_project_type(project_analysis)

        return {
            "project_metadata": {
                "name": project_analysis.get("project_name", "Unknown"),
                "type": project_type,
                "technologies": project_analysis["technologies"],
                "primary_language": self.get_primary_language(project_analysis["technologies"]),
                "architecture": project_analysis["architecture_patterns"],
                "complexity": project_analysis["complexity_metrics"]["estimated_complexity"]
            },

            "project_structure": {
                "total_files": project_analysis["total_files"],
                "code_files_count": project_analysis["code_files_count"],
                "test_files_count": project_analysis["test_files_count"],
                "file_structure": project_analysis.get("file_structure", {}),
                "key_directories": self.extract_key_directories(project_analysis.get("file_structure", {})),
                "entry_points": self.find_entry_points(project_analysis)
            },

            "code_analysis": {
                "file_samples": detailed_files,
                "dependencies": project_analysis.get("dependencies", {}),
                "import_patterns": self.analyze_import_patterns(project_analysis["code_files"]),
                "function_density": self.calculate_function_density(project_analysis["code_files"]),
                "class_usage": self.analyze_class_usage(project_analysis["code_files"])
            },

            "testing_context": {
                "existing_tests": {
                    "has_tests": project_analysis["has_existing_tests"],
                    "frameworks": project_analysis["existing_test_frameworks"],
                    "directories": project_analysis["test_directories"],
                    "coverage_estimate": project_analysis.get("coverage_estimate", 0)
                },
                "recommended_test_approach": self.get_recommended_test_approach(project_analysis),
                "potential_test_focus_areas": self.identify_test_focus_areas(project_analysis)
            },

            "architecture_insights": architecture_insights,

            "generation_guidelines": {
                "test_style_recommendations": self.get_test_style_recommendations(project_analysis),
                "common_patterns_to_test": self.get_common_patterns_to_test(project_analysis),
                "edge_cases_to_consider": self.get_edge_cases_to_consider(project_analysis),
                "mock_recommendations": self.get_mock_recommendations(project_analysis)
            }
        }

    def analyze_architecture_insights(self, project_analysis: Dict) -> Dict[str, Any]:
        """Глубокий анализ архитектурных инсайтов"""
        insights = {
            "project_scale": "small" if project_analysis["total_files"] < 50 else "medium" if project_analysis[
                                                                                                  "total_files"] < 200 else "large",
            "modularity": self.assess_modularity(project_analysis),
            "testability": self.assess_testability(project_analysis),
            "dependencies_complexity": self.assess_dependencies_complexity(project_analysis)
        }

        # Определяем стиль кода для разных языков
        technologies = [tech.lower() for tech in project_analysis["technologies"]]

        if "python" in technologies:
            insights["coding_style"] = self.assess_python_style(project_analysis)
        elif "javascript" in technologies or "typescript" in technologies:
            insights["coding_style"] = self.assess_javascript_style(project_analysis)
        elif "java" in technologies:
            insights["coding_style"] = self.assess_java_style(project_analysis)
        else:
            insights["coding_style"] = {"probable_style": "general", "conventions_followed": ["unknown"]}

        return insights

    def determine_project_type(self, project_analysis: Dict) -> str:
        """Определение типа проекта"""
        technologies = [tech.lower() for tech in project_analysis["technologies"]]
        file_structure = project_analysis.get("file_structure", {})

        # Веб-приложение
        if any(tech in technologies for tech in ["html", "javascript", "react", "vue", "angular"]):
            if "api" in str(file_structure) or "controllers" in file_structure:
                return "web_application"
            return "frontend_app"

        # API сервис
        if any(keyword in str(file_structure) for keyword in ["api", "routes", "endpoints", "controllers"]):
            return "api_service"

        # Библиотека
        if "src" in file_structure and "setup.py" in str(file_structure):
            return "library"

        # Микросервис
        if any(keyword in str(file_structure) for keyword in ["docker", "k8s", "microservice"]):
            return "microservice"

        # Скриптовый проект
        if project_analysis["total_files"] < 20:
            return "script_project"

        return "general_application"

    def get_primary_language(self, technologies: List[str]) -> str:
        """Определение основного языка программирования"""
        priority_order = ["python", "javascript", "typescript", "java", "go", "rust", "csharp", "php"]
        for lang in priority_order:
            if lang in [tech.lower() for tech in technologies]:
                return lang
        return technologies[0].lower() if technologies else "unknown"

    def extract_key_directories(self, file_structure: Dict) -> List[str]:
        """Извлечение ключевых директорий"""
        key_dirs = []
        important_dirs = ["src", "app", "lib", "components", "models", "controllers", "services", "utils", "tests"]

        def find_dirs(structure: Dict, path: str = ""):
            for key, value in structure.items():
                current_path = f"{path}/{key}" if path else key
                if key in important_dirs and isinstance(value, dict):
                    key_dirs.append(current_path)
                if isinstance(value, dict):
                    find_dirs(value, current_path)

        find_dirs(file_structure)
        return key_dirs

    def find_entry_points(self, project_analysis: Dict) -> List[str]:
        """Поиск точек входа"""
        entry_files = ["main.py", "app.py", "index.js", "server.js", "app.js", "main.java", "application.py"]
        entry_points = []

        def search_files(structure: Dict, path: str = ""):
            for key, value in structure.items():
                current_path = f"{path}/{key}" if path else key
                if key in entry_files:
                    entry_points.append(current_path)
                if isinstance(value, dict):
                    search_files(value, current_path)

        search_files(project_analysis.get("file_structure", {}))
        return entry_points

    def analyze_import_patterns(self, code_files: List[Dict]) -> Dict[str, Any]:
        """Анализ паттернов импорта"""
        imports = {}
        for file_info in code_files:
            for imp in file_info.get("imports", []):
                imports[imp] = imports.get(imp, 0) + 1

        return {
            "most_common_imports": sorted(imports.items(), key=lambda x: x[1], reverse=True)[:10],
            "total_unique_imports": len(imports)
        }

    def calculate_function_density(self, code_files: List[Dict]) -> float:
        """Расчет плотности функций"""
        total_functions = sum(file_info.get("functions", 0) for file_info in code_files)
        total_files = len(code_files)
        return round(total_functions / max(1, total_files), 2)

    def analyze_class_usage(self, code_files: List[Dict]) -> Dict[str, Any]:
        """Анализ использования классов"""
        total_classes = sum(file_info.get("classes", 0) for file_info in code_files)
        files_with_classes = sum(1 for file_info in code_files if file_info.get("classes", 0) > 0)

        return {
            "total_classes": total_classes,
            "files_with_classes": files_with_classes,
            "class_usage_ratio": round(files_with_classes / max(1, len(code_files)), 2)
        }

    def get_recommended_test_approach(self, project_analysis: Dict) -> Dict[str, Any]:
        """Рекомендации по подходу к тестированию"""
        approach = {
            "unit_testing": "highly_recommended",
            "integration_testing": "recommended",
            "e2e_testing": "conditional"
        }

        # Настройка рекомендаций на основе типа проекта
        project_type = self.determine_project_type(project_analysis)

        if project_type == "web_application":
            approach["e2e_testing"] = "recommended"
        elif project_type == "api_service":
            approach["integration_testing"] = "highly_recommended"
        elif project_type == "library":
            approach["unit_testing"] = "critical"

        return approach

    def identify_test_focus_areas(self, project_analysis: Dict) -> List[str]:
        """Идентификация областей для фокуса тестирования"""
        focus_areas = []

        if any("api" in file_info["path"] for file_info in project_analysis["code_files"]):
            focus_areas.append("API endpoints")

        if any("model" in file_info["path"].lower() for file_info in project_analysis["code_files"]):
            focus_areas.append("Data models")

        if any("service" in file_info["path"].lower() for file_info in project_analysis["code_files"]):
            focus_areas.append("Business logic services")

        if any("util" in file_info["path"].lower() for file_info in project_analysis["code_files"]):
            focus_areas.append("Utility functions")

        return focus_areas

    # Дополнительные методы для анализа
    def assess_modularity(self, project_analysis: Dict) -> str:
        """Оценка модульности проекта"""
        total_files = project_analysis["total_files"]
        if total_files < 30:
            return "monolithic"
        elif total_files < 100:
            return "modular"
        else:
            return "highly_modular"

    def assess_testability(self, project_analysis: Dict) -> str:
        """Оценка тестируемости проекта"""
        if project_analysis["has_existing_tests"]:
            return "good"

        complexity = project_analysis["complexity_metrics"]["estimated_complexity"]
        if complexity == "low":
            return "excellent"
        elif complexity == "medium":
            return "good"
        else:
            return "moderate"

    def assess_dependencies_complexity(self, project_analysis: Dict) -> str:
        """Оценка сложности зависимостей"""
        deps = project_analysis.get("dependencies", {})
        total_deps = sum(len(deps_list) for deps_list in deps.values())

        if total_deps == 0:
            return "none"
        elif total_deps < 10:
            return "low"
        elif total_deps < 30:
            return "medium"
        else:
            return "high"

    def get_test_style_recommendations(self, project_analysis: Dict) -> List[str]:
        """Рекомендации по стилю тестов"""
        recommendations = []

        if "python" in project_analysis["technologies"]:
            recommendations.extend([
                "Use pytest fixtures for setup",
                "Follow Arrange-Act-Assert pattern",
                "Use descriptive test names"
            ])

        if "javascript" in project_analysis["technologies"]:
            recommendations.extend([
                "Use describe/it blocks",
                "Mock external dependencies",
                "Test both success and error cases"
            ])

        return recommendations

    def get_common_patterns_to_test(self, project_analysis: Dict) -> List[str]:
        """Общие паттерны для тестирования"""
        patterns = [
            "Input validation",
            "Error handling",
            "Boundary conditions",
            "Default values",
            "State changes"
        ]

        if any("api" in file_info["path"] for file_info in project_analysis["code_files"]):
            patterns.extend(["HTTP status codes", "Response formats", "Authentication"])

        return patterns

    def get_edge_cases_to_consider(self, project_analysis: Dict) -> List[str]:
        """Edge cases для рассмотрения"""
        return [
            "Empty inputs",
            "Null/None values",
            "Extreme values",
            "Concurrent access",
            "Network failures"
        ]

    def get_mock_recommendations(self, project_analysis: Dict) -> List[str]:
        """Рекомендации по мокам"""
        recommendations = []

        if any("api" in file_info["path"] for file_info in project_analysis["code_files"]):
            recommendations.append("Mock external API calls")

        if any("database" in file_info["path"].lower() for file_info in project_analysis["code_files"]):
            recommendations.append("Mock database operations")

        if any("file" in file_info["path"].lower() for file_info in project_analysis["code_files"]):
            recommendations.append("Mock file system operations")

        return recommendations

    def analyze_existing_tests(self, test_analysis: Dict) -> Dict[str, Any]:
        """Анализ существующих тестов из данных анализа"""
        return {
            "has_tests": test_analysis.get("has_tests", False),
            "test_frameworks": test_analysis.get("test_frameworks", []),
            "test_files_count": test_analysis.get("test_files_count", 0),
            "test_directories": test_analysis.get("test_directories", []),
            "coverage": test_analysis.get("coverage", 0)
        }

    def analyze_project_structure(self, analysis_data: Dict) -> Dict[str, Any]:
        """Анализ структуры проекта для генерации тестов"""

        technologies = analysis_data.get("technologies", [])
        file_structure = analysis_data.get("file_structure", {})
        test_analysis = analysis_data.get("test_analysis", {})
        file_summary = analysis_data.get("file_structure_summary", {})

        # Извлекаем файлы кода
        code_files = self.extract_code_files(file_structure, technologies)

        # Анализируем зависимости
        dependencies = analysis_data.get("dependencies", {})

        # Анализируем существующие тесты
        existing_tests = self.analyze_existing_tests(test_analysis)

        return {
            "technologies": technologies,
            "file_structure": file_structure,
            "code_files": code_files,
            "total_files": file_summary.get("total_files", 0),
            "code_files_count": file_summary.get("code_files", 0),
            "test_files_count": file_summary.get("test_files", 0),
            "dependencies": dependencies,
            "existing_test_frameworks": test_analysis.get("test_frameworks", []),
            "has_existing_tests": test_analysis.get("has_tests", False),
            "test_directories": test_analysis.get("test_directories", []),
            "architecture_patterns": self.detect_architecture_patterns(file_structure, technologies),
            "complexity_metrics": self.calculate_complexity_metrics(code_files, technologies)
        }

    def extract_code_files(self, file_structure: Dict, technologies: List[str]) -> List[Dict]:
        """Извлечение файлов с кодом и их метаданных"""
        code_files = []
        code_extensions = self.get_code_extensions(technologies)

        def traverse_structure(structure: Dict, current_path: str = ""):
            for key, value in structure.items():
                item_path = f"{current_path}/{key}" if current_path else key

                if isinstance(value, dict):
                    # Это директория
                    traverse_structure(value, item_path)
                else:
                    # Это файл
                    if any(item_path.endswith(ext) for ext in code_extensions):
                        code_files.append({
                            "path": item_path,
                            "name": key,
                            "extension": os.path.splitext(key)[1],
                            "type": self.classify_file_type(key, technologies)
                        })

        traverse_structure(file_structure)
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
            if tech.lower() in tech_extensions:
                extensions.extend(tech_extensions[tech.lower()])

        return list(set(extensions))

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

        # Простой анализ структуры директорий
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

    def calculate_complexity_metrics(self, code_files: List[Dict], technologies: List[str]) -> Dict[str, Any]:
        """Расчет метрик сложности проекта"""
        total_files = len(code_files)

        # Простые метрики (в реальности можно добавить более сложный анализ)
        file_types = {}
        for file in code_files:
            file_type = file["type"]
            file_types[file_type] = file_types.get(file_type, 0) + 1

        return {
            "total_files": total_files,
            "file_type_distribution": file_types,
            "estimated_complexity": "low" if total_files < 50 else "medium" if total_files < 200 else "high"
        }

    def determine_test_framework(self, technologies: List[str], existing_frameworks: List[str],
                                 user_choice: str) -> str:
        """Определение фреймворка тестирования"""

        if user_choice != "auto":
            return user_choice

        # Используем существующие фреймворки если есть
        if existing_frameworks:
            return existing_frameworks[0]

        # Определяем по технологиям
        primary_tech = technologies[0].lower() if technologies else "python"

        framework_map = {
            "python": "pytest",
            "javascript": "jest",
            "typescript": "jest",
            "java": "junit",
            "html": "cypress"
        }

        return framework_map.get(primary_tech, "pytest")

    async def generate_test_suite_with_ai(self, project_analysis: Dict, test_config: Dict, framework: str) -> Dict[
        str, Any]:
        """Генерация полного набора тестов с использованием ИИ"""

        tests = []
        warnings = []
        recommendations = []
        ai_provider = "unknown"

        # Генерация unit тестов с ИИ
        if test_config.get("generate_unit_tests", True):
            unit_tests, provider = await self.generate_unit_tests_with_ai(project_analysis, framework, test_config)
            tests.extend(unit_tests)
            ai_provider = provider

        # Генерация интеграционных тестов с ИИ
        if test_config.get("generate_integration_tests", True):
            integration_tests, provider = await self.generate_integration_tests_with_ai(project_analysis, framework,
                                                                                        test_config)
            tests.extend(integration_tests)
            ai_provider = provider or ai_provider

        # Генерация E2E тестов с ИИ
        if test_config.get("generate_e2e_tests", False) and self.has_web_components(project_analysis):
            e2e_tests, provider = await self.generate_e2e_tests_with_ai(project_analysis, framework, test_config)
            tests.extend(e2e_tests)
            ai_provider = provider or ai_provider
        elif test_config.get("generate_e2e_tests", False):
            warnings.append("E2E tests requested but no web components detected in project")

        # Расчет покрытия
        coverage_estimate = self.calculate_coverage_estimate(
            len(tests),
            project_analysis["test_files_count"],
            project_analysis["code_files_count"]
        )

        # Проверка целевого покрытия
        target_coverage = test_config.get("coverage_target", 80)
        if coverage_estimate < target_coverage:
            recommendations.append(
                f"Для достижения целевого покрытия {target_coverage}% рекомендуется "
                f"добавить дополнительные тесты или увеличить глубину тестирования"
            )

        return {
            "total_tests": len(tests),
            "tests": tests,
            "coverage_estimate": coverage_estimate,
            "files_created": [test["file"] for test in tests],
            "warnings": warnings,
            "recommendations": recommendations,
            "ai_provider": ai_provider
        }

    async def generate_unit_tests_with_ai(self, project_analysis: Dict, framework: str, config: Dict) -> tuple[
        List[Dict], str]:
        """Генерация unit тестов с использованием ИИ"""
        tests = []
        code_files = project_analysis["code_files"]
        ai_provider = "unknown"

        # Ограничиваем количество для демо
        files_to_test = code_files[:config.get("max_unit_tests", 5)]

        for file_info in files_to_test:
            # Подготавливаем улучшенный промпт
            prompt = self._create_test_generation_prompt(
                "unit", framework, config, file_info,
                self.prepare_project_context(project_analysis)
            )

            # Подготавливаем данные для запроса
            request_data = self._prepare_test_request_data(
                file_info,
                self.prepare_project_context(project_analysis),
                "unit",
                framework,
                config
            )

            test_content = await ai_service.generate_test_content(
                file_info=file_info,
                project_context=self.prepare_project_context(project_analysis),
                test_type="unit",
                framework=framework,
                config=config
            )

            if test_content:
                tests.append({
                    "name": f"test_{file_info['name'].replace('.', '_')}",
                    "file": self.generate_test_filename(file_info, "unit", framework),
                    "type": "unit",
                    "framework": framework,
                    "content": test_content,
                    "target_file": file_info["path"],
                    "priority": "high" if file_info["type"] in ["python_module", "java_class"] else "medium"
                })
                ai_provider = "ai_generated"
            else:
                # Fallback на шаблонные тесты если ИИ не сработал
                fallback_test = await self.create_fallback_unit_test(file_info, framework, config, project_analysis)
                tests.append(fallback_test)
                ai_provider = "fallback"

        return tests, ai_provider

    async def generate_integration_tests_with_ai(self, project_analysis: Dict, framework: str, config: Dict) -> tuple[
        List[Dict], str]:
        """Генерация интеграционных тестов с использованием ИИ"""
        tests = []
        ai_provider = "unknown"

        integration_modules = self.identify_integration_modules(project_analysis)

        for module in integration_modules[:config.get("max_integration_tests", 3)]:
            # Создаем mock file_info для интеграционных тестов
            mock_file_info = {
                "path": f"integration/{module}",
                "name": module,
                "type": "integration_module",
                "functions": 0,
                "classes": 0,
                "imports": [],
                "content_preview": f"Integration module: {module}"
            }

            test_content = await ai_service.generate_test_content(
                file_info=mock_file_info,
                project_context=self.prepare_project_context(project_analysis),
                test_type="integration",
                framework=framework,
                config=config
            )

            if test_content:
                tests.append({
                    "name": f"test_integration_{module}",
                    "file": f"test_integration_{module}.{self.get_file_extension(framework)}",
                    "type": "integration",
                    "framework": framework,
                    "content": test_content,
                    "priority": "medium"
                })
                ai_provider = "ai_generated"

        return tests, ai_provider

    async def generate_e2e_tests_with_ai(self, project_analysis: Dict, framework: str, config: Dict) -> tuple[
        List[Dict], str]:
        """Генерация E2E тестов с использованием ИИ"""
        tests = []
        ai_provider = "unknown"

        e2e_scenarios = self.identify_e2e_scenarios(project_analysis)

        for scenario in e2e_scenarios[:config.get("max_e2e_tests", 2)]:
            # Создаем mock file_info для E2E тестов
            mock_file_info = {
                "path": f"e2e/{scenario}",
                "name": scenario,
                "type": "e2e_scenario",
                "functions": 0,
                "classes": 0,
                "imports": [],
                "content_preview": f"E2E scenario: {scenario}"
            }

            test_content = await ai_service.generate_test_content(
                file_info=mock_file_info,
                project_context=self.prepare_project_context(project_analysis),
                test_type="e2e",
                framework=framework,
                config=config
            )

            if test_content:
                tests.append({
                    "name": f"test_e2e_{scenario}",
                    "file": f"test_e2e_{scenario}.{self.get_file_extension(framework)}",
                    "type": "e2e",
                    "framework": framework,
                    "content": test_content,
                    "priority": "low"
                })
                ai_provider = "ai_generated"

        return tests, ai_provider

    async def create_fallback_unit_test(self, file_info: Dict, framework: str, config: Dict,
                                        project_analysis: Dict) -> Dict:
        """Создание fallback теста если ИИ не сработал"""
        fallback_content = f"""
# Fallback unit test for {file_info['path']}
# Generated automatically (AI service unavailable)

import pytest

class Test{file_info['name'].replace('.', '').title()}:
    \"\"\"Auto-generated test suite for {file_info['name']}\"\"\"

    def test_basic_functionality(self):
        \"\"\"Basic functionality test\"\"\"
        assert True

    def test_edge_cases(self):
        \"\"\"Edge cases test\"\"\"
        assert 1 == 1
"""

        return {
            "name": f"test_{file_info['name'].replace('.', '_')}",
            "file": self.generate_test_filename(file_info, "unit", framework),
            "type": "unit",
            "framework": framework,
            "content": fallback_content,
            "target_file": file_info["path"],
            "priority": "medium"
        }

    def identify_integration_modules(self, project_analysis: Dict) -> List[str]:
        """Идентификация модулей для интеграционного тестирования"""
        modules = []

        # Простая эвристика для демо
        for file_info in project_analysis["code_files"]:
            if any(keyword in file_info["path"].lower() for keyword in ["api", "service", "controller", "model"]):
                modules.append(file_info["name"])

        return modules[:10]  # Ограничиваем

    def identify_e2e_scenarios(self, project_analysis: Dict) -> List[str]:
        """Идентификация сценариев для E2E тестирования"""
        scenarios = ["user_authentication", "main_workflow", "data_processing"]

        # Добавляем специфичные сценарии на основе технологий
        if "react" in project_analysis["technologies"]:
            scenarios.append("component_rendering")
        if "api" in str(project_analysis["code_files"]):
            scenarios.append("api_endpoints")

        return scenarios

    def has_web_components(self, project_analysis: Dict) -> bool:
        """Проверка наличия веб-компонентов"""
        technologies = [tech.lower() for tech in project_analysis["technologies"]]
        web_techs = ["html", "javascript", "typescript", "react", "vue", "angular"]

        return any(tech in web_techs for tech in technologies)

    def calculate_coverage_estimate(self, generated_tests: int, existing_tests: int, total_code_files: int) -> float:
        """Оценка покрытия тестами"""
        if total_code_files == 0:
            return 0.0

        # Простая эвристика для оценки покрытия
        total_tests = generated_tests + existing_tests
        base_coverage = min(95.0, (total_tests / max(1, total_code_files)) * 100)
        return round(base_coverage, 1)

    def generate_test_filename(self, file_info: Dict, test_type: str, framework: str) -> str:
        """Генерация имени тестового файла"""
        base_name = file_info["name"].replace(file_info["extension"], "")
        return f"test_{test_type}_{base_name}.{self.get_file_extension(framework)}"

    def get_file_extension(self, framework: str) -> str:
        """Получение расширения файла для тестов"""
        extensions = {
            "pytest": "py",
            "unittest": "py",
            "jest": "js",
            "mocha": "js",
            "jasmine": "js",
            "junit": "java",
            "testng": "java",
            "cypress": "js",
            "playwright": "js",
            "selenium": "py"
        }
        return extensions.get(framework, "txt")


test_generation_pipeline = TestGenerationPipeline()
