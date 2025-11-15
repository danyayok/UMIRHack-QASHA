from fastapi.testclient import TestClient
from app.main import app
import pytest

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_health_endpoint_invalid_method():
    response = client.post("/health")
    assert response.status_code == 405

    response = client.put("/health")
    assert response.status_code == 405

    response = client.delete("/health")
    assert response.status_code == 405