import asyncio
import logging
from functools import wraps

logger = logging.getLogger(__name__)


def robust_async_to_sync(coro_func):
    """Упрощенный декоратор для асинхронных задач в Celery"""

    @wraps(coro_func)
    def wrapper(*args, **kwargs):
        try:
            # Пытаемся использовать существующий loop
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # Если loop не существует, создаем новый
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            return loop.run_until_complete(coro_func(*args, **kwargs))
        finally:
            # НЕ закрываем loop, чтобы он мог использоваться в следующих задачах
            pass

    return wrapper