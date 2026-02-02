#!/usr/bin/env python3
"""
Build the comprehensive African Medical Supply Chain dataset.

Combines:
  1. Existing city-level facility data (Healthsites.io via african_cities_with_facilities.csv)
  2. Country-level WHO GHO API data (hospital beds, physicians, nurses)
  3. Country-level World Bank API data (health expenditure, out-of-pocket %)
  4. Static lookup CSVs (JEE scores, GHSI, pharma capacity, cold chain)

Downscales country-level data to city level using facility-weighted proportional
allocation, preserving country totals.

Output: african_medical_supply_chain.csv (442 rows × 34 columns)

Usage:
    python build_supply_chain_dataset.py [--offline]

The --offline flag skips API fetching and uses cached/fallback data only.
"""

import csv
import json
import sys
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from collections import defaultdict

import numpy as np

# Paths
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_DATA = _SCRIPT_DIR.parent.parent.parent / "backend" / "data"
_SOURCES_DIR = _SCRIPT_DIR / "sources"
_OUTPUT_PATH = _SCRIPT_DIR / "african_medical_supply_chain.csv"

# WHO GHO indicator codes
WHO_INDICATORS = {
    "beds_per_10k": "WHS6_102",        # Hospital beds per 10,000 population
    "physicians_per_10k": "HWF_0001",  # Medical doctors per 10,000 population
    "nurses_per_10k": "HWF_0006",      # Nursing/midwifery per 10,000 population
}

# World Bank indicator codes
WB_INDICATORS = {
    "health_exp_pc": "SH.XPD.CHEX.PC.CD",  # Health expenditure per capita (USD)
    "oop_pct": "SH.XPD.OOPC.CH.ZS",        # Out-of-pocket spending %
}

# ISO alpha-2 to alpha-3 mapping for African countries
ISO2_TO_ISO3 = {
    "DZ": "DZA", "AO": "AGO", "BJ": "BEN", "BW": "BWA", "BF": "BFA",
    "BI": "BDI", "CM": "CMR", "CV": "CPV", "CF": "CAF", "TD": "TCD",
    "KM": "COM", "CG": "COG", "CD": "COD", "DJ": "DJI", "EG": "EGY",
    "GQ": "GNQ", "ER": "ERI", "SZ": "SWZ", "ET": "ETH", "GA": "GAB",
    "GM": "GMB", "GH": "GHA", "GN": "GIN", "GW": "GNB", "CI": "CIV",
    "KE": "KEN", "LS": "LSO", "LR": "LBR", "LY": "LBY", "MG": "MDG",
    "MW": "MWI", "ML": "MLI", "MR": "MRT", "MU": "MUS", "MA": "MAR",
    "MZ": "MOZ", "NA": "NAM", "NE": "NER", "NG": "NGA", "RW": "RWA",
    "ST": "STP", "SN": "SEN", "SL": "SLE", "SO": "SOM", "ZA": "ZAF",
    "SS": "SSD", "SD": "SDN", "TZ": "TZA", "TG": "TGO", "TN": "TUN",
    "UG": "UGA", "ZM": "ZMB", "ZW": "ZWE",
}

# Regional CHW estimates per 100K (from WHO African Region workforce data)
REGIONAL_CHW_PER_100K = {
    "Northern Africa": 15.0,
    "Eastern Africa": 40.0,
    "Southern Africa": 25.0,
    "Western Africa": 30.0,
    "Central Africa": 20.0,
}

