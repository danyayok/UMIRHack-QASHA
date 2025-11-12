import asyncio
import requests
import redis
from app.db.session import AsyncSessionLocal
from app.models import Project, Analysis

async def test_database():
    """Проверяем подключение к базе"""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute("SELECT 1")
            print("✅ Database: OK")
    except Exception as e:
        print(f"❌ Database: {e}")

def test_redis():
    """Проверяем Redis"""
    try:
        r = redis.Redis(host='localhost', port=6379)
        r.ping()
        print("✅ Redis: OK")
        return True
    except Exception as e:
        print(f"❌ Redis: {e}")
        return False

def test_backend():
    """Проверяем бэкенд"""
    try:
        response = requests.get('http://localhost:8000/')
        if response.status_code == 200:
            print("✅ Backend: OK")
            return True
        else:
            print(f"❌ Backend: Status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Backend: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Testing system...")
    test_redis()
    test_backend()
    asyncio.run(test_database())