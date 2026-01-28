#!/usr/bin/env python3
"""
Extract African cities with population >= threshold to CSV.
Includes rough medical services score per country.

Medical services score (0-100) is based on Healthcare Access and Quality (HAQ) Index
from the Global Burden of Disease study. Higher = better healthcare access.
"""

import csv
import json
import sys
from pathlib import Path

import geopandas as gpd

# African country ISO codes
AFRICAN_ISO_CODES = {
    'DZ', 'AO', 'BJ', 'BW', 'BF', 'BI', 'CV', 'CM', 'CF', 'TD', 'KM', 'CG', 'CD',
    'DJ', 'EG', 'GQ', 'ER', 'SZ', 'ET', 'GA', 'GM', 'GH', 'GN', 'GW', 'CI', 'KE',
    'LS', 'LR', 'LY', 'MG', 'MW', 'ML', 'MR', 'MU', 'MA', 'MZ', 'NA', 'NE', 'NG',
    'RW', 'ST', 'SN', 'SC', 'SL', 'SO', 'ZA', 'SS', 'SD', 'TZ', 'TG', 'TN', 'UG',
    'ZM', 'ZW', 'EH'
}

# Healthcare Access and Quality (HAQ) Index scores by country (0-100 scale)
# Source: Global Burden of Disease 2019 study
# Higher scores = better healthcare access and quality
MEDICAL_SERVICES_SCORE = {
    # North Africa (generally higher scores)
    'DZ': 62,  # Algeria
    'EG': 55,  # Egypt
    'LY': 58,  # Libya
    'MA': 53,  # Morocco
    'TN': 65,  # Tunisia

    # Southern Africa
    'BW': 48,  # Botswana
    'LS': 38,  # Lesotho
    'NA': 45,  # Namibia
    'ZA': 52,  # South Africa
    'SZ': 36,  # Eswatini
    'ZW': 40,  # Zimbabwe
    'ZM': 38,  # Zambia
    'MZ': 32,  # Mozambique
    'MW': 35,  # Malawi

    # East Africa
    'KE': 42,  # Kenya
    'TZ': 36,  # Tanzania
    'UG': 38,  # Uganda
    'RW': 44,  # Rwanda
    'BI': 30,  # Burundi
    'ET': 34,  # Ethiopia
    'ER': 28,  # Eritrea
    'DJ': 35,  # Djibouti
    'SO': 19,  # Somalia
    'SS': 18,  # South Sudan
    'SD': 35,  # Sudan

    # West Africa
    'NG': 37,  # Nigeria
    'GH': 45,  # Ghana
    'CI': 36,  # Côte d'Ivoire
    'SN': 38,  # Senegal
    'ML': 28,  # Mali
    'BF': 32,  # Burkina Faso
    'NE': 26,  # Niger
    'TD': 24,  # Chad
    'MR': 34,  # Mauritania
    'GM': 38,  # Gambia
    'GW': 28,  # Guinea-Bissau
    'GN': 30,  # Guinea
    'SL': 30,  # Sierra Leone
    'LR': 32,  # Liberia
    'BJ': 38,  # Benin
    'TG': 36,  # Togo
    'CV': 58,  # Cape Verde

    # Central Africa
    'CM': 38,  # Cameroon
    'CF': 22,  # Central African Republic
    'CG': 36,  # Congo
    'CD': 28,  # DR Congo
    'GA': 48,  # Gabon
    'GQ': 45,  # Equatorial Guinea
    'ST': 52,  # São Tomé and Príncipe
    'AO': 32,  # Angola

    # Island nations
    'MG': 32,  # Madagascar
    'MU': 68,  # Mauritius
    'SC': 70,  # Seychelles
    'KM': 35,  # Comoros

    # Other
    'EH': 40,  # Western Sahara (estimated, limited data)
}

# Default score for countries not in the lookup
DEFAULT_MEDICAL_SCORE = 35


def extract_cities(
    shapefile_path: str,
    output_csv: str,
    output_json: str,
    min_population: int = 100000
) -> int:
    """
    Extract African cities to CSV and JSON.

    Args:
        shapefile_path: Path to Natural Earth populated places shapefile
        output_csv: Path for output CSV
        output_json: Path for output JSON (for frontend)
        min_population: Minimum population threshold

    Returns:
        Number of cities extracted
    """
    print(f"Reading shapefile: {shapefile_path}")
    gdf = gpd.read_file(shapefile_path)
    print(f"Total places in dataset: {len(gdf)}")

    # Filter for African cities
    african_cities = gdf[gdf['iso_a2'].isin(AFRICAN_ISO_CODES)]
    print(f"African cities (all sizes): {len(african_cities)}")

    # Filter by population
    large_cities = african_cities[african_cities['pop_max'] >= min_population]
    print(f"Cities with population >= {min_population:,}: {len(large_cities)}")

    # Sort by population descending
    large_cities = large_cities.sort_values('pop_max', ascending=False)

    # Prepare output data
    rows = []
    for _, row in large_cities.iterrows():
        iso_code = row['iso_a2']
        medical_score = MEDICAL_SERVICES_SCORE.get(iso_code, DEFAULT_MEDICAL_SCORE)

        rows.append({
            'city': row['name'],
            'country': row['adm0name'],
            'country_code': iso_code,
            'latitude': round(float(row['latitude']), 4),
            'longitude': round(float(row['longitude']), 4),
            'population': int(row['pop_max']),
            'medical_services_score': medical_score,
        })

    # Write CSV
    csv_file = Path(output_csv)
    csv_file.parent.mkdir(parents=True, exist_ok=True)

    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'city', 'country', 'country_code', 'latitude', 'longitude',
            'population', 'medical_services_score'
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote {len(rows)} cities to {output_csv}")

    # Write JSON for frontend
    json_file = Path(output_json)
    json_file.parent.mkdir(parents=True, exist_ok=True)

    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump({"cities": rows}, f, indent=2)

    print(f"Wrote {len(rows)} cities to {output_json}")

    # Show top 10
    print("\nTop 10 cities by population:")
    for i, row in enumerate(rows[:10], 1):
        print(f"  {i}. {row['city']}, {row['country']}: "
              f"{row['population']:,} (medical score: {row['medical_services_score']})")

    return len(rows)


def main():
    # Paths
    project_root = Path(__file__).parent.parent
    shapefile = project_root / "frontend/public/data/ne_10m_populated_places_simple.shp"
    output_csv = project_root / "backend/data/african_cities.csv"
    output_json = project_root / "frontend/public/data/african_cities.json"

    # Default threshold, can be overridden via command line
    min_pop = 100000
    if len(sys.argv) > 1:
        min_pop = int(sys.argv[1])
        print(f"Using population threshold: {min_pop:,}")

    if not shapefile.exists():
        print(f"Error: Shapefile not found at {shapefile}")
        sys.exit(1)

    count = extract_cities(
        shapefile_path=str(shapefile),
        output_csv=str(output_csv),
        output_json=str(output_json),
        min_population=min_pop
    )

    print(f"\nDone! Extracted {count} cities.")


if __name__ == "__main__":
    main()