COUNTRY_TO_REGION = {
    "Algeria": "Northern Africa", "Egypt": "Northern Africa",
    "Libya": "Northern Africa", "Morocco": "Northern Africa",
    "Tunisia": "Northern Africa", "Sudan": "Northern Africa",
    "Mauritania": "Northern Africa",
    "Kenya": "Eastern Africa", "Ethiopia": "Eastern Africa",
    "Tanzania": "Eastern Africa", "Uganda": "Eastern Africa",
    "Rwanda": "Eastern Africa", "Burundi": "Eastern Africa",
    "Somalia": "Eastern Africa", "Djibouti": "Eastern Africa",
    "Eritrea": "Eastern Africa", "South Sudan": "Eastern Africa",
    "Madagascar": "Eastern Africa", "Comoros": "Eastern Africa",
    "Mauritius": "Eastern Africa", "Malawi": "Eastern Africa",
    "Mozambique": "Eastern Africa",
    "South Africa": "Southern Africa", "Botswana": "Southern Africa",
    "Namibia": "Southern Africa", "Zambia": "Southern Africa",
    "Zimbabwe": "Southern Africa", "Eswatini": "Southern Africa",
    "Lesotho": "Southern Africa", "Angola": "Southern Africa",
    "Nigeria": "Western Africa", "Ghana": "Western Africa",
    "Senegal": "Western Africa", "Mali": "Western Africa",
    "Burkina Faso": "Western Africa", "Niger": "Western Africa",
    "Guinea": "Western Africa", "Ivory Coast": "Western Africa",
    "Benin": "Western Africa", "Togo": "Western Africa",
    "Sierra Leone": "Western Africa", "Liberia": "Western Africa",
    "Gambia": "Western Africa", "Guinea-Bissau": "Western Africa",
    "Cape Verde": "Western Africa",
    "Congo (Kinshasa)": "Central Africa", "Congo (Brazzaville)": "Central Africa",
    "Cameroon": "Central Africa", "Central African Republic": "Central Africa",
    "Chad": "Central Africa", "Gabon": "Central Africa",
    "Equatorial Guinea": "Central Africa", "Sao Tome and Principe": "Central Africa",
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_cities() -> list[dict]:
    """Load the existing city-facility dataset."""
    path = _PROJECT_DATA / "african_cities_with_facilities.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing: {path}")
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def load_source_csv(name: str) -> dict[str, dict]:
    """Load a source lookup CSV, keyed by country_code."""
    path = _SOURCES_DIR / name
    if not path.exists():
        print(f"  WARNING: {name} not found, using empty data")
        return {}
    data = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            data[row["country_code"]] = row
    return data


# ---------------------------------------------------------------------------
# API fetching
# ---------------------------------------------------------------------------

def _fetch_json(url: str, timeout: int = 30) -> dict | None:
    """Fetch JSON from URL, return None on failure."""
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        print(f"  WARNING: API fetch failed for {url}: {e}")
        return None


def fetch_who_gho(indicator_code: str, iso3_codes: set[str]) -> dict[str, float]:
    """Fetch WHO GHO indicator for African countries. Returns {iso3: value}."""
    filt = urllib.parse.quote("SpatialDimType eq 'COUNTRY'")
    url = f"https://ghoapi.azureedge.net/api/{indicator_code}?$filter={filt}"
    data = _fetch_json(url)
    if not data or "value" not in data:
        return {}

    result = {}
    for item in data["value"]:
        iso3 = item.get("SpatialDim", "")
        if iso3 in iso3_codes and item.get("NumericValue") is not None:
            # Take most recent value
            year = int(item.get("TimeDim", 0))
            if iso3 not in result or year > result[iso3][1]:
                result[iso3] = (float(item["NumericValue"]), year)

    return {k: v[0] for k, v in result.items()}


def fetch_world_bank(indicator: str, iso3_codes: set[str]) -> dict[str, float]:
    """Fetch World Bank indicator for African countries. Returns {iso3: value}."""
    codes = ";".join(sorted(iso3_codes))
    url = (
        f"https://api.worldbank.org/v2/country/{codes}/indicator/{indicator}"
        f"?format=json&per_page=5000&date=2018:2024"
    )
    data = _fetch_json(url)
    if not data or len(data) < 2:
        return {}

    result = {}
    for item in data[1] or []:
        iso3 = item.get("countryiso3code", "")
        val = item.get("value")
        year = int(item.get("date", 0))
        if iso3 in iso3_codes and val is not None:
            if iso3 not in result or year > result[iso3][1]:
                result[iso3] = (float(val), year)

    return {k: v[0] for k, v in result.items()}


def fetch_all_api_data(iso3_codes: set[str], offline: bool = False) -> dict:
    """Fetch all API data. Returns dict of {indicator_name: {iso3: value}}."""
    if offline:
        print("  Offline mode: skipping API fetches")
        return {k: {} for k in list(WHO_INDICATORS) + list(WB_INDICATORS)}

    api_data = {}

    print("  Fetching WHO GHO data...")
    for name, code in WHO_INDICATORS.items():
        print(f"    {name} ({code})...")
        api_data[name] = fetch_who_gho(code, iso3_codes)
        print(f"    → {len(api_data[name])} countries")

    print("  Fetching World Bank data...")
    for name, code in WB_INDICATORS.items():
        print(f"    {name} ({code})...")
        api_data[name] = fetch_world_bank(code, iso3_codes)
        print(f"    → {len(api_data[name])} countries")

    return api_data


# ---------------------------------------------------------------------------
# Fallback data (used when APIs are unavailable)
# ---------------------------------------------------------------------------

