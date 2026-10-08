"""How sensitive is the plan to the Ideal TP (Throughput) setting?

The Ideal TP is the throughput (liters per freezer per week) below which adding
more freezers stops paying off. It is a judgement call, so this script reruns the
model for a range of values and shows how the plan changes:
  * a lower Ideal TP lets more freezers in before the stop rule triggers,
  * a higher Ideal TP stops earlier, so fewer districts and freezers qualify.

Usage:
    python scripts/ideal_tp_sensitivity.py
Saves outputs/tables/ideal_tp_sensitivity.csv and outputs/figures/08_ideal_tp_sensitivity.png.
All data is simulated.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from footprint import census as census_mod  # noqa: E402
from footprint import charts, config, geo, model, pipeline, rollout  # noqa: E402

IDEAL_TP_VALUES = np.arange(13.0, 17.01, 0.5)


def run() -> pd.DataFrame:
    districts, population, attrs, retailers, census = pipeline.load_inputs()
    mapped = geo.map_points_to_districts(retailers, districts)
    metrics = model.district_metrics(mapped, attrs, population)
    supply = census_mod.district_supply(census_mod.run(census, mapped, districts))

    rows = []
    for tp in IDEAL_TP_VALUES:
        checked = census_mod.reality_check(model.prioritize(model.recommend(metrics, ideal_tp=tp)), supply)
        plan = rollout.build_plan(checked)
        rows.append({
            "ideal_tp": tp,
            "districts_with_demand": int((checked["recommended_new_outlets"] > 0).sum()),
            "shortlisted_districts": len(plan),
            "phase1_demand_outlets": int(plan["recommended_new_outlets"].sum()),
            "final_new_outlets": int(plan["final_new_outlets"].sum()),
            "supply_constrained_districts": int(plan["constraint"].str.startswith("Supply").sum()),
        })
    return pd.DataFrame(rows)


def chart(df: pd.DataFrame) -> None:
    plt = charts.plt
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8.5, 6.5), sharex=True, gridspec_kw={"hspace": 0.3})
    ax1.plot(df["ideal_tp"], df["phase1_demand_outlets"], color=charts.BLUE, linewidth=2, marker="o", markersize=5,
             label="Phase 1 demand (new outlets)")
    ax1.plot(df["ideal_tp"], df["final_new_outlets"], color=charts.ORANGE, linewidth=2, marker="o", markersize=5,
             label="Final after the census check")
    ax1.yaxis.set_major_formatter(charts.thousands)
    ax1.set_ylabel("New outlets (freezers)")
    ax1.legend(fontsize=8.5, loc="upper right")
    ax1.set_title("How the plan changes with the Ideal TP setting")
    colors = [charts.BLUE if abs(t - config.IDEAL_TP) < 1e-9 else charts.GREY_LINE for t in df["ideal_tp"]]
    ax2.bar(df["ideal_tp"], df["shortlisted_districts"], width=0.3, color=colors)
    for x, y in zip(df["ideal_tp"], df["shortlisted_districts"]):
        ax2.text(x, y, f"{y}", ha="center", va="bottom", fontsize=8, color=charts.INK_2)
    ax2.set_ylabel("Shortlisted districts")
    ax2.set_xlabel("Ideal TP (liters per freezer per week)")
    ax1.axvline(config.IDEAL_TP, color=charts.INK_3, linestyle="--", linewidth=1)
    ax1.set_ylim(0, None)
    ax1.text(config.IDEAL_TP, ax1.get_ylim()[1], f" Model setting ({config.IDEAL_TP:.0f})", fontsize=8.5,
             color=charts.INK_2, va="top")
    charts._note(fig, charts.SIM_NOTE)
    charts._save(fig, "08_ideal_tp_sensitivity.png")


if __name__ == "__main__":
    result = run()
    config.TABLES.mkdir(parents=True, exist_ok=True)
    result.to_csv(config.TABLES / "ideal_tp_sensitivity.csv", index=False)
    chart(result)
    print(result.to_string(index=False))
