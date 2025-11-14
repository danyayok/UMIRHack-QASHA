import os
import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple
import logging

logger = logging.getLogger("qa_automata")


class CodeAnalyzer:
    def __init__(self):
        self.supported_techs = {
            'python': ['.py'],
            'javascript': ['.js', '.jsx', '.ts', '.tsx', '.vue'],
            'java': ['.java'],
            'go': ['.go'],
            'rust': ['.rs'],
            'cpp': ['.cpp', '.c', '.h', '.hpp'],
            'csharp': ['.cs'],
            'php': ['.php'],
            'ruby': ['.rb'],
            'swift': ['.swift'],
            'kotlin': ['.kt', '.kts'],
            'html': ['.html', '.htm'],
            'css': ['.css', '.scss', '.sass', '.less'],
        }

        # Расширенный список игнорируемых директорий
        self.ignored_directories: Set[str] = {
            # Dependency directories (полные пути)
            '**/node_modules/**', '**/vendor/**', '**/bower_components/**',
            '**/jspm_packages/**', '**/elm-stuff/**', '**/deps/**',
            '**/_build/**', '**/build/**', '**/dist/**', '**/out/**',
            '**/target/**', '**/bin/**', '**/obj/**', '**/.next/**',
            '**/.nuxt/**', '**/.output/**', '**/.svelte-kit/**',
            '**/.pnp/**', '**/.yarn/**', '**/.npm/**',

            # Python specific
            '**/__pycache__/**', '**/.mypy_cache/**', '**/.pytest_cache/**',
            '**/.ruff_cache/**', '**/*.egg-info/**',

            # System and IDE
            '**/.git/**', '**/.svn/**', '**/.hg/**', '**/.vscode/**',
            '**/.idea/**', '**/.vs/**',

            # Cache and temp
            '**/.cache/**', '**/.tmp/**', '**/temp/**', '**/tmp/**',
            '**/.turbo/**', '**/.nyc_output/**', '**/.parcel-cache/**',

            # Environment
            '**/.env/**', '**/.venv/**', '**/env/**', '**/venv/**',
            '**/ENV/**', '**/virtualenv/**',

            # Logs and coverage
            '**/logs/**', '**/log/**', '**/coverage/**', '**/htmlcov/**',
            '**/.coverage/**',

            # Documentation
            '**/docs/**', '**/documentation/**', '**/apidoc/**',

            # Mobile specific
            '**/Pods/**', '**/DerivedData/**', '**/.gradle/**',
        }

        # Расширения файлов для игнорирования
        self.ignored_extensions: Set[str] = {
            '.log', '.tmp', '.temp', '.cache', '.pid', '.seed',
            '.lock', '.swp', '.swo', '.DS_Store', '.min.js', '.min.css',
            '.map', '.snap', '.tar.gz', '.zip', '.rar', '.7z',
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.ico',
            '.mp3', '.mp4', '.avi', '.mov', '.wmv',
            '.pyc', '.pyo', '.pyd', '.so', '.dll', '.exe',
            '.class', '.jar', '.war',
        }

        # Файлы блокировок зависимостей
        self.dependency_lock_files: Set[str] = {
            'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',
            'composer.lock', 'Gemfile.lock', 'Cargo.lock',
            'Pipfile.lock', 'poetry.lock', 'go.sum',
            'npm-shrinkwrap.json', 'shrinkwrap.yaml',
        }

        # Более строгие индикаторы фреймворков
        self.framework_indicators = {
            'python': {
                'django': {
                    'imports': ['from django', 'import django'],
                    'patterns': [r'from django\.', r'import django\.'],
                    'files': ['manage.py', 'wsgi.py', 'asgi.py'],
                    'configs': ['DJANGO', 'django.contrib'],
                    'min_matches': 3  # Минимум 3 различных индикатора
                },
                'flask': {
                    'imports': ['from flask', 'import flask'],
                    'patterns': [r'from flask\.', r'import flask\.', r'@app\.route'],
                    'files': ['app.py', 'application.py'],
                    'configs': ['FLASK', 'Flask'],
                    'min_matches': 2
                },
                'fastapi': {
                    'imports': ['from fastapi', 'import fastapi'],
                    'patterns': [r'from fastapi\.', r'import fastapi\.', r'@app\.'],
                    'files': ['main.py'],
                    'configs': ['FastAPI'],
                    'min_matches': 2
                },
                'pandas': {
                    'imports': ['import pandas', 'from pandas'],
                    'patterns': [r'pd\.', r'pandas\.'],
                    'min_matches': 2
                },
                'numpy': {
                    'imports': ['import numpy', 'from numpy'],
                    'patterns': [r'np\.', r'numpy\.'],
                    'min_matches': 2
                }
            },
            'javascript': {
                'react': {
                    'imports': ['import React', 'from react'],
                    'patterns': [r'import.*from.*react', r'React\.'],
                    'files': ['package.json'],
                    'package_json': {'dependencies': ['react'], 'devDependencies': ['react']},
                    'min_matches': 2
                },
                'vue': {
                    'imports': ['import Vue', 'from vue'],
                    'patterns': [r'import.*from.*vue', r'Vue\.'],
                    'files': ['package.json'],
                    'package_json': {'dependencies': ['vue'], 'devDependencies': ['vue']},
                    'min_matches': 2
                },
                'angular': {
                    'imports': ['@angular'],
                    'patterns': [r'@angular/'],
                    'files': ['package.json'],
                    'package_json': {'dependencies': ['@angular/core']},
                    'min_matches': 2
                },
                'express': {
                    'imports': ["require('express')", 'import express'],
                    'patterns': [r'app\.get', r'app\.post', r'app\.use'],
                    'files': ['package.json', 'app.js', 'server.js'],
                    'package_json': {'dependencies': ['express']},
                    'min_matches': 2
                },
                'node.js': {
                    'patterns': [r'module\.exports', r'require\(', r'__dirname', r'__filename'],
                    'files': ['package.json'],
                    'min_matches': 3
                }
            }
        }

    async def analyze_repository(self, repo_path: str) -> Dict[str, Any]:
        """Анализирует структуру репозитория и определяет технологии"""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._analyze_sync, repo_path)
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            raise

    def _analyze_sync(self, repo_path: str) -> Dict[str, Any]:
        """Синхронный анализ репозитория с агрессивным игнорированием зависимостей"""
        analysis_result = {
            'technologies': [],
            'frameworks': [],
            'file_structure': {},  # Полная структура файлов
            'file_structure_summary': {},  # Сводка по файлам
            'test_analysis': {
                'has_tests': False,
                'test_frameworks': [],
                'test_files_count': 0,
                'test_directories': [],
            },
            'dependencies': {},
            'metrics': {
                'total_files': 0,
                'code_files': 0,
                'test_files': 0,
                'total_lines': 0,
                'total_size_kb': 0,
                'ignored_files': 0,
                'ignored_directories': set(),
                'dependency_files_count': 0,
            },
            'project_structure': {
                'has_requirements': False,
                'has_package_json': False,
                'has_pom_xml': False,
                'has_dockerfile': False,
                'has_readme': False,
                'has_gitignore': False,
                'has_docker_compose': False,
            },
            'complexity_metrics': {
                'avg_file_size': 0,
                'largest_file': {'path': '', 'size': 0},
                'file_extensions': {},
            },
            'coverage_estimate': 0,
            'source': 'github',
            'branch': 'main',
            'analysis_timestamp': datetime.utcnow().isoformat()
        }
        repo_path_obj = Path(repo_path)
        if not repo_path_obj.exists():
            logger.error(f"[DEBUG] Repository path does not exist: {repo_path}")
            return analysis_result

        try:
            contents = list(repo_path_obj.iterdir())
            logger.info(f"[DEBUG] Directory contents: {[str(c.name) for c in contents]}")
        except Exception as e:
            logger.error(f"[DEBUG] Error reading directory: {e}")

        all_files = list(repo_path_obj.rglob('*'))
        logger.info(f"[DEBUG] Total files found by rglob: {len(all_files)}")

        for i, file_path in enumerate(all_files[:10]):
            logger.info(f"[DEBUG] File {i}: {file_path} (is_file: {file_path.is_file()})")
        total_size = 0
        dependency_files_count = 0

        all_files = list(repo_path_obj.rglob('*'))

        file_count = sum(1 for f in all_files if f.is_file())
        logger.info(f"Total files found: {file_count}")
        # ВАЖНО: Сохраняем плоскую структуру файлов для пайплайна
        flat_file_structure = {}

        for file_path in all_files:
            if file_path.is_file():
                # АГРЕССИВНАЯ проверка на игнорирование
                should_ignore, ignore_reason = self._should_ignore_file_aggressive(file_path, repo_path_obj)

                if should_ignore:
                    analysis_result['metrics']['ignored_files'] += 1

                    if 'dependency' in ignore_reason or 'node_modules' in ignore_reason:
                        dependency_files_count += 1
                        # Полностью пропускаем файлы из node_modules и других зависимостей
                        continue

                    # Логируем только первые несколько игнорированных файлов для отладки
                    if analysis_result['metrics']['ignored_files'] <= 5:
                        logger.debug(f"Ignored {ignore_reason}: {file_path}")
                    continue

                # Если файл прошел фильтрацию, анализируем его
                analysis_result['metrics']['total_files'] += 1
                file_size = file_path.stat().st_size
                total_size += file_size

                # Обновляем самый большой файл
                if file_size > analysis_result['complexity_metrics']['largest_file']['size']:
                    analysis_result['complexity_metrics']['largest_file'] = {
                        'path': str(file_path.relative_to(repo_path)),
                        'size': file_size
                    }

                # Определяем технологию и расширение
                tech, file_extension = self._detect_technology_and_extension(file_path)

                # Считаем расширения файлов
                if file_extension:
                    analysis_result['complexity_metrics']['file_extensions'][file_extension] = \
                        analysis_result['complexity_metrics']['file_extensions'].get(file_extension, 0) + 1

                if tech and tech not in analysis_result['technologies']:
                    analysis_result['technologies'].append(tech)

                # УМНАЯ проверка на тестовый файл
                is_test_file, test_framework = self._analyze_test_file(file_path)
                if is_test_file:
                    analysis_result['metrics']['test_files'] += 1
                    analysis_result['test_analysis']['has_tests'] = True
                    analysis_result['test_analysis']['test_files_count'] += 1

                    if test_framework and test_framework not in analysis_result['test_analysis']['test_frameworks']:
                        analysis_result['test_analysis']['test_frameworks'].append(test_framework)

                # Анализируем фреймворки (только для файлов кода)
                if tech and not is_test_file:
                    analysis_result['metrics']['code_files'] += 1

                    # Считаем строки кода
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = f.readlines()
                            analysis_result['metrics']['total_lines'] += len(lines)
                    except:
                        pass

                # Проверяем специальные файлы
                self._check_special_files(file_path, analysis_result)

                relative_path = str(file_path.relative_to(repo_path))
                file_info = {
                    'path': relative_path,
                    'technology': tech,
                    'extension': file_extension,
                    'is_test': is_test_file,
                    'size': file_size,
                    'lines': self._count_file_lines(file_path)
                }

                # ВАЖНО: Сохраняем в file_structure (плоский формат для пайплайна)
                analysis_result['file_structure'][relative_path] = file_info
                flat_file_structure[relative_path] = file_info

        # Создаем summary из собранных данных
        analysis_result['file_structure_summary'] = {
            'total_files': analysis_result['metrics']['total_files'],
            'code_files': analysis_result['metrics']['code_files'],
            'test_files': analysis_result['metrics']['test_files'],
            'total_lines': analysis_result['metrics']['total_lines'],
            'total_size_kb': round(total_size / 1024, 2)
        }

        # Анализ зависимостей и фреймворков ПОСЛЕ сбора всех файлов
        self._analyze_dependencies(repo_path_obj, analysis_result)

        # Анализ фреймворков на основе ВСЕГО проекта
        self._analyze_frameworks_project_wide(repo_path_obj, analysis_result)

        # УМНЫЙ анализ тестовых директорий
        self._analyze_test_directories(repo_path_obj, analysis_result)

        self.detect_api_endpoints(repo_path_obj, analysis_result)
        # Финальные вычисления
        analysis_result['metrics']['dependency_files_count'] = dependency_files_count
        analysis_result['metrics']['ignored_directories'] = list(analysis_result['metrics']['ignored_directories'])

        if analysis_result['metrics']['code_files'] > 0:
            analysis_result['complexity_metrics']['avg_file_size'] = total_size / analysis_result['metrics'][
                'code_files']

        # Рассчитываем оценку покрытия
        analysis_result['coverage_estimate'] = self._calculate_coverage_estimate(analysis_result)

        # Логируем итоговую статистику
        logger.info(f"FINAL ANALYSIS: {analysis_result['metrics']['total_files']} project files, "
                    f"{analysis_result['metrics']['ignored_files']} ignored files "
                    f"({dependency_files_count} from dependencies)")

        # Логируем структуру файлов
        logger.info(f"FILE STRUCTURE: Contains {len(analysis_result['file_structure'])} files")
        logger.info(f"FILE SUMMARY: {analysis_result['file_structure_summary']}")

        # Логируем первые несколько файлов для отладки
        file_keys = list(analysis_result['file_structure'].keys())[:5]
        logger.info(f"SAMPLE FILES: {file_keys}")
        logger.info(f"ANALYSIS_RESULT_KEYS: {analysis_result.keys()}")
        logger.info(f"ANALYSIS_TECHNOLOGIES: {analysis_result['technologies']}")
        logger.info(f"ANALYSIS_METRICS: {analysis_result['metrics']}")
        return analysis_result

    def detect_api_endpoints(self, repo_path: Path, analysis_result: Dict[str, Any]):
        """Обнаруживает API endpoints в проекте"""
        api_endpoints = []

        logger.info(f"🔍 API_ENDPOINT_SEARCH: Starting endpoint detection in {repo_path}")

        # Анализируем ВСЕ Python файлы, а не только из file_structure
        python_files = list(repo_path.rglob("*.py"))
        logger.info(f"🔍 API_ENDPOINT_SEARCH: Found {len(python_files)} Python files to analyze")

        for python_file in python_files:
            # Пропускаем тестовые файлы и файлы из зависимостей
            file_path_str = str(python_file.relative_to(repo_path))

            if any(pattern in file_path_str for pattern in ['test_', '_test.py', '/test', '/tests']):
                continue

            if any(dep in file_path_str for dep in ['node_modules', '__pycache__', '.venv']):
                continue

            logger.info(f"🔍 API_ENDPOINT_SEARCH: Analyzing {file_path_str}")
            endpoints = self._analyze_file_for_api_endpoints(python_file, repo_path)
            if endpoints:
                api_endpoints.extend(endpoints)
                logger.info(f"✅ API_ENDPOINT_FOUND: {len(endpoints)} endpoints in {file_path_str}")

        # Группируем endpoints по файлам
        endpoints_by_file = {}
        for endpoint in api_endpoints:
            file_path = endpoint['file']
            if file_path not in endpoints_by_file:
                endpoints_by_file[file_path] = []
            endpoints_by_file[file_path].append(endpoint)

        analysis_result['api_endpoints'] = api_endpoints
        analysis_result['api_endpoints_by_file'] = endpoints_by_file

        logger.info(
            f"📊 API_ENDPOINT_SUMMARY: Found {len(api_endpoints)} total endpoints in {len(endpoints_by_file)} files")

    def _analyze_file_for_api_endpoints(self, file_path: Path, repo_root: Path) -> List[Dict]:
        """Анализирует файл на наличие API endpoints с улучшенными паттернами"""
        endpoints = []

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')

            relative_path = str(file_path.relative_to(repo_root))

            # Улучшенные паттерны для FastAPI
            fastapi_patterns = [
                # Стандартные декораторы FastAPI
                (r'@(app|router)\.(get|post|put|delete|patch|options|head)\s*\(\s*["\']([^"\']+)["\']', 'FastAPI'),
                # С параметрами пути и другими параметрами
                (r'@(app|router)\.(get|post|put|delete|patch|options|head)\s*\(\s*["\']([^"\']+?)["\'][^)]*\)',
                 'FastAPI'),
                # С пробелами и разными кавычками
                (r'@(app|router)\.(get|post|put|delete|patch|options|head)\s*\(\s*[\'"]([^\'"]+)[\'"]', 'FastAPI'),
            ]

            # Улучшенные паттерны для Flask
            flask_patterns = [
                (r'@(app|blueprint)\.route\s*\(\s*["\']([^"\']+)["\']\s*,\s*methods\s*=\s*\[([^\]]+)\]', 'Flask'),
                (r'@(app|blueprint)\.route\s*\(\s*["\']([^"\']+)["\']', 'Flask'),
                # Flask с разными вариантами
                (r'@(app|bp|blueprint)\.route\s*\([^)]*[\'"]([^\'"]+)[\'"][^)]*\)', 'Flask'),
            ]

            # Новые паттерны для Starlette и других фреймворков
            generic_patterns = [
                # Общие HTTP методы
                (r'\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']', 'Generic'),
                # Router добавление маршрутов
                (r'\.add_route\s*\(\s*["\']([^"\']+)["\']', 'Generic'),
            ]

            # Поиск FastAPI endpoints
            for pattern, framework in fastapi_patterns:
                for i, line in enumerate(lines):
                    matches = re.finditer(pattern, line)
                    for match in matches:
                        endpoint_path = match.group(3)
                        method = match.group(2).upper() if match.group(2) else 'GET'

                        endpoint = {
                            'path': endpoint_path,
                            'method': method,
                            'framework': framework,
                            'file': relative_path,
                            'line': i + 1,
                            'function_name': self._extract_function_name(lines, i),
                            'full_line': line.strip()[:100]  # Ограничиваем длину для логов
                        }
                        endpoints.append(endpoint)
                        logger.info(f"🎯 FASTAPI_ENDPOINT: {method} {endpoint_path} in {relative_path}:{i + 1}")

            # Поиск Flask endpoints
            for pattern, framework in flask_patterns:
                for i, line in enumerate(lines):
                    matches = re.finditer(pattern, line)
                    for match in matches:
                        endpoint_path = match.group(2) if match.group(2) else match.group(1)
                        methods = ['GET']  # по умолчанию

                        if len(match.groups()) >= 3 and match.group(3):
                            methods = [m.strip().strip('"\'') for m in match.group(3).split(',')]

                        for method in methods:
                            endpoint = {
                                'path': endpoint_path,
                                'method': method.upper(),
                                'framework': framework,
                                'file': relative_path,
                                'line': i + 1,
                                'function_name': self._extract_function_name(lines, i),
                                'full_line': line.strip()[:100]
                            }
                            endpoints.append(endpoint)
                            logger.info(f"🎯 FLASK_ENDPOINT: {method} {endpoint_path} in {relative_path}:{i + 1}")

            # Поиск generic endpoints
            for pattern, framework in generic_patterns:
                for i, line in enumerate(lines):
                    matches = re.finditer(pattern, line)
                    for match in matches:
                        endpoint_path = match.group(2) if len(match.groups()) >= 2 else match.group(1)
                        method = match.group(1).upper() if match.group(1) else 'GET'

                        endpoint = {
                            'path': endpoint_path,
                            'method': method,
                            'framework': framework,
                            'file': relative_path,
                            'line': i + 1,
                            'function_name': self._extract_function_name(lines, i),
                            'full_line': line.strip()[:100]
                        }
                        endpoints.append(endpoint)
                        logger.info(f"🎯 GENERIC_ENDPOINT: {method} {endpoint_path} in {relative_path}:{i + 1}")

        except Exception as e:
            logger.error(f"❌ Error analyzing API endpoints in {file_path}: {e}")

        return endpoints

    def _extract_function_name(self, lines: List[str], line_index: int) -> str:
        """Извлекает имя функции из декоратора endpoint"""
        try:
            # Ищем следующую строку после декоратора (обычно это определение функции)
            for i in range(line_index + 1, min(line_index + 5, len(lines))):
                line = lines[i].strip()

                # Паттерны для определения функций
                function_patterns = [
                    r'def\s+(\w+)\s*\(',
                    r'async\s+def\s+(\w+)\s*\(',
                ]

                for pattern in function_patterns:
                    match = re.search(pattern, line)
                    if match:
                        return match.group(1)

            # Если не нашли имя функции, возвращаем имя по умолчанию
            return "unknown_function"

        except Exception as e:
            logger.debug(f"Error extracting function name: {e}")
            return "unknown_function"

    def _should_ignore_file_aggressive(self, file_path: Path, repo_root: Path) -> Tuple[bool, str]:
        """АГРЕССИВНАЯ проверка на игнорирование файлов"""
        try:
            relative_path = file_path.relative_to(repo_root)
            relative_path_str = str(relative_path)
            relative_path_lower = relative_path_str.lower()

            # 1. АБСОЛЮТНОЕ игнорирование node_modules и других зависимостей
            if any(pattern in relative_path_lower for pattern in [
                'node_modules',
                'bower_components',
                'vendor',
                '.yarn',
                '.pnp'
            ]):
                return True, 'dependency_directory'

            # 2. Проверка по полным путям с glob-паттернами
            for ignored_pattern in self.ignored_directories:
                if self._match_glob_pattern(relative_path_str, ignored_pattern):
                    return True, 'ignored_pattern'

            # 3. Файлы блокировок зависимостей
            if file_path.name in self.dependency_lock_files:
                return True, 'dependency_lock_file'

            # 4. Расширения файлов
            if file_path.suffix.lower() in self.ignored_extensions:
                return True, 'ignored_extension'

            # 5. Скрытые файлы (кроме важных конфигов)
            if self._is_hidden_file(file_path) and not self._is_important_hidden_file(file_path):
                return True, 'hidden_file'

            # 6. Большие бинарные файлы
            try:
                file_size = file_path.stat().st_size
                if file_size > 5 * 1024 * 1024:  # 5MB
                    return True, 'large_binary_file'
            except:
                pass

            return False, ''

        except Exception as e:
            logger.debug(f"Error checking file {file_path}: {e}")
            return True, 'error_checking'

    def _match_glob_pattern(self, path: str, pattern: str) -> bool:
        """Проверяет соответствие пути glob-паттерну"""
        try:
            # Простая проверка для **/pattern/**
            if pattern.startswith('**/') and pattern.endswith('/**'):
                pattern_content = pattern[3:-3]
                return pattern_content in path
            # Более сложная логика может быть добавлена при необходимости
            return False
        except:
            return False

    def _analyze_frameworks_project_wide(self, repo_path: Path, analysis_result: Dict[str, Any]):
        """Анализирует фреймворки на основе всего проекта с строгими критериями"""
        framework_evidence = {}

        # Анализируем только файлы проекта (не тестовые и не зависимости)
        for file_path_str, file_info in analysis_result['file_structure'].items():
            if not file_info['is_test'] and file_info['technology']:
                tech = file_info['technology']
                file_path = repo_path / file_path_str

                if tech in self.framework_indicators:
                    self._check_framework_evidence(file_path, tech, framework_evidence)

        # Определяем фреймворки на основе собранных доказательств
        detected_frameworks = []
        for framework, evidence in framework_evidence.items():
            tech = self._get_framework_technology(framework)
            framework_config = self.framework_indicators[tech][framework]
            min_matches = framework_config.get('min_matches', 2)

            total_evidence = sum(evidence.values())
            if total_evidence >= min_matches:
                detected_frameworks.append(framework)
                logger.info(f"Detected framework: {framework} (evidence: {evidence})")

        analysis_result['frameworks'] = detected_frameworks

    def _check_framework_evidence(self, file_path: Path, tech: str, framework_evidence: Dict):
        """Собирает доказательства использования фреймворков"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            for framework, config in self.framework_indicators.get(tech, {}).items():
                evidence_count = 0

                # Проверка импортов
                for import_stmt in config.get('imports', []):
                    if import_stmt in content:
                        evidence_count += 1
                        break

                # Проверка паттернов (регулярные выражения)
                for pattern in config.get('patterns', []):
                    if re.search(pattern, content):
                        evidence_count += 1
                        break

                # Проверка специальных файлов
                for special_file in config.get('files', []):
                    if special_file in file_path.name:
                        evidence_count += 1
                        break

                # Проверка конфигураций
                for config_pattern in config.get('configs', []):
                    if config_pattern in content:
                        evidence_count += 1
                        break

                if evidence_count > 0:
                    if framework not in framework_evidence:
                        framework_evidence[framework] = {}
                    framework_evidence[framework][str(file_path)] = evidence_count

        except Exception as e:
            logger.debug(f"Error analyzing framework evidence in {file_path}: {e}")

    def _get_framework_technology(self, framework: str) -> str:
        """Определяет технологию фреймворка"""
        for tech, frameworks in self.framework_indicators.items():
            if framework in frameworks:
                return tech
        return 'unknown'

    def _analyze_test_file(self, file_path: Path) -> tuple:
        """Умный анализ тестовых файлов - проверяет реальное содержание тестов"""
        name = file_path.name.lower()
        path_str = str(file_path).lower()
        parent_dir = file_path.parent.name.lower()

        # Игнорируем тестовые файлы из зависимостей
        if any(dep in path_str for dep in ['node_modules', 'vendor', 'bower_components']):
            return False, None

        # Паттерны для тестовых файлов и директорий
        test_patterns = [
            # Имена файлов
            re.search(r'^test_|_test\.|\.test\.|_spec\.|\.spec\.', name),
            # Директории
            any(pattern in path_str for pattern in [
                '/test/', '/tests/', '/__tests__/', '/spec/', '/specs/',
                '/test_cases/', '/unit_test/', '/integration_test/'
            ]) and 'node_modules' not in path_str,
            # Особые случаи (только в корневых тестовых директориях)
            parent_dir in ['test', 'tests', '__tests__', 'spec', 'specs'] and
            'node_modules' not in path_str
        ]

        has_test_pattern = any(test_patterns)

        # Если нет паттернов тестов - точно не тестовый файл
        if not has_test_pattern:
            return False, None

        # 🔥 УМНАЯ ПРОВЕРКА: анализируем содержимое файла
        is_real_test, test_framework = self._analyze_test_content(file_path)

        return is_real_test, test_framework

    def _analyze_test_content(self, file_path: Path) -> tuple:
        """Анализирует содержимое файла на наличие реальных тестов"""
        suffix = file_path.suffix.lower()

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Минимальный размер для реального теста (исключает пустые/заглушки)
            if len(content.strip()) < 50:  # меньше 50 символов - вероятно заглушка
                return False, None

            # Проверяем наличие реальных тестовых конструкций
            test_indicators_count = 0

            if suffix == '.py':
                test_indicators_count = self._analyze_python_test_content(content)
            elif suffix in ['.js', '.jsx', '.ts', '.tsx']:
                test_indicators_count = self._analyze_javascript_test_content(content)
            elif suffix == '.java':
                test_indicators_count = self._analyze_java_test_content(content)
            else:
                # Для других языков используем общие паттерны
                test_indicators_count = self._analyze_generic_test_content(content)

            # Считаем файл тестовым если найдено достаточно индикаторов
            is_real_test = test_indicators_count >= 2

            # Определяем фреймворк
            test_framework = self._detect_test_framework_by_content(content, suffix) if is_real_test else None

            return is_real_test, test_framework

        except Exception as e:
            logger.debug(f"Error analyzing test content {file_path}: {e}")
            return False, None

    def _analyze_python_test_content(self, content: str) -> int:
        """Анализирует Python файл на наличие реальных тестов"""
        indicators = 0

        # Паттерны реальных тестов
        test_patterns = [
            # Pytest
            (r'import pytest|from pytest import', 2),
            (r'@pytest\.fixture', 2),
            (r'@pytest\.mark\.\w+', 2),
            (r'def test_\w+', 3),
            (r'class Test\w+', 2),

            # Unittest
            (r'import unittest|from unittest import', 2),
            (r'class \w+\(.*TestCase\):', 3),
            (r'self\.assert\w+\(', 2),
            (r'def test_\w+\(self\)', 3),

            # Общие тестовые паттерны
            (r'assert\s+\w+\s*==\s*\w+', 1),
            (r'assert\s+\w+\s*!=\s*\w+', 1),
            (r'assert\s+\w+\s+in\s+\w+', 1),
            (r'assert\s+\w+\s+not in\s+\w+', 1),
            (r'assert\s+isinstance\(', 1),
            (r'assert\s+len\(', 1),

            # Моки и фикстуры
            (r'@patch|@mock\.patch', 2),
            (r'from unittest\.mock import', 2),
            (r'import mock', 1),

            # Тестовые данные и setup/teardown
            (r'def setUp\(|def setUpClass\(|def tearDown\(|def tearDownClass\(', 2),
            (r'setup_method|teardown_method', 2),
        ]

        for pattern, weight in test_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                indicators += weight

        return indicators

    def _analyze_javascript_test_content(self, content: str) -> int:
        """Анализирует JavaScript/TypeScript файл на наличие реальных тестов"""
        indicators = 0

        test_patterns = [
            # Jest
            (r'describe\(', 3),
            (r'it\(|test\(', 3),
            (r'expect\(', 3),
            (r'jest\.', 2),
            (r'beforeEach\(|afterEach\(|beforeAll\(|afterAll\(', 2),

            # Mocha/Chai
            (r'describe\(', 2),
            (r'it\(', 2),
            (r'chai\.expect', 2),
            (r'should\.', 2),
            (r'assert\.', 2),

            # Testing Library
            (r'@testing-library', 2),
            (r'render\(', 2),
            (r'fireEvent\(', 2),
            (r'screen\.', 2),

            # Общие тестовые паттерны
            (r'\.toBe\(|\.toEqual\(|\.toBeTruthy\(|\.toBeFalsy\(', 2),
            (r'\.toThrow\(|\.toMatch\(|\.toContain\(', 2),
            (r'simulate\(|click\(|change\(', 1),

            # Моки и спаи
            (r'jest\.mock\(|jest\.spyOn\(', 3),
            (r'sinon\.', 2),
            (r'mock\.', 1),
        ]

        for pattern, weight in test_patterns:
            if re.search(pattern, content):
                indicators += weight

        return indicators

    def _analyze_java_test_content(self, content: str) -> int:
        """Анализирует Java файл на наличие реальных тестов"""
        indicators = 0

        test_patterns = [
            # JUnit
            (r'@Test', 3),
            (r'import org\.junit', 2),
            (r'Assert\.', 2),
            (r'assertEquals|assertTrue|assertFalse|assertNull', 2),

            # TestNG
            (r'@Test.*TestNG', 2),
            (r'import org\.testng', 2),

            # Mockito
            (r'@Mock|@InjectMocks', 2),
            (r'Mockito\.', 2),
            (r'when\(.*thenReturn\(', 2),

            # Spring Test
            (r'@SpringBootTest', 2),
            (r'@WebMvcTest', 2),
            (r'TestRestTemplate', 1),
            (r'MockMvc', 1),
        ]

        for pattern, weight in test_patterns:
            if re.search(pattern, content):
                indicators += weight

        return indicators

    def _analyze_generic_test_content(self, content: str) -> int:
        """Общий анализ для других языков"""
        indicators = 0

        generic_patterns = [
            (r'test.*function|test.*def|test.*method', 1),
            (r'assert\w*\(', 1),
            (r'verify\w*\(', 1),
            (r'should.*equal|expect.*equal', 1),
            (r'fixture|setup|teardown', 1),
            (r'mock|stub|spy', 1),
        ]

        for pattern, weight in generic_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                indicators += weight

        return indicators

    def _detect_test_framework_by_content(self, content: str, file_extension: str) -> str:
        """Определяет тестовый фреймворк по содержимому файла"""

        framework_indicators = {
            'pytest': [
                r'import pytest',
                r'@pytest\.fixture',
                r'@pytest\.mark',
                r'pytest\.'
            ],
            'unittest': [
                r'import unittest',
                r'class.*TestCase',
                r'self\.assert',
                r'unittest\.main'
            ],
            'jest': [
                r'describe\(',
                r'it\(|test\(',
                r'expect\(',
                r'jest\.',
                r'beforeEach\(|afterEach\('
            ],
            'mocha': [
                r'describe\(',
                r'it\(',
                r'before\(|after\(',
                r'chai\.expect'
            ],
            'junit': [
                r'@Test',
                r'import org\.junit',
                r'Assert\.',
                r'assertEquals'
            ],
            'testng': [
                r'@Test.*TestNG',
                r'import org\.testng'
            ]
        }

        for framework, patterns in framework_indicators.items():
            for pattern in patterns:
                if re.search(pattern, content):
                    return framework

        return 'unknown'

    def _analyze_test_directories(self, repo_path: Path, analysis_result: Dict[str, Any]):
        """Анализирует тестовые директории с проверкой реального содержания"""
        real_test_dirs = set()

        for test_file_path, file_info in analysis_result['file_structure'].items():
            if file_info['is_test']:
                # Получаем директорию тестового файла
                dir_path = str(Path(test_file_path).parent)

                # Игнорируем директории из зависимостей
                if not any(dep in dir_path.lower() for dep in ['node_modules', 'vendor', 'bower_components']):
                    # Проверяем, что в директории есть реальные тесты (не только по названию)
                    dir_has_real_tests = self._check_directory_has_real_tests(repo_path / dir_path)
                    if dir_has_real_tests:
                        real_test_dirs.add(dir_path)

        analysis_result['test_analysis']['test_directories'] = list(real_test_dirs)

    def _check_directory_has_real_tests(self, dir_path: Path) -> bool:
        """Проверяет, содержит ли директория реальные тесты (а не только по названию)"""
        if not dir_path.exists() or not dir_path.is_dir():
            return False

        # Считаем файлы с реальным тестовым содержанием
        real_test_files_count = 0

        for file_path in dir_path.rglob('*'):
            if file_path.is_file():
                is_test, _ = self._analyze_test_file(file_path)
                if is_test:
                    real_test_files_count += 1

                    # Если нашли несколько реальных тестов - директория валидна
                    if real_test_files_count >= 2:
                        return True

        return real_test_files_count > 0

    def _is_hidden_file(self, file_path: Path) -> bool:
        """Проверяет, является ли файл скрытым"""
        return any(part.startswith('.') and part not in ['.', '..'] and part != '.github'
                   for part in file_path.parts)

    def _is_important_hidden_file(self, file_path: Path) -> bool:
        """Проверяет, является ли скрытый файл важным"""
        important_hidden_files = {
            '.gitignore', '.gitattributes', '.env.example', '.eslintrc.js',
            '.eslintrc.json', '.prettierrc', '.babelrc', '.npmrc', '.nvmrc',
            '.dockerignore', '.eslintignore', '.prettierignore',
            '.python-version', '.ruby-version', '.node-version'
        }
        return file_path.name in important_hidden_files

    def _detect_technology_and_extension(self, file_path: Path) -> tuple:
        """Определяет технологию и расширение файла"""
        suffix = file_path.suffix.lower()
        name = file_path.name.lower()

        for tech, extensions in self.supported_techs.items():
            if suffix in extensions:
                return tech, suffix

        # Проверка конфигурационных файлов
        config_files = {
            'requirements.txt': ('python', '.txt'),
            'package.json': ('javascript', '.json'),
            'pom.xml': ('java', '.xml'),
            'build.gradle': ('java', '.gradle'),
            'go.mod': ('go', '.mod'),
            'cargo.toml': ('rust', '.toml'),
            'composer.json': ('php', '.json'),
            'gemfile': ('ruby', ''),
            'dockerfile': ('docker', ''),
            'docker-compose.yml': ('docker', '.yml'),
        }

        for file_pattern, (tech, ext) in config_files.items():
            if file_pattern in name:
                return tech, ext

        return None, suffix

    def _count_file_lines(self, file_path: Path) -> int:
        """Считает количество строк в файле"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return len(f.readlines())
        except:
            return 0

    def _check_special_files(self, file_path: Path, analysis_result: Dict[str, Any]):
        """Проверяет наличие специальных файлов"""
        name = file_path.name.lower()

        special_files = {
            'requirements.txt': 'has_requirements',
            'package.json': 'has_package_json',
            'pom.xml': 'has_pom_xml',
            'dockerfile': 'has_dockerfile',
            'readme.md': 'has_readme',
            '.gitignore': 'has_gitignore',
            'docker-compose.yml': 'has_docker_compose',
        }

        for file_pattern, flag_name in special_files.items():
            if file_pattern in name:
                analysis_result['project_structure'][flag_name] = True

    def _analyze_dependencies(self, repo_path: Path, analysis_result: Dict[str, Any]):
        """Анализирует зависимости проекта"""
        dependencies = {}

        # Python dependencies
        requirements_files = [
            repo_path / 'requirements.txt',
            repo_path / 'setup.py',
            repo_path / 'pyproject.toml'
        ]

        for req_file in requirements_files:
            if req_file.exists():
                try:
                    deps = self._parse_python_dependencies(req_file)
                    if deps:
                        dependencies['python'] = deps[:15]
                        break
                except Exception as e:
                    logger.debug(f"Error parsing {req_file}: {e}")

        # JavaScript dependencies
        package_json = repo_path / 'package.json'
        if package_json.exists():
            try:
                import json
                with open(package_json, 'r') as f:
                    data = json.load(f)
                    deps = list(data.get('dependencies', {}).keys())[:15]
                    dev_deps = list(data.get('devDependencies', {}).keys())[:10]
                    dependencies['javascript'] = {
                        'dependencies': deps,
                        'devDependencies': dev_deps
                    }
            except Exception as e:
                logger.debug(f"Error parsing package.json: {e}")

        analysis_result['dependencies'] = dependencies

    def _parse_python_dependencies(self, file_path: Path) -> List[str]:
        """Парсит Python зависимости"""
        deps = []
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('-'):
                        dep = line.split('==')[0].split('>=')[0].split('<=')[0].split('#')[0].strip()
                        if dep and not dep.startswith('['):
                            deps.append(dep)
        except:
            pass
        return deps

    def _calculate_coverage_estimate(self, analysis_result: Dict[str, Any]) -> float:
        """Рассчитывает оценку покрытия тестами"""
        total_code_files = analysis_result['metrics']['code_files']
        test_files = analysis_result['metrics']['test_files']

        if total_code_files == 0:
            return 0.0

        # Базовая оценка на основе соотношения тестовых и обычных файлов
        file_ratio = test_files / total_code_files

        # Учитываем наличие тестовых фреймворков
        framework_bonus = 0.0
        if analysis_result['test_analysis']['test_frameworks']:
            framework_bonus = 0.2

        # Учитываем тестовые директории
        directory_bonus = 0.0
        if analysis_result['test_analysis']['test_directories']:
            directory_bonus = 0.1

        coverage = min(0.95, (file_ratio * 0.7) + framework_bonus + directory_bonus)

        return round(coverage * 100, 2)