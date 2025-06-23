from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from geojson_pydantic.geometries import Polygon


ConfigT = TypeVar("ConfigT")


class GroupLayout(StrEnum):
    planar = "planar"  # each group respresents a single band
    chunky = "chunky"  # each group contains multiple bands


class GeoZarrExtensionType(StrEnum):
    stac = "stac"
    gdal = "gdal"
    cf = "cf"
    geotiff = "geotiff"


class GeoZarrExtension(BaseModel, Generic[ConfigT]):
    model_config = ConfigDict(use_enum_values=True)

    name: GeoZarrExtensionType
    configuration: ConfigT


class _GeoZarrConfiguration(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    band_names: list[str]
    group_configuration: GroupLayout


class CfConfiguration(_GeoZarrConfiguration):
    crs_wkt: str
    semi_major_axis: float
    semi_minor_axis: float
    inverse_flattening: float
    reference_ellipsoid_name: str
    longitude_of_prime_meridian: float
    prime_meridian_name: str
    geographic_crs_name: str
    horizontal_datum_name: str
    projected_crs_name: str
    grid_mapping_name: str
    latitude_of_projection_origin: float
    longitude_of_central_meridian: float
    false_easting: float
    false_northing: float
    scale_factor_at_central_meridian: float
    spatial_ref: str
    GeoTransform: str


class GdalConfiguration(_GeoZarrConfiguration):
    transform: list[float]
    epsg: str
    wkt: str
    projjson: str


class Centroid(BaseModel):
    lon: float
    lat: float


class StacConfiguration(_GeoZarrConfiguration):
    model_config = ConfigDict(
        alias_generator=lambda field_name: f"proj:{field_name}"
        if field_name not in ("band_names", "group_configuration")
        else field_name
    )
    wkt: str | None = None
    projjson: dict | None = None
    geometry: Polygon | None = None
    bbox: list[float] | None = None
    centroid: Centroid | None = None
    code: str | None
    shape: tuple[int, int]
    transform: list[float]
