import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon
import re
from tqdm import tqdm

cities_df = pd.read_csv('Maps.csv')
coordinates_df = pd.read_csv('MissedCoordinates.csv')

def multipolygon_string_to_polygon(multipolygon_string):
    if not isinstance(multipolygon_string, str):
        raise ValueError(f"Expected string for polygon coordinates, got {type(multipolygon_string)}: {multipolygon_string}")
    # Use regex to find all coordinate pairs
    coord_pattern = re.compile(r'(\d+\.\d+)\s+(\d+\.\d+)')
    coordinates = coord_pattern.findall(multipolygon_string)
    # Convert coordinate pairs to a list of tuples (lon, lat)
    coordinates = [(float(lon), float(lat)) for lon, lat in coordinates]
    return Polygon(coordinates)

cities_df['Co-ordinates'] = cities_df['Co-ordinates'].astype(str)

try:
    cities_df['geometry'] = cities_df['Co-ordinates'].apply(multipolygon_string_to_polygon)
except ValueError as e:
    print(f"Error processing polygons: {e}")
    raise

cities_gdf = gpd.GeoDataFrame(cities_df, geometry='geometry')

def find_city(lat, lon):
    point = Point(lon, lat)
    for idx, row in cities_gdf.iterrows():
        if row['geometry'].contains(point):
            return row['Name']
    return None

coordinates_df['City'] = None

for index, row in tqdm(coordinates_df.iterrows(), total=coordinates_df.shape[0], desc="Processing coordinates"):
    coordinates_df.at[index, 'City'] = find_city(row['Latitude'], row['Longtitude'])

coordinates_df.to_csv('Updated_Missed_Cordinates.csv', index=False)

print("Updated_Missed_Cordinates.csv has been created with the city labels.")