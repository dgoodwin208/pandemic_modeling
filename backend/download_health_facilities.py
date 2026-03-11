#!/usr/bin/env python3
"""
Download health facility data from HDX (Humanitarian Data Exchange) for all African countries.
Uses healthsites.io data via HDX CKAN API.

Data includes: hospitals, clinics, pharmacies, health posts, etc.
Key fields: name, type, lat, lon, beds, staff, emergency services, operational status.
"""

import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

# African country names mapped to HDX dataset slugs and ISO codes
# HDX uses lowercase country names with hyphens
AFRICAN_COUNTRIES = {
    'DZ': {'name': 'Algeria', 'hdx_slug': 'algeria'},
    'AO': {'name': 'Angola', 'hdx_slug': 'angola'},
    'BJ': {'name': 'Benin', 'hdx_slug': 'benin'},
    'BW': {'name': 'Botswana', 'hdx_slug': 'botswana'},
    'BF': {'name': 'Burkina Faso', 'hdx_slug': 'burkina-faso'},
    'BI': {'name': 'Burundi', 'hdx_slug': 'burundi'},
    'CV': {'name': 'Cape Verde', 'hdx_slug': 'cape-verde'},
    'CM': {'name': 'Cameroon', 'hdx_slug': 'cameroon'},
    'CF': {'name': 'Central African Republic', 'hdx_slug': 'central-african-republic'},
    'TD': {'name': 'Chad', 'hdx_slug': 'chad'},
    'KM': {'name': 'Comoros', 'hdx_slug': 'comoros'},
    'CG': {'name': 'Congo', 'hdx_slug': 'congo-brazzaville'},
    'CD': {'name': 'DR Congo', 'hdx_slug': 'democratic-republic-of-the-congo'},
    'DJ': {'name': 'Djibouti', 'hdx_slug': 'djibouti'},
    'EG': {'name': 'Egypt', 'hdx_slug': 'egypt'},
    'GQ': {'name': 'Equatorial Guinea', 'hdx_slug': 'equatorial-guinea'},
    'ER': {'name': 'Eritrea', 'hdx_slug': 'eritrea'},
    'SZ': {'name': 'Eswatini', 'hdx_slug': 'eswatini'},
    'ET': {'name': 'Ethiopia', 'hdx_slug': 'ethiopia'},
    'GA': {'name': 'Gabon', 'hdx_slug': 'gabon'},
    'GM': {'name': 'Gambia', 'hdx_slug': 'gambia'},
    'GH': {'name': 'Ghana', 'hdx_slug': 'ghana'},
    'GN': {'name': 'Guinea', 'hdx_slug': 'guinea'},
    'GW': {'name': 'Guinea-Bissau', 'hdx_slug': 'guinea-bissau'},
    'CI': {'name': 'Ivory Coast', 'hdx_slug': 'cote-d-ivoire'},
    'KE': {'name': 'Kenya', 'hdx_slug': 'kenya'},
    'LS': {'name': 'Lesotho', 'hdx_slug': 'lesotho'},
    'LR': {'name': 'Liberia', 'hdx_slug': 'liberia'},
    'LY': {'name': 'Libya', 'hdx_slug': 'libya'},
    'MG': {'name': 'Madagascar', 'hdx_slug': 'madagascar'},
    'MW': {'name': 'Malawi', 'hdx_slug': 'malawi'},
    'ML': {'name': 'Mali', 'hdx_slug': 'mali'},
    'MR': {'name': 'Mauritania', 'hdx_slug': 'mauritania'},
    'MU': {'name': 'Mauritius', 'hdx_slug': 'mauritius'},
    'MA': {'name': 'Morocco', 'hdx_slug': 'morocco'},
    'MZ': {'name': 'Mozambique', 'hdx_slug': 'mozambique'},
    'NA': {'name': 'Namibia', 'hdx_slug': 'namibia'},
    'NE': {'name': 'Niger', 'hdx_slug': 'niger'},
    'NG': {'name': 'Nigeria', 'hdx_slug': 'nigeria'},
    'RW': {'name': 'Rwanda', 'hdx_slug': 'rwanda'},
    'ST': {'name': 'Sao Tome and Principe', 'hdx_slug': 'sao-tome-and-principe'},
    'SN': {'name': 'Senegal', 'hdx_slug': 'senegal'},
    'SC': {'name': 'Seychelles', 'hdx_slug': 'seychelles'},
    'SL': {'name': 'Sierra Leone', 'hdx_slug': 'sierra-leone'},
    'SO': {'name': 'Somalia', 'hdx_slug': 'somalia'},
    'ZA': {'name': 'South Africa', 'hdx_slug': 'south-africa'},
    'SS': {'name': 'South Sudan', 'hdx_slug': 'south-sudan'},
    'SD': {'name': 'Sudan', 'hdx_slug': 'sudan'},
    'TZ': {'name': 'Tanzania', 'hdx_slug': 'tanzania'},
    'TG': {'name': 'Togo', 'hdx_slug': 'togo'},
    'TN': {'name': 'Tunisia', 'hdx_slug': 'tunisia'},
    'UG': {'name': 'Uganda', 'hdx_slug': 'uganda'},
    'ZM': {'name': 'Zambia', 'hdx_slug': 'zambia'},
    'ZW': {'name': 'Zimbabwe', 'hdx_slug': 'zimbabwe'},
    'EH': {'name': 'Western Sahara', 'hdx_slug': 'western-sahara'},
}


