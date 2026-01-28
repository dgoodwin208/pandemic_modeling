# Datasets

This document tracks all external data sources used in the Pandemic Response Model.

---

## Population Data

### Kontur Population Dataset (Primary)

High-resolution population density data based on H3 hexagonal spatial indexing.

| Resolution | File Size | Use Case | Download |
|------------|-----------|----------|----------|
| 400m (Global) | 2.3 GB | High-detail analysis | [HDX Link](https://data.humdata.org/dataset/kontur-population-dataset) |
| 3km (Global) | 176.8 MB | Web visualization | [Direct Download](https://geodata-eu-central-1-kontur-public.s3.eu-central-1.amazonaws.com/kontur_datasets/kontur_population_20231101_r6.gpkg.gz) |
| 22km (Global) | ~20 MB | Overview maps | [HDX Link](https://data.humdata.org/dataset/kontur-population-dataset-22km) |

**Data Sources Combined:**
- Global Human Settlement Layer (GHSL)
- Facebook High Resolution Settlement Layer (HRSL)
- Microsoft Building Footprints
- Copernicus Global Land Service

**Format:** GeoPackage (.gpkg) with H3 hexagon geometries
**License:** CC BY 4.0
**Last Updated:** October 31, 2023

**Per-Country Downloads:** Available at [Kontur HDX Organization](https://data.humdata.org/organization/kontur) (502 datasets)

---

### WorldPop (Recommended for High-Resolution)

High-resolution population estimates from the WorldPop research group with **hosted tile services**.

| Coverage | Resolution | Format | Link |
|----------|------------|--------|------|
| Global | ~100m | ArcGIS ImageServer | [100m Tiles](https://worldpop.arcgis.com/arcgis/rest/services/WorldPop_Population_Density_100m/ImageServer) |
| Global | ~1km | ArcGIS ImageServer | [1km Tiles](https://worldpop.arcgis.com/arcgis/rest/services/WorldPop_Population_Density_1km/ImageServer) |
| Africa | ~100m | GeoTIFF Download | [WorldPop Portal](https://www.portal.worldpop.org/) |

**Hosted Tile Service URLs:**
```
# 100m Resolution (WMTS)
https://worldpop.arcgis.com/arcgis/rest/services/WorldPop_Population_Density_100m/ImageServer/WMTS

# Export Image API (for dynamic rendering)
https://worldpop.arcgis.com/arcgis/rest/services/WorldPop_Population_Density_100m/ImageServer/exportImage

# 1km Resolution (lighter weight)
https://worldpop.arcgis.com/arcgis/rest/services/WorldPop_Population_Density_1km/ImageServer
```

**Features:**
- Sub-national population distribution (shows density within countries)
- Age and gender distributions available
- Annual data from 2000-2020
- No API key required for basic access
- Tile size: 256×256 pixels

**License:** CC BY 4.0

---

### SEDAC/CIESIN (Alternative)

NASA Socioeconomic Data and Applications Center gridded population data.

| Dataset | Resolution | Link |
|---------|------------|------|
| GPWv4 | 30 arc-second (~1km) | [SEDAC](https://sedac.ciesin.columbia.edu/data/collection/gpw-v4) |
| Africa Density Maps | Various | [SEDAC Africa](https://sedac.ciesin.columbia.edu/data/set/grump-v1-population-density/maps?facets=region:africa) |

---

## Geographic Boundaries

### Natural Earth (Country Boundaries)

Free vector map data at multiple scales.

| Scale | Detail Level | File Size | Use Case |
|-------|--------------|-----------|----------|
| 1:10m | High | ~5 MB | Detailed country view |
| 1:50m | Medium | ~1 MB | Regional overview |
| 1:110m | Low | ~200 KB | Continental view |

**Download:** [Natural Earth Downloads](https://www.naturalearthdata.com/downloads/)
**Format:** Shapefile, GeoJSON
**License:** Public Domain

### African Union Countries GeoJSON

Custom extract of 55 AU member state boundaries.

| File | Source | Status |
|------|--------|--------|
| `data/africa_boundaries.geojson` | Natural Earth 1:50m | To be created |

---

## Health Infrastructure Data

### To Be Added

- [ ] Hospital locations (WHO, OpenStreetMap)
- [ ] Testing facility data
- [ ] Supply chain hub locations
- [ ] Healthcare worker distribution

---

## Data Processing Notes

### Converting Kontur GeoPackage to GeoJSON

```bash
# Using ogr2ogr (GDAL)
ogr2ogr -f GeoJSON africa_population.geojson kontur_population.gpkg \
  -clipsrc -25 -35 55 40  # Africa bounding box

# Or using Python with geopandas
import geopandas as gpd
gdf = gpd.read_file("kontur_population.gpkg")
africa = gdf.cx[-25:55, -35:40]  # Clip to Africa
africa.to_file("africa_population.geojson", driver="GeoJSON")
```

### Recommended Processing Pipeline

1. Download 3km Kontur dataset (176 MB)
2. Extract Africa region using bounding box
3. Convert to GeoJSON for web use
4. Optionally simplify geometries for faster loading

---

## Attribution Requirements

When using these datasets, include the following attributions:

**Kontur:**
> Population data © Kontur, CC BY 4.0. Based on GHSL, Facebook HRSL, and Microsoft Building Footprints.

**Natural Earth:**
> Made with Natural Earth. Free vector and raster map data @ naturalearthdata.com.

**WorldPop:**
> WorldPop (www.worldpop.org - School of Geography and Environmental Science, University of Southampton)

---

## Version History

| Date | Change | Author |
|------|--------|--------|
| 2025-01-20 | Initial dataset documentation | AI Assistant |
