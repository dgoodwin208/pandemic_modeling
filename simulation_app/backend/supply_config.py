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

    return {
        "beds": beds,
        "ppe": (hospitals + clinics) * d.ppe_sets_per_facility,
        "swabs": labs * d.swabs_per_lab,
        "reagents": labs * d.reagents_per_lab,
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
