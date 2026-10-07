# Outputs

Everything in this folder is produced by `python run_pipeline.py`. **All results come from simulated data** and only demonstrate the method. They are not real company figures.

Short forms used below: **PCC** (Per Capita Consumption, liters per target person per year), **PPO** (Population Per Outlet, target people for every freezer outlet), **TP** (Throughput, liters sold per freezer per week), **NI** (New Induction, a retailer that received a freezer during the year).

## Tables (`tables/`)

### `expansion_plan_top50.csv`
One row per shortlisted district, in priority order.

| Column | Meaning |
|---|---|
| `priority_rank` | Order of expansion (1 = first) |
| `district`, `province`, `region` | Location and sales region |
| `nature_of_district` | Stronghold, Neighbouring, Population High or Rest (sets the expansion wave) |
| `phase` | Phase 1, 2 or 3 from the PCC against PPO quadrant |
| `quadrant_pcc_ppo`, `quadrant_tp_ppo` | The district's position in each quadrant view |
| `retailers_2024`, `ppo_2024`, `tp_2024` | Outlets, PPO and TP in the base year |
| `recommended_new_outlets` | Phase 1 demand: new freezers before TP or PPO reaches its ideal |
| `limiting_factor` | Which limit stopped the additions (TP or PPO) |
| `usable_supply` | Phase 2: suitable census shops not yet customers, after the 80 percent conversion rate |
| `final_new_outlets` | The smaller of demand and usable supply |
| `constraint` | Supply constrained (not enough shops) or demand constrained (enough shops) |
| `budget_4000`, `budget_6000` | Freezers allocated if only 4,000 or 6,000 are funded nationally |
| `rollout_2025`, `rollout_2026`, `rollout_2027` | Final new freezers split by year |

### `sales_target_list.csv`
The exact stores the sales team should visit, one row per new freezer.

| Column | Meaning |
|---|---|
| `priority_rank`, `district`, `phase` | The district the store belongs to |
| `rollout_year` | Year the store should receive its freezer (highest turnover stores first) |
| `store_id` | Simulated census store identifier |
| `channel`, `turnover_band`, `est_monthly_turnover_pkr` | Store type and estimated monthly turnover in PKR |
| `latitude`, `longitude` | Store location |

### `data_quality_summary.csv`
Counts from the data cleaning step: retailer records, distinct typed district names, coordinates fixed or invalid, and records mapped to an official district.

### `vba_check.csv`
Result of running the VBA macro (`scripts/check_vba_with_libreoffice.py`): the macro's recommendation and limiting factor for each district, the Excel formula answer, and whether they match.

## Figures (`figures/`)

| File | What it shows |
|---|---|
| `01_retailers_mapped_to_districts.png` | Every retailer placed in its official district from GPS coordinates |
| `02_priority_districts_map.png` | Shortlisted districts colored by phase |
| `03_quadrant_pcc_vs_ppo.png` | Quadrant view 1: PCC against the national PCC, PPO against the ideal PPO (750) |
| `04_quadrant_tp_vs_ppo.png` | Quadrant view 2: TP against the ideal TP (15), PPO against the ideal PPO |
| `05_tp_curve_example.png` | One district: volume and TP as freezers are added, and where to stop |
| `06_demand_vs_supply.png` | Phase 1 demand against Phase 2 usable shops for the largest districts |
| `07_census_funnel.png` | How the retail census is narrowed down to usable shops |

## Interactive map

`sales_target_map.html` shows the shortlisted districts and every target store by rollout year. Download it and open it in a web browser.
