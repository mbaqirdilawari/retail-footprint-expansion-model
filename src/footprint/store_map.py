"""Interactive map of the sales target list (open outputs/sales_target_map.html in a browser)."""
from __future__ import annotations

import folium
import pandas as pd

from . import config

YEAR_COLORS = {2025: "#2a78d6", 2026: "#eb6834", 2027: "#1baf7a"}
PHASE_FILL = {"Phase 1": "#2a78d6", "Phase 2": "#eb6834", "Phase 3": "#1baf7a"}


def build(districts, district_model: pd.DataFrame, targets: pd.DataFrame, path) -> None:
    fmap = folium.Map(location=[30.4, 69.4], zoom_start=6, tiles="OpenStreetMap", prefer_canvas=True)

    shortlist = district_model[district_model["shortlisted"]][
        ["district", "phase", "priority_rank", "recommended_new_outlets", "usable_supply", "final_new_outlets", "constraint"]
    ]
    gdf = districts.merge(shortlist, on="district")
    gdf["geometry"] = gdf.geometry.simplify(0.01)  # lighter file, same look at this zoom
    gdf["priority_rank"] = gdf["priority_rank"].astype(int)
    folium.GeoJson(
        gdf.to_json(),
        name="Shortlisted districts",
        style_function=lambda f: {
            "fillColor": PHASE_FILL.get(f["properties"]["phase"], "#cccccc"),
            "color": "#ffffff",
            "weight": 1,
            "fillOpacity": 0.18,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["district", "priority_rank", "phase", "recommended_new_outlets", "usable_supply", "final_new_outlets", "constraint"],
            aliases=["District", "Priority rank", "Phase", "Demand (new outlets)", "Usable shops", "Final new outlets", "Constraint"],
        ),
    ).add_to(fmap)

    for year, color in YEAR_COLORS.items():
        stores = targets[targets["rollout_year"] == year]
        features = [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [round(s.longitude, 5), round(s.latitude, 5)]},
                "properties": {"Store": s.store_id, "District": s.district, "Channel": s.channel,
                               "Turnover": s.turnover_band, "Rollout year": int(year)},
            }
            for s in stores.itertuples(index=False)
        ]
        folium.GeoJson(
            {"type": "FeatureCollection", "features": features},
            name=f"Target stores, rollout {year} ({len(stores):,})",
            marker=folium.CircleMarker(radius=3, weight=0, fill=True, fill_opacity=0.85),
            style_function=lambda f, c=color: {"fillColor": c, "color": c},
            popup=folium.GeoJsonPopup(fields=["Store", "District", "Channel", "Turnover", "Rollout year"]),
        ).add_to(fmap)

    folium.LayerControl(collapsed=False).add_to(fmap)
    title = (
        "<div style='position:fixed;top:12px;left:60px;z-index:9999;background:white;padding:8px 12px;"
        "border-radius:6px;font-family:Arial;font-size:13px;box-shadow:0 1px 4px rgba(0,0,0,.2)'>"
        f"<b>Sales target list: {len(targets):,} stores in {targets['district'].nunique()} districts</b><br>"
        "<span style='color:#a00'>Simulated data for illustration only. Not real company or store data.</span></div>"
    )
    fmap.get_root().html.add_child(folium.Element(title))
    fmap.save(str(path))