# Regional averages from WHO Africa Health Observatory
REGIONAL_FALLBACKS = {
    "beds_per_10k": {
        "Northern Africa": 18.0, "Eastern Africa": 8.0,
        "Southern Africa": 15.0, "Western Africa": 5.0,
        "Central Africa": 8.0,
    },
    "physicians_per_10k": {
        "Northern Africa": 12.0, "Eastern Africa": 1.0,
        "Southern Africa": 5.0, "Western Africa": 1.5,
        "Central Africa": 0.8,
    },
    "nurses_per_10k": {
        "Northern Africa": 25.0, "Eastern Africa": 5.0,
        "Southern Africa": 12.0, "Western Africa": 4.0,
        "Central Africa": 3.0,
    },
    "health_exp_pc": {
        "Northern Africa": 150.0, "Eastern Africa": 30.0,
        "Southern Africa": 200.0, "Western Africa": 25.0,
        "Central Africa": 20.0,
    },
    "oop_pct": {
        "Northern Africa": 35.0, "Eastern Africa": 40.0,
        "Southern Africa": 15.0, "Western Africa": 50.0,
        "Central Africa": 45.0,
    },
}


def get_country_value(api_data: dict, indicator: str, iso3: str,
                      country: str) -> float:
    """Get indicator value for a country, falling back to regional average."""
    values = api_data.get(indicator, {})
    if iso3 in values:
        return values[iso3]
    region = COUNTRY_TO_REGION.get(country, "Western Africa")
    fallback = REGIONAL_FALLBACKS.get(indicator, {}).get(region, 5.0)
    return fallback


# ---------------------------------------------------------------------------
# Downscaling: country-level → city-level
# ---------------------------------------------------------------------------

def downscale_to_cities(
    cities: list[dict],
    country_values: dict[str, float],  # country_name -> density per 10K (or per capita)
    weight_column: str = "total_facilities",
    per_n: int = 10_000,
) -> dict[str, float]:
    """
    Downscale a country-level per-capita density to city-level totals.

    Method:
      1. Naive city total = density × city_pop / per_n
      2. Facility-weight = city_weight / country_avg_weight
      3. Normalize so country total is preserved

    Returns: {city_name: estimated_total}
    """
    # Group cities by country
    by_country: dict[str, list[dict]] = defaultdict(list)
    for c in cities:
        by_country[c["country"]].append(c)

    result = {}
    for country_name, country_cities in by_country.items():
        density = country_values.get(country_name, 0)
        if density <= 0:
            for c in country_cities:
                result[c["city"]] = 0
            continue

        # Get weights
        weights = []
        pops = []
        for c in country_cities:
            w = max(1, int(c.get(weight_column, 0) or 0))
            p = max(1, int(c.get("population", 0) or 0))
            weights.append(w)
            pops.append(p)

        # Naive totals
        naive = [density * p / per_n for p in pops]

        # Facility weights (relative to country average)
        fac_per_100k = [w / (p / 100_000) for w, p in zip(weights, pops)]
        avg_fpc = np.mean(fac_per_100k) if fac_per_100k else 1.0
        if avg_fpc <= 0:
            avg_fpc = 1.0
        rel_weights = [f / avg_fpc for f in fac_per_100k]

        # Weighted totals
        weighted = [n * rw for n, rw in zip(naive, rel_weights)]

        # Normalize to preserve country total
        country_pop = sum(pops)
        expected_total = density * country_pop / per_n
        actual_total = sum(weighted)
        if actual_total > 0:
            scale = expected_total / actual_total
            weighted = [w * scale for w in weighted]

        for c, w in zip(country_cities, weighted):
            result[c["city"]] = max(0, w)

    return result


# ---------------------------------------------------------------------------
# Main assembly
# ---------------------------------------------------------------------------

