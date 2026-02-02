"""
Simulation wrapper for the pandemic modeling web app.

Runs the multicity DES with dual ACTUAL/OBSERVED tracking.
The ACTUAL view shows true SEIR-D compartment counts from the DES.
The OBSERVED view shows only what the healthcare system has detected
through provider screening, plus estimates for unobserved compartments.

7-state model: S, E, I_minor, I_needs_care, I_receiving_care, R, D
"""

import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

# Add module paths for imports from the pandemic_modeling package
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
# Insert local backend dir FIRST so our supply_chain.py wins over des_system/supply_chain.py
_BACKEND_DIR = str(Path(__file__).resolve().parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
sys.path.insert(1, str(_PROJECT_ROOT / "des_system"))
sys.path.insert(2, str(_PROJECT_ROOT / "004_multicity"))
sys.path.insert(3, str(_PROJECT_ROOT / "005_multicity_des"))

from validation_config import (  # noqa: E402
    COVID_LIKE,
    COVID_BIOATTACK,
    EBOLA_LIKE,
    EBOLA_BIOATTACK,
)
from gravity_model import compute_distance_matrix  # noqa: E402
from city_des_extended import CityDES  # noqa: E402
from sim_config import (  # noqa: E402
    BIOATTACK_SEED_CITIES,
    NATURAL_SEED_CITIES,
    score_to_receptivity,
    score_to_care_quality,
    load_disease_params,
    load_household_sizes,
    household_size_to_avg_contacts,
)
from supply_config import ResourceDefaults, derive_city_resources, load_facility_data  # noqa: E402
from supply_chain import CitySupply, CountrySupplyManager, ContinentSupplyManager  # noqa: E402
from event_log import EventLog  # noqa: E402


# -- Data types ----------------------------------------------------------------

@dataclass
class SimulationParams:
    country: str = "Nigeria"
    scenario: str = "covid_natural"
    n_people: int = 5000
    avg_contacts: int | None = None  # None = infer from country household size
    rewire_prob: float = 0.4
    daily_contact_rate: float = 0.5
    p_random: float = 0.15  # fraction of contacts with random agents (mass-action mixing)
    transmission_factor: float = 0.3
    gravity_scale: float = 0.04
    gravity_alpha: float = 2.0
    provider_density: float = 5.0
    screening_capacity: int = 20
    disclosure_prob: float = 0.5
    base_isolation_prob: float = 0.05
    advised_isolation_prob: float = 0.20
    advice_decay_prob: float = 0.05
    receptivity_override: float | None = None  # Override per-city receptivity
    # AI healthcare worker reach (fraction of population reachable via mobile phone)
    mobile_phone_reach: float = 0.84  # 84% of Africans have a cell phone
    days: int = 200
    seed_fraction: float = 0.002
    random_seed: int = 42
    incubation_days: float | None = None   # Override scenario default
    infectious_days: float | None = None
    r0_override: float | None = None
    # Supply chain
    enable_supply_chain: bool = False
    beds_per_hospital: int = 120
    beds_per_clinic: int = 8
    ppe_sets_per_facility: int = 500
    swabs_per_lab: int = 1000
    reagents_per_lab: int = 2000
    lead_time_mean_days: float = 7.0
    continent_vaccine_stockpile: int = 0
    continent_pill_stockpile: int = 0
    # Debug / validation
    debug_validation: bool = False


@dataclass
class DualViewResult:
    city_names: list[str]
    city_coords: list[tuple[float, float]]
    city_populations: list[int]
    t: np.ndarray
    # ACTUAL view — full 7-state compartments
    actual_S: np.ndarray        # (n_cities, days+1)
    actual_E: np.ndarray
    actual_I: np.ndarray        # Total I (minor + needs + care)
    actual_I_minor: np.ndarray
    actual_I_needs: np.ndarray
    actual_I_care: np.ndarray
    actual_R: np.ndarray
    actual_D: np.ndarray
    # OBSERVED view — provider-detected counts
    observed_S: np.ndarray
    observed_E: np.ndarray
    observed_I: np.ndarray
    observed_R: np.ndarray
    observed_D: np.ndarray
    # Resource tracking (None when supply chain disabled)
    resource_beds_occupied: np.ndarray | None = None  # (n_cities, days+1)
    resource_beds_total: np.ndarray | None = None
    resource_ppe: np.ndarray | None = None
    resource_swabs: np.ndarray | None = None
    resource_reagents: np.ndarray | None = None
    resource_vaccines: np.ndarray | None = None
    resource_pills: np.ndarray | None = None
    # Metadata
    seed_city_indices: list[int] = None
    n_people_per_city: int = 0
    scenario_name: str = ""
    provider_density: float = 0.0
    incubation_days: float = 0.0
    infectious_days: float = 0.0
    ifr: float = 0.0
    supply_chain_enabled: bool = False
    event_log: EventLog | None = None


# -- City helper ---------------------------------------------------------------

class _City:
    """Lightweight city object for gravity model compatibility."""

    def __init__(self, row: dict):
        self.name = row["city"]
        self.population = int(row["population"])
        self.latitude = float(row["latitude"])
        self.longitude = float(row["longitude"])
        self.medical_services_score = float(row.get("medical_services_score", 0))

    def __repr__(self):
        return f"_City({self.name}, pop={self.population:,})"


def load_cities(country: str) -> list[dict]:
    """
    Load cities from the african_cities.csv data file.

    Args:
        country: Country name to filter by, or "ALL" for all African cities.

    Returns:
        List of city dicts sorted by population descending.
    """
    csv_path = _PROJECT_ROOT / "backend" / "data" / "african_cities.csv"
    cities = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if country == "ALL" or row["country"] == country:
                cities.append(row)
    cities.sort(key=lambda x: int(x["population"]), reverse=True)
    return cities


# -- DES-scale travel matrix ---------------------------------------------------

def _compute_des_travel_matrix(
    city_objs: list[_City],
    n_people: int,
    alpha: float = 2.0,
    scale: float = 0.01,
) -> np.ndarray:
    """
    Compute gravity-based travel matrix at DES population scale.

    Uses uniform DES population (n_people) for all cities instead of real
    populations, so coupling rates are already at DES scale.
    """
    dist = compute_distance_matrix(city_objs)
    n = len(city_objs)
    travel = np.zeros((n, n))
    pop_product = n_people * n_people

    for i in range(n):
        for j in range(i + 1, n):
            if dist[i, j] > 0:
                rate = scale * pop_product / (dist[i, j] ** alpha)
                travel[i, j] = rate
                travel[j, i] = rate

    return travel


# -- Travel coupling -----------------------------------------------------------

def _apply_travel_coupling_des(
    city_sims: list[CityDES],
    city_real_populations: list[int],
    travel_matrix: np.ndarray,
    transmission_factor: float,
    exposure_debt: np.ndarray,
    des_scale_travel: bool = False,
) -> None:
    """
    Apply inter-city infection coupling to DES cities.

    Same formula as module 004, but infection fractions come from the DES
    and new exposures are injected via inject_exposed().
    """
    n = len(city_sims)

    for i in range(n):
        daily = 0.0
        for j in range(n):
            if i == j:
                continue
            travelers = travel_matrix[j, i]
            inf_frac = city_sims[j].infection_fraction
            daily += travelers * inf_frac * transmission_factor

        if des_scale_travel:
            exposure_debt[i] += daily
        else:
            scale = city_sims[i].n_people / city_real_populations[i]
            exposure_debt[i] += daily * scale

    # Inject whole persons from accumulated debt
    for i in range(n):
        if exposure_debt[i] >= 1.0:
            n_inject = int(exposure_debt[i])
            exposure_debt[i] -= n_inject
            city_sims[i].inject_exposed(n_inject)


# -- Scenario configuration ----------------------------------------------------

def _build_scenarios(largest_city_name: str) -> dict:
    """
    Build scenario mapping for the given country context.

    Each entry: scenario_key -> (EpidemicScenario, seed_city_names)
    IFR now comes from disease_params.csv, not hardcoded here.
    """
    return {
        "covid_natural": (COVID_LIKE, NATURAL_SEED_CITIES),
        "covid_bioattack": (COVID_BIOATTACK, BIOATTACK_SEED_CITIES),
        "ebola_natural": (EBOLA_LIKE, NATURAL_SEED_CITIES),
        "ebola_bioattack": (EBOLA_BIOATTACK, BIOATTACK_SEED_CITIES),
    }


# -- Main simulation function -------------------------------------------------

def run_absdes_simulation(
    params: SimulationParams,
    progress_callback: Callable[[str, int, int, str], None] | None = None,
) -> DualViewResult:
    """
    Run the multi-city ABS-DES simulation with dual ACTUAL/OBSERVED tracking.

    Args:
        params: Simulation parameters.
        progress_callback: Optional callback(phase, current, total, message)
            called each day for progress reporting.

    Returns:
        DualViewResult with full time series for both actual and observed views.
    """

    def _progress(phase: str, current: int, total: int, message: str = ""):
        if progress_callback is not None:
            progress_callback(phase, current, total, message)

    # -- Load disease parameters from CSV --------------------------------------
    disease_params_map = load_disease_params()

    # -- Load cities -----------------------------------------------------------
    _progress("initializing", 0, 0, f"Loading cities for {params.country}...")
    raw_cities = load_cities(params.country)
    if not raw_cities:
        raise ValueError(f"No cities found for country: {params.country}")

    city_objs = [_City(c) for c in raw_cities]
    n_cities = len(raw_cities)

    city_names = [c["city"] for c in raw_cities]
    city_pops = [int(c["population"]) for c in raw_cities]
    city_coords = [(float(c["latitude"]), float(c["longitude"])) for c in raw_cities]

    # Largest city is first (sorted by population descending)
    largest_city_name = city_names[0]

    # -- Build scenario --------------------------------------------------------
    _progress("initializing", 0, 0, "Setting up scenario...")
    scenarios = _build_scenarios(largest_city_name)
    if params.scenario not in scenarios:
        raise ValueError(
            f"Unknown scenario: {params.scenario}. "
            f"Valid: {list(scenarios.keys())}"
        )
    scenario, seed_city_names = scenarios[params.scenario]

    # Get disease params for severity model
    dp = disease_params_map.get(params.scenario)
    if dp is None:
        raise ValueError(f"No disease parameters found for scenario: {params.scenario}")
    ifr = dp.ifr

    # Override scenario parameters if requested
    if params.incubation_days is not None:
        from dataclasses import replace
        scenario = replace(scenario, incubation_days=params.incubation_days)
    if params.infectious_days is not None:
        from dataclasses import replace
        scenario = replace(scenario, infectious_days=params.infectious_days)

    incubation_days = scenario.incubation_days
    infectious_days = scenario.infectious_days

    # Filter seed cities to those that exist in the selected country
    seed_city_names_filtered = [
        name for name in seed_city_names if name in city_names
    ]
    if not seed_city_names_filtered:
        seed_city_names_filtered = [largest_city_name]

    seed_indices = [city_names.index(name) for name in seed_city_names_filtered]

    # -- Compute travel matrix -------------------------------------------------
    _progress("initializing", 0, 0, f"Computing travel matrix for {n_cities} cities...")
    travel_matrix = _compute_des_travel_matrix(
        city_objs, params.n_people,
        alpha=params.gravity_alpha,
        scale=params.gravity_scale,
    )

    # -- Resolve avg_contacts from household size data --------------------------
    if params.avg_contacts is not None:
        avg_contacts = params.avg_contacts
    else:
        hh_sizes = load_household_sizes()
        hh_size = hh_sizes.get(params.country, 5.0)  # default 5.0 if missing
        avg_contacts = household_size_to_avg_contacts(hh_size)
    _progress("initializing", 0, 0,
              f"Network contacts: {avg_contacts} (per agent)")

    # -- Per-city receptivity and care quality from medical scores --------------
    if params.receptivity_override is not None:
        per_city_receptivity = [params.receptivity_override] * n_cities
    else:
        per_city_receptivity = [
            score_to_receptivity(float(c.get("medical_services_score", 0)))
            for c in raw_cities
        ]

    per_city_care_quality = [
        score_to_care_quality(float(c.get("medical_services_score", 0)))
        for c in raw_cities
    ]

    # -- Compute provider count from density -----------------------------------
    n_providers = max(0, int(params.provider_density * params.n_people / 1000))
    des_initial = max(1, int(params.seed_fraction * params.n_people))

    # -- Create DES for each city ----------------------------------------------
    _progress("initializing", 0, 0, f"Building {n_cities} city simulations...")
    city_sims: list[CityDES] = []
    for i in range(n_cities):
        seed_count = des_initial if i in seed_indices else 0
        city_sims.append(CityDES(
            n_people=params.n_people,
            scenario=scenario,
            seed_infected=seed_count,
            random_seed=params.random_seed + i,
            avg_contacts=avg_contacts,
            rewire_prob=params.rewire_prob,
            daily_contact_rate=params.daily_contact_rate,
            r0_override=params.r0_override,
            n_providers=n_providers,
            screening_capacity=params.screening_capacity,
            disclosure_prob=params.disclosure_prob,
            receptivity=per_city_receptivity[i],
            base_isolation_prob=params.base_isolation_prob,
            advised_isolation_prob=params.advised_isolation_prob,
            advice_decay_prob=params.advice_decay_prob,
            # Severity parameters from disease_params.csv
            severe_fraction=dp.severe_fraction,
            care_survival_prob=dp.care_survival_prob,
            base_daily_death_prob=dp.base_daily_death_prob,
            death_prob_increase_per_day=dp.death_prob_increase_per_day,
            gamma_shape=dp.gamma_shape,
            care_quality=per_city_care_quality[i],
            p_random=params.p_random,
            mobile_phone_reach=params.mobile_phone_reach,
        ))

    # -- Initialize supply chain (if enabled) ----------------------------------
    supply_enabled = params.enable_supply_chain
    city_supplies: list[CitySupply] | None = None
    country_managers: dict[str, CountrySupplyManager] | None = None
    continent_manager: ContinentSupplyManager | None = None

    if supply_enabled:
        _progress("initializing", 0, 0, "Setting up supply chain resources...")

        # Build ResourceDefaults from params
        res_defaults = ResourceDefaults(
            beds_per_hospital=params.beds_per_hospital,
            beds_per_clinic=params.beds_per_clinic,
            ppe_sets_per_facility=params.ppe_sets_per_facility,
            swabs_per_lab=params.swabs_per_lab,
            reagents_per_lab=params.reagents_per_lab,
            lead_time_mean_days=params.lead_time_mean_days,
        )

        # Load facility data
        facility_data = load_facility_data()

        # Create CitySupply for each city
        city_supplies = []
        for i in range(n_cities):
            city_name = city_names[i]
            fac = facility_data.get(city_name, {})
            hospitals = fac.get("hospitals", 0)
            clinics = fac.get("clinics", 0)
            labs = fac.get("laboratories", 0)
            total_beds_csv = fac.get("total_beds", 0)

            resources = derive_city_resources(
                hospitals=hospitals,
                clinics=clinics,
                labs=labs,
                total_beds_csv=total_beds_csv,
                defaults=res_defaults,
            )

            # Scale resources to DES population using per-capita density.
            # Real-world resource counts (from facility data) are for real
            # populations (millions). We derive per-capita rates, then scale
            # to the DES agent count to preserve realistic ratios.
            real_pop = city_pops[i]
            des_pop = params.n_people
            if real_pop > 0:
                beds_pc = resources["beds"] / real_pop
                ppe_pc = resources["ppe"] / real_pop
                swabs_pc = resources["swabs"] / real_pop
                reagents_pc = resources["reagents"] / real_pop
            else:
                beds_pc = ppe_pc = swabs_pc = reagents_pc = 0

            cs = CitySupply(
                beds_total=max(1, int(beds_pc * des_pop)),
                ppe=max(0, int(ppe_pc * des_pop)),
                swabs=max(0, int(swabs_pc * des_pop)),
                reagents=max(0, int(reagents_pc * des_pop)),
                vaccines=resources["vaccines"],
                pills=resources["pills"],
                n_days=params.days + 1,
            )
            city_supplies.append(cs)

            # Attach to CityDES
            city_sims[i]._supply = cs

        # Build CountrySupplyManagers (group cities by country)
        # For single-country sims, there's one manager; for ALL, group by country
        country_city_map: dict[str, dict[str, CitySupply]] = {}
        for i in range(n_cities):
            country_name = raw_cities[i].get("country", params.country)
            if country_name not in country_city_map:
                country_city_map[country_name] = {}
            country_city_map[country_name][city_names[i]] = city_supplies[i]

        supply_rng = np.random.RandomState(params.random_seed + 9999)
        country_managers = {}
        for country_name, city_map in country_city_map.items():
            country_managers[country_name] = CountrySupplyManager(
                city_supplies=city_map,
                defaults=res_defaults,
                rng=supply_rng,
            )

        # Build ContinentSupplyManager
        continent_reserves = {
            "vaccines": params.continent_vaccine_stockpile,
            "pills": params.continent_pill_stockpile,
            "ppe": 0,
            "swabs": 0,
            "reagents": 0,
        }
        continent_manager = ContinentSupplyManager(
            country_managers=country_managers,
            reserves=continent_reserves,
            defaults=res_defaults,
            rng=supply_rng,
        )

    # -- Allocate time-series storage ------------------------------------------
    days = params.days
    n_people = params.n_people

    actual_S = np.zeros((n_cities, days + 1))
    actual_E = np.zeros((n_cities, days + 1))
    actual_I = np.zeros((n_cities, days + 1))
    actual_I_minor = np.zeros((n_cities, days + 1))
    actual_I_needs = np.zeros((n_cities, days + 1))
    actual_I_care = np.zeros((n_cities, days + 1))
    actual_R = np.zeros((n_cities, days + 1))
    actual_D = np.zeros((n_cities, days + 1))

    observed_S = np.zeros((n_cities, days + 1))
    observed_E = np.zeros((n_cities, days + 1))
    observed_I = np.zeros((n_cities, days + 1))
    observed_R = np.zeros((n_cities, days + 1))
    observed_D = np.zeros((n_cities, days + 1))

    # Resource time-series (only if supply chain enabled)
    res_beds_occupied = np.zeros((n_cities, days + 1)) if supply_enabled else None
    res_beds_total = np.zeros((n_cities, days + 1)) if supply_enabled else None
    res_ppe = np.zeros((n_cities, days + 1)) if supply_enabled else None
    res_swabs = np.zeros((n_cities, days + 1)) if supply_enabled else None
    res_reagents = np.zeros((n_cities, days + 1)) if supply_enabled else None
    res_vaccines = np.zeros((n_cities, days + 1)) if supply_enabled else None
    res_pills = np.zeros((n_cities, days + 1)) if supply_enabled else None

    # Record initial state (day 0)
    for i in range(n_cities):
        actual_S[i, 0] = city_sims[i].S
        actual_E[i, 0] = city_sims[i].E
        actual_I[i, 0] = city_sims[i].I
        actual_I_minor[i, 0] = city_sims[i].I_minor
        actual_I_needs[i, 0] = city_sims[i].I_needs_care
        actual_I_care[i, 0] = city_sims[i].I_receiving_care
        actual_R[i, 0] = city_sims[i].R
        actual_D[i, 0] = city_sims[i].D
        # Observed: nothing detected yet on day 0
        observed_S[i, 0] = n_people
        observed_E[i, 0] = 0
        observed_I[i, 0] = 0
        observed_R[i, 0] = 0
        observed_D[i, 0] = 0

    # Record initial resource state (day 0)
    if supply_enabled:
        for i in range(n_cities):
            res_beds_occupied[i, 0] = city_supplies[i].beds_occupied
            res_beds_total[i, 0] = city_supplies[i].beds_total
            res_ppe[i, 0] = city_supplies[i].ppe
            res_swabs[i, 0] = city_supplies[i].swabs
            res_reagents[i, 0] = city_supplies[i].reagents
            res_vaccines[i, 0] = city_supplies[i].vaccines
            res_pills[i, 0] = city_supplies[i].pills

    # Exposure debt accumulators
    exposure_debt = np.zeros(n_cities)

    # Event log for interpretability
    elog = EventLog()

    # -- Daily stepping loop ---------------------------------------------------
    _progress("simulation", 0, days, "Starting simulation...")

    for day in range(1, days + 1):
        # Step 0: Receive arrived shipments (supply chain)
        if supply_enabled:
            for i in range(n_cities):
                received = city_supplies[i].receive_shipments(day)
                if received > 0:
                    elog.log(day, city_names[i], "shipment", "receive",
                             quantity=received, reason="pending_arrival")

        # Step 1: Advance each city's DES by 1 day
        for i in range(n_cities):
            city_sims[i].step(until=day)

        # Step 2: Provider screening (consumes diagnostics + PPE if supply enabled)
        for i in range(n_cities):
            pre_detected = city_sims[i].observed_I
            city_sims[i].run_provider_screening()
            new_detected = city_sims[i].new_detections_today
            if new_detected > 0:
                elog.log(day, city_names[i], "screening", "detect",
                         quantity=new_detected,
                         screened=city_sims[i]._last_screened_count if hasattr(city_sims[i], '_last_screened_count') else 0)

        # Step 3: Apply vaccinations (supply chain)
        if supply_enabled:
            for i in range(n_cities):
                vaccines_available = city_supplies[i].vaccines
                if vaccines_available > 0:
                    max_daily = max(1, int(city_sims[i].n_people * res_defaults.daily_vaccine_rate_pct / 100))
                    daily_doses = min(vaccines_available, max_daily)
                    actually_vaccinated = city_sims[i].apply_vaccinations(daily_doses)
                    if actually_vaccinated > 0:
                        city_supplies[i].try_consume("vaccines", actually_vaccinated)
                        elog.log(day, city_names[i], "vaccination", "administer",
                                 resource="vaccines", quantity=actually_vaccinated)

        # Step 4: Apply inter-city travel coupling
        _apply_travel_coupling_des(
            city_sims, city_pops, travel_matrix, params.transmission_factor,
            exposure_debt, des_scale_travel=True,
        )

        # Step 5: Record ACTUAL snapshot + conservation check
        for i in range(n_cities):
            actual_S[i, day] = city_sims[i].S
            actual_E[i, day] = city_sims[i].E
            actual_I[i, day] = city_sims[i].I
            actual_I_minor[i, day] = city_sims[i].I_minor
            actual_I_needs[i, day] = city_sims[i].I_needs_care
            actual_I_care[i, day] = city_sims[i].I_receiving_care
            actual_R[i, day] = city_sims[i].R
            actual_D[i, day] = city_sims[i].D

            # B4: Conservation law assertion (debug mode)
            if params.debug_validation:
                total = (city_sims[i].S + city_sims[i].E +
                         city_sims[i].I_minor + city_sims[i].I_needs_care +
                         city_sims[i].I_receiving_care + city_sims[i].R +
                         city_sims[i].D)
                assert total == n_people, (
                    f"Conservation violated: city {city_names[i]}, day {day}: "
                    f"S+E+I+R+D={total} != {n_people}"
                )

        # Step 6: Record OBSERVED snapshot
        for i in range(n_cities):
            obs_i = city_sims[i].observed_I
            obs_r = city_sims[i].observed_R
            obs_d = city_sims[i].observed_D

            # Estimate observed E: new_detections_today * incubation_days
            obs_e_raw = city_sims[i].new_detections_today * incubation_days
            obs_e = max(0, min(int(obs_e_raw), n_people - obs_i - obs_r - obs_d))

            obs_s = n_people - obs_i - obs_r - obs_e - obs_d

            observed_S[i, day] = obs_s
            observed_E[i, day] = obs_e
            observed_I[i, day] = obs_i
            observed_R[i, day] = obs_r
            observed_D[i, day] = obs_d

        # Step 7: Record resource snapshot + end-of-day supply updates
        if supply_enabled:
            for i in range(n_cities):
                res_beds_occupied[i, day] = city_supplies[i].beds_occupied
                res_beds_total[i, day] = city_supplies[i].beds_total
                res_ppe[i, day] = city_supplies[i].ppe
                res_swabs[i, day] = city_supplies[i].swabs
                res_reagents[i, day] = city_supplies[i].reagents
                res_vaccines[i, day] = city_supplies[i].vaccines
                res_pills[i, day] = city_supplies[i].pills
                city_supplies[i].record_day()

                # Log stockouts and capacity events
                cs = city_supplies[i]
                cn = city_names[i]
                if cs.beds_occupied >= cs.beds_total:
                    elog.log(day, cn, "admission", "capacity_full",
                             resource="beds", quantity=cs.beds_occupied)
                for res_name in ("ppe", "swabs", "reagents"):
                    if getattr(cs, res_name) == 0 and getattr(cs, f"_initial_{res_name}", 0) > 0:
                        elog.log(day, cn, "stockout", "depleted",
                                 resource=res_name)

            # Country redistribution (daily)
            for mgr in country_managers.values():
                mgr.update_and_redistribute(day, elog)

            # Continent deployment (weekly)
            if day % 7 == 0:
                continent_manager.deploy_reserves(day, elog)

        # Progress callback
        total_ever = sum(city_sims[i].n_people - city_sims[i].S for i in range(n_cities))
        total_i = sum(city_sims[i].I for i in range(n_cities))
        total_d = sum(city_sims[i].D for i in range(n_cities))
        _progress(
            "simulation", day, days,
            f"Day {day}/{days} | Infected: {total_ever:,} | Active: {total_i:,} | Deaths: {total_d:,}",
        )

    _progress("simulation", days, days, "Simulation phase complete.")

    return DualViewResult(
        city_names=city_names,
        city_coords=city_coords,
        city_populations=city_pops,
        t=np.arange(days + 1, dtype=float),
        actual_S=actual_S,
        actual_E=actual_E,
        actual_I=actual_I,
        actual_I_minor=actual_I_minor,
        actual_I_needs=actual_I_needs,
        actual_I_care=actual_I_care,
        actual_R=actual_R,
        actual_D=actual_D,
        observed_S=observed_S,
        observed_E=observed_E,
        observed_I=observed_I,
        observed_R=observed_R,
        observed_D=observed_D,
        resource_beds_occupied=res_beds_occupied,
        resource_beds_total=res_beds_total,
        resource_ppe=res_ppe,
        resource_swabs=res_swabs,
        resource_reagents=res_reagents,
        resource_vaccines=res_vaccines,
        resource_pills=res_pills,
        seed_city_indices=seed_indices,
        n_people_per_city=n_people,
        scenario_name=params.scenario,
        provider_density=params.provider_density,
        incubation_days=incubation_days,
        infectious_days=infectious_days,
        ifr=ifr,
        supply_chain_enabled=supply_enabled,
        event_log=elog,
    )
