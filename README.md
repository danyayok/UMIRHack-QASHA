# QASHA - AI-Powered QA Automation Platform

![QASHA](https://img.shields.io/badge/QASHA-AI--Powered%20QA%20Automation-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104.0-green)
![React](https://img.shields.io/badge/React-18.2.0-blue)
![Celery](https://img.shields.io/badge/Celery-5.3.0-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15.0-blue)
![Redis](https://img.shields.io/badge/Redis-7.0-red)

## 📋 О проекте

**QASHA** - это современная AI-платформа для автоматизации процессов контроля качества (QA), которая использует искусственный интеллект для анализа кода, генерации тестов и управления тест-кейсами.

### 🎯 Ключевые возможности

- **🤖 AI-анализ проектов** - интеллектуальный анализ репозиториев с фильтрацией зависимостей
- **🚀 Умная генерация тестов** - AI-генерация unit, integration, API и E2E тестов
- **📊 Автоматическое покрытие** - расчет coverage на основе реальных данных
- **🔗 Git интеграция** - автоматическая отправка тестов в репозитории
- **⚡ Параллельная обработка** - одновременная работа с множеством проектов
- **📋 Управление тест-кейсами** - создание, импорт, экспорт тест-кейсов

## 🏗️ Архитектура

### Backend (FastAPI + Celery)
```
app/
├── api/
│   └── v1/
│       ├── projects.py      # Основной роутер проектов
│       ├── auth.py          # Аутентификация
│       ├── agents.py        # Управление агентами
│       └── ai_route.py      # AI endpoints
├── core/
│   ├── dependencies.py      # Управление зависимостями
│   └── config.py           # Конфигурация
├── services/
│   ├── git_service.py       # Работа с Git
│   ├── code_analyzer.py     # Анализ кода
│   ├── generate_pipeline.py # Пайплайн генерации тестов
│   └── ai_service.py        # AI сервисы
├── tasks/
│   └── tasks.py            # Celery задачи
├── models/                 # SQLAlchemy модели
└── db/
    └── session.py          # Сессии базы данных
```

### Frontend (React)
```
src/
├── pages/
│   ├── Landing.jsx           # Лендинг страница
│   ├── Auth.jsx             # Авторизация
│   ├── Dashboard.jsx        # Главная панель
│   ├── ProjectAnalysisPage.jsx   # Анализ проектов
│   └── ProjectTestsPage.jsx      # Управление тестами
├── hooks/
│   └── useAuth.js           # Хук аутентификации
└── index.css                # Стили
```

## 🚀 Быстрый старт

### Предварительные требования

- **Python 3.9+**
- **Node.js 16+**
- **PostgreSQL 14+**
- **Redis 6+**
- **Git**
- **Docker & Docker Compose (рекомендуется)**

### Установка с Docker (рекомендуется)

```bash
# Клонирование репозитория
git clone <repository-url>
cd qasha

# Создание файла окружения
cp .env.example .env
# Отредактируйте .env при необходимости

# Запуск всех сервисов
docker-compose up -d

# Просмотр логов
docker-compose logs -f
```

### Ручная установка

#### 1. Настройка базы данных PostgreSQL

```bash
# Создание базы данных
sudo -u postgres psql
CREATE USER qa_user WITH PASSWORD 'qa_pass';
CREATE DATABASE qa_db OWNER qa_user;
\q
```

#### 2. Настройка Redis

```bash
# Установка Redis
sudo apt update && sudo apt install redis-server

# Запуск Redis
sudo systemctl start redis
sudo systemctl enable redis
```

#### 3. Установка Backend

```bash
# Клонирование репозитория
git clone <repository-url>
cd qasha

# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Установка зависимостей
pip install -r requirements.txt

# Настройка окружения
cp .env.example .env
# Отредактируйте .env (см. раздел Конфигурация)

# Запуск миграций
alembic upgrade head

# Запуск сервера разработки
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 4. Запуск Celery Workers

```bash
# Откройте новые терминалы для каждого воркера

# Worker для анализа
celery -A app.celery_app worker --loglevel=info --queues=analysis,batch_analysis -n analysis_worker

# Worker для генерации тестов
celery -A app.celery_app worker --loglevel=info --queues=generation,batch_generation -n generation_worker

# Worker для мониторинга
celery -A app.celery_app worker --loglevel=info --queues=monitoring,maintenance -n maintenance_worker
```

#### 5. Установка Frontend

```bash
cd frontend

# Установка зависимостей
npm install

# Запуск разработки
npm run dev
```

## ⚙️ Конфигурация

### Файл окружения (.env)

```env
# ========================
# БАЗА ДАННЫХ PostgreSQL
# ========================
POSTGRES_USER=qa_user
POSTGRES_PASSWORD=qa_pass
POSTGRES_DB=qa_db
DATABASE_URL=postgresql+asyncpg://qa_user:qa_pass@localhost:5432/qa_db

# ========================
# БЕЗОПАСНОСТЬ
# ========================
SECRET_KEY=Pr3p4rE_f0ur_N5cLE4r_4114CK
ACCESS_TOKEN_EXPIRE_MINUTES=60
ALGORITHM=HS256

# ========================
# REDIS & CELERY
# ========================
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# ========================
# AI ПРОВАЙДЕРЫ
# ========================
GIGACHAT_KEY="MDE5YTY4NmEtZDBjOS03OGY5LTkyNmQtNDJjMzAyN2JlZmVkOmUwOTc4YjYwLTZmZjItNGZhNS05ZDQwLTI3NmC4NjgwNTQ0Mw=="
OLLAMA_API_KEY="04886c30b45b41a99b3012cd955f9d6f.tMGmDURT6ZICpygRUDz76k2N"
OLLAMA_HOST=https://ollama.com
OLLAMA_MODEL=qwen3-coder:480b

# ========================
# GITHUB ИНТЕГРАЦИЯ
# ========================
GITHUB_TOKEN=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
GITHUB_USERNAME=danyayok

# ========================
# НАСТРОЙКИ ПРИЛОЖЕНИЯ
# ========================
UPLOAD_DIR=./storage/uploads
MAX_FILE_SIZE=52428800
ENVIRONMENT=development
```

### Очереди Celery

- **`analysis`** - анализ репозиториев
- **`batch_analysis`** - пакетный анализ
- **`generation`** - генерация тестов
- **`batch_generation`** - пакетная генерация
- **`monitoring`** - мониторинг прогресса
- **`maintenance`** - обслуживание системы

## 📚 API Документация

После запуска сервера документация доступна по адресам:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## 🎯 Основные эндпоинты

### 🔐 Аутентификация
- `POST /api/v1/auth/login` - вход в систему
- `POST /api/v1/auth/register` - регистрация
- `GET /api/v1/auth/me` - информация о текущем пользователе

### 📁 Проекты
- `GET /api/v1/projects/` - список проектов пользователя
- `POST /api/v1/projects/` - создание проекта (GitHub/ZIP)
- `GET /api/v1/projects/{id}` - получение проекта
- `DELETE /api/v1/projects/{id}` - удаление проекта
- `POST /api/v1/projects/{id}/analyze` - запуск анализа проекта

### 🤖 Генерация тестов
- `POST /api/v1/projects/{id}/generate-tests` - AI-генерация тестов
- `GET /api/v1/projects/{id}/generated-tests` - получение сгенерированных тестов
- `POST /api/v1/projects/{id}/run-tests` - запуск тестов
- `GET /api/v1/projects/{id}/test-results` - история запусков тестов

### 📋 Тест-кейсы
- `POST /api/v1/projects/{id}/generate-test-cases` - генерация тест-кейсов
- `POST /api/v1/projects/{id}/test-cases/upload` - загрузка тест-кейсов
- `GET /api/v1/projects/{id}/test-cases` - получение тест-кейсов
- `POST /api/v1/projects/{id}/test-cases/export` - экспорт тест-кейсов

### ⚡ Параллельные операции
- `POST /api/v1/projects/batch/analyze` - пакетный анализ проектов
- `POST /api/v1/projects/batch/generate-tests` - пакетная генерация тестов
- `GET /api/v1/projects/task/{task_id}/status` - статус задачи Celery
- `GET /api/v1/projects/batch/queue/stats` - статистика очередей

## 🗂️ Структура базы данных

### Основные модели:

- **`Project`** - проекты пользователей
- **`Analysis`** - анализы проектов
- **`TestBatch`** - пачки сгенерированных тестов
- **`GeneratedTest`** - сгенерированные тесты
- **`TestCase`** - тест-кейсы
- **`TestCaseFile`** - загруженные файлы с тест-кейсами
- **`TestRun`** - запуски тестов
- **`AgentReport`** - отчеты агентов

## 🚀 Процесс работы

### 1. Создание проекта

```bash
# Из GitHub репозитория
POST /api/v1/projects/
{
  "name": "My Project",
  "source_type": "github",
  "repo_url": "https://github.com/user/repo",
  "branch": "main",
  "auto_analyze": true
}

# Из ZIP архива
POST /api/v1/projects/
{
  "name": "My Project", 
  "source_type": "zip",
  "zip_file": [file],
  "auto_analyze": true
}
```

### 2. Анализ проекта

Система автоматически:
- Клонирует репозиторий
- Анализирует структуру проекта
- Определяет технологии и фреймворки
- Фильтрует зависимости (node_modules, venv и т.д.)
- Рассчитывает метрики покрытия

### 3. Генерация тестов

```bash
POST /api/v1/projects/{id}/generate-tests
{
  "generate_unit_tests": true,
  "generate_api_tests": true, 
  "generate_integration_tests": true,
  "generate_e2e_tests": false,
  "max_unit_tests": 10,
  "max_api_tests": 5
}
```

### 4. Управление тестами

- Просмотр сгенерированных тестов
- Группировка по пачкам (TestBatch)
- Отправка тестов в репозиторий
- Запуск и мониторинг тестов

## 🔧 Разработка

### Запуск в режиме разработки

```bash
# Backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd frontend && npm run dev

# Celery workers (в отдельных терминалах)
celery -A app.celery_app worker --loglevel=info -Q analysis -n analysis_worker
celery -A app.celery_app worker --loglevel=info -Q generation -n generation_worker
```

### Тестирование

```bash
# Запуск тестов
pytest

# С покрытием кода
pytest --cov=app tests/

# С генерацией отчета
pytest --cov=app --cov-report=html tests/
```

### Миграции базы данных

```bash
# Создание новой миграции
alembic revision --autogenerate -m "Description"

# Применение миграций
alembic upgrade head

# Откат миграции
alembic downgrade -1
```

## 📈 Мониторинг и логи

### Логирование

- **Уровень**: INFO для продакшена, DEBUG для разработки
- **Формат**: JSON-structured logs
- **Назначение**: Файл `app.log` + stdout

### Мониторинг задач

```bash
# Статус конкретной задачи
GET /api/v1/projects/task/{task_id}/status

# Статистика очередей
GET /api/v1/projects/batch/queue/stats

# Мониторинг группы задач
GET /api/v1/projects/batch/{group_id}/status
```

### Health Checks

- **Основной**: `GET /health`
- **База данных**: автоматическая проверка подключения
- **Redis**: проверка подключения к брокеру
- **AI провайдеры**: проверка доступности сервисов

## 🐛 Диагностика проблем

### Проверка зависимостей

```bash
# Тест фильтрации зависимостей
celery -A app.celery_app call app.tasks.test_dependency_filtering_task --args '["https://github.com/octocat/Hello-World", "main"]'

# Диагностика системы
celery -A app.celery_app call app.tasks.diagnostic_task --args '["full"]'
```

### Частые проблемы

1. **Redis недоступен**
   ```bash
   sudo systemctl status redis
   redis-cli ping
   ```

2. **Проблемы с базой данных**
   ```bash
   psql -U qa_user -d qa_db -h localhost
   ```

3. **Ошибки Celery**
   ```bash
   celery -A app.celery_app inspect active
   celery -A app.celery_app inspect stats
   ```

## 🤝 Вклад в проект

1. Форкните репозиторий
2. Создайте feature ветку (`git checkout -b feature/amazing-feature`)
3. Закоммитьте изменения (`git commit -m 'Add amazing feature'`)
4. Запушьте в ветку (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

## 📄 Лицензия

Этот проект распространяется под лицензией MIT. Смотрите `LICENSE` для подробностей.

## 📞 Поддержка

- **Документация**: [docs.qasha.dev](https://docs.qasha.dev)
- **Issues**: [GitHub Issues](https://github.com/your-org/qasha/issues)
- **Discord**: [QASHA Community](https://discord.gg/qasha)

## 🔮 Roadmap

- [ ] Поддержка дополнительных AI провайдеров
- [ ] Интеграция с CI/CD системами
- [ ] Расширенная аналитика покрытия
- [ ] Мобильное приложение
- [ ] Плагины для IDE

---

**QASHA** - Automating QA with AI Power 🤖✨