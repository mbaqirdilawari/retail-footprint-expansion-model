"""Run the whole project end to end.

    python run_pipeline.py

Steps:
  1. Load public district boundaries and census population.
  2. Load the simulated retailers and map each one to its district (geospatial).
  3. Phase 1: district metrics, outlet recommendation, prioritization.
  4. Phase 2: retail census reality check.
  5. Rollout plan: budget scenarios, yearly phasing, sales target list.
  6. Save tables, charts, the interactive map, and the Excel model.
"""
from __future__ import annotations

import time

import pandas as pd

from . import census as census_mod
from . import charts, config, excel_export, geo, model, rollout, store_map


def load_inputs():
    districts = geo.load_districts()
    population = pd.read_csv(config.DATA_RAW / "census_2023_district_population.csv")
    attrs = pd.read_csv(config.DATA_SIM / "district_attributes.csv")
    retailers = pd.read_csv(config.DATA_SIM / "retailers.csv", dtype={"induction_year": str})
    census = pd.read_csv(config.DATA_SIM / "retail_census.csv")
    return districts, population, attrs, retailers, census


def run(save: bool = False, basis: str | None = None) -> dict:
    """Run the model. Settings are read from config at call time, so they can be overridden."""
    basis = basis or config.NEW_OUTLET_TP_BASIS
    districts, population, attrs, retailers, census = load_inputs()

    # Geospatial mapping of retailers
    retailers_mapped = geo.map_points_to_districts(retailers, districts)

    # Phase 1
    metrics = model.district_metrics(retailers_mapped, attrs, population)
    recommended = model.recommend(metrics, basis=basis, ideal_tp=config.IDEAL_TP, ideal_ppo=config.IDEAL_PPO)
    prioritized = model.prioritize(recommended)

    # Phase 2
    stores = census_mod.run(census, retailers_mapped, districts)
    supply = census_mod.district_supply(stores)
    checked = census_mod.reality_check(prioritized, supply)

    # Rollout
    plan = rollout.build_plan(checked)
    targets = rollout.sales_target_list(stores, plan)

    results = {
        "districts": districts,
        "retailers_mapped": retailers_mapped,
        "district_model": checked,
        "plan": plan,
        "stores": stores,
        "targets": targets,
    }
    if save:
        save_outputs(results)
    return results


def save_outputs(results: dict) -> None:
    for folder in [config.DATA_OUT, config.TABLES, config.FIGURES]:
        folder.mkdir(parents=True, exist_ok=True)

    results["retailers_mapped"].to_csv(config.DATA_OUT / "retailers_mapped.csv", index=False)
    results["district_model"].to_csv(config.DATA_OUT / "district_model.csv", index=False)
    results["targets"].to_csv(config.TABLES / "sales_target_list.csv", index=False)

    plan_cols = [
        "priority_rank", "district", "province", "region", "nature_of_district", "phase",
        "quadrant_pcc_ppo", "quadrant_tp_ppo", "retailers_2024", "ppo_2024", "tp_2024",
        "recommended_new_outlets", "limiting_factor", "usable_supply", "final_new_outlets", "constraint",
        *[f"budget_{b}" for b in config.BUDGET_SCENARIOS], *[f"rollout_{y}" for y in config.PHASING],
    ]
    results["plan"][plan_cols].round(2).to_csv(config.TABLES / "expansion_plan_top50.csv", index=False)

    # Data quality summary for the README
    r = results["retailers_mapped"]
    quality = pd.DataFrame(
        {
            "measure": [
                "Retailer records",
                "Distinct typed district names",
                "Official districts after mapping",
                "Coordinates fixed (latitude and longitude swapped)",
                "Coordinates invalid (missing or outside Pakistan)",
                "Records mapped to a district",
            ],
            "value": [
                len(r),
                r["district_typed"].fillna("").str.strip().nunique(),
                r["district_mapped"].nunique(),
                int((r["coordinate_status"] == "Fixed (lat and lon swapped)").sum()),
                int((r["coordinate_status"] == "Invalid (outside Pakistan or missing)").sum()),
                int((r["mapping_status"] == "Mapped").sum()),
            ],
        }
    )
    quality.to_csv(config.TABLES / "data_quality_summary.csv", index=False)


def main() -> None:
    """Run everything and save every output (tables, charts, map, Excel model)."""
    started = time.time()
    results = run(save=True)
    print("1. Mapped retailers and built the district model (data/processed/).")
    example = charts.all_charts(results)
    print(f"2. Saved charts to outputs/figures/ (TP curve example: {example}).")
    store_map.build(results["districts"], results["district_model"], results["targets"],
                    config.ROOT / "outputs" / "sales_target_map.html")
    print("3. Saved the interactive sales target map to outputs/sales_target_map.html.")
    excel_export.build_workbook(results["district_model"], config.ROOT / "excel" / "Retail_Footprint_Expansion_Model.xlsx")
    print("4. Saved the Excel model to excel/Retail_Footprint_Expansion_Model.xlsx.")

    m, plan = results["district_model"], results["plan"]
    print("\nHeadline results (simulated data)")
    print(f"  Districts in the model:              {len(m)}")
    print(f"  Current outlets (freezers):          {m['retailers_2024'].sum():,}")
    print(f"  Shortlisted districts:               {len(plan)}")
    print(f"  Phase 1 demand (new outlets):        {plan['recommended_new_outlets'].sum():,}")
    print(f"  Phase 2 usable shops:                {plan['usable_supply'].sum():,}")
    print(f"  Final recommendation (new outlets):  {plan['final_new_outlets'].sum():,}")
    print(f"Finished in {time.time() - started:.0f} seconds.")
