import unittest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app
from app.models import User
from app.schemas import UserCreate
from app.services.ai_service import get_response
from fastapi.testclient import TestClient

class TestExternalAPIIntegration(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpassword"
        }

    @patch('app.services.ai_service.get_response')
    def test_data_flow_between_components(self, mock_get_response):
        mock_get_response.return_value = {"response": "Test AI response"}
        response = self.client.post("/register", json=self.user_data)
        self.assertEqual(response.status_code, 200)
        user_response = response.json()
        self.assertIn("id", user_response)
        self.assertEqual(user_response["username"], self.user_data["username"])

        ai_response = self.client.get("/response")
        self.assertEqual(ai_response.status_code, 200)
        self.assertEqual(ai_response.json(), {"response": "Test AI response"})

    @patch('app.services.ai_service.get_response')
    def test_error_propagation_across_services(self, mock_get_response):
        mock_get_response.side_effect = Exception("AI Service Error")
        response = self.client.post("/register", json=self.user_data)
        self.assertEqual(response.status_code, 200)

        ai_response = self.client.get("/response")
        self.assertEqual(ai_response.status_code, 500)
        self.assertIn("detail", ai_response.json())

    @patch('app.models.User.create')
    def test_transaction_consistency(self, mock_user_create):
        mock_user_create.side_effect = Exception("Database Error")
        response = self.client.post("/register", json=self.user_data)
        self.assertEqual(response.status_code, 500)
        self.assertIn("detail", response.json())

    @patch('app.services.ai_service.get_response')
    def test_performance_under_load(self, mock_get_response):
        mock_get_response.return_value = {"response": "Load test response"}

        responses = []
        for _ in range(10):
            response = self.client.get("/response")
            responses.append(response.status_code)

        self.assertTrue(all(status == 200 for status in responses))

    @patch('app.services.ai_service.get_response')
    def test_recovery_from_failures(self, mock_get_response):
        mock_get_response.side_effect = [Exception("Temporary Error"), {"response": "Recovered"}]

        first_response = self.client.get("/response")
        self.assertEqual(first_response.status_code, 500)

        second_response = self.client.get("/response")
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.json(), {"response": "Recovered"})

if __name__ == '__main__':
    unittest.main()