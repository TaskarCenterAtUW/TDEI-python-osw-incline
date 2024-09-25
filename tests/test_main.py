import unittest
from fastapi import status
from src.main import app, get_settings
from fastapi.testclient import TestClient


class TestApp(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_root(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.text.strip('\"'), "I'm healthy !!")

    def test_ping(self):
        response = self.client.get('/ping')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.text.strip('\"'), "I'm healthy !!")

    def test_get_settings(self):
        settings = get_settings()
        self.assertIsNotNone(settings)


if __name__ == '__main__':
    unittest.main()
