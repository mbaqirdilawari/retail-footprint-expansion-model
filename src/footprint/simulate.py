"""Generate the SIMULATED data used in this project.

IMPORTANT: everything this script creates is fake. It is not real company data.
It exists only to show how the method works, at a realistic shape and scale.

Real, public inputs:
  * District boundaries (geoBoundaries, public domain)
  * District population and urban share (Pakistan Population Census 2023)

Simulated outputs (data/simulated/):
  * district_attributes.csv : sales region, LSM 5+ share, nature of district
  * retailers.csv           : one row per retailer with a freezer, with messy typed
                              district names, GPS coordinates and yearly volume (liters)
  * retail_census.csv       : the store list a third party retail census agency would
                              deliver for Phase 2 (stores, channels, brands sold, turnover)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import shapely

from . import config, geo

# Sales regions are named after the city they are run from
REGION_HUBS = {
    "Lahore Region": (31.55, 74.34),
    "Islamabad Region": (33.68, 73.05),
    "Multan Region": (30.20, 71.47),
    "Karachi Region": (24.86, 67.01),
    "Peshawar Region": (34.01, 71.58),
}

# Cities where the company historically built its business (used to simulate strength)
HISTORIC_HUBS = [
    (31.55, 74.34), (24.86, 67.01), (33.68, 73.05), (31.42, 73.08),
    (30.20, 71.47), (34.01, 71.58), (25.39, 68.37), (32.16, 74.19), (32.49, 74.53),
]

ABBREVIATIONS = {
    "Lahore": ["LHR", "Lahore Cantt", "Lahore City"],
    "Karachi": ["KHI", "Karachi City", "Karachi South", "Khi"],
    "Islamabad Capital Territory": ["ISB", "Islamabad", "Isb"],
    "Rawalpindi": ["RWP", "Pindi", "Rawalpindi Cantt"],
    "Faisalabad": ["FSD", "Lyallpur", "Faisalabad City"],
    "Multan": ["MUX", "Multan Cantt"],
    "Peshawar": ["PEW", "Peshawar Cantt"],
    "Hyderabad": ["HYD", "Hyderabad City"],
    "Gujranwala": ["GRW", "Gujranwala Cantt"],
    "Quetta": ["UET", "Quetta City"],
}


def _km(lat1, lon1, lat2, lon2):
    """Great circle distance in kilometers."""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))


def _messy_name(name: str, rng: np.random.Generator) -> str:
    """Return the district name the way a salesperson might have typed it."""
    roll = rng.random()
    if roll < 0.50:
        return name
    if roll < 0.60:
        return name.lower()
    if roll < 0.68:
        return name.upper() + (" " if rng.random() < 0.5 else "")
    if roll < 0.80 and len(name) > 4:
        i = rng.integers(1, len(name) - 1)
        return name[:i] + name[i + 1:] if rng.random() < 0.5 else name[:i] + name[i] + name[i:]
    if roll < 0.93 and name in ABBREVIATIONS:
        return str(rng.choice(ABBREVIATIONS[name]))
    if roll < 0.97:
        return f"{name} District"
    return ""


def _points_in_polygon(polygon, n: int, rng: np.random.Generator, spread: float) -> np.ndarray:
    """Draw n random points inside a polygon, clustered around a few town centres."""
    if n == 0:
        return np.empty((0, 2))
    minx, miny, maxx, maxy = polygon.bounds
    centre = polygon.representative_point()
    centres = [(centre.x, centre.y)]
    while len(centres) < 3:
        x, y = rng.uniform(minx, maxx), rng.uniform(miny, maxy)
        if shapely.contains_xy(polygon, x, y):
            centres.append((x, y))
    weights = np.array([0.6, 0.25, 0.15])
    collected, total = [], 0
    while total < n:
        batch = max((n - total) * 3, 50)
        which = rng.choice(3, size=batch, p=weights)
        pts = np.array(centres)[which] + rng.normal(0, spread, size=(batch, 2))
        inside = pts[shapely.contains_xy(polygon, pts[:, 0], pts[:, 1])]
        collected.append(inside)
        total += len(inside)
    return np.vstack(collected)[:n]


def build_district_attributes(districts, census: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Simulated district level attributes: region, LSM share, strength, nature of district."""
    df = districts[["district", "province", "geometry"]].merge(census, on=["district", "province"], how="inner")
    pts = df.geometry.representative_point()
    df["lat"], df["lon"] = pts.y.to_numpy(), pts.x.to_numpy()

    hub_names = list(REGION_HUBS)
    dist_to_region = np.column_stack([_km(df.lat, df.lon, *REGION_HUBS[h]) for h in hub_names])
    df["region"] = [hub_names[i] for i in dist_to_region.argmin(axis=1)]

    dist_hist = np.column_stack([_km(df.lat, df.lon, *h) for h in HISTORIC_HUBS]).min(axis=1)
    # "strength" is 1 next to a historic hub and fades with distance (simulated)
    df["strength"] = np.exp(-dist_hist / 220) * (0.75 + 0.5 * df["urban_share"])
    df["strength"] = (df["strength"] / df["strength"].max()).clip(0.02, 1)

    df["lsm5_share"] = (0.12 + 0.6 * df["urban_share"] + rng.normal(0, 0.04, len(df))).clip(0.08, 0.80).round(3)

    # Strongholds: the strongest, most populous districts (citadels and distributor towns)
    score = df["strength"] * np.log(df["population_2023"])
    strongholds = set(df.nlargest(30, "strength").sort_values("population_2023").tail(25)["district"])
    strongholds |= set(df.loc[score.nlargest(20).index, "district"])
    neighbours = geo.neighbouring_districts(districts, strongholds)

    target_pop = df["population_2023"] * df["lsm5_share"]
    big = target_pop >= target_pop.quantile(0.70)
    df["nature_of_district"] = np.select(
        [df["district"].isin(strongholds), df["district"].isin(neighbours), big],
        ["Stronghold", "Neighbouring", "Population High"],
        "Rest",
    )
    return df.drop(columns=["geometry"])


