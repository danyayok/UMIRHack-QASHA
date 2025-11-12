from app.tasks.worker import celery_app
import redis


def check_worker_and_queue():
    print("🔍 Checking Celery worker and queue...")

    # 1. Проверяем Redis очередь
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)

        # Смотрим задачи в очереди
        queue_length = r.llen('celery')
        print(f"📊 Tasks in celery queue: {queue_length}")

        if queue_length > 0:
            # Показываем первые несколько задач
            for i in range(min(3, queue_length)):
                task_data = r.lindex('celery', i)
                if task_data:
                    print(f"  Task {i + 1}: {task_data[:100]}...")

    except Exception as e:
        print(f"❌ Redis queue check failed: {e}")

    # 2. Проверяем worker через inspection
    try:
        insp = celery_app.control.inspect()

        # Активные worker'ы
        active = insp.active()
        if active:
            print("✅ Active workers found:")
            for worker, tasks in active.items():
                print(f"  {worker}: {len(tasks)} active tasks")
        else:
            print("❌ No active workers")

        # Зарегистрированные worker'ы
        registered = insp.registered()
        if registered:
            print("✅ Registered workers:")
            for worker, tasks in registered.items():
                print(f"  {worker}: {len(tasks)} registered tasks")
        else:
            print("❌ No registered workers")

        # Запланированные задачи
        scheduled = insp.scheduled()
        if scheduled:
            print("⏰ Scheduled tasks found")
        else:
            print("📭 No scheduled tasks")

    except Exception as e:
        print(f"❌ Worker inspection failed: {e}")


if __name__ == "__main__":
    check_worker_and_queue()