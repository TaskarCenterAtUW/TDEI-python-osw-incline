import os
import json
import unittest
from unittest.mock import patch, MagicMock, mock_open
from src.inclination_helper.inclination import Inclination


class TestInclination(unittest.TestCase):

    def setUp(self):
        # Reset any static state before each test
        self.file_path = "https://example.com/test.zip"
        self.prefix = "test_prefix"

    @patch('src.inclination_helper.inclination.get_unique_id', return_value='test_unique_id')
    @patch('src.inclination_helper.inclination.urlparse')
    @patch('src.inclination_helper.inclination.os.path.exists', return_value=False)
    @patch('src.inclination_helper.inclination.os.makedirs')
    @patch('src.inclination_helper.inclination.Core')
    def test_inclination_init(self, mock_core, mock_makedirs, mock_exists, mock_urlparse, mock_get_unique_id):
        # Arrange
        mock_storage_client = MagicMock()
        mock_core.return_value.get_storage_client.return_value = mock_storage_client
        mock_urlparse.return_value.path = "/path/to/test.zip"

        # Act
        inclination = Inclination(file_path=self.file_path)

        # Assert
        self.assertEqual(inclination.file_path, self.file_path)
        self.assertEqual(inclination.prefix, 'test_unique_id')
        mock_makedirs.assert_called_once()  # Ensure directory is created
        mock_exists.assert_called_once_with(inclination.download_dir)
        mock_core.return_value.get_storage_client.assert_called_once()

    @patch('src.inclination_helper.inclination.open', new_callable=mock_open)
    @patch('src.inclination_helper.inclination.create_zip')
    @patch('src.inclination_helper.inclination.OSWIncline')
    @patch('src.inclination_helper.inclination.DEMDownloader')
    @patch('src.inclination_helper.inclination.Path')
    @patch('src.inclination_helper.inclination.unzip')
    @patch('src.inclination_helper.inclination.Core')
    def test_calculate_inclination(self, mock_core, mock_unzip, mock_path, mock_dem_downloader, mock_osw_incline,
                                   mock_create_zip, mock_open):
        # Arrange
        # Mock for the 'ned_13_index.json' file
        ned_13_index_content = json.dumps({"tiles": ["tile1", "tile2"]})

        # Mock for the 'edges' file content with valid geometry
        edge_file_content = json.dumps({
            "features": [
                {
                    "geometry": {
                        "type": "Point",
                        "coordinates": [100.0, 0.0]
                    }
                }
            ]
        })

        # Set up the mock 'open' to return correct content when 'read' is called
        mock_open().read.side_effect = [ned_13_index_content, edge_file_content]

        mock_storage_client = MagicMock()
        mock_core.return_value.get_storage_client.return_value = mock_storage_client

        # Mocking unzip to return file paths for nodes and edges
        mock_unzip.return_value = (
            {'nodes': 'nodes_file_path', 'edges': 'edges_file_path'},
            ['nodes_file_path', 'edges_file_path']
        )

        mock_osw_incline.return_value.calculate.return_value = True
        mock_create_zip.return_value = 'output.zip'

        inclination = Inclination(file_path=self.file_path, prefix=self.prefix)

        # Act
        result = inclination.calculate()

        # Assert
        self.assertEqual(result, 'output.zip')
        mock_unzip.assert_called_once()
        mock_create_zip.assert_called_once_with(
            files=['nodes_file_path', 'edges_file_path'],
            zip_file_path=os.path.join(inclination.download_dir, f'{self.prefix}/{inclination.updated_file_name}')
        )
        mock_osw_incline.return_value.calculate.assert_called_once()
        mock_dem_downloader.return_value.get_ned13_for_bounds.assert_called()

    @patch('src.inclination_helper.inclination.open', new_callable=mock_open,
           read_data='{"features":[]}')  # Mock the JSON file reading
    @patch('src.inclination_helper.inclination.os.path.exists', return_value=True)
    @patch('src.inclination_helper.inclination.os.makedirs')
    @patch('src.inclination_helper.inclination.Core')
    @patch('src.inclination_helper.inclination.get_unique_id', return_value='test_unique_id')
    def test_download_file(self, mock_get_unique_id, mock_core, mock_makedirs, mock_exists, mock_open):
        # Arrange
        storage_client = MagicMock()
        mock_core.return_value.get_storage_client.return_value = storage_client
        mock_file = MagicMock()
        mock_file.file_path = '/path/to/file.txt'
        mock_file.get_stream.return_value = b'test_data'
        storage_client.get_file_from_url.return_value = mock_file

        inclination = Inclination(file_path=self.file_path, prefix=self.prefix)

        # Act
        result = inclination.download_file(self.file_path)

        # Assert
        self.assertTrue(result.endswith('file.txt'))
        mock_open.assert_called_once_with(result, 'wb')
        mock_file.get_stream.assert_called_once()

    @patch('src.inclination_helper.inclination.Core')
    @patch('builtins.open', new_callable=mock_open)
    def test_download_file_error(self, mock_open, mock_core):
        # Arrange
        mock_storage_client = MagicMock()
        mock_core.return_value.get_storage_client.return_value = mock_storage_client
        mock_storage_client.get_file_from_url.return_value.file_path = None

        inclination = Inclination(file_path=self.file_path)

        # Act and Assert
        with self.assertRaises(Exception) as context:
            inclination.download_file(self.file_path)

        self.assertTrue('File not found' in str(context.exception))

    @patch('src.inclination_helper.inclination.Core')
    @patch('builtins.open', new_callable=mock_open)
    def test_download_file_exception(self, mock_open, mock_core, ):
        # Arrange
        mock_storage_client = MagicMock()
        mock_core.return_value.get_storage_client.return_value = mock_storage_client
        mock_storage_client.get_file_from_url.side_effect = Exception('Download error')

        inclination = Inclination(file_path=self.file_path)

        # Act and Assert
        with self.assertRaises(Exception) as context:
            inclination.download_file(self.file_path)

        self.assertTrue('Download error' in str(context.exception))


if __name__ == '__main__':
    unittest.main()
