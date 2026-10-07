"""All model settings in one place.

Every number that drives a business decision lives here, so it can be changed
without touching the logic. The Excel model has the same values on its
"Inputs" sheet.

Short forms used across the project:
    PCC  = Per Capita Consumption (liters of ice cream per target person per year)
    PPO  = Population Per Outlet (target people for every freezer outlet)
    TP   = Throughput (liters sold per freezer per week)
    NI   = New Induction (a retailer that received a freezer during the year)
    LSM  = Living Standards Measure (LSM 5+ is the target, ice cream buying population)
    GOLY = Growth Over Last Year
    CAGR = Compound Annual Growth Rate
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"
DATA_SIM = ROOT / "data" / "simulated"
DATA_OUT = ROOT / "data" / "processed"
FIGURES = ROOT / "outputs" / "figures"
TABLES = ROOT / "outputs" / "tables"

# Random seed, so the simulated data is identical every time it is generated
SEED = 2024

# Years covered by the (simulated) sales history. The model base year is the last one.
YEARS = [2022, 2023, 2024]
BASE_YEAR = 2024

# One outlet means one freezer (cabinet) at one retailer.
WEEKS_PER_YEAR = 52

# ---------------------------------------------------------------------------
# Phase 1: demand model settings
# ---------------------------------------------------------------------------
IDEAL_TP = 15.0          # liters per freezer per week. Stop adding freezers below this.
IDEAL_PPO = 750          # industry benchmark: target people per outlet.
FIRST_FILL_LITERS = 80   # liters needed to stock a brand new freezer the first time.

# Which throughput to assume for every new outlet:
#   "ni_tp"        -> average TP of retailers inducted in the base year (what the original model used)
#   "district_tp"  -> average TP of all retailers in the district
NEW_OUTLET_TP_BASIS = "ni_tp"

# Layers group districts into five bands (Layer 01 is the strongest).
# PCC thresholds are in liters per target person per year.
PCC_LAYERS = [(1.20, "Layer 01"), (0.80, "Layer 02"), (0.45, "Layer 03"), (0.20, "Layer 04")]
PPO_LAYERS = [(50_000, "Layer 01"), (15_000, "Layer 02"), (3_500, "Layer 03"), (1_700, "Layer 04")]
LAST_LAYER = "Layer 05"

# How many districts make the priority shortlist
TOP_N_DISTRICTS = 50

# ---------------------------------------------------------------------------
# Phase 2: retail census reality check
# ---------------------------------------------------------------------------
# A store is "high potential" only if it meets ALL three conditions.
COMPETITOR_BRANDS = ["sells_coke_or_pepsi", "sells_dairy_milk", "sells_lays", "sells_sooper"]
TARGET_CHANNELS = ["Grocery", "Bakery", "Supermarket", "Petro Mart", "Pharmacy"]
TARGET_TURNOVER = "High"

# Not every eligible store will agree to take a freezer.
CENSUS_CONVERSION_RATE = 0.80

# A census store within this distance of an existing customer is the same shop.
EXISTING_CUSTOMER_MATCH_METERS = 25

# Budget scenarios: total freezers the company can fund nationally.
BUDGET_SCENARIOS = [4_000, 6_000]

# Roll out over three years (same split as the original plan: 300, 300, 250 out of 850).
PHASING = {2025: 300 / 850, 2026: 300 / 850, 2027: 250 / 850}

# ---------------------------------------------------------------------------
# Expansion order (from the strategy brief): strongholds first, then their
# neighbours, then districts with a large target population, then the rest.
# ---------------------------------------------------------------------------
WAVE_ORDER = {
    "Stronghold": 1,
    "Neighbouring": 2,
    "Population High": 3,
    "Rest": 4,
}
