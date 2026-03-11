#!/usr/bin/env python3
"""
Process and normalize downloaded health facility data.
Associates facilities with cities based on geographic proximity.
Creates curated datasets for the frontend.
"""

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371  # Earth's radius in km

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def normalize_facility_type(amenity: str, healthcare: str) -> str:
    amenity = (amenity or '').lower().strip()
    healthcare = (healthcare or '').lower().strip()

    # Priority: more specific healthcare field, then amenity
    type_val = healthcare if healthcare else amenity

    type_mapping = {
        'hospital': 'hospital',
        'clinic': 'clinic',
        'health_centre': 'health_center',
        'health_center': 'health_center',
        'health centre': 'health_center',
        'health center': 'health_center',
        'doctors': 'clinic',
        'doctor': 'clinic',
        'pharmacy': 'pharmacy',
        'dentist': 'dentist',
        'laboratory': 'laboratory',
        'birthing_centre': 'maternity',
        'birthing_center': 'maternity',
        'maternity': 'maternity',
        'rehabilitation': 'rehabilitation',
        'nursing_home': 'nursing_home',
        'blood_bank': 'blood_bank',
        'blood_donation': 'blood_bank',
        'optometrist': 'optometry',
        'midwife': 'maternity',
        'health_post': 'health_post',
        'dispensary': 'dispensary',
    }

    return type_mapping.get(type_val, type_val or 'unknown')