def build_retailers(districts, attrs: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Simulated retailer list with yearly volumes in liters."""
    geom = districts.set_index("district").geometry
    rows = []
    rid = 0
    for d in attrs.itertuples(index=False):
        s = d.strength
        target_pop_2024 = d.population_2023 * (1 + d.annual_growth_rate) * d.lsm5_share
        ppo = np.exp(np.log(900) + (1 - s) * 3.3 + rng.normal(0, 0.30))
        n_active_2024 = int(round(target_pop_2024 / ppo))
        if n_active_2024 == 0:
            continue
        tp_2024 = float(np.clip(8.5 + 13 * s + rng.normal(0, 2.5), 4, 27))
        decline = rng.uniform(0.02, 0.09)            # TP has been falling every year
        ni_ratio = rng.uniform(0.35, 0.75)           # new shops sell less than established ones
        n_closed = int(round(n_active_2024 * rng.uniform(0.04, 0.10)))
        n = n_active_2024 + n_closed

        induction = rng.choice([2019, 2022, 2023, 2024], size=n, p=[0.70, 0.09, 0.10, 0.11])
        closure = np.full(n, 0)
        closure[n_active_2024:] = rng.choice([2023, 2024], size=n_closed)
        induction[n_active_2024:] = np.minimum(induction[n_active_2024:], 2022)

        shop_factor = rng.lognormal(0, 0.45, n)
        pts = _points_in_polygon(geom[d.district], n, rng, spread=0.06 + 0.10 * (1 - s))
        channel = rng.choice(["Traditional Trade", "Modern Trade", "Out of Home"], size=n, p=[0.80, 0.08, 0.12])
        distributors = [f"DST-{d.region[:3].upper()}-{k:02d}" for k in range(1, 2 + n // 400)]

        for i in range(n):
            rid += 1
            vols = {}
            for y in config.YEARS:
                active = induction[i] <= y and (closure[i] == 0 or closure[i] > y)
                if not active:
                    vols[f"volume_{y}"] = 0.0
                    continue
                tp_year = tp_2024 * (1 + decline) ** (config.BASE_YEAR - y)
                if induction[i] == y:
                    tp_year *= ni_ratio
                vols[f"volume_{y}"] = round(tp_year * shop_factor[i] * config.WEEKS_PER_YEAR, 1)
            rows.append(
                {
                    "retailer_id": f"R{rid:06d}",
                    "region": d.region,
                    "distributor_id": str(rng.choice(distributors)),
                    "channel": channel[i],
                    "district_typed": _messy_name(d.district, rng),
                    "latitude": round(float(pts[i, 1]), 6),
                    "longitude": round(float(pts[i, 0]), 6),
                    "induction_year": int(induction[i]) if induction[i] > 2019 else "2021 or earlier",
                    "status": "Active" if closure[i] == 0 else f"Closed in {closure[i]}",
                    **vols,
                }
            )
    df = pd.DataFrame(rows)

    # Field data is never perfect: swap some coordinates and blank out a few
    swap = rng.random(len(df)) < 0.004
    df.loc[swap, ["latitude", "longitude"]] = df.loc[swap, ["longitude", "latitude"]].to_numpy()
    zero = rng.random(len(df)) < 0.002
    df.loc[zero, ["latitude", "longitude"]] = 0.0
    return df


def build_retail_census(districts, attrs: pd.DataFrame, retailers: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Simulated store list from a third party retail census (Phase 2)."""
    geom = districts.set_index("district").geometry
    channels = ["Grocery", "General Store", "Bakery", "Supermarket", "Petro Mart", "Pharmacy", "Tea Shop", "Restaurant"]
    channel_p = [0.38, 0.16, 0.10, 0.05, 0.03, 0.10, 0.11, 0.07]
    rows = []
    sid = 0
    for d in attrs.itertuples(index=False):
        target_pop = d.population_2023 * (1 + d.annual_growth_rate) * d.lsm5_share
        density = rng.uniform(0.4, 1.6) * (0.5 + d.urban_share)
        n = int(round(target_pop / 450 * density))
        if n == 0:
            continue
        pts = _points_in_polygon(geom[d.district], n, rng, spread=0.06 + 0.10 * (1 - d.strength))
        turnover = rng.choice(["Low", "Medium", "High"], size=n, p=[0.45, 0.33, 0.22])
        boost = np.select([turnover == "High", turnover == "Medium"], [0.25, 0.10], 0.0)
        for i in range(n):
            sid += 1
            b = boost[i]
            rows.append(
                {
                    "store_id": f"CS{sid:07d}",
                    "latitude": round(float(pts[i, 1]), 6),
                    "longitude": round(float(pts[i, 0]), 6),
                    "channel": str(rng.choice(channels, p=channel_p)),
                    "turnover_band": turnover[i],
                    "est_monthly_turnover_pkr": int(
                        {"Low": 1, "Medium": 3, "High": 8}[turnover[i]] * 100_000 * rng.lognormal(0, 0.3)
                    ),
                    "sells_coke_or_pepsi": bool(rng.random() < 0.70 + b),
                    "sells_dairy_milk": bool(rng.random() < 0.50 + b),
                    "sells_lays": bool(rng.random() < 0.60 + b),
                    "sells_sooper": bool(rng.random() < 0.55 + b),
                }
            )
    census = pd.DataFrame(rows)

    # Many of the company's existing customers also appear in the census, a few meters away
    active = retailers[(retailers["status"] == "Active") & retailers["latitude"].between(23.5, 37.5)]
    active = active.sample(frac=0.30, random_state=config.SEED)
    jitter_deg = rng.uniform(-8, 8, size=(len(active), 2)) / 111_000  # up to about 8 meters
    ex_turnover = rng.choice(["Low", "Medium", "High"], size=len(active), p=[0.25, 0.40, 0.35])
    existing = pd.DataFrame(
        {
            "store_id": [f"CS{sid + k + 1:07d}" for k in range(len(active))],
            "latitude": (active["latitude"].to_numpy() + jitter_deg[:, 0]).round(6),
            "longitude": (active["longitude"].to_numpy() + jitter_deg[:, 1]).round(6),
            "channel": rng.choice(channels, size=len(active), p=channel_p),
            "turnover_band": ex_turnover,
            "est_monthly_turnover_pkr": (
                pd.Series(ex_turnover).map({"Low": 1, "Medium": 3, "High": 8}).to_numpy()
                * 100_000 * rng.lognormal(0, 0.3, len(active))
            ).astype(int),
            "sells_coke_or_pepsi": rng.random(len(active)) < 0.90,
            "sells_dairy_milk": rng.random(len(active)) < 0.70,
            "sells_lays": rng.random(len(active)) < 0.85,
            "sells_sooper": rng.random(len(active)) < 0.75,
        }
    )
    census = pd.concat([census, existing], ignore_index=True)
    return census.sample(frac=1, random_state=config.SEED).reset_index(drop=True)


def main() -> None:
    rng = np.random.default_rng(config.SEED)
    config.DATA_SIM.mkdir(parents=True, exist_ok=True)
    districts = geo.load_districts()
    census_pop = pd.read_csv(config.DATA_RAW / "census_2023_district_population.csv")

    attrs = build_district_attributes(districts, census_pop, rng)
    retailers = build_retailers(districts, attrs, rng)
    census = build_retail_census(districts, attrs, retailers, rng)

    keep = ["district", "province", "region", "lsm5_share", "nature_of_district"]
    attrs[keep].sort_values("district").to_csv(config.DATA_SIM / "district_attributes.csv", index=False)
    retailers.to_csv(config.DATA_SIM / "retailers.csv", index=False)
    census.to_csv(config.DATA_SIM / "retail_census.csv", index=False)
    print(f"Simulated {len(retailers):,} retailers and {len(census):,} census stores across {len(attrs)} districts.")


if __name__ == "__main__":
    main()
