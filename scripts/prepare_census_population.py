"""Build the district population table from the public 2023 Census.

Source: Pakistan Bureau of Statistics, Population Census 2023 (district tables),
as converted to CSV by github.com/fahad-mirza/pakistan_census_2023_tables (MIT).

The census lists 137 districts, while the public boundary file (geoBoundaries,
2019 districts) has fewer, because some districts were split after 2019.
This script adds each newer district back into the boundary district it was
carved out of, so that every population figure lines up with a map polygon.

Usage:
    python scripts/prepare_census_population.py <path to District_Tehsil_Tables>
"""
import glob
import re
import sys
from pathlib import Path

import pandas as pd

# Census district name -> boundary file district name (only where they differ)
CENSUS_TO_BOUNDARY = {
    "BATAGRAM": "Battagram",
    "ISLAMABAD": "Islamabad Capital Territory",
    "JAFFARABAD": "Jafarabad",
    "SOHBATPUR": "Jafarabad",
    "KILLA ABDULLAH": "Qilla Abdullah",
    "CHAMAN": "Qilla Abdullah",
    "KILLA SAIFULLAH": "Qilla Saifullah",
    "DUKI": "Loralai",
    "HARNAI": "Sibi",
    "SHERANI": "Zhob",
    "SURAB": "Kalat",
    "WASHUK": "Kharan",
    "KAMBAR SHAHDAD KOT": "Qambar Shahdadkot",
    "LARKANA": "Qambar Shahdadkot",
    "KARACHI CENTRAL": "Karachi",
    "KARACHI EAST": "Karachi",
    "KARACHI SOUTH": "Karachi",
    "KARACHI WEST": "Karachi",
    "KEAMARI": "Karachi",
    "KORANGI": "Karachi",
    "MALIR": "Karachi",
    "NAUSHAHRO FEROZE": "Naushehro Feroze",
    "SHAHEED BENAZIRABAD": "Nawabshah",
    "SUJAWAL": "Thatta",
    "TANDO AHYAR": "Tando Allahyar",
    "KOLAI PALAS KOHISTAN": "Kohistan",
    "LOWER KOHISTAN": "Kohistan",
    "UPPER KOHISTAN": "Kohistan",
    "LOWER CHITRAL": "Chitral",
    "UPPER CHITRAL": "Chitral",
    "TORGHAR": "Mansehra",
    "CHINIOT": "Jhang",
    "NANKANA SAHIB": "Sheikhpura",
    "SHEIKHUPURA": "Sheikhpura",
    "VEHARI": "Vihari",
    "MIRPUR KHAS": "Mirpurkhas",
    "UMER KOT": "Umerkot",
}

PROVINCE_NAMES = {
    "punjab": "Punjab",
    "sindh": "Sindh",
    "kp": "Khyber Pakhtunkhwa",
    "balochistan": "Balochistan",
    "islamabad": "Islamabad Capital Territory",
}


def to_boundary_name(census_name: str) -> str:
    if census_name in CENSUS_TO_BOUNDARY:
        return CENSUS_TO_BOUNDARY[census_name]
    return census_name.title()


def main(table_dir: str) -> None:
    frames = []
    for path in glob.glob(f"{table_dir}/table_01_*_all.csv"):
        df = pd.read_csv(path)
        df = df[(df["admin_unit"] == "DISTRICT") & (df["region"] == "OVERALL")].copy()
        df["province"] = PROVINCE_NAMES[re.search(r"table_01_(\w+)_all", path).group(1)]
        frames.append(df)
    census = pd.concat(frames, ignore_index=True)
    census["district"] = census["name_admin_unit"].map(to_boundary_name)

    # Population weighted urban share, so merged districts stay correct
    census["urban_people"] = census["all_sexes"] * census["urban_prop"] / 100
    out = (
        census.groupby(["district", "province"], as_index=False)
        .agg(
            population_2017=("pop_2017", "sum"),
            population_2023=("all_sexes", "sum"),
            urban_people=("urban_people", "sum"),
        )
    )
    out["urban_share"] = (out["urban_people"] / out["population_2023"]).round(4)
    years = 6  # 2017 to 2023
    out["annual_growth_rate"] = (
        (out["population_2023"] / out["population_2017"]) ** (1 / years) - 1
    ).round(5)
    out = out.drop(columns="urban_people").sort_values("district")
    out[["population_2017", "population_2023"]] = out[
        ["population_2017", "population_2023"]
    ].astype(int)

    target = Path(__file__).resolve().parents[1] / "data/raw/census_2023_district_population.csv"
    out.to_csv(target, index=False)
    print(f"Saved {len(out)} districts to {target}")


if __name__ == "__main__":
    main(sys.argv[1])
