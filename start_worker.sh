#!/bin/bash

echo "🚀 Starting Celery workers for parallel processing..."

# Воркер для анализа (высокая нагрузка)
celery -A app.celery_app worker \
    --queues=analysis,batch_analysis \
    --concurrency=4 \
    --hostname=analysis_worker@%h \
    --loglevel=info \
    --pool=prefork \
    --detach

# Воркер для генерации тестов (средняя нагрузка)
celery -A app.celery_app worker \
    --queues=generation,batch_generation \
    --concurrency=3 \
    --hostname=generation_worker@%h \
    --loglevel=info \
    --pool=prefork \
    --detach

# Воркер для мониторинга и обслуживания (низкая нагрузка)
celery -A app.celery_app worker \
    --queues=monitoring,maintenance,celery \
    --concurrency=2 \
    --hostname=monitoring_worker@%h \
    --loglevel=info \
    --pool=prefork \
    --detach

echo "✅ All workers started!"
echo "📊 Queues: analysis, generation, monitoring"
echo "🔍 Monitor at: http://localhost:5555"