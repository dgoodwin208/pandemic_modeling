"""
Supply chain resource configuration and facility-to-resource derivation.

Defines default resource levels, consumption rates, and replenishment
parameters for the three-tier supply chain (city, country, continent).

Resource categories:
  - Protection (IPC): masks, medical PPE
  - Diagnostics: swabs, testing reagents
  - MCMs: vaccines, therapeutic pills, hospital beds
"""

from dataclasses import dataclass
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "backend" / "data"


@dataclass
class ResourceDefaults:
    """Default resource parameters for supply chain initialization."""

    # Facility-to-resource derivation
    beds_per_hospital: int = 120
    beds_per_clinic: int = 8
    ppe_sets_per_facility: int = 500
    swabs_per_lab: int = 1000
    reagents_per_lab: int = 2000
    # Daily consumption rates
    ppe_per_screening: int = 1
    ppe_per_care_day: int = 2
    swabs_per_test: int = 1
    reagents_per_test: int = 1
    pills_per_care_day: int = 1

    # Replenishment thresholds and lead times
    country_reorder_threshold: float = 0.3   # reorder when < 30% of initial
    continent_deploy_threshold: float = 0.15  # deploy reserves when < 15%
    lead_time_mean_days: float = 7.0
    lead_time_shape: float = 4.0  # Gamma shape (CV ~0.5)
    continent_lead_time_mean: float = 14.0

    # Country order quantities (as fraction of initial stock)
    country_order_fraction: float = 0.5

    # Redistribution thresholds
    surplus_threshold: float = 0.6   # cities above this fraction donate
    donation_floor: float = 0.4      # surplus cities won't donate below this fraction
    daily_vaccine_rate_pct: float = 2.0  # % of DES population vaccinated per day when supply exists


def derive_city_resources(
    hospitals: int,
    clinics: int,
    labs: int,
    total_beds_csv: int = 0,
    defaults: ResourceDefaults | None = None,
) -> dict[str, int]:
    """Derive initial resource levels from facility counts.

    Args:
        hospitals: Number of hospitals in the city.
        clinics: Number of clinics in the city.
        labs: Number of laboratories in the city.
        total_beds_csv: Bed count from CSV (used if > 0, otherwise estimated).
        defaults: Resource configuration defaults.

    Returns:
        Dict with keys: beds, ppe, swabs, reagents, vaccines, pills.
    """
    d = defaults or ResourceDefaults()

    if total_beds_csv > 0:
        beds = total_beds_csv
    else:
        beds = hospitals * d.beds_per_hospital + clinics * d.beds_per_clinic

    # Ensure minimum resource levels even if data shows 0 facilities.
    # Cities without labs in the data should still have some screening capacity
    # (via mobile units, regional sharing, etc).
    facilities = max(1, hospitals + clinics)
    lab_capacity = max(1, labs)  # At least 1 lab's worth of supplies

    return {
        "beds": max(10, beds),  # At least 10 beds
        "ppe": facilities * d.ppe_sets_per_facility,
        "swabs": lab_capacity * d.swabs_per_lab,
        "reagents": lab_capacity * d.reagents_per_lab,
        "vaccines": 0,  # deployed by continent, not seeded locally
        "pills": 0,    # deployed by continent, not seeded locally
    }


def load_facility_data() -> dict[str, dict]:
    """Load facility counts from african_cities_with_facilities.csv.

    Returns:
        Dict keyed by city name, each value a dict with facility counts.
    """
    import csv

    path = _DATA_DIR / "african_cities_with_facilities.csv"
    if not path.exists():
        return {}

    facilities: dict[str, dict] = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            facilities[row["city"]] = {
                "hospitals": int(row.get("hospitals", 0)),
                "clinics": int(row.get("clinics", 0)),
                "laboratories": int(row.get("laboratories", 0)),
                "total_beds": int(row.get("total_beds", 0)),
                "health_capacity_score": float(row.get("health_capacity_score", 0)),
            }
    return facilities


