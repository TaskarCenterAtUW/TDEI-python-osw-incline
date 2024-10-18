import logging
import unittest
from src.logger import Logger
from unittest.mock import patch, MagicMock


class TestLogger(unittest.TestCase):

    def setUp(self):
        Logger.logger = None

    @patch('src.logger.logging.getLogger')
    def test_configure_logger(self, mock_get_logger):
        # Arrange
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Act
        result_logger = Logger.configure_logger()

        # Assert
        self.assertEqual(result_logger, mock_logger)
        mock_get_logger.assert_called_once_with('OSW INCLINATION SERVICE')
        mock_logger.setLevel.assert_called_once_with(logging.DEBUG)

    @patch('src.logger.logging.getLogger')
    def test_info_logging(self, mock_get_logger):
        # Arrange
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Act
        Logger.info('This is an info message')

        # Assert
        mock_logger.info.assert_called_once_with('This is an info message', stacklevel=2)

    @patch('src.logger.logging.getLogger')
    def test_error_logging(self, mock_get_logger):
        # Arrange
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Act
        Logger.error('This is an error message')

        # Assert
        mock_logger.error.assert_called_once_with('This is an error message', stacklevel=2)

    @patch('src.logger.logging.getLogger')
    def test_warning_logging(self, mock_get_logger):
        # Arrange
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Act
        Logger.warning('This is a warning message')

        # Assert
        mock_logger.warning.assert_called_once_with('This is a warning message', stacklevel=2)

    @patch('src.logger.logging.getLogger')
    def test_debug_logging(self, mock_get_logger):
        # Arrange
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Act
        Logger.debug('This is a debug message')

        # Assert
        mock_logger.debug.assert_called_once_with('This is a debug message', stacklevel=2)
        mock_logger.setLevel.assert_called_once_with(logging.DEBUG)


if __name__ == '__main__':
    unittest.main()
