import asyncio
import shutil
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

import pystac
import rioxarray as rxr
import xarray as xr
from async_tiff import TIFF
from async_tiff.store import HTTPStore

from cog_to_zarr.types import (
    CfConfiguration,
    GdalConfiguration,
    GeoTiffConfiguration,
    GeoZarrExtension,
    GeoZarrExtensionType,
    GroupLayout,
    StacConfiguration,
)


def _stac_to_xarray(
    stac_item: pystac.Item,
    chunk_size_x: int,
    chunk_size_y: int,
    group_layout: GroupLayout,
) -> dict[str, xr.DataArray]:
    """Convert a STAC item into xarray datasets by parsing each TIFF asset.  Return a dictionary where
    each key/value pair represents a single Zarr group where the key is the name of the group and the value
    is an `xr.DataArray` containing the data.  The goal is to process the assets referenced by the STAC item
    into a normalized format that is easier to work with.  This will probably only work on STAC items from
    https://earth-search.aws.element84.com/v1/sentinel-2-l2a

    `GroupLayout.planar` will create one group for each asset in the STAC item:

        {'red': <xr.DataArray>, 'blue', <xr.DataArray>, ...}

    `GroupLayout.chunky` will concatenate bands with similar spatial resolution into individual groups:

        {'10m': <xr.DataArray>, '20m': xr.DataArray, '60m': xr.DataArray}

    In either case, the resulting <xr.DataArray> each contain a spatially homgenous set of data which may be described
    by a single affine transform and CRS.  I'm sure there is a better way of doing all of this, I'm not too familiar
    with (rio)xarray.
    """
    datasets = {}
    for name, asset in stac_item.assets.items():
        # Skip multi-band and non-tiff assets
        if len(asset.to_dict().get("raster:bands", [])) > 1:
            continue
        if "tif" not in asset.media_type:
            continue
        da = rxr.open_rasterio(
            asset.href,
            chunks={"band": 1, "x": chunk_size_x, "y": chunk_size_y},
            masked=True,
        ).assign_coords(band=[name])
        # Keep track of metadata about the asset, we will rewrite this later.
        da.attrs["_asset_names"] = [name]
        datasets[name] = da

    if group_layout == GroupLayout.chunky:
        # Stack bands with similar spatial resolution.
        grouped_datasets = defaultdict(list)
        grouped_asset_names = defaultdict(list)
        for dataset in datasets.values():
            asset_name = dataset._asset_names[0]
            gsd = stac_item.assets[asset_name].common_metadata.gsd
            grouped_datasets[gsd].append(dataset)
            grouped_asset_names[gsd].append(asset_name)

        # Reorganize the 10m bands into R/G/B/NIR for convenience.
        new_order = [3, 1, 0, 2]
        reordered_rgbnir = [grouped_datasets[10][i] for i in new_order]
        grouped_datasets.pop(10)
        grouped_datasets[10] = reordered_rgbnir
        grouped_asset_names.pop(10)
        grouped_asset_names[10] = [band._asset_names[0] for band in reordered_rgbnir]

        # Concat
        datasets = {k: xr.concat(v, dim="band") for (k, v) in grouped_datasets.items()}
        for k, v in datasets.items():
            v.attrs["_asset_names"] = grouped_asset_names[k]

        # Group names must be strings.
        # Rename keys (group names) from `10`` to `10m`.
        datasets = {f"{k}m": v for (k, v) in datasets.items()}

    return datasets


def _create_stac_geo_extension(
    stac_item: pystac.Item, da: xr.DataArray, group_configuration: GroupLayout
) -> GeoZarrExtension[StacConfiguration]:
    """The <stac> geo extension uses the `proj` extension to encode georeferencing information."""
    kls = GeoZarrExtension[StacConfiguration]
    props = {
        **{k: v for (k, v) in stac_item.properties.items() if k.startswith("proj:")},
        **{
            k: v
            for (k, v) in stac_item.assets[da._asset_names[0]].to_dict().items()
            if k.startswith("proj:")
        },
    }
    return kls.model_validate(
        {
            "name": "stac",
            "configuration": {
                **props,
                "band_names": da._asset_names,
                "group_configuration": group_configuration.value,
            },
        }
    )


