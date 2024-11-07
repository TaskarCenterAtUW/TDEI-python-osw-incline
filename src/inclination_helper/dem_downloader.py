import gc
import time
import math
import requests
from pathlib import Path
import concurrent.futures
from src.logger import Logger


class DEMDownloader:
    TEMPLATE = 'https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/{e}/USGS_13_{e}.tif'

    def __init__(self, ned_13_index, workdir):
        self.ned_13_tiles = []
        self.workdir = workdir
        self.ned_13_index = ned_13_index

    def get_dem_dir(self):
        dem_path = Path(self.workdir, 'dems')
        dem_path.mkdir(exist_ok=True)
        return dem_path

    def download_tile(self, tile_name: str):
        if tile_name not in self.ned_13_index:
            raise ValueError(f'Invalid tile name {tile_name}')

        url = self.TEMPLATE.format(e=tile_name)
        filename = f'{tile_name}.tif'
        dem_dir = self.get_dem_dir()
        path = Path(dem_dir, filename)

        start_time = time.time()
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        end_time = time.time()
        Logger.info(f'{tile_name} downloaded in {end_time - start_time} seconds')

        gc.collect()

    def fetch_ned_tiles(self, tile_names, max_workers=4):
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_tile = {
                executor.submit(self.download_tile, tile_name): tile_name
                for tile_name in tile_names
            }

            # Iterate over the results as they complete
            for future in concurrent.futures.as_completed(future_to_tile):
                tile_name = future_to_tile[future]
                try:
                    future.result()
                    Logger.info(f'Tile {tile_name} downloaded successfully')
                except Exception as exc:
                    Logger.info(f'Tile {tile_name} generated an exception: {exc}')
        gc.collect()

    def get_ned13_for_bounds(self, total_bounds):
        for bounds in total_bounds:
            north_min = int(math.floor(bounds[1]))
            north_max = int(math.ceil(bounds[3]))
            west_min = int(math.floor(-1 * bounds[2]))
            west_max = int(math.ceil(-1 * bounds[0]))
            for n in range(north_min + 1, north_max + 1):
                for w in range(west_min + 1, west_max + 1):
                    tile = f'n{n}w{w:03}'
                    if tile in self.ned_13_index:
                        if tile in self.ned_13_tiles:
                            pass
                        else:
                            self.ned_13_tiles.append(tile)
                    else:
                        Logger.warning(f'Tile not found {tile}')
                        pass

        # Check temporary dir for these tiles
        cached_tiles = self.list_ned13s()

        fetch_tiles = [tile for tile in self.ned_13_tiles if tile not in cached_tiles]

        if fetch_tiles:
            Logger.info(f"Fetching DEM data for {fetch_tiles}...")

        if len(fetch_tiles) > 0:
            self.fetch_ned_tiles(tile_names=fetch_tiles)

        gc.collect()

    def list_ned13s(self):
        dem_dir = self.get_dem_dir()
        return [Path(tif).stem for tif in dem_dir.glob('*.tif') if Path(tif).stem in self.ned_13_index]

    def list_ned13s_full_paths(self):
        dem_dir = self.get_dem_dir()
        # Return the full path for each matching file
        return [
            str(tif) for tif in dem_dir.glob('*.tif')
            if tif.stem in self.ned_13_index and tif.stem in self.ned_13_tiles
        ]
