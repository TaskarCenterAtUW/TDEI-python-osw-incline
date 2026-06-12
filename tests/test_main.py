import unittest
import asyncio
from fastapi import status
from src.main import app, get_settings
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from src.main import startup_event, shutdown_event


class TestApp(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        app.incline_service = None

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

    @patch('src.main.InclinationService')
    @patch('src.main.os.makedirs')
    @patch('src.main.os.path.exists', return_value=False)
    @patch('src.main.Settings')
    def test_startup_event_success(self, mock_settings, mock_exists, mock_makedirs, mock_inclination_service):
        mock_settings_obj = MagicMock()
        mock_settings_obj.get_download_directory.return_value = '/tmp/downloads'
        mock_settings.return_value = mock_settings_obj
        mock_service = MagicMock()
        mock_inclination_service.return_value = mock_service

        asyncio.run(startup_event())

        mock_makedirs.assert_called_once_with('/tmp/downloads')
        self.assertEqual(app.incline_service, mock_service)

    @patch('src.main.os._exit')
    @patch('src.main.Settings', side_effect=Exception('invalid settings'))
    def test_startup_event_failure_without_psutil(self, mock_settings, mock_exit):
        import builtins
        original_import = builtins.__import__

        def import_side_effect(name, *args, **kwargs):
            if name == 'psutil':
                raise ModuleNotFoundError('No module named psutil')
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=import_side_effect):
            asyncio.run(startup_event())

        mock_exit.assert_called_once_with(1)

    @patch('src.main.Settings', side_effect=Exception('invalid settings'))
    @patch('src.main.os.getpid', return_value=123)
    def test_startup_event_failure_with_psutil(self, mock_getpid, mock_settings):
        fake_child = MagicMock()
        fake_parent = MagicMock()
        fake_parent.children.return_value = [fake_child]

        fake_psutil_module = MagicMock()
        fake_psutil_module.Process.return_value = fake_parent

        with patch.dict('sys.modules', {'psutil': fake_psutil_module}):
            asyncio.run(startup_event())

        fake_parent.children.assert_called_once_with(recursive=True)
        fake_child.kill.assert_called_once()
        fake_parent.kill.assert_called_once()

    def test_shutdown_event_with_service(self):
        mock_service = MagicMock()
        app.incline_service = mock_service
        asyncio.run(shutdown_event())
        mock_service.stop_listening.assert_called_once()

    def test_shutdown_event_without_service(self):
        app.incline_service = None
        asyncio.run(shutdown_event())


if __name__ == '__main__':
    unittest.main()
