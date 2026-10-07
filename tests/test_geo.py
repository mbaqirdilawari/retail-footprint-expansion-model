"""Tests for the geospatial district mapping."""
import pandas as pd

from footprint import geo


def test_known_cities_land_in_the_right_district(districts):
    points = pd.DataFrame(
        {
            "name": ["Badshahi Mosque", "Clifton Beach", "Faisal Mosque", "Clock Tower"],
            "latitude": [31.5880, 24.7920, 33.7294, 31.4187],
            "longitude": [74.3106, 67.0300, 73.0377, 73.0791],
        }
    )
    mapped = geo.map_points_to_districts(points, districts)
    assert mapped["district_mapped"].tolist() == ["Lahore", "Karachi", "Islamabad Capital Territory", "Faisalabad"]
    assert (mapped["mapping_status"] == "Mapped").all()


def test_swapped_coordinates_are_fixed(districts):
    # Latitude and longitude typed the wrong way round (a point in Lahore)
    points = pd.DataFrame({"latitude": [74.3106], "longitude": [31.5880]})
    mapped = geo.map_points_to_districts(points, districts)
    assert mapped.loc[0, "coordinate_status"] == "Fixed (lat and lon swapped)"
    assert mapped.loc[0, "district_mapped"] == "Lahore"


def test_missing_coordinates_are_flagged_not_guessed(districts):
    points = pd.DataFrame({"latitude": [0.0, 51.5], "longitude": [0.0, -0.12]})
    mapped = geo.map_points_to_districts(points, districts)
    assert mapped["district_mapped"].isna().all()
    assert (mapped["mapping_status"] == "Invalid (outside Pakistan or missing)").all()


def test_every_district_has_a_province(districts):
    assert districts["province"].notna().all()
    assert len(districts) == 115


def test_messy_names_collapse_to_official_districts(results):
    r = results["retailers_mapped"]
    lahore = r[r["district_mapped"] == "Lahore"]
    assert lahore["district_typed"].nunique() > 5  # many spellings in the raw data
    assert r["district_mapped"].dropna().isin(set(results["districts"]["district"])).all()
