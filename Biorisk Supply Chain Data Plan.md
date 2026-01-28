# AU Biorisk Supply Chain Database — Data Download Battleplan (Geospatial-First)

This file is a **machine-actionable checklist** you can hand to local code-building tools (Claude Code, etc.) to start downloading and organizing a country-by-country biorisk supply-chain dataset for all **55 African Union member states**.

The goal: assemble a **best-available, source-linked, geospatially anchored** dataset that supports spatio-temporal simulations of pandemic response capacity (testing, reagents, logistics, health system constraints).

---

## 0) Suggested repo + folder layout

Create a repo like:

```
au-biorisk-supplychain/
  data_raw/
    boundaries/
    population/
    facilities/
    transport/
    health_indicators/
    preparedness_indices/
    outbreak_timeseries/
    trade/
    telecom/
  data_intermediate/
  data_curated/
  notebooks/
  scripts/
  README.md
```

Prefer to store curated tables as **Parquet** and geospatial layers as **GeoParquet** where possible.

---

## 1) Canonical country list (AU-55) + ISO codes (required for joining)

You want a canonical table with these columns:

- `country_name`
- `iso2`, `iso3`
- `un_m49` (optional)
- `au_member` (bool)
- `who_region` (optional)
- `adm0_geoboundaries_id` (optional)

### Option A (recommended): Start from World Bank country list, then filter to AU members
World Bank Countries endpoint:
- https://api.worldbank.org/v2/country?format=json&per_page=400

Download:
```
curl -L "https://api.worldbank.org/v2/country?format=json&per_page=400" -o data_raw/countries_worldbank.json
```

Then create `data_curated/au_countries.csv` by filtering to AU members (you can hardcode the AU list once and reuse).

### Option B: Start from AU member list (manual) and then resolve ISO codes
If you already have the AU list, resolve ISO codes with World Bank API lookups:
- https://api.worldbank.org/v2/country?format=json

---

## 2) Geospatial base layers (admin boundaries) — ADM0/ADM1/ADM2

### 2.1 geoBoundaries (open license, API-friendly) — recommended
API docs:
- https://www.geoboundaries.org/api.html

Global downloads (CGAZ composites):
- https://www.geoboundaries.org/globalDownloads.html

**Strategy**
- Download **ADM0 + ADM1 + ADM2** for all AU countries.
- Use these as your default geometry layers for mapping capacity and demand.

Example API pattern (replace ISO3 + ADM level):
- `https://www.geoboundaries.org/api/current/gbOpen/{ISO3}/{ADM}?format=geojson`
- `ADM` in {`ADM0`,`ADM1`,`ADM2`}

Example:
```
curl -L "https://www.geoboundaries.org/api/current/gbOpen/KEN/ADM1?format=geojson" -o data_raw/boundaries/geoBoundaries_KEN_ADM1.geojson
```

> Notes:
> - Prefer geoBoundaries over GADM for fewer licensing issues.
> - Keep “simplified” versions for visualization, “unsimplified” for spatial joins.

### 2.2 GADM (great coverage, but restrictive license) — use only if needed
- Main: https://gadm.org/
- License: https://gadm.org/license.html (non-commercial redistribution restrictions)
- Download by country: https://gadm.org/download_country.html

---

## 3) Population & settlement layers (for spatial demand modeling)

### 3.1 WorldPop rasters (100m / 1km; population counts & density)
WorldPop data hub:
- https://hub.worldpop.org/geodata/summary?id=127 (example “Population Counts” entry point)
- Portal: https://www.portal.worldpop.org/

**Download strategy**
- Grab per-country **2020** or **most recent** population count grids (GeoTIFF).
- Store under `data_raw/population/worldpop/{ISO3}/...tif`

WorldPop pages provide “Download Entire Dataset” and “Browse Individual Files” per country.

### 3.2 Optional: Humanitarian settlement/urban extents
If you need explicit urban/rural partitioning:
- Use WorldPop’s urban extent products where available, or derive from population density thresholds.

---

## 4) Health facility geodata (points) — hospitals, clinics, labs proxies

### 4.1 healthsites.io / HDX “Global Healthsites Mapping Project” (facility points)
- healthsites.io map: https://healthsites.io/map
- HDX org page: https://data.humdata.org/organization/healthsites
- OSM wiki notes that HDX hosts country datasets in GeoJSON/CSV/Shapefile:
  https://wiki.openstreetmap.org/wiki/Global_Healthsites_Mapping_Project

**Download strategy**
- For each AU country, download the HDX healthsites dataset (GeoJSON or Shapefile).
- Normalize columns: `name`, `amenity/type`, `lat`, `lon`, `source`, `last_updated`, `country_iso3`.

> These are not “lab capacity” records, but they give spatial anchors for:
> - hospitals/clinics distribution
> - travel-time-to-care modeling
> - candidate “deployment points” for mobile testing units

