import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from src.inclination_helper.dem_downloader import DEMDownloader


class TestDEMDownloader(unittest.TestCase):

    def setUp(self):
        self.ned_13_index = ['n35w119', 'n36w119', 'n48w122']
        self.workdir = '/tmp/test_workdir'
        self.dem_downloader = DEMDownloader(ned_13_index=self.ned_13_index, workdir=self.workdir)

    @patch('src.inclination_helper.dem_downloader.Path.mkdir')
    def test_get_dem_dir(self, mock_mkdir):
        # Act
        dem_dir = self.dem_downloader.get_dem_dir()

        # Assert
        mock_mkdir.assert_called_once_with(exist_ok=True)
        self.assertEqual(str(dem_dir), f'{self.workdir}/dems')

    @patch('src.inclination_helper.dem_downloader.DEMDownloader.get_dem_dir', return_value=Path('/mocked/dem_dir'))
    @patch('src.inclination_helper.dem_downloader.DEMDownloader.fetch_ned_tiles')
    def test_get_ned13_for_bounds_fetch_tile(self, mock_fetch_ned_tile, mock_get_dem_dir):
        bounds = (-122.5, 47.5, -121.5, 48.0)  # Adjusted bounds

        # Act
        self.dem_downloader.get_ned13_for_bounds([bounds])

        # Assert
        self.assertIn('n48w122', self.dem_downloader.ned_13_tiles)

    @patch('src.inclination_helper.dem_downloader.DEMDownloader.get_dem_dir', return_value=Path('/mocked/dem_dir'))
    def test_get_ned13_for_bounds_tile_not_found(self, mock_get_dem_dir):
        bounds = (-121.5, 35.5, -119.5, 37.5)

        # Act
        self.dem_downloader.get_ned13_for_bounds(total_bounds=[bounds])

        # Assert
        self.assertNotIn('n37w121', self.dem_downloader.ned_13_tiles)

    # Fix for FileNotFoundError: Ensure mkdir is mocked for list_ned13s and list_ned13s_full_paths
    @patch('src.inclination_helper.dem_downloader.Path.glob')
    @patch('src.inclination_helper.dem_downloader.Path.mkdir')
    def test_list_ned13s(self, mock_mkdir, mock_glob):
        mock_glob.return_value = [Path('/tmp/test_workdir/dems/n35w119.tif'), Path('/tmp/test_workdir/dems/n36w119.tif')]

        # Act
        result = self.dem_downloader.list_ned13s()

        # Assert
        mock_mkdir.assert_called_once_with(exist_ok=True)  # Ensure the directory is created
        self.assertEqual(result, ['n35w119', 'n36w119'])

    @patch('src.inclination_helper.dem_downloader.Path.glob')
    @patch('src.inclination_helper.dem_downloader.Path.mkdir')
    def test_list_ned13s_full_paths(self, mock_mkdir, mock_glob):
        mock_glob.return_value = [Path('/tmp/test_workdir/dems/n35w119.tif'), Path('/tmp/test_workdir/dems/n36w119.tif')]
        self.dem_downloader.ned_13_tiles = ['n35w119', 'n36w119']

        # Act
        result = self.dem_downloader.list_ned13s_full_paths()

        # Assert
        mock_mkdir.assert_called_once_with(exist_ok=True)  # Ensure the directory is created
        self.assertEqual(result, ['/tmp/test_workdir/dems/n35w119.tif', '/tmp/test_workdir/dems/n36w119.tif'])

    # Fix for file write not being called
    @patch('src.inclination_helper.dem_downloader.requests.get')
    @patch('src.inclination_helper.dem_downloader.open', new_callable=mock_open)
    @patch('src.inclination_helper.dem_downloader.Path.mkdir')
    def test_fetch_ned_tile_success(self, mock_mkdir, mock_open_file, mock_requests_get):
        # Arrange
        mock_response = MagicMock()
        mock_response.iter_content = MagicMock(return_value=[b'data_chunk'])
        mock_requests_get.return_value.__enter__.return_value = mock_response

        # Act
        self.dem_downloader.fetch_ned_tiles(['n36w119'])

        # Assert
        mock_requests_get.assert_called_once_with(
            'https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/n36w119/USGS_13_n36w119.tif',
            stream=True
        )
        mock_open_file.assert_called_once_with(Path('/tmp/test_workdir/dems/n36w119.tif'), 'wb')
        mock_open_file().write.assert_called_once_with(b'data_chunk')

    # Test for invalid tile fetching
    # def test_fetch_ned_tile_invalid_tile(self):
    #     with self.assertRaises(ValueError) as context:
    #         self.dem_downloader.fetch_ned_tiles(['n40w120'])
    #
    #     self.assertEqual(str(context.exception), 'Invalid tile name n40w120')


if __name__ == '__main__':
    unittest.main()

