import unittest
from unittest.mock import patch, MagicMock, mock_open
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
                                                         file_path=None)

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
                                                         file_path='dataset_url')

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
                                                         file_path='dataset_url')

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

    @patch('builtins.open', new_callable=mock_open)  # Mock open to simulate file handling
    def test_upload_to_azure_exception(self, mock_open):
        # Arrange
        mock_open.side_effect = Exception('File open error')

        # Act
        result = self.service.upload_to_azure(job_id='1234', file_path='/tmp/file_path')

        # Assert
        self.assertIsNone(result)

    @patch('builtins.open', new_callable=mock_open)  # Mock open to simulate file handling
    def test_upload_to_azure_container_error(self, mock_open):
        # Arrange
        self.service.storage_client.get_container.side_effect = Exception('Container error')

        # Act
        result = self.service.upload_to_azure(job_id='1234', file_path='/tmp/file_path')

        # Assert
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