### 4.2 HOTOSM / OSM exports (supplement)
If healthsites data is thin for a country, pull OSM extracts for:
- `amenity=hospital`, `amenity=clinic`, `healthcare=*`, `building=hospital`, etc.
Use Geofabrik (next section) and filter by tags.

---

## 5) Transport & logistics geodata (roads, ports, airports, borders)

### 5.1 OpenStreetMap extracts (Geofabrik) — roads/rail/ports/airports
Africa region downloads:
- https://download.geofabrik.de/africa.html

Per-country downloads:
- Example: https://download.geofabrik.de/africa/south-africa.html

**Download options**
- `.osm.pbf` for full fidelity + tag filtering
- “free” `.shp.zip` for pre-split shapefiles

Example:
```
curl -L "https://download.geofabrik.de/africa/kenya-latest.osm.pbf" -o data_raw/transport/osm/kenya-latest.osm.pbf
```

### 5.2 Airports datasets (HDX)
HDX has an “Our Airports - Airports” dataseries:
- https://data.humdata.org/dataset?dataseries_name=Our+Airports+-+Airports

Also HOTOSM “Airports (OpenStreetMap Export)” exists for some countries (example South Africa):
- https://data.humdata.org/dataset/hotosm_zaf_airports

**Use**
- Derive import capacity proxies (air cargo hubs), emergency deployment nodes, etc.

### 5.3 (Optional) Ports
Open datasets for African ports can be inconsistent. Start with OSM ports (`harbour=*`, `seamark:type=harbour`) via Geofabrik extracts and validate with official sources later.

---

## 6) Health system & preparedness indicators (country-level tables)

### 6.1 WHO Global Health Observatory (GHO) — country indicator time series
GHO OData API:
- https://www.who.int/data/gho/info/gho-odata-api

You’ll use this to pull country time series for:
- physicians per 10k / 100k
- hospital beds
- health expenditure
- immunization coverage proxies
- AMR indicators (optional)
- labs / diagnostics proxies when available

**Download strategy**
- Use OData queries; save results as CSV/Parquet.
- Maintain a mapping table from indicator codes → your schema variables.

Example (pattern; pick real indicator codes from GHO):
```
# You will construct a URL like:
# https://ghoapi.azureedge.net/api/Indicator?$filter=contains(IndicatorName,'hospital beds')
```

> Tip: Build a script that:
> 1) downloads the indicator catalog
> 2) searches keywords
> 3) pins a stable set of indicator codes in `config/indicators.yml`

### 6.2 World Bank Indicators API — complements WHO & easy ISO joins
Docs:
- https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation

Example:
- https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL?format=json

CSV download format is supported:
- https://datahelpdesk.worldbank.org/knowledgebase/articles/898581-api-basic-call-structures

Example CSV download:
```
curl -L "https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL?downloadformat=csv" \
  -o data_raw/health_indicators/worldbank_population.zip
```

---

## 7) Preparedness / capability indices (high-level, but useful covariates)

### 7.1 Global Health Security (GHS) Index 2021 — full CSV
GHS model page:
- https://ghsindex.org/report-model/

Direct CSV (2021):
- https://ghsindex.org/wp-content/uploads/2022/04/2021-GHS-Index-April-2022.csv

Download:
```
curl -L "https://ghsindex.org/wp-content/uploads/2022/04/2021-GHS-Index-April-2022.csv" \
  -o data_raw/preparedness_indices/ghs_2021.csv
```

**Use**
- Feature inputs / priors on response capabilities
- Gap signals (e.g., “medical countermeasure distribution plan” indicators)
- Benchmarking your constructed supply chain variables

---

## 8) Outbreak time series (space + time anchors)

### 8.1 WHO COVID-19 cases/deaths (HDX daily)
Dataset page:
- https://data.humdata.org/dataset/coronavirus-covid-19-cases-and-deaths

Direct resource (CSV):
- https://data.humdata.org/dataset/coronavirus-covid-19-cases-and-deaths/resource/2ac6c3c0-76fa-4486-9ad0-9aa9e253b78d

Download:
```
curl -L "https://data.humdata.org/dataset/coronavirus-covid-19-cases-and-deaths/resource/2ac6c3c0-76fa-4486-9ad0-9aa9e253b78d/download/WHO-COVID-19-global-data.csv" \
  -o data_raw/outbreak_timeseries/who_covid_cases_deaths.csv
```

### 8.2 Our World in Data (OWID) COVID dataset (cases/deaths/tests/etc.)
Dataset docs:
- https://docs.owid.io/projects/covid/en/latest/dataset.html

Download (canonical):
- https://covid.ourworldindata.org/data/owid-covid-data.csv

```
curl -L "https://covid.ourworldindata.org/data/owid-covid-data.csv" \
  -o data_raw/outbreak_timeseries/owid_covid_data.csv
```

> Note: OWID testing series stopped updating in 2022, but remains useful historically.

