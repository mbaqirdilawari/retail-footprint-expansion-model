"""Geospatial district mapping.

The problem: every retailer record has a district name typed in by hand,
for example "Lahore", "LHR", "Lahor", or "lahore cantt". Grouping sales by
that column creates hundreds of fake districts.

The fix: ignore the typed name. Every retailer also has GPS coordinates
(latitude and longitude). We check which official district boundary each
point falls inside (a "point in polygon" test) and use that district instead.

This module is the upgraded version of legacy/main.py. The original looped
over every retailer and every district one by one. Here GeoPandas does the
same test in one step with a spatial join, which uses a spatial index.
"""
from __future__ import annotations

import warnings

import geopandas as gpd
import numpy as np
import pandas as pd

from . import config

# Rough bounding box of Pakistan, used to catch broken coordinates
LAT_RANGE = (23.5, 37.5)
LON_RANGE = (60.5, 77.9)

# Gilgit-Baltistan and Azad Kashmir are not covered by the public 2023 district
# census tables, so they are left out of the model.
EXCLUDED_PROVINCES = {"Gilgit-Baltistan", "Azad Kashmir"}


def load_districts(include_excluded: bool = False) -> gpd.GeoDataFrame:
    """Load official district boundaries and attach each district's province.

    Returns one row per district with columns: district, province, geometry.
    Areas outside the census coverage are left out unless include_excluded is True
    (used only to draw the full map outline).
    """
    districts = gpd.read_file(config.DATA_RAW / "pak_ADM2.geojson")
    provinces = gpd.read_file(config.DATA_RAW / "pak_ADM1.geojson")
    districts = districts.rename(columns={"shapeName": "district"})[["district", "geometry"]]
    provinces = provinces.rename(columns={"shapeName": "province"})[["province", "geometry"]]

    # A district belongs to the province that contains a point inside it
    inner_points = districts.copy()
    inner_points["geometry"] = districts.representative_point()
    with_province = gpd.sjoin(inner_points, provinces, how="left", predicate="within")
    districts["province"] = with_province["province"].values

    if not include_excluded:
        districts = districts[~districts["province"].isin(EXCLUDED_PROVINCES)]
    return districts.reset_index(drop=True)


def clean_coordinates(df: pd.DataFrame, lat: str = "latitude", lon: str = "longitude") -> pd.DataFrame:
    """Fix or flag broken coordinates before mapping.

    Two common problems in field data:
      1. Latitude and longitude typed in the wrong columns (swapped).
      2. Missing or zero coordinates (the device had no GPS signal).
    Swapped values are switched back. Anything still outside Pakistan is flagged.
    """
    df = df.copy()
    in_lat = df[lat].between(*LAT_RANGE)
    in_lon = df[lon].between(*LON_RANGE)
    swapped = (~in_lat & ~in_lon) & df[lat].between(*LON_RANGE) & df[lon].between(*LAT_RANGE)
    df.loc[swapped, [lat, lon]] = df.loc[swapped, [lon, lat]].to_numpy()

    df["coordinate_status"] = np.where(swapped, "Fixed (lat and lon swapped)", "OK")
    valid = df[lat].between(*LAT_RANGE) & df[lon].between(*LON_RANGE)
    df.loc[~valid, "coordinate_status"] = "Invalid (outside Pakistan or missing)"
    return df


def map_points_to_districts(
    df: pd.DataFrame,
    districts: gpd.GeoDataFrame,
    lat: str = "latitude",
    lon: str = "longitude",
) -> pd.DataFrame:
    """Assign every row the official district its coordinates fall inside.

    Adds two columns:
      district_mapped : the district name from the boundary file
      mapping_status  : "Mapped", "Outside all districts", or the coordinate problem
    """
    df = clean_coordinates(df, lat, lon)
    valid = df["coordinate_status"] != "Invalid (outside Pakistan or missing)"

    points = gpd.GeoDataFrame(
        df.loc[valid],
        geometry=gpd.points_from_xy(df.loc[valid, lon], df.loc[valid, lat]),
        crs=districts.crs,
    )
    joined = gpd.sjoin(points, districts[["district", "geometry"]], how="left", predicate="within")
    # A point exactly on a shared border can match two districts. Keep the first.
    joined = joined[~joined.index.duplicated(keep="first")]

    df["district_mapped"] = joined["district"].reindex(df.index)
    df["mapping_status"] = np.where(df["district_mapped"].notna(), "Mapped", "Outside all districts")
    df.loc[~valid, "mapping_status"] = df.loc[~valid, "coordinate_status"]
    return df


def neighbouring_districts(districts: gpd.GeoDataFrame, of: set[str], tolerance_deg: float = 0.02) -> set[str]:
    """Return districts that share a border with any district in `of`.

    A small tolerance is used because simplified boundaries do not always touch exactly.
    """
    geoms = districts.set_index("district").geometry
    core = geoms[geoms.index.isin(of)].union_all()
    with warnings.catch_warnings():
        # Distances in degrees are fine here: we only need "touching or almost touching"
        warnings.simplefilter("ignore", UserWarning)
        near = geoms[geoms.distance(core) <= tolerance_deg].index
    return set(near) - set(of)
