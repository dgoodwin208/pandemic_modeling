# African Medical Supply Chain Dataset — Data Dictionary

**File**: `african_medical_supply_chain.csv`
**Rows**: 442 cities across 52 African countries
**Built by**: `build_supply_chain_dataset.py`

## Column Reference

### Geography & Population

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `city` | str | City name | Healthsites.io geocoded facilities |
| `country` | str | Country name | Healthsites.io |
| `country_code` | str | ISO 3166-1 alpha-2 | Healthsites.io |
| `latitude` | float | City centroid latitude | Healthsites.io |
| `longitude` | float | City centroid longitude | Healthsites.io |
| `population` | int | City population estimate | WorldPop / UN estimates |

### Healthcare Facilities

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `hospitals` | int | Number of hospitals | Healthsites.io (62,253 facilities geocoded) |
| `clinics` | int | Number of clinics | Healthsites.io |
| `health_centers` | int | Number of health centers | Healthsites.io |
| `pharmacies` | int | Number of pharmacies | Healthsites.io |
| `laboratories` | int | Number of laboratories | Healthsites.io |
| `total_facilities` | int | Sum of all facility types | Derived |
| `facilities_per_100k` | float | Facilities per 100,000 population | Derived |

### Hospital Beds

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `hospital_beds_total` | int | Estimated total hospital beds in city | WHO GHO `WHS6_102` (country) → facility-weighted downscaling |
| `hospital_beds_per_10k` | float | Hospital beds per 10,000 population | Derived from `hospital_beds_total / (population / 10,000)` |
| `icu_beds_estimated` | int | Estimated ICU beds | Derived: 5% of beds if HAQ ≥ 50, 2% if HAQ ≥ 30, 1% otherwise |

### Health Workforce

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `physicians_per_100k` | float | Physicians per 100,000 population | WHO GHO `HWF_0001` (country density per 10k) → hospital-weighted downscaling, converted to per 100k |
| `nurses_per_100k` | float | Nursing/midwifery personnel per 100,000 population | WHO GHO `HWF_0006` (country density per 10k) → facility-weighted downscaling, converted to per 100k |
| `chw_per_100k` | float | Community health workers per 100,000 population | Regional estimates from WHO workforce reports |
| `total_health_workers` | int | Total estimated health workers in city | Derived: `(physicians + nurses + CHW per 100k) × population / 100,000` |

### Diagnostic Capacity

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `daily_test_capacity` | int | Estimated daily diagnostic test capacity | Derived: `laboratories × 50 × (jee_detect / 3.0)` |
| `test_capacity_per_100k` | float | Daily tests per 100,000 population | Derived |

### Supply Chain Infrastructure

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `cold_chain_score` | float | Cold chain equipment adequacy (0-100) | Gavi immunization supply chain assessments + electricity access heuristics |
| `pharma_import_dependency_pct` | float | Pharmaceutical import dependency (%) | UNIDO/Brookings/AU pharmaceutical manufacturing data |
| `has_local_production` | int | Whether country has local pharma manufacturing (0/1) | AU pharmaceutical manufacturing directory |

### Health Financing

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `health_expenditure_per_capita` | float | Current health expenditure per capita (USD) | World Bank `SH.XPD.CHEX.PC.CD` (most recent year 2018-2024) |
| `out_of_pocket_pct` | float | Out-of-pocket spending as % of health expenditure | World Bank `SH.XPD.OOPC.CH.ZS` |

### Health Security Indices

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `jee_prevent` | float | WHO Joint External Evaluation — Prevent score (1-5) | WHO JEE mission reports (`sources/jee_scores.csv`) |
| `jee_detect` | float | WHO JEE — Detect score (1-5) | WHO JEE mission reports |
| `jee_respond` | float | WHO JEE — Respond score (1-5) | WHO JEE mission reports |
| `ghsi_overall` | float | Global Health Security Index overall score (0-100) | 2021 GHS Index (`sources/ghsi_scores.csv`) |

