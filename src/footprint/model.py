"""Phase 1: the district demand model.

Step by step, for every district:
  1. Count retailers (outlets) and add up volume sold, by year.
  2. Work out the target population (people in LSM 5+, who can afford ice cream).
  3. Calculate the three core metrics:
        PCC (Per Capita Consumption) = Volume / Target population
        PPO (Population Per Outlet)  = Target population / Outlets
        TP  (Throughput)             = Volume / Outlets / Weeks   (liters per freezer per week)
  4. Recommend how many new outlets (freezers) to add.

The recommendation rule (the bell curve in the original notebook):
  Every new freezer adds volume, but it also spreads demand across more freezers,
  so throughput per freezer falls. Keep adding freezers until EITHER
     * TP falls to the Ideal TP (15 liters per week), OR
     * PPO falls to the Ideal PPO (750 people per outlet),
  whichever comes first. Districts already below either line get no new freezers.

  New Volume(n) = Current Volume + n x (Weeks x New outlet TP + First fill)
  New TP(n)     = New Volume(n) / (Current Outlets + n) / Weeks
  New PPO(n)    = Target population / (Current Outlets + n)

  The original Excel model found n with Goal Seek. Here it is solved directly.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

Y0, Y1, Y2 = config.YEARS  # 2022, 2023, 2024


def _safe_div(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return np.divide(a, b, out=np.zeros_like(a), where=b != 0)


def _layer(values: pd.Series, thresholds) -> pd.Series:
    """Band a metric into Layer 01 (highest) to Layer 05 (lowest)."""
    out = pd.Series(config.LAST_LAYER, index=values.index)
    for cut, name in reversed(thresholds):
        out[values >= cut] = name
    return out


def district_metrics(retailers: pd.DataFrame, attrs: pd.DataFrame, population: pd.DataFrame) -> pd.DataFrame:
    """Roll retailers up to one row per district and calculate every metric.

    retailers  : must contain district_mapped, induction_year and volume_<year> columns
    attrs      : district, province, region, lsm5_share, nature_of_district
    population : district, population_2023, annual_growth_rate (public census)
    """
    r = retailers[retailers["mapping_status"] == "Mapped"].copy()
    rows = attrs.merge(population[["district", "population_2023", "annual_growth_rate"]], on="district")

    for y in config.YEARS:
        active = r[f"volume_{y}"] > 0
        new_this_year = active & (r["induction_year"].astype(str) == str(y))
        g = r[active].groupby("district_mapped")
        rows[f"retailers_{y}"] = rows["district"].map(g.size()).fillna(0).astype(int)
        rows[f"volume_{y}"] = rows["district"].map(g[f"volume_{y}"].sum()).fillna(0.0).round(1)
        g_ni = r[new_this_year].groupby("district_mapped")
        rows[f"ni_retailers_{y}"] = rows["district"].map(g_ni.size()).fillna(0).astype(int)
        rows[f"ni_volume_{y}"] = rows["district"].map(g_ni[f"volume_{y}"].sum()).fillna(0.0).round(1)

        # Population grows each year at the census growth rate
        rows[f"population_{y}"] = (
            rows["population_2023"] * (1 + rows["annual_growth_rate"]) ** (y - 2023)
        ).round(0)
        rows[f"target_population_{y}"] = (rows[f"population_{y}"] * rows["lsm5_share"]).round(0)

        rows[f"pcc_{y}"] = _safe_div(rows[f"volume_{y}"], rows[f"target_population_{y}"])
        rows[f"ppo_{y}"] = _safe_div(rows[f"target_population_{y}"], rows[f"retailers_{y}"])
        rows[f"tp_{y}"] = _safe_div(rows[f"volume_{y}"], rows[f"retailers_{y}"] * config.WEEKS_PER_YEAR)
        rows[f"ni_tp_{y}"] = _safe_div(rows[f"ni_volume_{y}"], rows[f"ni_retailers_{y}"] * config.WEEKS_PER_YEAR)

    # Growth: GOLY (Growth Over Last Year) and CAGR (Compound Annual Growth Rate, 2022 to 2024)
    for m in ["retailers", "volume", "tp", "pcc"]:
        rows[f"{m}_goly"] = _safe_div(rows[f"{m}_{Y2}"], rows[f"{m}_{Y1}"]) - 1
        rows[f"{m}_cagr"] = np.where(
            rows[f"{m}_{Y0}"] > 0, _safe_div(rows[f"{m}_{Y2}"], rows[f"{m}_{Y0}"]) ** 0.5 - 1, 0.0
        )
        rows.loc[rows[f"{m}_{Y1}"] == 0, f"{m}_goly"] = 0.0

    rows["pcc_layer"] = _layer(rows[f"pcc_{Y2}"], config.PCC_LAYERS)
    rows["ppo_layer"] = _layer(rows[f"ppo_{Y2}"], config.PPO_LAYERS)
    return rows.sort_values("district").reset_index(drop=True)


def new_outlet_tp(metrics: pd.DataFrame, basis: str = config.NEW_OUTLET_TP_BASIS) -> pd.Series:
    """Throughput assumed for each new outlet in a district.

    "ni_tp": average TP of retailers that got a freezer in the base year (the original method).
             If a district had no new inductions, use the average NI TP of its sales region.
    "district_tp": average TP of all retailers in the district.
    """
    district_tp = metrics[f"tp_{Y2}"]
    if basis == "district_tp":
        return district_tp
    if basis == "ni_tp":
        ni = metrics[f"ni_tp_{Y2}"]
        region = metrics.groupby("region")[[f"ni_volume_{Y2}", f"ni_retailers_{Y2}"]].transform("sum")
        region_ni_tp = _safe_div(region[f"ni_volume_{Y2}"], region[f"ni_retailers_{Y2}"] * config.WEEKS_PER_YEAR)
        return ni.where(ni > 0, pd.Series(region_ni_tp, index=metrics.index))
    raise ValueError(f"Unknown basis: {basis}")


def outlets_to_add(
    outlets: float,
    volume: float,
    target_population: float,
    outlet_tp: float,
    ideal_tp: float = config.IDEAL_TP,
    ideal_ppo: float = config.IDEAL_PPO,
    weeks: int = config.WEEKS_PER_YEAR,
    first_fill: float = config.FIRST_FILL_LITERS,
) -> tuple[int, str]:
    """How many outlets to add in one district, and which limit stopped us.

    Returns (outlets to add, reason).
    """
    if outlets <= 0:
        return 0, "No current outlets"
    current_tp = volume / outlets / weeks
    current_ppo = target_population / outlets
    if current_tp <= ideal_tp:
        return 0, "TP already at or below ideal"
    if current_ppo <= ideal_ppo:
        return 0, "PPO already at or below ideal"

    # PPO limit: outlets needed to bring PPO down to the ideal
    n_ppo = target_population / ideal_ppo - outlets

    # TP limit: solve New TP(n) = ideal TP for n
    #   volume + n * (weeks * outlet_tp + first_fill) = ideal_tp * weeks * (outlets + n)
    added_per_outlet = weeks * outlet_tp + first_fill
    gap = ideal_tp * weeks - added_per_outlet
    n_tp = (volume - ideal_tp * weeks * outlets) / gap if gap > 0 else np.inf

    if n_tp <= n_ppo:
        return int(np.floor(n_tp + 1e-9)), "Stopped by TP reaching ideal"
    return int(np.floor(n_ppo + 1e-9)), "Stopped by PPO reaching ideal"


def recommend(metrics: pd.DataFrame, basis: str = config.NEW_OUTLET_TP_BASIS, **settings) -> pd.DataFrame:
    """Apply the recommendation rule to every district."""
    df = metrics.copy()
    df["new_outlet_tp"] = new_outlet_tp(df, basis)
    results = [
        outlets_to_add(o, v, t, tp, **settings)
        for o, v, t, tp in zip(df[f"retailers_{Y2}"], df[f"volume_{Y2}"], df[f"target_population_{Y2}"], df["new_outlet_tp"])
    ]
    df["recommended_new_outlets"] = [n for n, _ in results]
    df["limiting_factor"] = [why for _, why in results]

    weeks = settings.get("weeks", config.WEEKS_PER_YEAR)
    first_fill = settings.get("first_fill", config.FIRST_FILL_LITERS)
    n = df["recommended_new_outlets"]
    df["first_fill_volume"] = n * first_fill
    df["refill_volume"] = n * weeks * df["new_outlet_tp"]
    df["new_total_volume"] = df[f"volume_{Y2}"] + df["first_fill_volume"] + df["refill_volume"]
    df["new_total_outlets"] = df[f"retailers_{Y2}"] + n
    df["new_tp"] = _safe_div(df["new_total_volume"], df["new_total_outlets"] * weeks)
    df["new_ppo"] = _safe_div(df[f"target_population_{Y2}"], df["new_total_outlets"])
    df["incremental_volume"] = df["new_total_volume"] - df[f"volume_{Y2}"]
    return df


def tp_curve(outlets: int, volume: float, target_population: float, outlet_tp: float, max_new: int,
             weeks: int = config.WEEKS_PER_YEAR, first_fill: float = config.FIRST_FILL_LITERS) -> pd.DataFrame:
    """Volume, TP and PPO for every possible number of new outlets (used for the charts)."""
    n = np.arange(0, max_new + 1)
    vol = volume + n * (weeks * outlet_tp + first_fill)
    return pd.DataFrame(
        {
            "new_outlets": n,
            "total_outlets": outlets + n,
            "volume": vol,
            "tp": vol / (outlets + n) / weeks,
            "ppo": target_population / (outlets + n),
        }
    )


def prioritize(df: pd.DataFrame) -> pd.DataFrame:
    """Place each district in the two quadrant views and build the priority shortlist.

    View 1 (presentation): PCC against the national PCC, PPO against the ideal PPO.
        Quadrant 1: High PCC, High PPO -> Phase 1 (people buy a lot, too few outlets)
        Quadrant 2: High PCC, Low PPO  -> Phase 2 (well served, people want more)
        Quadrants 3 and 4               -> Phase 3
    View 2 (working notes): TP against the ideal TP, PPO against the ideal PPO.
        High TP, High PPO is the clear "expand" box.
    Expansion wave (strategy brief): strongholds first, then their neighbours,
    then high population districts, then the rest.
    """
    df = df.copy()
    national_pcc = df[f"volume_{Y2}"].sum() / df[f"target_population_{Y2}"].sum()
    df["national_pcc"] = national_pcc
    high_pcc = df[f"pcc_{Y2}"] >= national_pcc
    high_ppo = df[f"ppo_{Y2}"] > config.IDEAL_PPO
    high_tp = df[f"tp_{Y2}"] > config.IDEAL_TP

    df["quadrant_pcc_ppo"] = np.select(
        [high_pcc & high_ppo, high_pcc & ~high_ppo, ~high_pcc & high_ppo],
        ["Q1: High PCC, High PPO", "Q2: High PCC, Low PPO", "Q3: Low PCC, High PPO"],
        "Q4: Low PCC, Low PPO",
    )
    df["phase"] = np.select([high_pcc & high_ppo, high_pcc & ~high_ppo], ["Phase 1", "Phase 2"], "Phase 3")
    df["quadrant_tp_ppo"] = np.select(
        [high_tp & high_ppo, high_tp & ~high_ppo, ~high_tp & high_ppo],
        ["High TP, High PPO", "High TP, Low PPO", "Low TP, High PPO"],
        "Low TP, Low PPO",
    )
    df["expansion_wave"] = df["nature_of_district"].map(config.WAVE_ORDER)

    candidates = df[df["recommended_new_outlets"] > 0].sort_values(
        ["expansion_wave", "phase", "recommended_new_outlets", "district"], ascending=[True, True, False, True]
    )
    rank = pd.Series(np.arange(1, len(candidates) + 1), index=candidates.index)
    df["priority_rank"] = rank.reindex(df.index)
    df["shortlisted"] = df["priority_rank"].le(config.TOP_N_DISTRICTS).fillna(False).astype(bool)
    return df
