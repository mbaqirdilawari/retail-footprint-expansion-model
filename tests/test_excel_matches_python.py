"""The Excel model must give the same answers as the Python model.

The workbook in excel/ is saved with calculated values, so it can be read
directly. If it was just rebuilt by the pipeline (formulas only, no saved
values), open and save it in Excel or LibreOffice first, otherwise this test
is skipped.
"""
from pathlib import Path

import pandas as pd
import pytest

from footprint import config

BOOK = Path(__file__).resolve().parents[1] / "excel" / "Retail_Footprint_Expansion_Model.xlsx"


@pytest.fixture(scope="module")
def excel_model():
    x = pd.read_excel(BOOK, sheet_name="Model", header=3)
    x = x[x["District"].notna()]
    if x["RECOMMENDED NEW OUTLETS (Phase 1 demand)"].isna().all():
        pytest.skip("Workbook has no calculated values yet. Open and save it in Excel or LibreOffice first.")
    return x.set_index("District")


def test_recommendations_match(results, excel_model):
    m = results["district_model"].set_index("district")
    x = excel_model.loc[m.index]
    assert (x["RECOMMENDED NEW OUTLETS (Phase 1 demand)"].astype(int) == m["recommended_new_outlets"]).all()
    assert (x["Limiting factor"] == m["limiting_factor"]).all()
    assert (x["FINAL NEW OUTLETS (smaller of demand and supply)"].astype(int) == m["final_new_outlets"]).all()
    assert (x["Phase"] == m["phase"]).all()


def test_plan_matches(results, excel_model):
    plan = results["plan"].set_index("district")
    x = excel_model.loc[plan.index]
    assert (x["Priority rank"].astype(int) == plan["priority_rank"].astype(int)).all()
    for i, budget in enumerate(config.BUDGET_SCENARIOS, start=1):
        assert (x[f"BUDGET SCENARIO {i} FREEZERS"].astype(int) == plan[f"budget_{budget}"]).all()
    for y in config.PHASING:
        assert (x[f"ROLLOUT {y}"].astype(int) == plan[f"rollout_{y}"]).all()