def parse_int_or_none(value: str) -> int | None:
    if not value:
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def load_cities(cities_file: Path) -> list[dict]:
    with open(cities_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['cities']


def find_nearest_city(lat: float, lon: float, cities: list[dict], max_distance_km: float = 50) -> dict | None:
    nearest = None
    min_distance = float('inf')

    for city in cities:
        distance = haversine_distance(lat, lon, city['latitude'], city['longitude'])
        if distance < min_distance and distance <= max_distance_km:
            min_distance = distance
            nearest = city
            nearest_distance = distance

    if nearest:
        return {**nearest, 'distance_km': round(nearest_distance, 2)}
    return None


def process_raw_files(raw_dir: Path, cities: list[dict]) -> tuple[list[dict], dict]:
    all_facilities = []
    stats = defaultdict(lambda: defaultdict(int))

    csv_files = list(raw_dir.glob("*_healthsites.csv"))
    print(f"Processing {len(csv_files)} country files...")

    for csv_file in sorted(csv_files):
        iso_code = csv_file.stem.split('_')[0].upper()
        country_facilities = []

        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        lon = float(row.get('X', 0))
                        lat = float(row.get('Y', 0))
                    except (ValueError, TypeError):
                        continue

                    # Skip invalid coordinates
                    if lat == 0 and lon == 0:
                        continue
                    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                        continue

                    facility_type = normalize_facility_type(
                        row.get('amenity', ''),
                        row.get('healthcare', '')
                    )

                    facility = {
                        'name': row.get('name', '').strip() or 'Unknown',
                        'type': facility_type,
                        'latitude': round(lat, 6),
                        'longitude': round(lon, 6),
                        'country_code': iso_code,
                        'beds': parse_int_or_none(row.get('beds', '')),
                        'has_emergency': row.get('emergency', '').lower() in ('yes', 'true', '1'),
                        'operational_status': row.get('operational_status', '').strip() or 'unknown',
                        'osm_id': row.get('osm_id', ''),
                    }

                    nearest_city = find_nearest_city(lat, lon, cities)
                    if nearest_city:
                        facility['city'] = nearest_city['city']
                        facility['city_distance_km'] = nearest_city['distance_km']
                    else:
                        facility['city'] = None
                        facility['city_distance_km'] = None

                    country_facilities.append(facility)
                    stats[iso_code]['total'] += 1
                    stats[iso_code][facility_type] += 1

        except Exception as e:
            print(f"  Error processing {csv_file.name}: {e}")
            continue

        all_facilities.extend(country_facilities)
        print(f"  {iso_code}: {len(country_facilities):,} facilities processed")

    return all_facilities, dict(stats)


def aggregate_by_city(facilities: list[dict], cities: list[dict]) -> list[dict]:
    city_stats = defaultdict(lambda: {
        'total_facilities': 0,
        'hospitals': 0,
        'clinics': 0,
        'health_centers': 0,
        'pharmacies': 0,
        'laboratories': 0,
        'other': 0,
        'total_beds': 0,
        'emergency_facilities': 0,
    })

    for facility in facilities:
        city_name = facility.get('city')
        if not city_name:
            continue

        country_code = facility.get('country_code')
        key = f"{city_name}|{country_code}"

        city_stats[key]['total_facilities'] += 1

        ftype = facility['type']
        if ftype == 'hospital':
            city_stats[key]['hospitals'] += 1
        elif ftype == 'clinic':
            city_stats[key]['clinics'] += 1
        elif ftype in ('health_center', 'health_post', 'dispensary'):
            city_stats[key]['health_centers'] += 1
        elif ftype == 'pharmacy':
            city_stats[key]['pharmacies'] += 1
        elif ftype == 'laboratory':
            city_stats[key]['laboratories'] += 1
        else:
            city_stats[key]['other'] += 1

        if facility.get('beds'):
            city_stats[key]['total_beds'] += facility['beds']

        if facility.get('has_emergency'):
            city_stats[key]['emergency_facilities'] += 1

    # Merge with original city data
    enriched_cities = []
    for city in cities:
        key = f"{city['city']}|{city['country_code']}"
        stats = city_stats.get(key, {
            'total_facilities': 0,
            'hospitals': 0,
            'clinics': 0,
            'health_centers': 0,
            'pharmacies': 0,
            'laboratories': 0,
            'other': 0,
            'total_beds': 0,
            'emergency_facilities': 0,
        })

        population = city.get('population', 0)
        facilities_per_100k = 0
        if population > 0:
            facilities_per_100k = round((stats['total_facilities'] / population) * 100000, 1)

        enriched_city = {
            **city,
            **stats,
            'facilities_per_100k': facilities_per_100k,
        }
        enriched_cities.append(enriched_city)

    return enriched_cities


def calculate_health_capacity_score(city: dict) -> int:
    score = 0

    # Base score from medical services score (0-100, weight: 40%)
    medical_score = city.get('medical_services_score', 35)
    score += medical_score * 0.4

    # Facilities per 100k population (weight: 30%)
    # 0 facilities = 0, 10+ facilities = full score
    facilities_per_100k = city.get('facilities_per_100k', 0)
    facilities_score = min(facilities_per_100k / 10, 1) * 30
    score += facilities_score

    # Hospital presence (weight: 15%)
    hospitals = city.get('hospitals', 0)
    if hospitals >= 5:
        score += 15
    elif hospitals >= 2:
        score += 10
    elif hospitals >= 1:
        score += 5

    # Emergency facilities (weight: 15%)
    emergency = city.get('emergency_facilities', 0)
    if emergency >= 3:
        score += 15
    elif emergency >= 1:
        score += 8

    return min(100, max(0, round(score)))


def main():
    project_root = Path(__file__).parent.parent
    raw_dir = project_root / "backend" / "data" / "healthsites_raw"
    cities_file = project_root / "frontend" / "public" / "data" / "african_cities.json"
    output_dir = project_root / "backend" / "data"
    frontend_output = project_root / "frontend" / "public" / "data"

    print("=" * 60)
    print("Processing Health Facility Data")
    print("=" * 60)
    print()

    print("Loading cities data...")
    cities = load_cities(cities_file)
    print(f"  Loaded {len(cities)} cities")
    print()

    facilities, country_stats = process_raw_files(raw_dir, cities)
    print()
    print(f"Total facilities processed: {len(facilities):,}")

    print("\nAggregating facilities by city...")
    enriched_cities = aggregate_by_city(facilities, cities)

    for city in enriched_cities:
        city['health_capacity_score'] = calculate_health_capacity_score(city)

    enriched_cities.sort(key=lambda x: x.get('population', 0), reverse=True)

    facilities_file = output_dir / "health_facilities_processed.json"
    with open(facilities_file, 'w', encoding='utf-8') as f:
        json.dump({
            'total_facilities': len(facilities),
            'countries': len(country_stats),
            'facilities': facilities
        }, f, indent=2)
    print(f"\nSaved processed facilities to: {facilities_file}")

    stats_file = output_dir / "health_facilities_stats.json"
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(country_stats, f, indent=2)
    print(f"Saved country statistics to: {stats_file}")

    cities_output = frontend_output / "african_cities.json"
    with open(cities_output, 'w', encoding='utf-8') as f:
        json.dump({'cities': enriched_cities}, f, indent=2)
    print(f"Saved enriched cities to: {cities_output}")

    # Also save as CSV for analysis
    csv_output = output_dir / "african_cities_with_facilities.csv"
    with open(csv_output, 'w', newline='', encoding='utf-8') as f:
        if enriched_cities:
            writer = csv.DictWriter(f, fieldnames=enriched_cities[0].keys())
            writer.writeheader()
            writer.writerows(enriched_cities)
    print(f"Saved CSV to: {csv_output}")

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    total_with_facilities = sum(1 for c in enriched_cities if c['total_facilities'] > 0)
    total_facilities_assigned = sum(c['total_facilities'] for c in enriched_cities)
    total_beds = sum(c['total_beds'] for c in enriched_cities)
    total_hospitals = sum(c['hospitals'] for c in enriched_cities)

    print(f"Cities with facilities: {total_with_facilities}/{len(enriched_cities)}")
    print(f"Facilities assigned to cities: {total_facilities_assigned:,}")
    print(f"Total hospital beds: {total_beds:,}")
    print(f"Total hospitals: {total_hospitals:,}")
    print()

    print("Top 10 cities by health facilities:")
    for i, city in enumerate(sorted(enriched_cities, key=lambda x: x['total_facilities'], reverse=True)[:10], 1):
        print(f"  {i}. {city['city']}, {city['country']}: {city['total_facilities']:,} facilities "
              f"({city['hospitals']} hospitals, {city['total_beds']} beds)")


if __name__ == "__main__":
    main()
