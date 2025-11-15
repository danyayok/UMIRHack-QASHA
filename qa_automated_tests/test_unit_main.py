import pytest
from unittest.mock import AsyncMock, Mock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.main import app, on_startup, root, health_check


@pytest.fixture
def client():
    return TestClient(app)


@patch("app.main.init_models")
@patch("app.main.init_app_dependencies")
def test_on_startup_success(mock_init_deps, mock_init_models):
    mock_init_models.return_value = None
    mock_init_deps.return_value = None
    
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(on_startup())
    
    assert mock_init_models.called
    assert mock_init_deps.called


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "QA Autopilot API is running"}


@patch("app.main.test_generation_pipeline", None)
def test_health_check_not_initialized(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "test_generation_pipeline": "not_initialized"
    }


@patch("app.main.test_generation_pipeline", Mock())
def test_health_check_initialized(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "test_generation_pipeline": "initialized"
    }