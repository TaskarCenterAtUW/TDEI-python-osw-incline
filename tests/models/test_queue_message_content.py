import unittest
from src.models.queue_message_content import RequestMessage, IncomingData


class TestRequestMessage(unittest.TestCase):

    def test_from_dict_with_complete_data(self):
        # Arrange
        data = {
            'messageId': '12345',
            'messageType': 'JobRequest',
            'data': {
                'dataset_url': 'http://example.com/data',
                'user_id': 'user_001',
                'jobId': 'job_001'
            }
        }

        # Act
        result = RequestMessage.from_dict(data)

        # Assert
        self.assertIsInstance(result, RequestMessage)
        self.assertEqual(result.messageId, '12345')
        self.assertEqual(result.messageType, 'JobRequest')
        self.assertIsInstance(result.data, IncomingData)
        self.assertEqual(result.data.dataset_url, 'http://example.com/data')
        self.assertEqual(result.data.user_id, 'user_001')
        self.assertEqual(result.data.jobId, 'job_001')

    def test_from_dict_with_missing_data_field(self):
        # Arrange
        data = {
            'messageId': '12345',
            'messageType': 'JobRequest',
            'data': None  # Missing data field
        }

        # Act
        result = RequestMessage.from_dict(data)

        # Assert
        self.assertIsInstance(result, RequestMessage)
        self.assertEqual(result.messageId, '12345')
        self.assertEqual(result.messageType, 'JobRequest')
        self.assertIsNone(result.data)  # Expecting data to be None

    def test_from_dict_with_incomplete_incoming_data(self):
        # Arrange
        data = {
            'messageId': '12345',
            'messageType': 'JobRequest',
            'data': {
                'dataset_url': 'http://example.com/data',
                # 'user_id' is missing
                'jobId': 'job_001'
            }
        }

        # Act and Assert
        with self.assertRaises(TypeError) as context:
            RequestMessage.from_dict(data)

        # Ensure the error message is related to the missing 'user_id' field
        self.assertIn("missing 1 required positional argument: 'user_id'", str(context.exception))


if __name__ == '__main__':
    unittest.main()
