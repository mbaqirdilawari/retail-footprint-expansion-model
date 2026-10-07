"""Turning the recommendation into a plan people can act on.

1. Budget scenarios: if the company can only fund a fixed number of freezers,
   share them across shortlisted districts in proportion to each district's
   final recommendation (its "contribution").
2. Phasing: split each district's freezers across 2025, 2026 and 2027.
3. Sales target list: the exact stores the sales team should visit, best first.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def _largest_remainder(weights: np.ndarray, total: int) -> np.ndarray:
    """Split a whole number total in proportion to weights, so the parts add up exactly."""
    weights = np.asarray(weights, dtype=float)
    if total <= 0 or weights.sum() == 0:
        return np.zeros(len(weights), dtype=int)
    exact = weights / weights.sum() * total
    base = np.floor(exact).astype(int)
    short = total - base.sum()
    order = np.argsort(-(exact - base), kind="stable")
    base[order[:short]] += 1
    return base


def allocate_budget(plan: pd.DataFrame, budget: int) -> pd.Series:
    """Freezers per district under a national budget.

    If the budget covers everything, every district gets its full final recommendation.
    Otherwise each district gets: budget x (district final / total final).
    """
    final = plan["final_new_outlets"].to_numpy()
    if budget >= final.sum():
        return pd.Series(final, index=plan.index)
    return pd.Series(_largest_remainder(final, budget), index=plan.index)


def phase_by_year(outlets: int, phasing: dict = config.PHASING) -> dict:
    """Split one district's freezers across the rollout years."""
    parts = _largest_remainder(np.array(list(phasing.values())), int(outlets))
    return dict(zip(phasing.keys(), parts))


def build_plan(checked: pd.DataFrame) -> pd.DataFrame:
    """The shortlisted districts, with budget scenarios and yearly phasing."""
    plan = checked[checked["shortlisted"]].sort_values("priority_rank").copy()
    for budget in config.BUDGET_SCENARIOS:
        plan[f"budget_{budget}"] = allocate_budget(plan, budget)
    years = plan["final_new_outlets"].apply(phase_by_year).apply(pd.Series)
    years.columns = [f"rollout_{y}" for y in years.columns]
    return pd.concat([plan, years], axis=1)


def sales_target_list(stores: pd.DataFrame, plan: pd.DataFrame) -> pd.DataFrame:
    """Pick the best eligible stores in each district, one per recommended freezer.

    Stores with the highest turnover are visited first (earliest rollout year).
    """
    picks = []
    eligible = stores[stores["eligible_new_store"]]
    for row in plan.itertuples(index=False):
        n = int(row.final_new_outlets)
        if n == 0:
            continue
        top = eligible[eligible["district_mapped"] == row.district].nlargest(n, "est_monthly_turnover_pkr").copy()
        yearly = phase_by_year(len(top))
        top["rollout_year"] = np.repeat(list(yearly.keys()), list(yearly.values()))
        top["priority_rank"] = int(row.priority_rank)
        top["phase"] = row.phase
        picks.append(top)
    cols = [
        "priority_rank", "district_mapped", "rollout_year", "store_id", "channel", "turnover_band",
        "est_monthly_turnover_pkr", "latitude", "longitude", "phase",
    ]
    out = pd.concat(picks, ignore_index=True)[cols].rename(columns={"district_mapped": "district"})
    return out.sort_values(["priority_rank", "rollout_year", "est_monthly_turnover_pkr"], ascending=[True, True, False])
