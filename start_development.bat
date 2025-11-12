@echo off
echo Starting QA Automation Development Environment...

echo 1. Starting Redis...
start cmd /k "C:\Program Files\Redis\redis-server.exe"

echo 2. Waiting for Redis to start...
timeout /t 3

echo 3. Starting Celery Worker...
cd /d C:\python\qa_automation
call .venv\Scripts\activate.bat
start cmd /k "celery -A app.tasks.worker.celery_app worker --loglevel=info --concurrency=2"

echo 4. Creating test data...
start cmd /k "python add_test_data.py"

echo 5. Starting FastAPI Backend...
start cmd /k "uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

echo 6. Waiting for backend to start...
timeout /t 5

echo 7. Starting Frontend...
cd frontend
start cmd /k "npm run dev"

echo.
echo ✅ All services started!
echo 📊 Backend: http://localhost:8000
echo 🎨 Frontend: http://localhost:5173
echo 🔧 API Docs: http://localhost:8000/docs
echo.
echo Test credentials:
echo Email: test@example.com
echo Password: test123
echo.
pause