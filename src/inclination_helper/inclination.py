import os
import gc
import json
from pathlib import Path
from src.logger import Logger
from src.config import Settings
from python_ms_core import Core
from urllib.parse import urlparse
from osw_incline import OSWIncline
from shapely.geometry import shape
from src.inclination_helper.dem_downloader import DEMDownloader
from src.inclination_helper.utils import get_unique_id, unzip, create_zip


class Inclination:
    _config = Settings()

    def __init__(self, file_path=None, storage_client=None, prefix=None):
        self.core = Core()
        if storage_client:
            self.storage_client = storage_client
        else:
            self.storage_client = self.core.get_storage_client()

        self.container_name = self._config.event_bus.container_name
        self.download_dir = self._config.get_download_directory()
        is_exists = os.path.exists(self.download_dir)
        self.file_path = file_path
        self.prefix = get_unique_id() if not prefix else prefix
        parsed_url = urlparse(self.file_path)
        file_name = parsed_url.path.split('/')[-1]
        self.updated_file_name = file_name
        self.root_path = os.path.join(os.getcwd(), 'src')
        if not is_exists:
            os.makedirs(self.download_dir)

    def calculate(self):
        Logger.info(f'Calculating inclination for file: {self.file_path}')
        downloaded_file_path = self.download_file(file_path=self.file_path)
        Logger.info(f'Unzipping file: {downloaded_file_path}')
        unzip_files, all_files = unzip(
            zip_file=downloaded_file_path,
            output=os.path.join(self.download_dir, self.prefix)
        )
        with open(f'{self.root_path}/ned_13_index.json') as f:
            ned_13_index = json.load(f)['tiles']

        dem_downloader = DEMDownloader(ned_13_index=ned_13_index, workdir=self.download_dir)
        graph_nodes_path = Path(unzip_files['nodes'])
        graph_edges_path = Path(unzip_files['edges'])

        with open(graph_edges_path, 'r') as edge_file:
            EDGE_FILE = json.load(edge_file)

        Logger.info(f'No of edges: {len(EDGE_FILE["features"])} to be processed')

        Logger.info('Calculating NED13 files for the bounds')
        bounds = []
        for feature in EDGE_FILE['features']:
            bounds.append(shape(feature['geometry']).bounds)

        dem_downloader.get_ned13_for_bounds(total_bounds=bounds)

        tile_sets = dem_downloader.list_ned13s_full_paths()
        Logger.info(f'No of NED13 files: {len(tile_sets)} to be processed')
        dem_processor = OSWIncline(
            dem_files=tile_sets,
            nodes_file=str(graph_nodes_path),
            edges_file=str(graph_edges_path),
            debug=True
        )
        result = dem_processor.calculate()
        Logger.info(f"Inclination calculation result: {'Completed' if result else 'Failed'}")
        Logger.info(f'Creating zip file for all files')
        zip_file_path = create_zip(
            files=all_files,
            zip_file_path=os.path.join(self.download_dir, f'{self.prefix}/{self.updated_file_name}')
        )

        gc.collect()

        return zip_file_path

    def download_file(self, file_path: str) -> str:
        Logger.info(f'Downloading file from: {file_path}')
        file = self.storage_client.get_file_from_url(container_name=self.container_name, full_url=file_path)
        try:
            if file.file_path:
                file_path = os.path.basename(file.file_path)
                unique_directory = os.path.join(self.download_dir, self.prefix)
                if not os.path.exists(unique_directory):
                    os.makedirs(unique_directory)
                local_download_path = os.path.join(unique_directory, file_path)
                with open(local_download_path, 'wb') as blob:
                    blob.write(file.get_stream())
                return local_download_path
            else:
                Logger.error(f'Error downloading file from: {file_path}')
                raise Exception('File not found')
        except Exception as err:
            Logger.error(f'Error while downloading file: {err}')
            raise err
