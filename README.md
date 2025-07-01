# cog2zarr

TIFF to Zarr translator library which proposes a new `geo` Zarr v3 [extension](https://zarr-specs.readthedocs.io/en/latest/v3/core/index.html#extensions).  The extension currently supports several different configurations / encodings of georeferencing information (affine transform + CRS):
- CF conventions (via `rioxarray`).
- GDAL raster data model (via `rioxarray`).
- STAC proj extension (via `pystac`).
- GeoTIFF (via `async-tiff`).

Refer to the [jsonschemas](./jsonschemas/) directory for JSON schemas, or the pydantic models [here](./cog_to_zarr/types.py) for more information on each configuration.  See the [examples](./examples) for various examples from a Sentinel2 [STAC item](https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_33UWP_20250620_0_L2A).

**Caveats:**
- Only works on STAC items from the `sentinel-2-l2a` EarthSearch collection (https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a).  It may work on Microsoft PC but I haven't tested this yet.
- Ignores georectification / georeferencing edge-cases such as RPCs and GRPCs.  The code assumes the image has an affine transform + CRS information, which is true for the large majority of TIFFs found in the wild.
- The `geo` zarr extension is stored in the `attributes` key of each zarr group (`node_type = 'group'`).  Zarr extensions are supposed to be stored at the top level of the zarr group, however `zarr-python` doesn't support this yet.
- You must use `xarray.open_datatree("path/to/group.zarr", consolidated=True, engine="zarr")` to open these.  `xarray.open_dataset` does not work, and I'm not sure why.


## Usage

```shell
git clone https://github.com/geospatial-jeff/cog2zarr
pip install poetry==2.1.3
poetry install
```

## CLI

The CLI provides one command to generate JSON schemas and another to convert a STAC item to zarr.

```shell
Usage: cog2zarr [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  convert             Convert STAC item to zarr
  create-json-schema  Create JSON schemas.
```

The `convert` command has several options which determine how the resulting Zarr store is created:

```shell
Usage: cog2zarr convert [OPTIONS] STAC_ITEM_ID OUT_STORE

  Convert STAC item to zarr

Options:
  --extension-type [stac|gdal|cf|geotiff]
                                  [required]
  --group-layout [planar|chunky]  [required]
  --chunk-size-x INTEGER          [required]
  --chunk-size-y INTEGER          [required]
  --simple / --complex            [required]
  --help                          Show this message and exit.
```

- Sentinel2 is typically organized into a single TIFF file per band.  The `--group-layout` parameter determines how these individual TIFFs are organized into zarr groups.  `chunky` creates one Zarr group for each homogenous set of bands (ex. `10m`, `20m`, and `60m`), and `planar` creates a single Zarr group for each band.  The `chunky` layout offers more efficient encoding of geospatial metadata with smaller consolidated metadata, and allows the user to potentially chunk each Zarr array across multiple bands which is ideal for accessing the same pixel across multiple bands (ex. R/G/B composite).  While the `planar` layout is best for accessing individual bands, but requires duplicating the geospatial metadata multiple times.
- The `geo` extension contains all geospatial metadata required to georeference the Zarr array.  `rioxarray`, by default, includes the `bands`, `x`, and `y` variables when saving to Zarr.  The `--simple` flag may be added to drop these variables, greatly reducing the size of the Zarr store.  The default (`--complex`) is to include these variables as they are important for interoperability with current software.


## Examples

The [examples](./examples/) included in the repo were generated with the following commands:

```shell
# First example.
cog2zarr convert S2A_33UWP_20250620_0_L2A \
 examples/S2A_33UWP_20250620_0_L2A/stac_chunky_simple.zarr \
 --extension-type stac \
 --group-layout chunky \
 --simple

# Second example.
cog2zarr convert \
 S2A_33UWP_20250620_0_L2A \
 examples/S2A_33UWP_20250620_0_L2A/cf_planar.zarr \
 --extension-type cf \
 --group-layout planar

# Third example.
cog2zarr convert \
 S2A_33UWP_20250620_0_L2A \
 examples/S2A_33UWP_20250620_0_L2A/gdal_chunky.zarr \
 --extension-type gdal \
 --group-layout chunk
```

## Python Usage

You may also call this library through python, see the example below:

```python
from datetime import date
from pathlib import Path

import pystac_client

from cog_to_zarr import cog_to_zarr
from cog_to_zarr.types import GeoZarrExtensionType, GroupLayout

# 1. Query Earth-Search for a recent, low-cloud Sentinel-2 L2A scene.
API = "https://earth-search.aws.element84.com/v1"
coll = "sentinel-2-l2a"
bbox = [16.20, 48.10, 16.45, 48.30]  # Vienna
today = date.today()
last_year = today.replace(year=today.year - 1)
daterange = f"{last_year:%Y-%m-%d}/{today:%Y-%m-%d}"

item = next(
    pystac_client.Client.open(API)
    .search(
        collections=[coll],
        bbox=bbox,
        datetime=daterange,
        query={"eo:cloud_cover": {"lt": 5}},
        limit=1,
    )
    .items(),
    None,
)

cog_to_zarr.convert(
    item,
    Path("output.zarr"),
    extension_type=GeoZarrExtensionType.stac,
    group_layout=GroupLayout.chunky,
    simple=True
)
```
