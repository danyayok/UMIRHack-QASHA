import os
import asyncio
import re
from pathlib import Path
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)


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

        self.framework_indicators = {
            'python': {
                'django': ['django', 'from django', 'import django'],
                'flask': ['flask', 'from flask', 'import flask'],
                'fastapi': ['fastapi', 'from fastapi', 'import fastapi'],
                'pandas': ['pandas', 'import pandas'],
                'numpy': ['numpy', 'import numpy'],
            },
            'javascript': {
                'react': ['react', 'from react', 'import react'],
                'vue': ['vue', 'from vue', 'import vue'],
                'angular': ['angular', '@angular'],
                'express': ['express', 'require(\'express\')'],
                'node.js': ['module.exports', 'require('],
            },
            'java': {
                'spring': ['spring', '@spring', 'import org.springframework'],
                'hibernate': ['hibernate', 'import org.hibernate'],
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
        """Синхронный анализ репозитория"""
        analysis_result = {
            'technologies': [],
            'frameworks': [],
            'file_structure': {},
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
            }
        }

        repo_path_obj = Path(repo_path)
        total_size = 0

        for file_path in repo_path_obj.rglob('*'):
            if file_path.is_file() and not self._is_hidden_file(file_path):
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

                # Проверяем на тестовый файл
                is_test_file, test_framework = self._analyze_test_file(file_path)
                if is_test_file:
                    analysis_result['metrics']['test_files'] += 1
                    analysis_result['test_analysis']['has_tests'] = True
                    analysis_result['test_analysis']['test_files_count'] += 1

                    if test_framework and test_framework not in analysis_result['test_analysis']['test_frameworks']:
                        analysis_result['test_analysis']['test_frameworks'].append(test_framework)

                # Анализируем фреймворки
                if tech and not is_test_file:
                    analysis_result['metrics']['code_files'] += 1
                    frameworks = self._detect_frameworks(file_path, tech)
                    for framework in frameworks:
                        if framework not in analysis_result['frameworks']:
                            analysis_result['frameworks'].append(framework)

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

                analysis_result['file_structure'][relative_path] = file_info

        # Анализ зависимостей
        self._analyze_dependencies(repo_path_obj, analysis_result)

        # Финальные вычисления
        analysis_result['metrics']['total_size_kb'] = total_size / 1024
        if analysis_result['metrics']['code_files'] > 0:
            analysis_result['complexity_metrics']['avg_file_size'] = total_size / analysis_result['metrics'][
                'code_files']

        # Анализ тестовых директорий
        self._analyze_test_directories(repo_path_obj, analysis_result)

        return analysis_result

    def _is_hidden_file(self, file_path: Path) -> bool:
        """Проверяет, является ли файл скрытым"""
        return any(part.startswith('.') and part not in ['.', '..'] for part in file_path.parts)

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

    def _analyze_test_file(self, file_path: Path) -> tuple:
        """Анализирует, является ли файл тестовым и определяет фреймворк"""
        name = file_path.name.lower()
        path_str = str(file_path).lower()
        parent_dir = file_path.parent.name.lower()

        # Паттерны для тестовых файлов
        test_patterns = [
            # Имена файлов
            re.search(r'test_|_test\.|\.test\.|_spec\.|\.spec\.', name),
            # Директории
            any(pattern in path_str for pattern in [
                '/test', '/tests', '/__tests__', '/spec', '/specs',
                '/test_cases', '/unit_test', '/integration_test'
            ]),
            # Особые случаи
            parent_dir in ['test', 'tests', '__tests__', 'spec', 'specs']
        ]

        is_test_file = any(test_patterns)

        # Определяем тестовый фреймворк
        test_framework = None
        if is_test_file:
            test_framework = self._detect_test_framework(file_path)

        return is_test_file, test_framework

    def _detect_test_framework(self, file_path: Path) -> str:
        """Определяет тестовый фреймворк по содержимому файла"""
        suffix = file_path.suffix.lower()

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

                if suffix == '.py':
                    if re.search(r'(import|from)\s+pytest', content):
                        return 'pytest'
                    elif re.search(r'(import|from)\s+unittest', content):
                        return 'unittest'
                    elif re.search(r'(import|from)\s+nose', content):
                        return 'nose'
                    elif 'def test_' in content or 'def test_' in content:
                        return 'pytest'  # предположительно

                elif suffix in ['.js', '.jsx', '.ts', '.tsx']:
                    if 'jest' in content or 'describe(' in content or 'test(' in content:
                        return 'jest'
                    elif 'mocha' in content or 'describe(' in content:
                        return 'mocha'
                    elif 'jasmine' in content:
                        return 'jasmine'

                elif suffix == '.java':
                    if '@Test' in content or 'import org.junit' in content:
                        return 'junit'
                    elif 'import org.testng' in content:
                        return 'testng'

        except Exception as e:
            logger.debug(f"Error reading test file {file_path}: {e}")

        return 'unknown'

    def _detect_frameworks(self, file_path: Path, tech: str) -> List[str]:
        """Определяет фреймворки по содержимому файла"""
        frameworks = []

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().lower()

                if tech in self.framework_indicators:
                    for framework, indicators in self.framework_indicators[tech].items():
                        for indicator in indicators:
                            if indicator in content:
                                frameworks.append(framework)
                                break

        except:
            pass

        return frameworks

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
            'docker-compose.yaml': 'has_docker_compose',
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
                        dependencies['python'] = deps[:15]  # Берем первые 15
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
                        # Убираем версии и комментарии
                        dep = line.split('==')[0].split('>=')[0].split('<=')[0].split('#')[0].strip()
                        if dep and not dep.startswith('['):
                            deps.append(dep)
        except:
            pass
        return deps

    def _analyze_test_directories(self, repo_path: Path, analysis_result: Dict[str, Any]):
        """Анализирует тестовые директории"""
        test_dirs = set()

        for test_file_path, file_info in analysis_result['file_structure'].items():
            if file_info['is_test']:
                # Получаем директорию тестового файла
                dir_path = str(Path(test_file_path).parent)
                if any(pattern in dir_path.lower() for pattern in ['test', 'spec']):
                    test_dirs.add(dir_path)

        analysis_result['test_analysis']['test_directories'] = list(test_dirs)