def fetch_json(url: str) -> dict[str, Any]:
    req = Request(url, headers={'User-Agent': 'PandemicModeling/1.0'})
    with urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode('utf-8'))


def get_hdx_dataset_info(country_slug: str) -> dict[str, Any] | None:
    dataset_name = f"{country_slug}-healthsites"
    api_url = f"https://data.humdata.org/api/3/action/package_show?id={dataset_name}"

    try:
        data = fetch_json(api_url)
        if data.get('success'):
            return data['result']
    except HTTPError as e:
        if e.code == 404:
            return None
        raise
    except Exception as e:
        print(f"  Error fetching dataset info: {e}")
    return None


def download_csv(url: str, output_path: Path) -> bool:
    try:
        req = Request(url, headers={'User-Agent': 'PandemicModeling/1.0'})
        with urlopen(req, timeout=60) as response:
            content = response.read()
            output_path.write_bytes(content)
            return True
    except Exception as e:
        print(f"  Error downloading: {e}")
        return False


def find_csv_resource(dataset: dict) -> tuple[str, str] | None:
    for resource in dataset.get('resources', []):
        if resource.get('format', '').upper() == 'CSV':
            name = resource.get('name', '').lower()
            # Prefer non-HXL CSV
            if 'hxl' not in name:
                return resource['download_url'], resource['name']

    # Fall back to any CSV
    for resource in dataset.get('resources', []):
        if resource.get('format', '').upper() == 'CSV':
            return resource['download_url'], resource['name']

    return None


def download_all_countries(output_dir: Path) -> dict[str, dict]:
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    total = len(AFRICAN_COUNTRIES)

    for i, (iso_code, info) in enumerate(AFRICAN_COUNTRIES.items(), 1):
        country_name = info['name']
        hdx_slug = info['hdx_slug']

        print(f"[{i}/{total}] {country_name} ({iso_code})...")

        dataset = get_hdx_dataset_info(hdx_slug)
        if not dataset:
            print(f"  ⚠ No healthsites dataset found")
            results[iso_code] = {'status': 'not_found', 'facilities': 0}
            continue

        csv_info = find_csv_resource(dataset)
        if not csv_info:
            print(f"  ⚠ No CSV resource found")
            results[iso_code] = {'status': 'no_csv', 'facilities': 0}
            continue

        csv_url, resource_name = csv_info
        output_file = output_dir / f"{iso_code.lower()}_healthsites.csv"

        if download_csv(csv_url, output_file):
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader)  # Skip header
                    count = sum(1 for _ in reader)
                print(f"  ✓ Downloaded {count:,} facilities")
                results[iso_code] = {
                    'status': 'success',
                    'facilities': count,
                    'file': str(output_file),
                    'source_url': csv_url,
                    'last_modified': dataset.get('last_modified', 'unknown')
                }
            except Exception as e:
                print(f"  ⚠ Error counting: {e}")
                results[iso_code] = {'status': 'error', 'facilities': 0}
        else:
            results[iso_code] = {'status': 'download_failed', 'facilities': 0}

        # Be nice to the API
        time.sleep(0.5)

    return results


def main():
    project_root = Path(__file__).parent.parent
    output_dir = project_root / "backend" / "data" / "healthsites_raw"

    print("=" * 60)
    print("Downloading Health Facility Data from HDX")
    print("Source: healthsites.io via Humanitarian Data Exchange")
    print("=" * 60)
    print()

    results = download_all_countries(output_dir)

    print()
    print("=" * 60)
    print("DOWNLOAD SUMMARY")
    print("=" * 60)

    success_count = sum(1 for r in results.values() if r['status'] == 'success')
    total_facilities = sum(r['facilities'] for r in results.values())

    print(f"Countries with data: {success_count}/{len(AFRICAN_COUNTRIES)}")
    print(f"Total facilities: {total_facilities:,}")
    print()

    missing = [f"{AFRICAN_COUNTRIES[iso]['name']} ({iso})"
               for iso, r in results.items() if r['status'] != 'success']
    if missing:
        print("Countries without data:")
        for m in missing:
            print(f"  - {m}")

    metadata_file = output_dir / "download_metadata.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump({
            'download_date': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_countries': len(AFRICAN_COUNTRIES),
            'successful_downloads': success_count,
            'total_facilities': total_facilities,
            'results': results
        }, f, indent=2)

    print(f"\nMetadata saved to: {metadata_file}")
    return results


if __name__ == "__main__":
    main()