### 8.3 WHO COVID data portal “statistical releases” (weekly/daily extracts)
- https://data.who.int/dashboards/covid19/data

If you need newer WHO weekly data beyond HDX’s historic file, download from this portal.

---

## 9) Trade / import dependence for critical medical goods (reagents, PPE, devices)

### 9.1 UN Comtrade (trade flows by HS code)
Main:
- https://comtrade.un.org/

**Purpose**
Estimate dependency and likely sources for:
- diagnostic reagents / lab supplies
- PPE
- oxygen-related equipment
- medical devices

**Workflow**
1) Choose HS codes relevant to diagnostics & lab reagents (you’ll refine this list).
2) Pull import values/quantities by reporter country (AU countries) by year/month.
3) Derive top exporter partners (source countries) and concentration.

Implementation options:
- Use the official API directly (requires reading current API docs on Comtrade)
- Or use a client library (R has `comtradr`; Python options exist too)

Start here for general API availability:
- https://comtrade.un.org/

> Practical tip: begin with a small set of HS codes and a single year (e.g., 2019 baseline and 2020 shock),
> then expand.

---

## 10) Telecom penetration (for “phone agent” reach modeling)

Start with World Bank indicators for mobile subscriptions and/or ITU-derived series:
- Mobile cellular subscriptions (per 100 people): `IT.CEL.SETS.P2` via World Bank API.

Example:
```
curl -L "https://api.worldbank.org/v2/country/all/indicator/IT.CEL.SETS.P2?downloadformat=csv" \
  -o data_raw/telecom/worldbank_mobile_subscriptions.zip
```

Later you can add urban/rural splits if you find reliable sources (often in DHS surveys or ITU reports).

---

## 11) “Testing capacity” & “lab capacity” (hardest part) — practical starting moves

There is no single public, complete continent-wide lab capacity dataset that you can just download today.

So: bootstrap capacity proxies from **what is downloadable** + add higher-resolution values incrementally.

**Phase 1 (fast, proxy-ready)**
- Use:
  - health facility geodata (healthsites/OSM)
  - WHO/World Bank health system indicators
  - GHS Index indicators (detection/lab system strength proxies)
  - COVID time series (tests performed where available; or cases/deaths for calibration)

**Phase 2 (higher fidelity)**
- Add country-specific “lab network” counts from:
  - WHO AFRO / Africa CDC briefs
  - peer-reviewed country case studies
  - ministry of health bulletins
- Store in a manual-but-structured table:
  - `country_iso3`
  - `date_effective`
  - `num_pcr_labs`
  - `estimated_tests_per_day`
  - `source_url`
  - `notes`

**Phase 3 (geospatial lab registry)**
- When available publicly, incorporate outputs from Africa CDC / ASLM lab mapping programs and supply-chain dashboards.

---

## 12) Minimum viable “download scripts” you should ask your local code tool to generate

Ask your local coding tool to create:

1) `scripts/00_make_dirs.py`  
2) `scripts/01_download_countries_worldbank.py`  
3) `scripts/02_download_geoboundaries.py` (ADM0/ADM1/ADM2 for AU list)  
4) `scripts/03_download_worldpop.py` (per ISO3, handles manual URL patterns or a maintained manifest)  
5) `scripts/04_download_healthsites_hdx.py` (per country dataset; stores GeoJSON/Shapefile)  
6) `scripts/05_download_osm_geofabrik.py` (optional; per country PBF)  
7) `scripts/06_download_ghs_index.py`  
8) `scripts/07_download_outbreak_timeseries.py` (WHO HDX + OWID)  
9) `scripts/08_download_worldbank_indicators.py` (selected list, saved in config)

Also generate:
- `config/au_countries.csv` (the canonical list)
- `config/worldbank_indicators.csv` (indicator codes you want)
- `config/who_gho_indicators.csv` (GHO indicator codes you pin)

---

## 13) What the first “curated tables” should look like

Create these in `data_curated/`:

1) `countries.parquet`  
   - iso2/iso3/name/region/population

2) `admin_units_adm1.geoparquet`  
   - iso3/adm1_id/adm1_name/geometry

3) `health_facilities.geoparquet`  
   - iso3/name/type/source/geometry/last_updated

4) `health_system_indicators.parquet`  
   - iso3/year/indicator/value/source

5) `preparedness_ghs_2021.parquet`  
   - iso3/category/indicator/value

6) `outbreak_timeseries_covid.parquet`  
   - iso3/date/cases/deaths/tests_if_available/source

7) `trade_medical_goods.parquet` (optional in v1)  
   - reporter_iso3/year/hs_code/partner/flow/value/quantity

---

## 14) Done = you’re ready to build the simulation

Once the above downloads exist, you can build:

- a per-country “supply chain state” object
- a spatio-temporal demand model (cases → tests → reagents → logistics)
- intervention levers (phone agent adoption, mobile lab deployment)

Your next step after data download is a **schema mapping doc**: how each downloaded variable maps into your simulation parameters.

---
