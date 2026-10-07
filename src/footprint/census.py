"""Phase 2: the reality check. Do enough real shops exist to take the freezers?

Phase 1 says how many freezers the DEMAND in a district can support.
Phase 2 asks a practical question: are there actually that many suitable
shops in the district that could take one?

To answer it, a third party retail census agency provides a list of stores with
GPS coordinates. A store counts as "high potential" only if it meets ALL of:
  1. It already sells the biggest snacking competitors
     (Coke or Pepsi, Dairy Milk, Lays, and Sooper), so it has cold chain shoppers.
  2. It is in a target channel (Grocery, Bakery, Supermarket, Petro Mart, Pharmacy).
  3. It has high turnover.

Then:
  * Each store is placed in its district with the SAME geospatial code as Phase 1.
  * Stores that are already our customers are removed (matched by location).
  * Only a share of the remaining stores is counted, because not every shop owner
    will agree to take a freezer (the conversion rate, 80 percent).

  Final recommendation = the smaller of (Phase 1 demand, Phase 2 usable supply)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from . import config, geo


def flag_high_potential(census: pd.DataFrame) -> pd.DataFrame:
    """Mark which census stores pass all three filters."""
    df = census.copy()
    df["sells_all_competitor_brands"] = df[config.COMPETITOR_BRANDS].all(axis=1)
    df["in_target_channel"] = df["channel"].isin(config.TARGET_CHANNELS)
    df["high_turnover"] = df["turnover_band"] == config.TARGET_TURNOVER
    df["high_potential"] = df["sells_all_competitor_brands"] & df["in_target_channel"] & df["high_turnover"]
    return df


def _to_meters(lat: np.ndarray, lon: np.ndarray, ref_lat: float = 30.0) -> np.ndarray:
    """Convert latitude and longitude to approximate x and y in meters (fine for short distances)."""
    x = np.radians(lon) * 6_371_000 * np.cos(np.radians(ref_lat))
    y = np.radians(lat) * 6_371_000
    return np.column_stack([x, y])


def flag_existing_customers(census: pd.DataFrame, retailers: pd.DataFrame,
                            max_meters: float = config.EXISTING_CUSTOMER_MATCH_METERS) -> pd.DataFrame:
    """Mark census stores that are already our customers.

    The census and our own records spell shop names differently, so we match on
    location: a census store within a few meters of an active customer is that customer.
    """
    df = census.copy()
    active = retailers[(retailers["status"] == "Active") & (retailers["mapping_status"] == "Mapped")]
    tree = cKDTree(_to_meters(active["latitude"].to_numpy(), active["longitude"].to_numpy()))
    dist, _ = tree.query(_to_meters(df["latitude"].to_numpy(), df["longitude"].to_numpy()), k=1)
    df["existing_customer"] = dist <= max_meters
    return df


def district_supply(census: pd.DataFrame, conversion_rate: float = config.CENSUS_CONVERSION_RATE) -> pd.DataFrame:
    """Count stores per district at each step of the funnel."""
    mapped = census[census["mapping_status"] == "Mapped"]
    funnel = mapped.groupby("district_mapped").agg(
        census_stores=("store_id", "size"),
        high_potential_stores=("high_potential", "sum"),
        high_potential_existing=("existing_customer", lambda s: int((s & mapped.loc[s.index, "high_potential"]).sum())),
    )
    funnel["census_universe"] = funnel["high_potential_stores"] - funnel["high_potential_existing"]
    funnel["usable_supply"] = np.floor(funnel["census_universe"] * conversion_rate).astype(int)
    return funnel.reset_index().rename(columns={"district_mapped": "district"})


def reality_check(model: pd.DataFrame, supply: pd.DataFrame) -> pd.DataFrame:
    """Combine Phase 1 demand with Phase 2 supply."""
    df = model.merge(supply, on="district", how="left")
    for c in ["census_stores", "high_potential_stores", "high_potential_existing", "census_universe", "usable_supply"]:
        df[c] = df[c].fillna(0).astype(int)
    df["demand_outlets"] = df["recommended_new_outlets"]
    df["final_new_outlets"] = np.minimum(df["demand_outlets"], df["usable_supply"])
    df["constraint"] = np.select(
        [df["demand_outlets"] == 0, df["usable_supply"] < df["demand_outlets"]],
        ["No expansion", "Supply constrained (not enough shops)"],
        "Demand constrained (enough shops)",
    )
    return df


def run(census: pd.DataFrame, retailers_mapped: pd.DataFrame, districts) -> pd.DataFrame:
    """Full Phase 2 store level pipeline: filter, map, and remove existing customers."""
    df = flag_high_potential(census)
    df = geo.map_points_to_districts(df, districts)
    df = flag_existing_customers(df, retailers_mapped)
    df["eligible_new_store"] = df["high_potential"] & ~df["existing_customer"] & (df["mapping_status"] == "Mapped")
    return df
