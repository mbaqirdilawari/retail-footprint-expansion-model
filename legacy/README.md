# Legacy code

`main.py` is the original point in polygon script I wrote during the project, kept unchanged so the starting point is visible.

What it did:

1. Read district boundaries stored as raw coordinate text (`Maps.csv`) and parsed each one into a polygon with a regular expression and Shapely.
2. Read the retailers that could not be matched by name (`MissedCoordinates.csv`).
3. For every retailer, looped over every district polygon until it found the one that contains the retailer's point.
4. Saved the retailers with their district (`Updated_Missed_Cordinates.csv`).

The input files were company data and are not included. The rebuilt version is `src/footprint/geo.py`, which does the same test with a GeoPandas spatial join, cleans swapped and missing coordinates, and is reused for the retail census in Phase 2.