def build_dataset(offline: bool = False) -> list[dict]:
    """Assemble the complete dataset."""
    print("Loading existing city data...")
    cities = load_cities()
    print(f"  {len(cities)} cities loaded")

    # Get unique ISO3 codes
    iso2_set = {c["country_code"] for c in cities}
    iso3_set = {ISO2_TO_ISO3.get(c, c) for c in iso2_set}

    # Load static source CSVs
    print("Loading static source data...")
    jee_data = load_source_csv("jee_scores.csv")
    ghsi_data = load_source_csv("ghsi_scores.csv")
    pharma_data = load_source_csv("pharma_capacity.csv")
    cold_chain_data = load_source_csv("cold_chain.csv")

    # Fetch API data
    print("Fetching API data...")
    api_data = fetch_all_api_data(iso3_set, offline=offline)

    # Build country-level lookup: {country_name: value}
    print("Building country-level lookups...")
    country_beds = {}
    country_physicians = {}
    country_nurses = {}
    country_health_exp = {}
    country_oop = {}

    for c in cities:
        country = c["country"]
        iso3 = ISO2_TO_ISO3.get(c["country_code"], c["country_code"])
        if country not in country_beds:
            country_beds[country] = get_country_value(api_data, "beds_per_10k", iso3, country)
            country_physicians[country] = get_country_value(api_data, "physicians_per_10k", iso3, country)
            country_nurses[country] = get_country_value(api_data, "nurses_per_10k", iso3, country)
            country_health_exp[country] = get_country_value(api_data, "health_exp_pc", iso3, country)
            country_oop[country] = get_country_value(api_data, "oop_pct", iso3, country)

    # Downscale to city level
    print("Downscaling to city level...")
    city_beds = downscale_to_cities(cities, country_beds, weight_column="hospitals", per_n=10_000)
    city_physicians = downscale_to_cities(cities, country_physicians, weight_column="hospitals", per_n=10_000)
    city_nurses = downscale_to_cities(cities, country_nurses, weight_column="total_facilities", per_n=10_000)

    # Build output rows
    print("Assembling output rows...")
    output = []
    for c in cities:
        city_name = c["city"]
        country = c["country"]
        cc = c["country_code"]
        iso3 = ISO2_TO_ISO3.get(cc, cc)
        pop = int(c.get("population", 0) or 0)
        haq = float(c.get("medical_services_score", 0) or 0)
        hospitals = int(c.get("hospitals", 0) or 0)
        clinics = int(c.get("clinics", 0) or 0)
        health_centers = int(c.get("health_centers", 0) or 0)
        pharmacies = int(c.get("pharmacies", 0) or 0)
        labs = int(c.get("laboratories", 0) or 0)
        total_fac = int(c.get("total_facilities", 0) or 0)
        fac_per_100k = float(c.get("facilities_per_100k", 0) or 0)

        # Hospital beds (downscaled)
        beds_total = max(0, int(round(city_beds.get(city_name, 0))))
        beds_per_10k = beds_total / (pop / 10_000) if pop > 0 else 0

        # ICU beds: 1-5% of total based on HAQ
        if haq >= 50:
            icu_pct = 0.05
        elif haq >= 30:
            icu_pct = 0.02
        else:
            icu_pct = 0.01
        icu_beds = max(0, int(round(beds_total * icu_pct)))

        # Workforce (downscaled, convert from per-10K to per-100K)
        physicians_total = city_physicians.get(city_name, 0)
        physicians_per_100k = physicians_total / (pop / 100_000) if pop > 0 else 0
        nurses_total = city_nurses.get(city_name, 0)
        nurses_per_100k = nurses_total / (pop / 100_000) if pop > 0 else 0

        # CHW estimate (regional)
        region = COUNTRY_TO_REGION.get(country, "Western Africa")
        chw_per_100k = REGIONAL_CHW_PER_100K.get(region, 25.0)

        # Total health workers
        total_hw = int(round(
            (physicians_per_100k + nurses_per_100k + chw_per_100k)
            * pop / 100_000
        ))

        # Diagnostic capacity
        jee = jee_data.get(cc, {})
        jee_detect = float(jee.get("jee_detect", 2.0))
        daily_test_cap = max(0, int(labs * 50 * (jee_detect / 3.0)))
        test_cap_per_100k = daily_test_cap / (pop / 100_000) if pop > 0 else 0

        # Cold chain (country-level)
        cc_data = cold_chain_data.get(cc, {})
        cold_chain_score = float(cc_data.get("cold_chain_equipment_score", 40.0))
        electricity_pct = float(cc_data.get("electricity_access_pct", 50.0))

        # Pharma (country-level)
        ph = pharma_data.get(cc, {})
        import_dep = float(ph.get("import_dependency_pct", 95.0))
        has_production = int(ph.get("has_local_production", 0))

        # Health expenditure (country-level)
        health_exp = country_health_exp.get(country, 30.0)
        oop = country_oop.get(country, 40.0)

        # JEE scores
        jee_prevent = float(jee.get("jee_prevent", 2.0))
        jee_respond = float(jee.get("jee_respond", 2.0))

        # GHSI
        gh = ghsi_data.get(cc, {})
        ghsi_overall = float(gh.get("ghsi_overall", 25.0))

        # Health capacity score (existing)
        health_cap = float(c.get("health_capacity_score", 0) or 0)

        # Supply Chain Resilience Index
        def _norm(val, lo, hi):
            return max(0, min(1, (val - lo) / (hi - lo))) if hi > lo else 0

        scri = (
            0.20 * _norm(beds_per_10k, 0, 50) +
            0.15 * _norm(physicians_per_100k + nurses_per_100k, 0, 500) +
            0.15 * _norm(test_cap_per_100k, 0, 200) +
            0.15 * cold_chain_score / 100.0 +
            0.10 * (1.0 - import_dep / 100.0) +
            0.10 * _norm(health_exp, 0, 500) +
            0.15 * jee_respond / 5.0
        ) * 100

        output.append({
            "city": city_name,
            "country": country,
            "country_code": cc,
            "latitude": c["latitude"],
            "longitude": c["longitude"],
            "population": pop,
            "hospitals": hospitals,
            "clinics": clinics,
            "health_centers": health_centers,
            "pharmacies": pharmacies,
            "laboratories": labs,
            "total_facilities": total_fac,
            "facilities_per_100k": round(fac_per_100k, 1),
            "hospital_beds_total": beds_total,
            "hospital_beds_per_10k": round(beds_per_10k, 1),
            "icu_beds_estimated": icu_beds,
            "physicians_per_100k": round(physicians_per_100k, 1),
            "nurses_per_100k": round(nurses_per_100k, 1),
            "chw_per_100k": round(chw_per_100k, 1),
            "total_health_workers": total_hw,
            "daily_test_capacity": daily_test_cap,
            "test_capacity_per_100k": round(test_cap_per_100k, 1),
            "cold_chain_score": round(cold_chain_score, 1),
            "pharma_import_dependency_pct": round(import_dep, 1),
            "has_local_production": has_production,
            "health_expenditure_per_capita": round(health_exp, 1),
            "out_of_pocket_pct": round(oop, 1),
            "jee_prevent": round(jee_prevent, 1),
            "jee_detect": round(jee_detect, 1),
            "jee_respond": round(jee_respond, 1),
            "ghsi_overall": round(ghsi_overall, 1),
            "haq_index": round(haq, 1),
            "medical_services_score": round(haq, 1),
            "health_capacity_score": round(health_cap, 1),
            "supply_chain_resilience_index": round(scri, 1),
        })

    return output


