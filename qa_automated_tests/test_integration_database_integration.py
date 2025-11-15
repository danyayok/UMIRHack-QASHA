import unittest
from unittest.mock import patch, MagicMock
from app.main import app
from app.models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
import json


class TestDatabaseIntegration(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.app = TestClient(app)

    def tearDown(self):
        Base.metadata.drop_all(self.engine)

    @patch('app.main.get_db')
    def test_data_flow_between_components(self, mock_get_db):
        mock_db = self.SessionLocal()
        mock_get_db.return_value = mock_db

        response = self.app.post("/register", json={"username": "testuser", "password": "testpass"})
        self.assertEqual(response.status_code, 200)

        result = mock_db.execute("SELECT * FROM users WHERE username = 'testuser'").fetchone()
        self.assertIsNotNone(result)

    @patch('app.main.get_db')
    def test_error_propagation_across_services(self, mock_get_db):
        mock_db = self.SessionLocal()
        mock_get_db.return_value = mock_db
        mock_get_db.side_effect = Exception("DB Error")

        response = self.app.post("/register", json={"username": "testuser", "password": "testpass"})
        self.assertEqual(response.status_code, 500)
        self.assertIn("DB Error", response.text)

    @patch('app.main.get_db')
    def test_transaction_consistency(self, mock_get_db):
        mock_db = self.SessionLocal()
        mock_get_db.return_value = mock_db

        response = self.app.post("/register", json={"username": "testuser", "password": "testpass"})
        self.assertEqual(response.status_code, 200)

        user_count = mock_db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        self.assertEqual(user_count, 1)

    @patch('app.main.get_db')
    def test_performance_under_load(self, mock_get_db):
        mock_db = self.SessionLocal()
        mock_get_db.return_value = mock_db

        for i in range(100):
            response = self.app.post("/register", json={"username": f"user{i}", "password": "pass"})
            self.assertEqual(response.status_code, 200)

        user_count = mock_db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        self.assertEqual(user_count, 100)

    @patch('app.main.get_db')
    def test_recovery_from_failures(self, mock_get_db):
        mock_db = self.SessionLocal()
        mock_get_db.return_value = mock_db

        mock_get_db.side_effect = [Exception("DB Error"), mock_db]

        response = self.app.post("/register", json={"username": "testuser", "password": "testpass"})
        self.assertEqual(response.status_code, 500)

        response = self.app.post("/register", json={"username": "testuser", "password": "testpass"})
        self.assertEqual(response.status_code, 200)

        user_count = mock_db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        self.assertEqual(user_count, 1)


if __name__ == '__main__':
    unittest.main()