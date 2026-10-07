"""Charts for the README and the notebook (saved as PNG in outputs/figures)."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from . import config, geo, model  # noqa: E402

# Colors (validated, colorblind safe categorical order) and neutral inks
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
GREY_FILL, GREY_LINE = "#e4e2dc", "#b8b6b0"
INK, INK_2, INK_3 = "#0b0b0b", "#52514e", "#8a8984"
SURFACE = "#ffffff"
PHASE_COLORS = {"Phase 1": BLUE, "Phase 2": ORANGE, "Phase 3": AQUA}

plt.rcParams.update(
    {
        "font.family": ["Inter", "DejaVu Sans", "Arial", "sans-serif"],
        "font.size": 10,
        "axes.edgecolor": GREY_LINE,
        "axes.labelcolor": INK_2,
        "axes.titlecolor": INK,
        "axes.titlesize": 13,
        "axes.titleweight": "semibold",
        "axes.titlelocation": "left",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": INK_2,
        "ytick.color": INK_2,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.dpi": 160,
        "savefig.bbox": "tight",
        "legend.frameon": False,
    }
)

thousands = FuncFormatter(lambda v, _: f"{v:,.0f}")


def _note(fig, text: str) -> None:
    fig.text(0.01, -0.02, text, fontsize=8, color=INK_3, ha="left", va="top")


def _background(ax) -> None:
    """Areas not covered by the public district census, drawn in a lighter grey."""
    full = geo.load_districts(include_excluded=True)
    full[full["province"].isin(geo.EXCLUDED_PROVINCES)].plot(ax=ax, color="#f1f0ec", edgecolor=SURFACE, linewidth=0.6)


def _save(fig, name: str) -> None:
    config.FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(config.FIGURES / name)
    plt.close(fig)


SIM_NOTE = "Simulated data for illustration only. District boundaries: geoBoundaries. Population: Pakistan Census 2023."


def retailer_mapping_map(districts, retailers_mapped: pd.DataFrame) -> None:
    """Every retailer, placed in its official district from its GPS coordinates."""
    fig, ax = plt.subplots(figsize=(7.5, 6.6))
    _background(ax)
    districts.plot(ax=ax, color=GREY_FILL, edgecolor=SURFACE, linewidth=0.6)
    ok = retailers_mapped[retailers_mapped["mapping_status"] == "Mapped"]
    ax.scatter(ok["longitude"], ok["latitude"], s=0.4, color=BLUE, alpha=0.35, linewidths=0)
    n_typed = retailers_mapped["district_typed"].fillna("").str.strip().nunique()
    ax.set_title(f"{len(ok):,} retailers mapped to {ok['district_mapped'].nunique()} official districts", pad=22)
    ax.text(0, 1.01, f"The raw data had {n_typed:,} different spellings of district names",
            transform=ax.transAxes, color=INK_2, fontsize=9.5, va="bottom")
    ax.set_axis_off()
    _note(fig, SIM_NOTE)
    _save(fig, "01_retailers_mapped_to_districts.png")


def priority_map(districts, district_model: pd.DataFrame) -> None:
    """Shortlisted districts colored by phase."""
    gdf = districts.merge(district_model[["district", "shortlisted", "phase", "final_new_outlets"]], on="district")
    fig, ax = plt.subplots(figsize=(7.5, 6.6))
    _background(ax)
    gdf[~gdf["shortlisted"]].plot(ax=ax, color=GREY_FILL, edgecolor=SURFACE, linewidth=0.6)
    for phase, color in PHASE_COLORS.items():
        part = gdf[gdf["shortlisted"] & (gdf["phase"] == phase)]
        if len(part):
            part.plot(ax=ax, color=color, edgecolor=SURFACE, linewidth=0.6)
    descriptions = {
        "Phase 1": "Phase 1: high consumption, underserved",
        "Phase 2": "Phase 2: high consumption, well served",
        "Phase 3": "Phase 3: other shortlisted districts",
    }
    present = [p for p in PHASE_COLORS if (gdf["shortlisted"] & (gdf["phase"] == p)).any()]
    handles = [plt.Rectangle((0, 0), 1, 1, color=PHASE_COLORS[p]) for p in present]
    labels = [descriptions[p] for p in present]
    handles += [plt.Rectangle((0, 0), 1, 1, color=GREY_FILL), plt.Rectangle((0, 0), 1, 1, color="#f1f0ec")]
    labels += ["Not shortlisted", "Not covered by public district census"]
    ax.legend(handles, labels, loc="upper left", fontsize=8.5, labelcolor=INK_2)
    n = int(gdf["shortlisted"].sum())
    ax.set_title(f"Where to expand: {n} shortlisted districts")
    ax.set_axis_off()
    _note(fig, SIM_NOTE)
    _save(fig, "02_priority_districts_map.png")


def _label_points(ax, df, x, y, names, max_labels=8):
    """Label the largest districts, nudging labels so they do not overlap."""
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    placed = []
    offsets = [(5, 4, "left"), (5, -12, "left"), (-5, 4, "right"), (-5, -12, "right"), (5, 14, "left")]
    rows = df[df["district"].isin(names)].nlargest(max_labels, "target_population_2024")
    for _, r in rows.iterrows():
        for dx, dy, ha in offsets:
            t = ax.annotate(r["district"], (r[x], r[y]), xytext=(dx, dy), textcoords="offset points",
                            fontsize=8, color=INK_2, ha=ha)
            box = t.get_window_extent(renderer).expanded(1.05, 1.15)
            if not any(box.overlaps(b) for b in placed):
                placed.append(box)
                break
            t.remove()


def quadrant_pcc_ppo(district_model: pd.DataFrame) -> None:
    """Presentation view: PCC against the national PCC, PPO against the ideal PPO."""
    df = district_model[district_model["retailers_2024"] > 0]
    nat = df["national_pcc"].iloc[0]
    fig, ax = plt.subplots(figsize=(8.5, 6))
    for phase, color in PHASE_COLORS.items():
        part = df[df["phase"] == phase]
        if len(part) == 0:
            continue
        ax.scatter(part["pcc_2024"], part["ppo_2024"], s=np.sqrt(part["target_population_2024"]) / 25,
                   color=color, alpha=0.85, edgecolor=SURFACE, linewidth=1.2, label=phase)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.axvline(nat, color=INK_3, linewidth=1, linestyle="--", label=f"National PCC ({nat:.2f} liters)")
    ax.axhline(config.IDEAL_PPO, color=INK_3, linewidth=1, linestyle=":", label=f"Industry ideal PPO ({config.IDEAL_PPO})")
    ylo, yhi = ax.get_ylim()
    ax.set_ylim(ylo * 0.8, yhi * 1.6)
    box = {"boxstyle": "round,pad=0.3", "facecolor": SURFACE, "edgecolor": "none", "alpha": 0.9}
    for qx, qy, txt in [(0.99, 0.99, "Q1: high consumption, underserved"),
                        (0.99, 0.01, "Q2: high consumption, well served"),
                        (0.01, 0.99, "Q3: low consumption, underserved"),
                        (0.01, 0.01, "Q4: low consumption, well served")]:
        ax.text(qx, qy, txt, transform=ax.transAxes, ha="right" if qx > 0.5 else "left",
                va="top" if qy > 0.5 else "bottom", fontsize=8.5, color=INK_3, bbox=box)
    _label_points(ax, df, "pcc_2024", "ppo_2024", set(df[df["shortlisted"]]["district"]))
    ax.set_xlabel("PCC: Per Capita Consumption (liters per target person per year, log scale)")
    ax.set_ylabel("PPO: Population Per Outlet (log scale)")
    ax.yaxis.set_major_formatter(thousands)
    ax.set_title("Quadrant view 1: consumption against outlet coverage")
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, 0.06), fontsize=8.5,
              title="Bubble size = target population", title_fontsize=8)
    _note(fig, SIM_NOTE)
    _save(fig, "03_quadrant_pcc_vs_ppo.png")


def quadrant_tp_ppo(district_model: pd.DataFrame) -> None:
    """Working notes view: TP against the ideal TP, PPO against the ideal PPO."""
    df = district_model[district_model["retailers_2024"] > 0]
    expand = (df["tp_2024"] > config.IDEAL_TP) & (df["ppo_2024"] > config.IDEAL_PPO)
    fig, ax = plt.subplots(figsize=(8.5, 6))
    ax.scatter(df.loc[~expand, "tp_2024"], df.loc[~expand, "ppo_2024"], s=28, color=GREY_LINE,
               edgecolor=SURFACE, linewidth=1, label="Do not expand yet")
    ax.scatter(df.loc[expand, "tp_2024"], df.loc[expand, "ppo_2024"], s=34, color=BLUE,
               edgecolor=SURFACE, linewidth=1, label="Expand: High TP and High PPO")
    ax.set_yscale("log")
    ax.axvline(config.IDEAL_TP, color=INK_3, linewidth=1, linestyle="--", label=f"Ideal TP ({config.IDEAL_TP:.0f} liters per week)")
    ax.axhline(config.IDEAL_PPO, color=INK_3, linewidth=1, linestyle=":", label=f"Ideal PPO ({config.IDEAL_PPO})")
    ylo, yhi = ax.get_ylim()
    ax.set_ylim(ylo * 0.8, yhi * 1.6)
    _label_points(ax, df, "tp_2024", "ppo_2024", set(df[expand]["district"]))
    ax.set_xlabel("TP: Throughput (liters per freezer per week)")
    ax.set_ylabel("PPO: Population Per Outlet (log scale)")
    ax.yaxis.set_major_formatter(thousands)
    ax.set_title("Quadrant view 2: freezer productivity against outlet coverage")
    ax.legend(loc="upper right", fontsize=8.5)
    _note(fig, SIM_NOTE)
    _save(fig, "04_quadrant_tp_vs_ppo.png")


def tp_curve_example(district_model: pd.DataFrame, district: str | None = None) -> str:
    """The core idea: more freezers add volume, but each freezer sells less."""
    df = district_model
    if district is None:
        pool = df[df["limiting_factor"] == "Stopped by TP reaching ideal"]
        district = pool.nlargest(1, "recommended_new_outlets")["district"].iloc[0]
    r = df[df["district"] == district].iloc[0]
    stop = int(r["recommended_new_outlets"])
    curve = model.tp_curve(int(r["retailers_2024"]), r["volume_2024"], r["target_population_2024"],
                           r["new_outlet_tp"], max_new=int(stop * 2.2) + 10)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8.5, 7), sharex=True, gridspec_kw={"hspace": 0.25})
    ax1.plot(curve["total_outlets"], curve["volume"] / 1000, color=BLUE, linewidth=2)
    ax1.set_ylabel("Total volume (thousand liters per year)")
    ax1.yaxis.set_major_formatter(thousands)
    ax1.set_title(f"{district}: adding freezers until throughput reaches the ideal")
    ax2.plot(curve["total_outlets"], curve["tp"], color=ORANGE, linewidth=2)
    ax2.axhline(config.IDEAL_TP, color=INK_3, linewidth=1, linestyle="--")
    ax2.text(curve["total_outlets"].iloc[-1], config.IDEAL_TP, f"Ideal TP {config.IDEAL_TP:.0f} ",
             ha="right", va="bottom", fontsize=8.5, color=INK_2)
    ax2.set_ylabel("TP (liters per freezer per week)")
    ax2.set_xlabel("Total outlets (freezers) in the district")
    stop_x = int(r["retailers_2024"]) + stop
    for ax in (ax1, ax2):
        ax.axvline(stop_x, color=INK_2, linewidth=1, linestyle=":")
        ax.xaxis.set_major_formatter(thousands)
    ax2.annotate(f"Stop at {stop_x:,} outlets\n(+{stop:,} new freezers)", xy=(stop_x, config.IDEAL_TP),
                 xytext=(10, 25), textcoords="offset points", fontsize=8.5, color=INK,
                 arrowprops={"arrowstyle": "-", "color": INK_3, "linewidth": 0.8})
    ax1.annotate("Today", xy=(r["retailers_2024"], r["volume_2024"] / 1000), xytext=(-8, 10),
                 textcoords="offset points", fontsize=8.5, color=INK_2, ha="right")
    _note(fig, SIM_NOTE)
    _save(fig, "05_tp_curve_example.png")
    return district


def demand_vs_supply(plan: pd.DataFrame, top: int = 15) -> None:
    """Phase 2: what demand supports against how many suitable shops exist."""
    df = plan.nlargest(top, "recommended_new_outlets").iloc[::-1]
    y = np.arange(len(df))
    h = 0.38
    fig, ax = plt.subplots(figsize=(8.5, 6.5))
    ax.barh(y + h / 2, df["recommended_new_outlets"], height=h - 0.04, color=BLUE, label="Demand (Phase 1 model)")
    ax.barh(y - h / 2, df["usable_supply"], height=h - 0.04, color=ORANGE, label="Usable shops (Phase 2 census)")
    for yi, (d, s) in enumerate(zip(df["recommended_new_outlets"], df["usable_supply"])):
        ax.text(d, yi + h / 2, f" {d:,}", va="center", fontsize=7.5, color=INK_2)
        ax.text(s, yi - h / 2, f" {s:,}", va="center", fontsize=7.5, color=INK_2)
    ax.set_yticks(y, df["district"])
    ax.xaxis.set_major_formatter(thousands)
    ax.set_xlabel("New freezers")
    ax.set_title("Demand against real shops: the final number is the smaller of the two")
    ax.legend(loc="lower right", fontsize=8.5)
    ax.grid(axis="x", color=GREY_FILL, linewidth=0.8)
    ax.set_axisbelow(True)
    _note(fig, SIM_NOTE)
    _save(fig, "06_demand_vs_supply.png")


def census_funnel(stores: pd.DataFrame, conversion_rate: float = config.CENSUS_CONVERSION_RATE) -> None:
    """How the census store list is narrowed down to usable shops."""
    s = stores[stores["mapping_status"] == "Mapped"]
    step1 = len(s)
    step2 = int(s["sells_all_competitor_brands"].sum())
    step3 = int((s["sells_all_competitor_brands"] & s["in_target_channel"]).sum())
    step4 = int(s["high_potential"].sum())
    step5 = int(s["eligible_new_store"].sum())
    step6 = int(np.floor(step5 * conversion_rate))
    labels = [
        "Stores in the retail census",
        "Sell Coke or Pepsi, Dairy Milk, Lays and Sooper",
        "In a target channel",
        "High turnover",
        "Not already our customer",
        f"Usable after {conversion_rate:.0%} conversion rate",
    ]
    values = [step1, step2, step3, step4, step5, step6]
    shades = ["#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#1c5cab"]
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    y = np.arange(len(values))[::-1]
    ax.barh(y, values, color=shades, height=0.62)
    for yi, v in zip(y, values):
        ax.text(v, yi, f"  {v:,}", va="center", fontsize=9, color=INK)
    ax.set_yticks(y, labels)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.set_title("Phase 2 funnel: from every store to the shops that can take a freezer")
    _note(fig, SIM_NOTE)
    _save(fig, "07_census_funnel.png")


def all_charts(results: dict) -> str:
    districts, m, plan = results["districts"], results["district_model"], results["plan"]
    retailer_mapping_map(districts, results["retailers_mapped"])
    priority_map(districts, m)
    quadrant_pcc_ppo(m)
    quadrant_tp_ppo(m)
    example = tp_curve_example(m)
    demand_vs_supply(plan)
    census_funnel(results["stores"])
    return example
