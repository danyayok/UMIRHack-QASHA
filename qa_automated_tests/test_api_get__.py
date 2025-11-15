import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_root_success():
    response = client.get("/")
    assert response.status_code == 200

def test_get_root_not_found():
    response = client.get("/nonexistent")
    assert response.status_code == 404

@pytest.mark.parametrize("invalid_data", [
    {"invalid": "data"},
    {"key": ""},
    {}
])
def test_get_root_invalid_data(invalid_data):
    response = client.get("/", params=invalid_data)
    assert response.status_code == 422

def test_get_root_unauthorized():
    headers = {"Authorization": "Bearer invalid_token"}
    response = client.get("/", headers=headers)
    assert response.status_code == 401

def test_get_root_server_error(mocker):
    mocker.patch("app.main.some_dependency", side_effect=Exception("Internal Server Error"))
    response = client.get("/")
    assert response.status_code == 500
    assert "detail" in response.json()