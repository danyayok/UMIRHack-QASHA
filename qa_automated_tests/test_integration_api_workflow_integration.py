import unittest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app
from app.models import User
from app.schemas import UserCreate
from app.services.ai_service import process_request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[override_get_db] = override_get_db

client = TestClient(app)

class TestAPIWorkflowIntegration(unittest.TestCase):
    def setUp(self):
        self.db = TestingSessionLocal()
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    def tearDown(self):
        self.db.close()

    def test_user_registration_and_login_flow(self):
        register_response = client.post("/register", json={"username": "testuser", "password": "testpass"})
        self.assertEqual(register_response.status_code, 200)
        login_response = client.post("/login", data={"username": "testuser", "password": "testpass"})
        self.assertEqual(login_response.status_code, 200)
        token = login_response.json().get("access_token")
        self.assertIsNotNone(token)

    def test_user_authentication_failure(self):
        login_response = client.post("/login", data={"username": "nonexistent", "password": "wrongpass"})
        self.assertEqual(login_response.status_code, 401)

    @patch('app.services.ai_service.external_ai_call')
    def test_data_flow_through_ai_service(self, mock_external_call):
        mock_external_call.return_value = {"result": "success"}
        response = process_request("test input")
        self.assertEqual(response["result"], "success")

    def test_error_propagation_on_invalid_endpoint(self):
        response = client.post("/nonexistent", json={"invalid": "data"})
        self.assertEqual(response.status_code, 404)

    def test_transaction_consistency_on_user_creation(self):
        user_data = {"username": "consistent_user", "password": "consistent_pass"}
        response = client.post("/register", json=user_data)
        self.assertEqual(response.status_code, 200)
        db_user = self.db.query(User).filter(User.username == "consistent_user").first()
        self.assertIsNotNone(db_user)

    def test_recovery_from_failed_user_creation(self):
        with patch('app.models.User.create', side_effect=Exception("DB Error")):
            response = client.post("/register", json={"username": "fail_user", "password": "fail_pass"})
            self.assertEqual(response.status_code, 500)
        db_user = self.db.query(User).filter(User.username == "fail_user").first()
        self.assertIsNone(db_user)

if __name__ == '__main__':
    unittest.main()