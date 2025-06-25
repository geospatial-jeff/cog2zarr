from enum import StrEnum
from typing import Generic, TypeVar

from geojson_pydantic.geometries import Polygon
from pydantic import BaseModel, ConfigDict

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


class GeoTiffConfiguration(_GeoZarrConfiguration):
    citation: str | None
    geog_angular_unit_size: float | None
    geog_angular_units: int | None
    geog_azimuth_units: int | None
    geog_citation: str | None
    geog_ellipsoid: int | None
    geog_geodetic_datum: int | None
    geog_inv_flattening: float | None
    geog_linear_unit_size: float | None
    geog_linear_units: int | None
    geog_prime_meridian: int | None
    geog_prime_meridian_long: float | None
    geog_semi_major_axis: float | None
    geog_semi_minor_axis: float | None
    geographic_type: int | None
    model_type: int | None
    proj_azimuth_angle: float | None
    proj_center_easting: float | None
    proj_center_lat: float | None
    proj_center_long: float | None
    proj_center_northing: float | None
    proj_citation: str | None
    proj_coord_trans: int | None
    proj_false_easting: float | None
    proj_false_northing: float | None
    proj_false_origin_easting: float | None
    proj_false_origin_lat: float | None
    proj_false_origin_long: float | None
    proj_false_origin_northing: float | None
    proj_linear_unit_size: float | None
    proj_linear_units: int | None
    proj_nat_origin_lat: float | None
    proj_nat_origin_long: float | None
    proj_scale_at_center: float | None
    proj_scale_at_nat_origin: float | None
    proj_std_parallel1: float | None
    proj_std_parallel2: float | None
    proj_straight_vert_pole_long: float | None
    projected_type: int | None
    projection: int | None
    raster_type: int | None
    vertical: int | None
    vertical_citation: str | None
    vertical_datum: int | None
    vertical_units: int | None
    model_tiepoint: list[float] | None
    model_pixel_scale: list[float] | None
