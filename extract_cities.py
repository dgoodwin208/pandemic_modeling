#!/usr/bin/env python3
"""Extract African cities with population >= 500k from Natural Earth data."""

import json
import geopandas as gpd

# African country ISO codes
AFRICAN_ISO_CODES = {
    'DZ', 'AO', 'BJ', 'BW', 'BF', 'BI', 'CV', 'CM', 'CF', 'TD', 'KM', 'CG', 'CD',
    'DJ', 'EG', 'GQ', 'ER', 'SZ', 'ET', 'GA', 'GM', 'GH', 'GN', 'GW', 'CI', 'KE',
    'LS', 'LR', 'LY', 'MG', 'MW', 'ML', 'MR', 'MU', 'MA', 'MZ', 'NA', 'NE', 'NG',
    'RW', 'ST', 'SN', 'SC', 'SL', 'SO', 'ZA', 'SS', 'SD', 'TZ', 'TG', 'TN', 'UG',
    'ZM', 'ZW', 'EH'  # Western Sahara
}

# Population threshold
MIN_POPULATION = 100000

def main():
    # Read shapefile
    shapefile_path = "frontend/public/data/ne_10m_populated_places_simple.shp"
    print(f"Reading shapefile: {shapefile_path}")

    gdf = gpd.read_file(shapefile_path)
    print(f"Total places: {len(gdf)}")
    print(f"Columns: {list(gdf.columns)}")

    # Show sample data
    print("\nSample of first 5 rows (key columns):")
    print(gdf[['name', 'iso_a2', 'adm0name', 'pop_max', 'latitude', 'longitude']].head())

    # Filter for African cities
    african_cities = gdf[gdf['iso_a2'].isin(AFRICAN_ISO_CODES)]
    print(f"\nAfrican cities (all): {len(african_cities)}")

    # Filter by population
    large_african_cities = african_cities[african_cities['pop_max'] >= MIN_POPULATION]
    print(f"African cities with pop >= {MIN_POPULATION:,}: {len(large_african_cities)}")

    # Show the cities we found
    if len(large_african_cities) > 0:
        print("\nCities found:")
        for _, row in large_african_cities.sort_values('pop_max', ascending=False).head(20).iterrows():
            print(f"  {row['name']}, {row['adm0name']}: {row['pop_max']:,.0f}")

    # Create GeoJSON output
    output_data = {
        "type": "FeatureCollection",
        "features": []
    }

    for _, row in large_african_cities.iterrows():
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(row['longitude']), float(row['latitude'])]
            },
            "properties": {
                "name": row['name'],
                "country": row['adm0name'],
                "iso_a2": row['iso_a2'],
                "population": int(row['pop_max']),
                "rank": int(row['rank_max']) if row['rank_max'] else 0
            }
        }
        output_data["features"].append(feature)

    # Sort features by population descending
    output_data["features"].sort(key=lambda x: x["properties"]["population"], reverse=True)

    # Write output
    output_path = "frontend/public/data/africa_cities.geojson"
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"\nWrote {len(output_data['features'])} cities to {output_path}")

if __name__ == "__main__":
    main()
