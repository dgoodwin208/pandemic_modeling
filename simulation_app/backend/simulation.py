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
    BIOATTACK_SCHEDULE,
    NATURAL_SCHEDULE_LAGOS,
    NATURAL_SCHEDULE_KINSHASA,
    RING_3_SCHEDULE,
    SeedEvent,
    SeedSchedule,
    score_to_receptivity,
    score_to_care_quality,
    load_disease_params,
    load_household_sizes,
    household_size_to_avg_contacts,
)
from supply_config import ResourceDefaults, derive_city_resources, load_facility_data, load_enriched_supply_data, derive_city_resources_enriched  # noqa: E402
from supply_chain import CitySupply, CountrySupplyManager, ContinentSupplyManager  # noqa: E402
from allocation_strategy import (  # noqa: E402
    AllocationStrategy, RuleBasedStrategy, AIOptimizedStrategy,
    EpidemicSnapshot, CONSUMABLE_RESOURCES,
)
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
    seed_fraction: float = 0.005
    random_seed: int = 42
    incubation_days: float | None = None   # Override scenario default
    infectious_days: float | None = None
    r0_override: float | None = None
    # Seed schedule: list of {"city": str, "day": int, "count": int|None}
    # When provided, overrides the scenario's default seeding pattern.
    seed_schedule: list[dict] | None = None
    # Supply chain
    enable_supply_chain: bool = False
    allocation_strategy: str = "rule_based"  # "rule_based" or "ai_optimized"
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
    # Shadow demand tracking — daily resource demand per city (always populated)
    shadow_demand_ppe: np.ndarray | None = None       # (n_cities, days+1)
    shadow_demand_swabs: np.ndarray | None = None
    shadow_demand_reagents: np.ndarray | None = None
    shadow_demand_pills: np.ndarray | None = None
    shadow_demand_beds: np.ndarray | None = None
    shadow_demand_vaccines: np.ndarray | None = None
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
    # Vaccine manufacturing metadata
    vaccine_manufacturing_sites: list[str] | None = None
    vaccine_manufacturing_lead_days: int = 120
    vaccine_cumulative_production: int = 0


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

    Each entry: scenario_key -> (EpidemicScenario, SeedSchedule)
    IFR now comes from disease_params.csv, not hardcoded here.
    """
    return {
        "covid_natural": (COVID_LIKE, NATURAL_SCHEDULE_LAGOS),
        "covid_bioattack": (COVID_BIOATTACK, BIOATTACK_SCHEDULE),
        "covid_ring3": (COVID_BIOATTACK, RING_3_SCHEDULE),
        "ebola_natural": (EBOLA_LIKE, NATURAL_SCHEDULE_KINSHASA),
        "ebola_bioattack": (EBOLA_BIOATTACK, BIOATTACK_SCHEDULE),
        "ebola_ring3": (EBOLA_BIOATTACK, RING_3_SCHEDULE),
    }


def _resolve_seed_schedule(
    params: SimulationParams,
    scenario_schedule: SeedSchedule,
    city_names: list[str],
) -> tuple[dict[int, int], dict[int, list[tuple[int, int]]]]:
    """Resolve seed schedule into day-0 seeds and later-day injections.

    Returns:
        day0_seeds: {city_index: count} for initial CityDES construction
        later_seeds: {day: [(city_index, count), ...]} for daily injection
    """
    # Use override schedule from params if provided, else scenario default
    if params.seed_schedule is not None:
        schedule = [
            SeedEvent(
                city=s["city"],
                day=s.get("day", 0),
                count=s.get("count"),
            )
            for s in params.seed_schedule
        ]
    else:
        schedule = scenario_schedule

    des_initial = max(1, int(params.seed_fraction * params.n_people))

    # Build city name -> index lookup
    name_to_idx = {name: i for i, name in enumerate(city_names)}

    day0_seeds: dict[int, int] = {}
    later_seeds: dict[int, list[tuple[int, int]]] = {}

    for evt in schedule:
        if evt.city not in name_to_idx:
            continue  # Skip cities not in selected country
        idx = name_to_idx[evt.city]
        count = evt.count if evt.count is not None else des_initial

        if evt.day == 0:
            day0_seeds[idx] = count
        else:
            later_seeds.setdefault(evt.day, []).append((idx, count))

    # Fallback: if no day-0 seeds matched, seed the largest city
    if not day0_seeds and not later_seeds:
        day0_seeds[0] = des_initial  # index 0 = largest city (sorted by pop)

    return day0_seeds, later_seeds


# -- City network centrality ---------------------------------------------------

def _compute_city_centrality(travel_matrix: np.ndarray) -> np.ndarray:
    """Compute normalized eigenvector centrality from the travel matrix.

    Returns a 1D array of length n_cities with values in [0, 1].
    """
    n = travel_matrix.shape[0]
    if n == 0:
        return np.array([])
    # Power iteration for dominant eigenvector
    x = np.ones(n, dtype=float)
    for _ in range(100):
        x_new = travel_matrix @ x
        norm = np.linalg.norm(x_new)
        if norm == 0:
            return np.ones(n) / n
        x = x_new / norm
    # Normalize to [0, 1]
    mx = np.max(x)
    if mx > 0:
        x = x / mx
    return x


# -- EpidemicSnapshot builder -------------------------------------------------

def _build_snapshot(
    day: int,
    city_sims: list[CityDES],
    city_names: list[str],
    city_pops: list[int],
    city_supplies: list[CitySupply] | None,
    actual_I: np.ndarray,
    actual_S: np.ndarray,
    actual_D: np.ndarray,
    city_centrality: np.ndarray,
    n_people: int,
) -> EpidemicSnapshot:
    """Build an EpidemicSnapshot from current simulation state."""
    n_cities = len(city_sims)

    active_cases = np.array([city_sims[i].I for i in range(n_cities)], dtype=float)
    new_cases = np.zeros(n_cities)
    cumulative = np.zeros(n_cities)
    deaths_today = np.zeros(n_cities)
    susceptible_frac = np.zeros(n_cities)
    beds_occ = np.zeros(n_cities)
    beds_tot = np.zeros(n_cities)

    for i in range(n_cities):
        cumulative[i] = n_people - city_sims[i].S
        susceptible_frac[i] = city_sims[i].S / n_people
        if day > 0:
            new_cases[i] = actual_S[i, day - 1] - actual_S[i, day]
            deaths_today[i] = actual_D[i, day] - actual_D[i, day - 1]

        if city_supplies is not None:
            beds_occ[i] = city_supplies[i].beds_occupied
            beds_tot[i] = city_supplies[i].beds_total

    # Stock levels and burn rates from city supplies
    stock_levels: dict[str, np.ndarray] = {}
    initial_stock: dict[str, np.ndarray] = {}
    burn_rates: dict[str, np.ndarray] = {}

    for resource in CONSUMABLE_RESOURCES:
        if city_supplies is not None:
            stock_levels[resource] = np.array(
                [getattr(city_supplies[i], resource) for i in range(n_cities)], dtype=float
            )
            initial_stock[resource] = np.array(
                [getattr(city_supplies[i], f"_initial_{resource}", 0) for i in range(n_cities)], dtype=float
            )
            burn_rates[resource] = np.array(
                [city_supplies[i]._burn_rate_ema.get(resource, 0.0) for i in range(n_cities)], dtype=float
            )
        else:
            stock_levels[resource] = np.zeros(n_cities)
            initial_stock[resource] = np.zeros(n_cities)
            burn_rates[resource] = np.zeros(n_cities)

    # Recent trajectory (last 7 days of continent-wide active I)
    start = max(0, day - 6)
    recent_traj = actual_I[:, start:day + 1].sum(axis=0).astype(float)

    return EpidemicSnapshot(
        day=day,
        n_cities=n_cities,
        city_names=city_names,
        active_cases=active_cases,
        new_cases_today=new_cases,
        cumulative_cases=cumulative,
        deaths_today=deaths_today,
        susceptible_fraction=susceptible_frac,
        beds_occupied=beds_occ,
        beds_total=beds_tot,
        populations=np.array(city_pops, dtype=float),
        stock_levels=stock_levels,
        initial_stock=initial_stock,
        burn_rates=burn_rates,
        recent_active_trajectory=recent_traj,
        city_centrality=city_centrality,
    )


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
    scenario, seed_schedule = scenarios[params.scenario]

    # Get disease params for severity model
    # For ring3 scenarios, disease params share the bioattack row
    scenario_key = params.scenario
    dp = disease_params_map.get(scenario_key)
    if dp is None:
        raise ValueError(f"No disease parameters found for scenario: {scenario_key}")
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

    # Resolve seed schedule into day-0 and later-day injections
    day0_seeds, later_seeds = _resolve_seed_schedule(params, seed_schedule, city_names)
    seed_indices = list(day0_seeds.keys())

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

    # -- Create DES for each city ----------------------------------------------
    _progress("initializing", 0, 0, f"Building {n_cities} city simulations...")
    city_sims: list[CityDES] = []
    for i in range(n_cities):
        seed_count = day0_seeds.get(i, 0)
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
    strategy: AllocationStrategy | None = None

    # Pre-compute city centrality from travel matrix (used by strategy)
    city_centrality = _compute_city_centrality(travel_matrix)

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

        # Create allocation strategy
        if params.allocation_strategy == "ai_optimized":
            strategy = AIOptimizedStrategy(
                lead_time_days=params.lead_time_mean_days,
            )
        else:
            strategy = RuleBasedStrategy()

        # Load enriched supply chain data (falls back to basic facility data)
        enriched_data = load_enriched_supply_data()

        # Create CitySupply for each city
        city_supplies = []
        for i in range(n_cities):
            city_name = city_names[i]
            city_data = enriched_data.get(city_name, {})

            if city_data:
                resources = derive_city_resources_enriched(
                    city_data=city_data,
                    defaults=res_defaults,
                )
            else:
                # Fallback to basic facility data
                fac = load_facility_data().get(city_name, {})
                resources = derive_city_resources(
                    hospitals=fac.get("hospitals", 0),
                    clinics=fac.get("clinics", 0),
                    labs=fac.get("laboratories", 0),
                    total_beds_csv=fac.get("total_beds", 0),
                    defaults=res_defaults,
                )

            # Scale resources to DES population using per-capita density.
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
        country_city_map: dict[str, dict[str, CitySupply]] = {}
        country_city_indices: dict[str, list[int]] = {}
        for i in range(n_cities):
            country_name = raw_cities[i].get("country", params.country)
            if country_name not in country_city_map:
                country_city_map[country_name] = {}
                country_city_indices[country_name] = []
            country_city_map[country_name][city_names[i]] = city_supplies[i]
            country_city_indices[country_name].append(i)

        supply_rng = np.random.RandomState(params.random_seed + 9999)
        country_managers = {}
        for country_name, city_map in country_city_map.items():
            mgr = CountrySupplyManager(
                city_supplies=city_map,
                defaults=res_defaults,
                rng=supply_rng,
                strategy=strategy,
            )
            mgr.city_global_indices = country_city_indices[country_name]
            country_managers[country_name] = mgr

        # Build ContinentSupplyManager
        continent_reserves = {
            "vaccines": params.continent_vaccine_stockpile,
            "pills": params.continent_pill_stockpile,
            "ppe": 0,
            "swabs": 0,
            "reagents": 0,
        }

        # Identify top-3 cities by population as vaccine manufacturing sites
        pop_order = sorted(range(n_cities), key=lambda i: city_pops[i], reverse=True)
        mfg_sites = [city_names[i] for i in pop_order[:3]]
        total_real_pop = int(sum(city_pops))

        continent_manager = ContinentSupplyManager(
            country_managers=country_managers,
            reserves=continent_reserves,
            defaults=res_defaults,
            rng=supply_rng,
            strategy=strategy,
            manufacturing_sites=mfg_sites,
            manufacturing_lead_days=120,
            total_population=total_real_pop,
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

    # Shadow demand tracking — always populated, tracks resource demand per city per day
    shadow_ppe = np.zeros((n_cities, days + 1))
    shadow_swabs = np.zeros((n_cities, days + 1))
    shadow_reagents = np.zeros((n_cities, days + 1))
    shadow_pills = np.zeros((n_cities, days + 1))
    shadow_beds = np.zeros((n_cities, days + 1))
    shadow_vaccines = np.zeros((n_cities, days + 1))

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

        # Step 1b: Scheduled seeding (staggered injections for ring/cascade models)
        if day in later_seeds:
            for city_idx, count in later_seeds[day]:
                city_sims[city_idx].inject_exposed(count)
                elog.log(day, city_names[city_idx], "seeding", "scheduled",
                         quantity=count)

        # Step 2: Provider screening (consumes diagnostics + PPE if supply enabled)
        for i in range(n_cities):
            pre_detected = city_sims[i].observed_I
            screening_result = city_sims[i].run_provider_screening()
            screened_count = screening_result.get("screened", 0)
            new_detected = city_sims[i].new_detections_today

            # Shadow demand: testing resources driven by observed illness
            # Each detected case triggers contact-tracing tests (~3 contacts tested per case)
            observed_i = city_sims[i].observed_I
            shadow_swabs[i, day] += observed_i * 3
            shadow_reagents[i, day] += observed_i * 3
            shadow_ppe[i, day] += observed_i * 3  # PPE for testing contacts

            if new_detected > 0:
                elog.log(day, city_names[i], "screening", "detect",
                         quantity=new_detected, screened=screened_count)

        # Step 3: Apply vaccinations (supply chain, strategy-aware)
        if supply_enabled:
            available_per_city = np.array(
                [city_supplies[i].vaccines for i in range(n_cities)], dtype=float
            )
            max_daily_per_city = np.array(
                [max(1, int(city_sims[i].n_people * res_defaults.daily_vaccine_rate_pct / 100))
                 for i in range(n_cities)], dtype=float
            )

            if strategy is not None:
                # Build snapshot for strategy-based vaccine allocation
                snapshot = _build_snapshot(
                    day, city_sims, city_names, city_pops,
                    city_supplies, actual_I, actual_S, actual_D,
                    city_centrality, n_people,
                )
                alloc = strategy.allocate_vaccines(snapshot, available_per_city, max_daily_per_city)
                doses_per_city = alloc.doses_per_city
            else:
                doses_per_city = np.minimum(available_per_city, max_daily_per_city).astype(int)

            for i in range(n_cities):
                daily_doses = int(doses_per_city[i])
                if daily_doses > 0:
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

            # Shadow demand: care resources
            # Each patient in I_receiving_care consumes 2 PPE + 1 pill per day
            care_patients = city_sims[i].I_receiving_care
            shadow_ppe[i, day] += care_patients * 2
            shadow_pills[i, day] += care_patients
            # Beds demanded = patients needing or receiving care
            shadow_beds[i, day] = care_patients + city_sims[i].I_needs_care

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

            # Build snapshot for strategy-driven supply chain decisions
            eod_snapshot = _build_snapshot(
                day, city_sims, city_names, city_pops,
                city_supplies, actual_I, actual_S, actual_D,
                city_centrality, n_people,
            ) if strategy is not None else None

            # Country redistribution (daily)
            for mgr in country_managers.values():
                mgr.update_and_redistribute(day, elog, snapshot=eod_snapshot)

            # Vaccine manufacturing (daily production)
            continent_manager.produce_vaccines(day, elog)

            # Continent deployment (weekly)
            if day % 7 == 0:
                continent_manager.deploy_reserves(day, elog, snapshot=eod_snapshot)

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
        shadow_demand_ppe=shadow_ppe,
        shadow_demand_swabs=shadow_swabs,
        shadow_demand_reagents=shadow_reagents,
        shadow_demand_pills=shadow_pills,
        shadow_demand_beds=shadow_beds,
        shadow_demand_vaccines=shadow_vaccines,
        seed_city_indices=seed_indices,
        n_people_per_city=n_people,
        scenario_name=params.scenario,
        provider_density=params.provider_density,
        incubation_days=incubation_days,
        infectious_days=infectious_days,
        ifr=ifr,
        supply_chain_enabled=supply_enabled,
        event_log=elog,
        vaccine_manufacturing_sites=continent_manager.manufacturing_sites if continent_manager else None,
        vaccine_manufacturing_lead_days=continent_manager.manufacturing_lead_days if continent_manager else 120,
        vaccine_cumulative_production=continent_manager.cumulative_vaccine_production if continent_manager else 0,
    )
