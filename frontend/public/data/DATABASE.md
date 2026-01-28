# Biorisk Supply Chain Database

**African Union Pandemic Response Data Collection**

This document describes the datasets powering the AI-Augmented Pandemic Response dashboard. All data is city-level resolution, covering 442 cities across 55 African Union member states.

---

## Overview

| Metric | Value |
|--------|-------|
| **Total Cities** | 442 |
| **Countries Covered** | 49 (with health facility data) |
| **Total Health Facilities** | 62,253 |
| **Facilities Assigned to Cities** | 44,075 |
| **Total Hospital Beds Recorded** | 5,022 |
| **Population Covered** | 1.4 Billion |

---

## Data Sources

### 1. Cities & Population
**Source:** Natural Earth Populated Places (10m resolution)
**File:** `african_cities.json`

Contains 442 African cities with population >= 100,000 including:
- City name and coordinates (lat/lon)
- Country name and ISO code
- Population estimates
- Medical services score (HAQ Index)

### 2. Health Facilities
**Source:** [Humanitarian Data Exchange (HDX)](https://data.humdata.org/organization/healthsites) via healthsites.io
**License:** Open Database License (ODbL)
**Last Updated:** October 2025

Downloaded health facility point data for 49 African countries containing:
- Facility name and type
- Geographic coordinates
- Operational status
- Bed counts (where available)
- Emergency services availability

### 3. Healthcare Access & Quality Index
**Source:** Global Burden of Disease Study 2019
**Metric:** HAQ Index (0-100 scale)

Country-level healthcare quality scores used as baseline for medical services assessment.

---

## City Data Schema

Each city record contains:

```json
{
  "city": "Cairo",
  "country": "Egypt",
  "country_code": "EG",
  "latitude": 30.0519,
  "longitude": 31.248,
  "population": 11893000,
  "medical_services_score": 55,
  "total_facilities": 305,
  "hospitals": 103,
  "clinics": 88,
  "health_centers": 0,
  "pharmacies": 101,
  "laboratories": 3,
  "other": 10,
  "total_beds": 0,
  "emergency_facilities": 3,
  "facilities_per_100k": 2.6,
  "health_capacity_score": 60
}
```

### Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `city` | string | City name |
| `country` | string | Country name |
| `country_code` | string | ISO 3166-1 alpha-2 code |
| `latitude` | float | Latitude coordinate |
| `longitude` | float | Longitude coordinate |
| `population` | int | Population estimate |
| `medical_services_score` | int | Country HAQ Index (0-100) |
| `total_facilities` | int | Health facilities within 50km |
| `hospitals` | int | Hospital count |
| `clinics` | int | Clinic count |
| `health_centers` | int | Health center count |
| `pharmacies` | int | Pharmacy count |
| `laboratories` | int | Laboratory count |
| `other` | int | Other facility types |
| `total_beds` | int | Hospital beds (where known) |
| `emergency_facilities` | int | Facilities with emergency services |
| `facilities_per_100k` | float | Facilities per 100,000 population |
| `health_capacity_score` | int | Composite health capacity (0-100) |

---

## Health Capacity Score

The `health_capacity_score` is a composite metric (0-100) calculated from:

| Component | Weight | Description |
|-----------|--------|-------------|
| HAQ Index | 40% | Country-level healthcare quality |
| Facilities per 100K | 30% | Local facility density |
| Hospital Presence | 15% | Number of hospitals |
| Emergency Services | 15% | Emergency facility availability |

### Score Interpretation

| Score | Rating | Description |
|-------|--------|-------------|
| 70-100 | **Strong** | Well-equipped healthcare infrastructure |
| 50-69 | **Moderate** | Adequate but limited capacity |
| 30-49 | **Limited** | Significant gaps in coverage |
| 0-29 | **Critical** | Severe healthcare shortages |

---

## Top Cities by Health Facilities

| Rank | City | Country | Population | Facilities | Hospitals |
|------|------|---------|------------|------------|-----------|
| 1 | Algiers | Algeria | 3.4M | 1,770 | 45 |
| 2 | Kampala | Uganda | 1.7M | 1,703 | 211 |
| 3 | Dar es Salaam | Tanzania | 2.7M | 1,339 | 44 |
| 4 | Kinshasa | DR Congo | 7.8M | 1,160 | 46 |
| 5 | Nairobi | Kenya | 2.8M | 1,090 | 164 |
| 6 | Casablanca | Morocco | 3.2M | 948 | 19 |
| 7 | Tripoli | Libya | 1.8M | 873 | 51 |
| 8 | Fez | Morocco | 1.0M | 851 | 2 |
| 9 | Kigali | Rwanda | 1.1M | 713 | 266 |
| 10 | Khartoum | Sudan | 4.8M | 660 | 48 |

---

## Facilities by Country

| Country | Code | Total | Hospitals | Clinics | Pharmacies | Labs |
|---------|------|-------|-----------|---------|------------|------|
| Algeria | DZ | 7,447 | 336 | 3,099 | 3,453 | - |
| Uganda | UG | 7,485 | 211+ | 5,000+ | 1,500+ | - |
| Morocco | MA | 7,703 | 19+ | 2,000+ | 5,000+ | - |
| Tanzania | TZ | 4,083 | 44+ | 2,500+ | 1,000+ | - |
| Nigeria | NG | 4,225 | 497+ | 1,500+ | 2,000+ | - |
| DR Congo | CD | 3,097 | 198 | 1,963 | 375 | 36 |
| South Africa | ZA | 1,745 | 200+ | 800+ | 600+ | - |
| Libya | LY | 2,158 | 51+ | 1,500+ | 500+ | - |
| Egypt | EG | 1,397 | 103+ | 500+ | 700+ | - |
| Kenya | KE | 1,864 | 164+ | 1,000+ | 500+ | - |

---

## Country Healthcare Quality (HAQ Index)

### Top Performers (Score >= 60)

| Country | HAQ Score | Notable |
|---------|-----------|---------|
| Seychelles | 70 | Highest in Africa |
| Mauritius | 68 | Strong island healthcare |
| Tunisia | 65 | Best in North Africa |
| Algeria | 62 | Large public health system |

### Moderate (Score 45-59)

| Country | HAQ Score |
|---------|-----------|
| Egypt | 55 |
| Libya | 58 |
| Morocco | 53 |
| South Africa | 52 |
| Botswana | 48 |
| Gabon | 48 |

### Limited (Score 30-44)

| Country | HAQ Score |
|---------|-----------|
| Kenya | 42 |
| Ghana | 45 |
| Rwanda | 44 |
| Nigeria | 37 |
| Zimbabwe | 40 |
| Zambia | 38 |

### Critical (Score < 30)

| Country | HAQ Score | Challenge |
|---------|-----------|-----------|
| Somalia | 19 | Ongoing conflict |
| South Sudan | 18 | Youngest nation, infrastructure gaps |
| Central African Republic | 22 | Conflict-affected |
| Chad | 24 | Limited infrastructure |
| Niger | 26 | Resource constraints |

---

## Data Processing Pipeline

```
1. Download from HDX API
   └── 49 country CSV files
   └── 82,895 raw facility records

2. Normalize & Geocode
   └── Filter valid coordinates
   └── Standardize facility types
   └── 62,253 valid facilities

3. City Association
   └── Haversine distance calculation
   └── 50km radius matching
   └── 44,075 facilities → 442 cities

4. Score Calculation
   └── Aggregate by city
   └── Calculate composite scores
   └── Generate enriched dataset
```

---

## Files Reference

### Backend Data
| File | Description | Size |
|------|-------------|------|
| `healthsites_raw/*.csv` | Raw HDX downloads | 49 files |
| `health_facilities_processed.json` | All facilities with coordinates | 21 MB |
| `health_facilities_stats.json` | Country-level statistics | 17 KB |
| `african_cities_with_facilities.csv` | Enriched cities CSV | 32 KB |

### Frontend Data
| File | Description |
|------|-------------|
| `african_cities.json` | City data with facility counts |
| `africa_boundaries.geojson` | Country boundary polygons |
| `africa_population.json` | Population by country |

---

## Data Limitations

1. **Completeness**: Not all facilities are mapped in OSM/healthsites.io
2. **Currency**: Data reflects last HDX update (Oct 2025)
3. **Bed Counts**: Only ~10% of facilities have bed data
4. **Rural Coverage**: Urban areas have better facility mapping
5. **Missing Countries**: 6 countries lack healthsites data:
   - Burkina Faso, Congo (Brazzaville), Eswatini
   - Ivory Coast, Sao Tome and Principe, Western Sahara

---

## Usage in Pandemic Modeling

This data enables:

- **Outbreak Response Planning**: Identify cities with weak healthcare capacity
- **Resource Allocation**: Target mobile testing units to underserved areas
- **Travel-Time Modeling**: Calculate access to nearest hospital
- **Scenario Simulation**: Estimate healthcare system strain during outbreaks
- **Intervention Targeting**: Prioritize AI phone agent deployment by need

---

## Updates & Maintenance

To refresh the data:

```bash
# Download latest from HDX
python backend/download_health_facilities.py

# Process and aggregate
python backend/process_health_facilities.py
```

---

*Data compiled January 2026 for the AU Biorisk Supply Chain Initiative*
