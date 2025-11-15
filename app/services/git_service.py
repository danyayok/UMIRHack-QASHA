import asyncio
import datetime
import tempfile
import os
import shutil
from pathlib import Path
import time
from typing import Dict, List, Any

from git import Repo, GitCommandError
import logging
import stat
import aiohttp

from app.core.config import settings

logger = logging.getLogger("qa_automata")


class GitService:
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()

    async def clone_repository(self, repo_url: str, branch: str = "main") -> str:
        """Клонирует репозиторий во временную директорию (всегда новая копия)"""
        try:
            # Создаем уникальную временную директорию
            temp_path = tempfile.mkdtemp(prefix="repo_")

            logger.info(f"Cloning {repo_url} (branch: {branch}) to {temp_path}")

            # Используем отдельный event loop для git операций
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            await loop.run_in_executor(
                None,
                lambda: Repo.clone_from(repo_url, temp_path, branch=branch, depth=1)
            )

            logger.info(f"Repository cloned successfully to {temp_path}")
            return temp_path

        except GitCommandError as e:
            logger.error(f"Git clone error: {e}")

            # Очищаем временную директорию при ошибке
            if 'temp_path' in locals() and os.path.exists(temp_path):
                self.cleanup(temp_path)

            if "not found" in str(e).lower():
                raise Exception("Repository not found - check URL")
            elif "branch" in str(e).lower():
                raise Exception(f"Branch '{branch}' not found")
            else:
                raise Exception(f"Failed to clone repository: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during clone: {e}")

            # Очищаем временную директорию при ошибке
            if 'temp_path' in locals() and os.path.exists(temp_path):
                self.cleanup(temp_path)

            raise Exception(f"Clone failed: {str(e)}")

    async def get_repo_info(self, repo_url: str) -> dict:
        """Получает информацию о репозитории через GitHub API"""
        try:
            # Извлекаем owner и repo из URL
            if "github.com" in repo_url:
                parts = repo_url.rstrip('/').split('/')
                if len(parts) >= 2:
                    owner = parts[-2]
                    repo_name = parts[-1].replace('.git', '')

                    api_url = f"https://api.github.com/repos/{owner}/{repo_name}"

                    async with aiohttp.ClientSession() as session:
                        async with session.get(api_url) as response:
                            if response.status == 200:
                                data = await response.json()
                                return {
                                    "name": data.get("name"),
                                    "description": data.get("description"),
                                    "language": data.get("language"),
                                    "stars": data.get("stargazers_count", 0),
                                    "forks": data.get("forks_count", 0),
                                    "size": data.get("size", 0),
                                    "default_branch": data.get("default_branch", "main"),
                                    "updated_at": data.get("updated_at"),
                                    "pushed_at": data.get("pushed_at")
                                }
            return {}
        except Exception as e:
            logger.error(f"Error getting repo info: {e}")
            return {}

    def _force_cleanup_with_retry(self, repo_path: str, max_retries: int = 3):
        """Пытается удалить директорию с повторными попытками"""
        for attempt in range(max_retries):
            try:
                if not os.path.exists(repo_path):
                    return

                # Ждем перед повторной попыткой
                if attempt > 0:
                    time.sleep(1)  # 1 секунда задержки

                # Пытаемся удалить все файлы по одному
                for root, dirs, files in os.walk(repo_path, topdown=False):
                    for name in files:
                        file_path = os.path.join(root, name)
                        try:
                            os.chmod(file_path, stat.S_IWRITE)
                            os.unlink(file_path)
                        except Exception as e:
                            logger.debug(f"Could not remove file {file_path}: {e}")

                    for name in dirs:
                        dir_path = os.path.join(root, name)
                        try:
                            os.chmod(dir_path, stat.S_IWRITE)
                            os.rmdir(dir_path)
                        except Exception as e:
                            logger.debug(f"Could not remove directory {dir_path}: {e}")

                # Пытаемся удалить корневую директорию
                os.rmdir(repo_path)
                logger.info(f"Successfully force-cleaned up {repo_path} after {attempt + 1} attempts")
                return

            except Exception as e:
                logger.warning(f"Force cleanup attempt {attempt + 1} failed for {repo_path}: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed to cleanup {repo_path} after {max_retries} attempts")
                    # Можно добавить отправку уведомления или логирование в отдельный файл

    def cleanup(self, repo_path: str):
        """Очищает временные файлы с обработкой ошибок доступа на Windows"""
        if not os.path.exists(repo_path):
            logger.info(f"⚠️  Repository path {repo_path} does not exist, nothing to clean")
            return

        try:
            # Функция для изменения прав доступа к файлам
            def remove_readonly(func, path, excinfo):
                """Обработчик для удаления файлов с правами только для чтения"""
                try:
                    os.chmod(path, stat.S_IWRITE)  # Устанавливаем права на запись
                    func(path)  # Пытаемся удалить снова
                except Exception as e:
                    logger.warning(f"Failed to remove {path}: {e}")
                    # Если не удалось удалить, оставляем файл (он будет удален при перезагрузке)

            # Рекурсивное удаление с обработкой ошибок доступа
            shutil.rmtree(repo_path, onerror=remove_readonly)
            logger.info(f"Successfully cleaned up temporary repository: {repo_path}")

        except PermissionError as e:
            logger.warning(f"Permission error during cleanup of {repo_path}: {e}")
            # Пытаемся удалить с задержкой
            self._force_cleanup_with_retry(repo_path)
        except Exception as e:
            logger.warning(f"Error during cleanup of {repo_path}: {e}")
            self._force_cleanup_with_retry(repo_path)

    async def commit_and_push_to_branch(self, repo_path: str, commit_message: str,
                                        branch: str = "qa-automated-tests") -> Dict[str, Any]:
        """Коммит и пуш в отдельную ветку с созданием если нужно"""
        try:
            logger.info(f"🔄 Starting commit and push to branch '{branch}'")

            if not os.path.exists(repo_path):
                raise Exception(f"Repository path not found: {repo_path}")

            repo = Repo(repo_path)

            if repo.bare:
                raise Exception("Repository is bare")

            # Настраиваем аутентификацию
            self._setup_git_authentication(
                repo,
                settings.GITHUB_TOKEN,
                settings.GITHUB_USERNAME
            )

            # 🔥 СОЗДАЕМ ИЛИ ПЕРЕКЛЮЧАЕМСЯ НА ВЕТКУ
            try:
                # Проверяем существует ли ветка
                if branch in [b.name for b in repo.branches]:
                    logger.info(f"📁 Branch '{branch}' exists, checking out...")
                    repo.git.checkout(branch)

                    # Пуллим последние изменения если ветка существует
                    try:
                        origin = repo.remote('origin')
                        origin.pull(branch)
                        logger.info(f"✅ Pulled latest changes from branch '{branch}'")
                    except GitCommandError as pull_error:
                        logger.warning(f"⚠️ Pull failed: {pull_error}")
                else:
                    # Создаем новую ветку
                    logger.info(f"🌱 Creating new branch '{branch}'...")
                    repo.git.checkout('-b', branch)
                    logger.info(f"✅ Created and switched to branch '{branch}'")

            except GitCommandError as branch_error:
                logger.error(f"❌ Branch operation failed: {branch_error}")
                return {
                    "success": False,
                    "error": f"Branch operation failed: {branch_error}"
                }

            # Добавляем файлы
            logger.info("📦 Adding files to git...")
            repo.git.add(A=True)

            # Проверяем изменения
            if not repo.index.diff("HEAD") and not repo.untracked_files:
                logger.info("📭 No changes to commit")
                return {
                    "success": True,
                    "commit_hash": None,
                    "message": "No changes to commit"
                }

            # Создаем коммит
            logger.info(f"💾 Creating commit: {commit_message}")
            commit = repo.index.commit(commit_message)

            # Получаем remote
            origin = repo.remote(name='origin')
            if not origin:
                raise Exception("No remote 'origin' found")

            # 🔥 ПУШ В УДАЛЕННУЮ ВЕТКУ
            logger.info(f"🚀 Pushing to remote branch '{branch}'...")
            try:
                # Пуш с установкой upstream если ветка новая
                push_result = origin.push(branch, set_upstream=True)

                # Проверяем результат
                for info in push_result:
                    if info.flags & info.ERROR:
                        error_msg = f"Push failed: {info.summary}"
                        raise Exception(error_msg)

                logger.info(f"✅ Successfully pushed to branch '{branch}'")

                return {
                    "success": True,
                    "commit_hash": commit.hexsha,
                    "branch": branch,
                    "message": f"Successfully pushed to branch '{branch}'"
                }

            except GitCommandError as push_error:
                error_msg = f"Git push error: {push_error}"
                logger.error(f"❌ {error_msg}")

                # Специфичная обработка ошибок
                if "auth" in str(push_error).lower() or "403" in str(push_error):
                    return {
                        "success": False,
                        "error": "Authentication failed. Check your GitHub token permissions.",
                        "details": str(push_error)
                    }
                else:
                    return {
                        "success": False,
                        "error": error_msg,
                        "details": str(push_error)
                    }

        except Exception as e:
            error_msg = f"Push to branch failed: {e}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }

    def _setup_git_authentication(self, repo: Repo, token: str = None, username: str = None):
        """Улучшенная аутентификация с username"""
        try:
            # Настройка пользователя
            with repo.config_writer() as config:
                config.set_value('user', 'name', username or 'danyayok')
                config.set_value('user', 'email', 'danildanfuntastic@gmail.com')

            if token and repo.remotes:
                origin = repo.remote('origin')
                current_url = list(origin.urls)[0]

                if 'https://' in current_url and 'github.com' in current_url:
                    # 🔥 ПРАВИЛЬНЫЙ ФОРМАТ С USERNAME
                    if username and not any(x in current_url for x in [f'{username}:', '@']):
                        # Формат: https://username:token@github.com/owner/repo.git
                        auth_url = current_url.replace(
                            'https://',
                            f'https://{username}:{token}@'
                        )
                    elif not any(x in current_url for x in ['@']):
                        # Формат: https://token@github.com/owner/repo.git
                        auth_url = current_url.replace(
                            'https://',
                            f'https://{token}@'
                        )
                    else:
                        auth_url = current_url

                    origin.set_url(auth_url)
                    logger.info("✅ Git authentication configured")

        except Exception as e:
            logger.warning(f"⚠️ Git auth setup warning: {e}")

    async def validate_repository(self, repo_path: str) -> Dict[str, Any]:
        """Проверяет валидность репозитория и доступность для пуша"""
        try:
            if not os.path.exists(repo_path):
                return {
                    "valid": False,
                    "error": f"Repository path does not exist: {repo_path}"
                }

            repo = Repo(repo_path)

            # Проверяем что это git репозиторий
            if repo.bare:
                return {
                    "valid": False,
                    "error": "Repository is bare"
                }

            # Проверяем наличие remote origin
            if not hasattr(repo.remotes, 'origin'):
                return {
                    "valid": False,
                    "error": "No remote 'origin' configured"
                }

            origin = repo.remote('origin')

            # Проверяем доступность remote
            try:
                origin.fetch()
                logger.info("✅ Repository remote is accessible")
            except GitCommandError as e:
                return {
                    "valid": False,
                    "error": f"Cannot access remote: {e}"
                }

            return {
                "valid": True,
                "branch": repo.active_branch.name,
                "remotes": [remote.name for remote in repo.remotes],
                "has_changes": bool(repo.untracked_files or repo.index.diff("HEAD"))
            }

        except Exception as e:
            return {
                "valid": False,
                "error": f"Repository validation failed: {e}"
            }

    async def create_files_in_repository(self, repo_path: str, files: List[Dict[str, str]]) -> Dict[str, Any]:
        """Создает файлы в репозитории"""
        try:
            created_files = []

            for file_info in files:
                file_path = os.path.join(repo_path, file_info["file_path"])

                # Создаем директории если нужно
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                # Записываем файл
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(file_info["content"])

                created_files.append(file_path)
                logger.info(f"📝 Created file: {file_info['file_path']}")

            return {
                "success": True,
                "created_files": created_files,
                "total_created": len(created_files)
            }

        except Exception as e:
            error_msg = f"File creation failed: {e}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "created_files": []
            }

    async def get_repository_status(self, repo_path: str) -> Dict[str, Any]:
        """Получает статус репозитория"""
        try:
            repo = Repo(repo_path)

            # Получаем изменения
            changed_files = [item.a_path for item in repo.index.diff("HEAD")]
            untracked_files = repo.untracked_files

            # Получаем последний коммит
            latest_commit = repo.head.commit.hexsha[:8] if not repo.head.is_detached else "detached"

            # Получаем информацию о ветках
            branches = [str(branch) for branch in repo.branches]
            active_branch = repo.active_branch.name if not repo.head.is_detached else "detached"

            return {
                "active_branch": active_branch,
                "branches": branches,
                "latest_commit": latest_commit,
                "has_changes": bool(changed_files or untracked_files),
                "changed_files": changed_files,
                "untracked_files": untracked_files,
                "total_changes": len(changed_files) + len(untracked_files)
            }

        except Exception as e:
            return {
                "error": f"Could not get repository status: {e}",
                "active_branch": "unknown",
                "has_changes": False,
                "changed_files": [],
                "untracked_files": []
            }

    async def push_tests_to_repository(self, repo_path: str, tests: List[Dict],
                                       test_cases: List[Dict] = None,
                                       commit_message: str = "Add generated tests and test cases",
                                       branch: str = "qa-automated-tests",  # 🔥 ОТДЕЛЬНАЯ ВЕТКА
                                       test_folder: str = "qa_automated_tests") -> Dict[str, Any]:  # 🔥 ОТДЕЛЬНАЯ ПАПКА
        """Полный процесс пуша тестов и тест-кейсов в репозиторий в отдельную ветку и папку"""
        try:
            logger.info(
                f"🚀 Starting push process for {len(tests)} tests and {len(test_cases or [])} test cases to branch '{branch}' in folder '{test_folder}'")

            # 1. Проверяем репозиторий
            validation = await self.validate_repository(repo_path)
            if not validation["valid"]:
                return {
                    "success": False,
                    "error": f"Repository validation failed: {validation['error']}"
                }

            # 2. Создаем тестовые файлы в отдельной папке
            files_to_create = []

            # Добавляем тестовые файлы в папку qa_automated_tests
            for test in tests:
                files_to_create.append({
                    "file_path": f"{test_folder}/{test['file_path']}",  # 🔥 ПАПКА ДЛЯ ТЕСТОВ
                    "content": test["content"]
                })

            # Добавляем файлы тест-кейсов если есть
            if test_cases:
                test_cases_content = self._format_test_cases_for_export(test_cases)
                files_to_create.append({
                    "file_path": f"{test_folder}/test_cases/test_cases.md",  # 🔥 ПАПКА ДЛЯ ТЕСТ-КЕЙСОВ
                    "content": test_cases_content
                })

            # 3. Создаем файлы
            creation_result = await self.create_files_in_repository(repo_path, files_to_create)
            if not creation_result["success"]:
                return creation_result

            # 4. Коммитим и пушим в отдельную ветку
            push_result = await self.commit_and_push_to_branch(repo_path, commit_message, branch)

            if push_result["success"]:
                return {
                    "success": True,
                    "pushed_files": creation_result["created_files"],
                    "commit_hash": push_result.get("commit_hash"),
                    "branch": branch,
                    "test_folder": test_folder,
                    "tests_count": len(tests),
                    "test_cases_count": len(test_cases or [])
                }
            else:
                return push_result

        except Exception as e:
            error_msg = f"Push process failed: {e}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }

    def _format_test_cases_for_export(self, test_cases: List[Dict]) -> str:
        """Форматирует тест-кейсы для экспорта в Markdown"""
        content = "# Test Cases Documentation\n\n"
        content += f"*Generated on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"

        for tc in test_cases:
            content += f"## {tc.get('test_case_id', 'TC')}: {tc.get('name', 'Unnamed')}\n\n"

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
                    content += "\n"

            if tc.get('postconditions'):
                content += f"**Postconditions:**\n{tc['postconditions']}\n\n"

            content += "---\n\n"

        return content