def _create_gdal_geo_extension(
    _: pystac.Item, da: xr.DataArray, group_configuration: GroupLayout
) -> GeoZarrExtension[GdalConfiguration]:
    """The <gdal> geo extension uses gdal to encode georeferencing information via rioxarray."""
    kls = GeoZarrExtension[GdalConfiguration]
    return kls.model_validate(
        {
            "name": "gdal",
            "configuration": {
                "transform": da.rio.transform().to_gdal(),
                "epsg": f"EPSG:{da.rio.crs.to_epsg()}",
                "wkt": da.rio.crs.to_wkt(),
                "projjson": da.rio.crs._projjson(),
                "band_names": da._asset_names,
                "group_configuration": group_configuration.value,
            },
        }
    )


def _create_cf_geo_extension(
    item: pystac.Item, da: xr.DataArray, group_configuration: GroupLayout
) -> GeoZarrExtension[CfConfiguration]:
    """The <cf> geo extension uses rioxarray's `spatial_ref` (which claims to be CF compliant) to encode
    georeferencing information"""
    kls = GeoZarrExtension[CfConfiguration]
    return kls.model_validate(
        {
            "name": "cf",
            "configuration": {
                **da.spatial_ref.attrs,
                "band_names": da._asset_names,
                "group_configuration": group_configuration.value,
            },
        }
    )


def _create_geotiff_geo_extension(
    item: pystac.Item, da: xr.DataArray, group_configuration: GroupLayout
) -> GeoZarrExtension[GeoTiffConfiguration]:
    href = item.assets[da._asset_names[0]].href

    async def _get_tiff_header(http_url: str) -> TIFF:
        splits = urlsplit(http_url)

        # It's bad to recreate store on every request but
        # I don't really care for now.
        store = HTTPStore.from_url(f"{splits.scheme}://{splits.netloc}")
        tiff = await TIFF.open(splits.path, store=store, prefetch=2**32)
        return tiff

    tiff = asyncio.run(_get_tiff_header(href))

    # Geotiff tags are only on the first ifd
    ifd = tiff.ifds[0]
    geokeys = {
        m: getattr(ifd.geo_key_directory, m)
        for m in dir(ifd.geo_key_directory)
        if not m.startswith("__")
    }

    kls = GeoZarrExtension[GeoTiffConfiguration]
    return kls.model_validate(
        {
            "name": "geotiff",
            "configuration": {
                **geokeys,
                "model_tiepoint": ifd.model_tiepoint,
                "model_pixel_scale": ifd.model_pixel_scale,
                "band_names": da._asset_names,
                "group_configuration": group_configuration.value,
            },
        }
    )


def _pick_geo_extension(
    item: pystac.Item,
    da: xr.DataArray,
    extension_type: GeoZarrExtensionType,
    configuration: GroupLayout,
) -> GeoZarrExtension:
    match extension_type:
        case GeoZarrExtensionType.stac:
            return _create_stac_geo_extension(item, da, configuration)
        case GeoZarrExtensionType.gdal:
            return _create_gdal_geo_extension(item, da, configuration)
        case GeoZarrExtensionType.cf:
            return _create_cf_geo_extension(item, da, configuration)
        case GeoZarrExtensionType.geotiff:
            return _create_geotiff_geo_extension(item, da, configuration)
        case _:
            raise ValueError("Unrecognized extension type")

def convert(
    item: pystac.Item,
    store_path: Path,
    extension_type: GeoZarrExtensionType,
    group_layout: GroupLayout = GroupLayout.chunky,
    chunk_size_x: int = 2048,
    chunk_size_y: int = 2048,
    simple: bool = False,
):
    if store_path.exists():
        shutil.rmtree(store_path)

    data_arrays = _stac_to_xarray(item, chunk_size_x, chunk_size_y, group_layout)
    for group_name, da in data_arrays.items():
        ds = da.to_dataset(name="data")

        # Store the `geo` extension in the group `attributes`.  Extensions should technically
        # be stored at the top level of the group but `zarr-python` doesn't support this.
        geo_metadata = _pick_geo_extension(item, da, extension_type, group_layout)
        ds.attrs.update({"geo": geo_metadata.model_dump(by_alias=True)})

        # Drop additional coordinate variables included by rioxarray.  These are already covered
        # by the `geo` extension.  They may still be included for interoperability with existing
        # software.
        if simple:
            ds = ds.drop_vars(names=["band", "spatial_ref", "x", "y"])

        # Write the group out to the zarr store
        ds.to_zarr(store_path, group=group_name, consolidated=True)
