## Run
1) `cp .env.example .env` и проверь значения.  
2) `docker-compose up --build`  
3) Открыть: `http://localhost:8000/docs`

## Mock C++ агент
- Зарегистрируй агента: `POST /api/v1/agents/register?name=mock-cpp-agent&token=<TOKEN>`
- Отправка отчёта (пример JSON см. ниже) в `POST /api/v1/agents/cpp/report` с заголовком `X-Agent-Token: <TOKEN>`

### Пример JSON для агента
```json
{
  "agent_name": "mock-cpp-agent",
  "project_id": 1,
  "run_id": "run-123",
  "meta": {
    "hostname": "mock-runner",
    "timestamp": "2025-11-07T12:00:00Z",
    "duration_seconds": 12.5
  },
  "payload": {
    "performance": {
      "functions": [
        {"name": "doWork", "p75_ms": 10.2, "p95_ms": 20.1, "allocations": 5}
      ],
      "max_memory_mb": 128
    },
    "fuzz": {"runs": 1000, "crashes": []}
  }
}
