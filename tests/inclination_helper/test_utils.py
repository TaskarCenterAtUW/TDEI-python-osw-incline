import os
import zipfile
import unittest
from unittest.mock import patch, call
from src.inclination_helper.utils import get_unique_id, unzip, clean_up, create_zip


class TestUtils(unittest.TestCase):

    @patch('src.inclination_helper.utils.uuid.uuid1')
    def test_get_unique_id(self, mock_uuid):
        # Arrange
        mock_uuid.return_value.hex = '1234567890abcdef1234567890abcdef'

        # Act
        result = get_unique_id()

        # Assert
        self.assertEqual(result, '1234567890abcdef12345678')
        mock_uuid.assert_called_once()

    @patch('src.inclination_helper.utils.zipfile.ZipFile')
    def test_unzip(self, mock_zipfile):
        # Arrange
        zip_file_path = 'test.zip'
        output_path = 'output'
        mock_zip = mock_zipfile.return_value.__enter__.return_value
        mock_zip.namelist.return_value = ['nodes.csv', 'edges.csv', 'unrelated_file.txt']

        # Act
        file_locations, full_paths = unzip(zip_file_path, output_path)

        # Assert
        self.assertEqual(file_locations, {
            'nodes': os.path.join(output_path, 'nodes.csv'),
            'edges': os.path.join(output_path, 'edges.csv')
        })
        self.assertEqual(full_paths, [
            os.path.join(output_path, 'nodes.csv'),
            os.path.join(output_path, 'edges.csv'),
            os.path.join(output_path, 'unrelated_file.txt')
        ])
        mock_zip.extractall.assert_called_once_with(output_path)

    @patch('src.inclination_helper.utils.os.path.isfile', return_value=True)
    @patch('src.inclination_helper.utils.os.remove')
    def test_clean_up_file(self, mock_remove, mock_isfile):
        # Arrange
        path = 'test.txt'

        # Act
        clean_up(path)

        # Assert
        mock_isfile.assert_called_once_with(path)
        mock_remove.assert_called_once_with(path)

    @patch('src.inclination_helper.utils.os.path.isfile', return_value=False)
    @patch('src.inclination_helper.utils.shutil.rmtree')
    def test_clean_up_directory(self, mock_rmtree, mock_isfile):
        # Arrange
        path = 'test_directory'

        # Act
        clean_up(path)

        # Assert
        mock_isfile.assert_called_once_with(path)
        mock_rmtree.assert_called_once_with(path, ignore_errors=True)

    @patch('src.inclination_helper.utils.zipfile.ZipFile')
    def test_create_zip(self, mock_zipfile):
        # Arrange
        files = ['file1.txt', 'file2.txt']
        zip_file_path = 'output.zip'
        mock_zip_writer = mock_zipfile.return_value.__enter__.return_value
        mock_zip_reader = mock_zipfile.return_value.__enter__.return_value
        mock_zip_reader.namelist.return_value = ['file1.txt', 'file2.txt']

        # Act
        with patch('src.inclination_helper.utils.os.path.isfile', return_value=True):
            result = create_zip(files, zip_file_path)

        # Assert
        self.assertEqual(result, zip_file_path)
        self.assertEqual(mock_zipfile.call_count, 2)
        mock_zipfile.assert_any_call(zip_file_path, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True)
        mock_zipfile.assert_any_call(zip_file_path, 'r')

        # Check that write was called with the correct arguments
        mock_zip_writer.write.assert_has_calls([
            call('file1.txt', 'file1.txt'),
            call('file2.txt', 'file2.txt')
        ], any_order=True)


if __name__ == '__main__':
    unittest.main()
