import asyncio
import tempfile
import os
import shutil
from pathlib import Path
import time
from git import Repo, GitCommandError
import logging
import stat
import aiohttp

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