### Composite Scores

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `haq_index` | float | Healthcare Access and Quality Index (0-100) | GBD 2016 / existing city data |
| `medical_services_score` | float | Medical services accessibility score (0-100) | Existing city data |
| `health_capacity_score` | float | Health system capacity score (0-100) | Existing city data |
| `supply_chain_resilience_index` | float | Composite resilience score (0-100) | Derived (see formula below) |

## Methodologies

### Downscaling (Country → City)

Country-level WHO/World Bank densities are distributed to cities using facility-weighted proportional allocation:

1. **Naive city total** = country density × city population / per_n
2. **Facility weight** = city facilities_per_100k / country avg facilities_per_100k
3. **Normalize** so country total is preserved (sum of city allocations = country total)

Weight column varies by resource:
- Hospital beds: weighted by `hospitals`
- Physicians: weighted by `hospitals`
- Nurses: weighted by `total_facilities`

### ICU Bed Estimation

No reliable ICU data exists for most African countries. Estimates use HAQ as a proxy:
- HAQ ≥ 50: 5% of total beds are ICU
- HAQ ≥ 30: 2% of total beds are ICU
- HAQ < 30: 1% of total beds are ICU

### Community Health Workers

Regional estimates based on WHO African Region workforce reports:
- Eastern Africa: 35 per 100k
- Western Africa: 30 per 100k
- Southern Africa: 40 per 100k
- Central Africa: 20 per 100k
- Northern Africa: 15 per 100k

### Daily Test Capacity

Estimated from laboratory count and JEE Detect capacity:
```
daily_test_capacity = laboratories × 50 × (jee_detect / 3.0)
```
Where 50 is assumed tests per lab per day at average capacity, scaled by JEE detection score (normalized to the mid-range score of 3).

### Supply Chain Resilience Index (SCRI)

Composite 0-100 score:
```
SCRI = (
    0.20 × normalize(beds_per_10k, 0, 50) +
    0.15 × normalize(physicians + nurses per 100k, 0, 500) +
    0.15 × normalize(test_capacity_per_100k, 0, 50) +
    0.15 × cold_chain_score / 100 +
    0.10 × (1 - import_dependency / 100) +
    0.10 × normalize(health_expenditure_per_capita, 0, 500) +
    0.15 × jee_respond / 5
) × 100
```

Where `normalize(x, lo, hi) = clip((x - lo) / (hi - lo), 0, 1)`.

## Source Files

| File | Description |
|------|-------------|
| `sources/jee_scores.csv` | WHO JEE Prevent/Detect/Respond scores for 53 African countries |
| `sources/ghsi_scores.csv` | 2021 Global Health Security Index scores (6 categories + overall) |
| `sources/pharma_capacity.csv` | Pharmaceutical manufacturing capacity and import dependency |
| `sources/cold_chain.csv` | Cold chain equipment scores and electricity access percentages |

## Known Limitations

1. **Bed data coverage**: Only 1.4% of the 62,253 source facilities have bed counts. City-level beds are downscaled from WHO country totals, not aggregated from facility data.
2. **Downscaling artifacts**: Small cities with unusually high facility density can receive disproportionate resource allocations. Cities with 0 facilities receive a minimum weight of 1 to avoid zero allocation.
3. **Temporal mismatch**: WHO GHO, World Bank, JEE, and GHSI data span different years (2014-2024). The most recent available value is used for each indicator.
4. **ICU estimates are heuristic**: No ground-truth ICU data exists for most of Africa. The HAQ-based percentage is a rough approximation.
5. **CHW data is regional**: Community health worker densities are regional averages, not country-specific.
6. **Static JEE/GHSI values**: Some countries use regional averages where specific JEE assessment data was not publicly available.
7. **Population represents major cities only**: The 442 cities capture urban population centers; rural populations are not directly represented.
