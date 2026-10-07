"""Tests for the Phase 2 reality check and the rollout plan."""
import numpy as np
import pandas as pd

from footprint import census, config, rollout


def test_high_potential_needs_all_three_conditions():
    stores = pd.DataFrame(
        {
            "channel": ["Grocery", "Tea Shop", "Grocery", "Bakery"],
            "turnover_band": ["High", "High", "Low", "High"],
            "sells_coke_or_pepsi": [True, True, True, True],
            "sells_dairy_milk": [True, True, True, False],
            "sells_lays": [True, True, True, True],
            "sells_sooper": [True, True, True, True],
        }
    )
    flagged = census.flag_high_potential(stores)
    assert flagged["high_potential"].tolist() == [True, False, False, False]


def test_existing_customer_is_matched_by_location():
    retailers = pd.DataFrame(
        {"latitude": [31.5], "longitude": [74.3], "status": ["Active"], "mapping_status": ["Mapped"]}
    )
    stores = pd.DataFrame({"latitude": [31.50005, 31.51], "longitude": [74.30005, 74.31]})  # about 7 m and 1.4 km away
    flagged = census.flag_existing_customers(stores, retailers)
    assert flagged["existing_customer"].tolist() == [True, False]


def test_final_is_smaller_of_demand_and_supply(results):
    m = results["district_model"]
    assert (m["final_new_outlets"] == np.minimum(m["recommended_new_outlets"], m["usable_supply"])).all()
    assert (m["usable_supply"] == np.floor(m["census_universe"] * config.CENSUS_CONVERSION_RATE)).all()


def test_sales_targets_are_eligible_and_match_the_plan(results):
    targets, plan, stores = results["targets"], results["plan"], results["stores"]
    eligible_ids = set(stores.loc[stores["eligible_new_store"], "store_id"])
    assert targets["store_id"].isin(eligible_ids).all()
    assert targets["store_id"].is_unique
    per_district = targets.groupby("district").size()
    expected = plan.set_index("district")["final_new_outlets"]
    expected = expected[expected > 0]
    assert per_district.reindex(expected.index).eq(expected).all()


def test_budget_allocation_adds_up_exactly(results):
    plan = results["plan"]
    for budget in config.BUDGET_SCENARIOS:
        alloc = plan[f"budget_{budget}"]
        assert alloc.sum() == min(budget, plan["final_new_outlets"].sum())
        assert (alloc <= plan["final_new_outlets"]).all()


def test_phasing_adds_up_for_every_district(results):
    plan = results["plan"]
    years = [f"rollout_{y}" for y in config.PHASING]
    assert (plan[years].sum(axis=1) == plan["final_new_outlets"]).all()
    assert rollout.phase_by_year(850) == {2025: 300, 2026: 300, 2027: 250}
