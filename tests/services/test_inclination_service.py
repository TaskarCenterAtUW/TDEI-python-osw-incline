import unittest
from unittest.mock import patch, MagicMock, mock_open
import signal
from src.services.inclination_service import InclinationService


class TestInclinationService(unittest.TestCase):

    @patch('src.services.inclination_service.Settings')
    @patch('src.services.inclination_service.Core')
    def setUp(self, mock_core, mock_settings):
        # Mock Settings
        mock_settings.return_value.event_bus.request_subscription = 'test_subscription'
        mock_settings.return_value.event_bus.request_topic = 'test_request_topic'
        mock_settings.return_value.event_bus.response_topic = 'test_response_topic'
        mock_settings.return_value.max_concurrent_messages = 10
        mock_settings.return_value.max_receivable_messages = -1
        mock_settings.return_value.get_download_directory.return_value = '/tmp'
        mock_settings.return_value.event_bus.container_name = 'test_container'

        # Mock Core
        mock_core.return_value.get_topic.return_value = MagicMock()
        mock_core.return_value.get_storage_client.return_value = MagicMock()

        # Initialize InclinationService with mocked dependencies
        self.service = InclinationService()
        self.service.storage_client = MagicMock()
        self.service.container_name = 'test_container'

    @patch('src.services.inclination_service.QueueMessage')
    @patch('src.services.inclination_service.RequestMessage')
    def test_subscribe_with_valid_message(self, mock_request_message, mock_queue_message):
        # Arrange
        mock_message = MagicMock()
        mock_queue_message.to_dict.return_value = {'messageId': '1234', 'data': {'jobId': '5678'}}
        mock_request_message.from_dict.return_value = mock_request_message
        self.service.process_message = MagicMock()

        # Act
        self.service.subscribe()
        callback = self.service.request_topic.subscribe.call_args[1]['callback']
        callback(mock_message)

        # Assert
        self.service.process_message.assert_called_once_with(mock_request_message)

    @patch('src.services.inclination_service.QueueMessage')
    @patch('src.services.inclination_service.RequestMessage')
    @patch('src.services.inclination_service.Logger')
    def test_subscribe_with_none_message(self, mock_logger, mock_request_message, mock_queue_message):
        self.service.process_message = MagicMock()
        self.service.subscribe()
        callback = self.service.request_topic.subscribe.call_args[1]['callback']
        callback(None)
        self.service.process_message.assert_not_called()
        mock_logger.info.assert_called_with(' No Message')

    def test_subscribe_triggers_shutdown_when_max_receivable_positive(self):
        self.service._config.max_receivable_messages = 1
        self.service._stop_server_and_container = MagicMock()

        self.service.subscribe()

        last_call_kwargs = self.service.request_topic.subscribe.call_args_list[-1][1]
        self.assertIn('subscription', last_call_kwargs)
        self.assertIn('callback', last_call_kwargs)
        self.assertEqual(last_call_kwargs['max_receivable_messages'], 1)
        self.service._stop_server_and_container.assert_called_once_with(delay_seconds=2)

    @patch('src.services.inclination_service.get_unique_id', return_value='unique_id')
    @patch('src.services.inclination_service.Inclination')
    def test_process_message_with_valid_file_path(self, mock_inclination, mock_get_unique_id):
        # Arrange
        mock_request_message = MagicMock()
        mock_request_message.data.jobId = None
        mock_request_message.data.dataset_url = 'test_dataset_url'
        mock_inclination_instance = mock_inclination.return_value
        mock_inclination_instance.calculate.return_value = 'calculated_file_path'
        self.service.upload_to_azure = MagicMock(return_value='uploaded_file_path')
        self.service.send_status = MagicMock()

        # Act
        self.service.process_message(mock_request_message)

        # Assert
        self.service.upload_to_azure.assert_called_once_with(file_path='calculated_file_path', job_id='unique_id')
        self.service.send_status.assert_called_once_with(valid=True, request_message=mock_request_message,
                                                         file_path='uploaded_file_path')

    @patch('src.services.inclination_service.get_unique_id', return_value='unique_id')
    @patch('src.services.inclination_service.Inclination')
    def test_process_message_marks_invalid_if_upload_fails(self, mock_inclination, mock_get_unique_id):
        # Arrange
        mock_request_message = MagicMock()
        mock_request_message.data.jobId = None
        mock_request_message.data.dataset_url = 'test_dataset_url'
        mock_inclination.return_value.calculate.return_value = 'calculated_file_path'
        self.service.upload_to_azure = MagicMock(return_value=None)
        self.service.send_status = MagicMock()

        # Act
        self.service.process_message(mock_request_message)

        # Assert
        self.service.send_status.assert_called_once_with(
            valid=False,
            request_message=mock_request_message,
            file_path='calculated_file_path',
            upload_message='Error: Failed to upload processed file to storage'
        )

    @patch('src.services.inclination_service.Logger')
    @patch('src.services.inclination_service.get_unique_id', return_value='unique_id')
    @patch('src.services.inclination_service.Inclination')
    def test_process_message_with_invalid_file_path(self, mock_inclination, mock_get_unique_id, mock_logger):
        # Arrange
        mock_request_message = MagicMock()
        mock_request_message.data.jobId = None
        mock_request_message.data.dataset_url = None
        self.service.send_status = MagicMock()

        # Act
        self.service.process_message(mock_request_message)

        # Assert
        self.service.send_status.assert_called_once_with(valid=False, request_message=mock_request_message,
                                                         file_path=None, upload_message='Error: Request does not have valid file path specified.')

    @patch('src.services.inclination_service.Logger')
    @patch('src.services.inclination_service.Inclination')
    def test_process_message_when_file_path_is_none_and_valid_is_false(self, mock_inclination, mock_logger):
        # Arrange
        mock_request_message = MagicMock()
        mock_request_message.data.jobId = '123'
        mock_request_message.data.dataset_url = 'dataset_url'
        mock_inclination.return_value.calculate.return_value = None
        self.service.send_status = MagicMock()

        # Act
        self.service.process_message(mock_request_message)

        # Assert
        self.service.send_status.assert_called_once_with(valid=False, request_message=mock_request_message,
                                                         file_path=None, upload_message='Error: Failed to generate processed file')

    @patch('src.services.inclination_service.Logger')
    @patch('src.services.inclination_service.Inclination')
    def test_process_message_when_exception_is_raised(self, mock_inclination, mock_logger):
        # Arrange
        mock_request_message = MagicMock()
        mock_request_message.data.jobId = '123'
        mock_request_message.data.dataset_url = 'dataset_url'
        self.service.send_status = MagicMock()

        # Mock Inclination to raise an exception
        mock_inclination.side_effect = Exception('Some error occurred')

        # Act
        self.service.process_message(mock_request_message)

        # Assert
        self.service.send_status.assert_called_once_with(valid=False, request_message=mock_request_message,
                                                         file_path='dataset_url', upload_message='Error: Some error occurred')

    @patch('src.services.inclination_service.QueueMessage')
    def test_send_status_success(self, mock_queue_message):
        # Arrange
        mock_request_message = MagicMock()
        mock_response_topic = self.service.core.get_topic.return_value
        mock_data = {'messageId': '1234', 'messageType': 'test', 'data': {'success': True}}
        mock_queue_message.data_from.return_value = mock_data

        # Act
        self.service.send_status(valid=True, request_message=mock_request_message, file_path='file_path')

        # Assert
        mock_queue_message.data_from.assert_called_once()
        mock_response_topic.publish.assert_called_once_with(data=mock_data)

    @patch('src.services.inclination_service.QueueMessage')
    def test_send_status_with_error_message(self, mock_queue_message):
        mock_request_message = MagicMock()
        mock_data = {'messageId': '1234', 'messageType': 'test', 'data': {'success': False}}
        mock_queue_message.data_from.return_value = mock_data

        self.service.send_status(
            valid=False,
            request_message=mock_request_message,
            file_path='file_path',
            upload_message='Error: failed'
        )

        payload = mock_queue_message.data_from.call_args[0][0]
        self.assertEqual(payload['data']['message'], 'Error: failed')

    @patch('src.services.inclination_service.os.path.getsize', return_value=10)
    @patch('builtins.open', new_callable=mock_open)  # Mock open to simulate file handling
    def test_upload_to_azure_exception(self, mock_open, mock_getsize):
        # Arrange
        mock_open.side_effect = Exception('File open error')

        # Act
        result = self.service.upload_to_azure(job_id='1234', file_path='/tmp/file_path')

        # Assert
        self.assertIsNone(result)

    @patch('src.services.inclination_service.os.path.getsize', return_value=10)
    @patch('builtins.open', new_callable=mock_open)
    def test_upload_to_azure_container_error(self, mock_open, mock_getsize):
        # Arrange
        self.service.storage_client.get_container.side_effect = Exception('Container error')

        # Act
        result = self.service.upload_to_azure(job_id='1234', file_path='/tmp/file_path')

        # Assert
        self.assertIsNone(result)

    @patch('src.services.inclination_service.threading.Thread')
    def test_stop_listening(self, mock_thread):
        # Arrange
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        self.service.listening_thread = mock_thread_instance
        self.service._shutdown_triggered = MagicMock()
        self.service._shutdown_triggered.is_set.return_value = True

        # Act
        result = self.service.stop_listening()

        # Assert
        mock_thread_instance.join.assert_called_once_with(timeout=0)
        self.assertIsNone(result)

    @patch('src.services.inclination_service.Logger')
    @patch('src.services.inclination_service.threading.Thread')
    def test_stop_server_and_container_skips_when_already_triggered(self, mock_thread, mock_logger):
        self.service._shutdown_triggered = MagicMock()
        self.service._shutdown_triggered.is_set.return_value = True

        self.service._stop_server_and_container()

        mock_logger.info.assert_any_call('Server stop already in progress; skipping duplicate trigger.')
        mock_thread.assert_not_called()

    @patch('src.services.inclination_service.time.sleep')
    @patch('src.services.inclination_service.os._exit')
    @patch('src.services.inclination_service.os.kill')
    @patch('src.services.inclination_service.os.getpid', return_value=999)
    @patch('src.services.inclination_service.threading.Thread')
    def test_stop_server_and_container_terminates_process(
        self, mock_thread, mock_getpid, mock_kill, mock_exit, mock_sleep
    ):
        self.service._shutdown_triggered = MagicMock()
        self.service._shutdown_triggered.is_set.return_value = False

        def make_thread(target=None, daemon=None):
            t = MagicMock()
            t.start.side_effect = lambda: target()
            return t

        mock_thread.side_effect = make_thread

        self.service._stop_server_and_container(delay_seconds=1)

        mock_sleep.assert_called_once_with(1)
        mock_kill.assert_called_once_with(999, signal.SIGTERM)
        mock_exit.assert_called_once_with(0)

    @patch('src.services.inclination_service.Logger')
    @patch('src.services.inclination_service.os._exit')
    @patch('src.services.inclination_service.os.kill', side_effect=Exception('kill failed'))
    @patch('src.services.inclination_service.os.getpid', return_value=999)
    @patch('src.services.inclination_service.threading.Thread')
    def test_stop_server_and_container_handles_kill_error(
        self, mock_thread, mock_getpid, mock_kill, mock_exit, mock_logger
    ):
        self.service._shutdown_triggered = MagicMock()
        self.service._shutdown_triggered.is_set.return_value = False

        def make_thread(target=None, daemon=None):
            t = MagicMock()
            t.start.side_effect = lambda: target()
            return t

        mock_thread.side_effect = make_thread

        self.service._stop_server_and_container(delay_seconds=0)

        mock_logger.warning.assert_called()
        mock_exit.assert_called_once_with(0)

    @patch('src.services.inclination_service.os.path.getsize', return_value=10)
    @patch('builtins.open', new_callable=mock_open, read_data='file data')
    def test_upload_to_azure_success(self, mock_file, mock_getsize):
        job_id = 'test_job_id'
        file_path = '/path/to/test_file.geojson'

        mock_container = MagicMock()
        self.service.storage_client.get_container.return_value = mock_container

        mock_file_obj = MagicMock()
        mock_container.create_file.return_value = mock_file_obj
        mock_file_obj.get_remote_url.return_value = 'https://azure.example.com/test-container/jobs/test_job_id/test_file.geojson'

        result = self.service.upload_to_azure(job_id, file_path)

        self.service.storage_client.get_container.assert_called_once_with(container_name='test_container')
        mock_container.create_file.assert_called_once_with(name='jobs/test_job_id/test_file.geojson')
        mock_file.assert_called_once_with(file_path, 'rb')
        mock_file_obj.upload.assert_called_once_with(mock_file())
        self.assertEqual(result, 'https://azure.example.com/test-container/jobs/test_job_id/test_file.geojson')

    @patch('src.services.inclination_service.os.path.getsize', return_value=0)
    def test_upload_to_azure_empty_file(self, mock_getsize):
        result = self.service.upload_to_azure(job_id='1234', file_path='/tmp/file_path')
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