def write_csv(rows: list[dict], path: Path) -> None:
    """Write rows to CSV."""
    if not rows:
        print("  ERROR: No rows to write")
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Written {len(rows)} rows to {path}")


def print_summary(rows: list[dict]) -> None:
    """Print dataset summary statistics."""
    n = len(rows)
    total_pop = sum(r["population"] for r in rows)
    total_beds = sum(r["hospital_beds_total"] for r in rows)
    total_icu = sum(r["icu_beds_estimated"] for r in rows)
    total_hw = sum(r["total_health_workers"] for r in rows)
    countries = len(set(r["country"] for r in rows))
    avg_scri = np.mean([r["supply_chain_resilience_index"] for r in rows])

    print(f"\n{'='*60}")
    print(f"  AFRICAN MEDICAL SUPPLY CHAIN DATASET SUMMARY")
    print(f"{'='*60}")
    print(f"  Cities:              {n}")
    print(f"  Countries:           {countries}")
    print(f"  Total population:    {total_pop:,.0f}")
    print(f"  Total hospital beds: {total_beds:,.0f}")
    print(f"  Total ICU beds:      {total_icu:,.0f}")
    print(f"  Total health workers:{total_hw:,.0f}")
    print(f"  Avg SCRI:            {avg_scri:.1f}/100")
    print(f"{'='*60}\n")

    # Top/bottom 5 by SCRI
    sorted_rows = sorted(rows, key=lambda r: r["supply_chain_resilience_index"], reverse=True)
    print("  Top 5 by Supply Chain Resilience:")
    for r in sorted_rows[:5]:
        print(f"    {r['city']:20s} ({r['country']:20s}) SCRI={r['supply_chain_resilience_index']:.1f}")
    print("\n  Bottom 5 by Supply Chain Resilience:")
    for r in sorted_rows[-5:]:
        print(f"    {r['city']:20s} ({r['country']:20s}) SCRI={r['supply_chain_resilience_index']:.1f}")


if __name__ == "__main__":
    offline = "--offline" in sys.argv
    rows = build_dataset(offline=offline)
    write_csv(rows, _OUTPUT_PATH)
    print_summary(rows)