def load_enriched_supply_data() -> dict[str, dict]:
    """Load enriched supply chain data from african_medical_supply_chain.csv.

    Returns the full dataset with beds, workforce, diagnostics, cold chain,
    JEE/GHSI scores, and SCRI for each city. Falls back to basic facility
    data if the enriched dataset is unavailable.

    Returns:
        Dict keyed by city name, each value a dict with all supply chain fields.
    """
    import csv

    path = _DATA_DIR / "african_medical_supply_chain.csv"
    if not path.exists():
        # Fall back to basic facility data
        basic = load_facility_data()
        return {
            city: {
                **data,
                "hospital_beds_total": data.get("total_beds", 0),
                "icu_beds_estimated": 0,
                "physicians_per_100k": 0.0,
                "nurses_per_100k": 0.0,
                "daily_test_capacity": 0,
                "cold_chain_score": 40.0,
                "jee_detect": 2.0,
                "jee_respond": 2.0,
                "supply_chain_resilience_index": 25.0,
            }
            for city, data in basic.items()
        }

    enriched: dict[str, dict] = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            city = row["city"]
            enriched[city] = {
                # Facility counts
                "hospitals": int(row.get("hospitals", 0)),
                "clinics": int(row.get("clinics", 0)),
                "laboratories": int(row.get("laboratories", 0)),
                "total_facilities": int(row.get("total_facilities", 0)),
                # Beds
                "hospital_beds_total": int(row.get("hospital_beds_total", 0)),
                "icu_beds_estimated": int(row.get("icu_beds_estimated", 0)),
                "hospital_beds_per_10k": float(row.get("hospital_beds_per_10k", 0)),
                # Workforce
                "physicians_per_100k": float(row.get("physicians_per_100k", 0)),
                "nurses_per_100k": float(row.get("nurses_per_100k", 0)),
                "chw_per_100k": float(row.get("chw_per_100k", 0)),
                "total_health_workers": int(row.get("total_health_workers", 0)),
                # Diagnostics
                "daily_test_capacity": int(row.get("daily_test_capacity", 0)),
                "test_capacity_per_100k": float(row.get("test_capacity_per_100k", 0)),
                # Supply chain
                "cold_chain_score": float(row.get("cold_chain_score", 40)),
                "pharma_import_dependency_pct": float(row.get("pharma_import_dependency_pct", 80)),
                "has_local_production": int(row.get("has_local_production", 0)),
                # Financing
                "health_expenditure_per_capita": float(row.get("health_expenditure_per_capita", 0)),
                "out_of_pocket_pct": float(row.get("out_of_pocket_pct", 50)),
                # Security indices
                "jee_prevent": float(row.get("jee_prevent", 2.0)),
                "jee_detect": float(row.get("jee_detect", 2.0)),
                "jee_respond": float(row.get("jee_respond", 2.0)),
                "ghsi_overall": float(row.get("ghsi_overall", 25.0)),
                # Composite scores
                "haq_index": float(row.get("haq_index", 0)),
                "medical_services_score": float(row.get("medical_services_score", 0)),
                "health_capacity_score": float(row.get("health_capacity_score", 0)),
                "supply_chain_resilience_index": float(row.get("supply_chain_resilience_index", 25)),
            }
    return enriched


def derive_city_resources_enriched(
    city_data: dict,
    defaults: ResourceDefaults | None = None,
) -> dict[str, int]:
    """Derive initial resource levels from enriched supply chain data.

    Uses real bed counts and workforce data from the enriched dataset
    instead of simple facility-count heuristics.

    Args:
        city_data: Dict from load_enriched_supply_data() for one city.
        defaults: Resource configuration defaults.

    Returns:
        Dict with keys: beds, icu_beds, ppe, swabs, reagents, vaccines, pills.
    """
    d = defaults or ResourceDefaults()

    beds = city_data.get("hospital_beds_total", 0)
    if beds <= 0:
        hospitals = city_data.get("hospitals", 0)
        clinics = city_data.get("clinics", 0)
        beds = hospitals * d.beds_per_hospital + clinics * d.beds_per_clinic

    icu_beds = city_data.get("icu_beds_estimated", 0)
    labs = city_data.get("laboratories", 0)
    hospitals = city_data.get("hospitals", 0)
    clinics = city_data.get("clinics", 0)

    # Ensure minimum resource levels
    facilities = max(1, hospitals + clinics)
    lab_capacity = max(1, labs)

    return {
        "beds": max(10, beds),
        "icu_beds": icu_beds,
        "ppe": facilities * d.ppe_sets_per_facility,
        "swabs": lab_capacity * d.swabs_per_lab,
        "reagents": lab_capacity * d.reagents_per_lab,
        "vaccines": 0,
        "pills": 0,
    }
