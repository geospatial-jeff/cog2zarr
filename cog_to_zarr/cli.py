import json
from pathlib import Path

import click
import pystac_client

from cog_to_zarr import cog_to_zarr
from cog_to_zarr.types import (
    CfConfiguration,
    GdalConfiguration,
    GeoTiffConfiguration,
    GeoZarrExtension,
    GeoZarrExtensionType,
    GroupLayout,
    StacConfiguration,
)

STAC_API_BASE_URL = "https://earth-search.aws.element84.com/v1"
STAC_COLLECTION = "sentinel-2-l2a"


@click.group()
def main():
    pass


@main.command()
@click.argument("outdir", type=click.Path(exists=True, file_okay=False, path_type=Path))
def create_json_schema(outdir: Path):
    """Create JSON schemas."""
    configs = {
        GeoZarrExtensionType.cf: CfConfiguration,
        GeoZarrExtensionType.gdal: GdalConfiguration,
        GeoZarrExtensionType.stac: StacConfiguration,
        GeoZarrExtensionType.geotiff: GeoTiffConfiguration,
    }
    for name, config in configs.items():
        json_schema = GeoZarrExtension[config].model_json_schema()
        with open(outdir / f"{name.value}.json", "w") as outf:
            json.dump(json_schema, outf, indent=2)


@main.command()
@click.argument("stac_item_id", type=str)
@click.argument("out_store", type=click.Path(file_okay=False, path_type=Path))
@click.option(
    "--extension-type", type=click.Choice(GeoZarrExtensionType), required=True
)
@click.option("--group-layout", type=click.Choice(GroupLayout), required=True)
@click.option("--chunk-size-x", type=int, required=True, default=2048)
@click.option("--chunk-size-y", type=int, required=True, default=2048)
@click.option("--simple/--complex", type=bool, default=False, required=True)
def convert(
    stac_item_id: str,
    out_store: Path,
    extension_type: GeoZarrExtensionType,
    group_layout: GroupLayout,
    chunk_size_x: int,
    chunk_size_y: int,
    simple: bool,
):
    """Convert STAC item to zarr"""
    client = pystac_client.Client.open(STAC_API_BASE_URL)
    item = next(
        client.search(
            ids=[stac_item_id], collections=[STAC_COLLECTION], limit=1
        ).items()
    )

    cog_to_zarr.convert(
        item,
        out_store,
        extension_type,
        group_layout,
        chunk_size_x,
        chunk_size_y,
        simple,
    )
