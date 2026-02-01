"""
Simulation wrapper for the pandemic modeling web app.

Runs the multicity DES with dual ACTUAL/OBSERVED tracking.
The ACTUAL view shows true SEIR compartment counts from the DES.
The OBSERVED view shows only what the healthcare system has detected
through provider screening, plus estimates for unobserved compartments.
"""

import csv
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

# Add module paths for imports from the pandemic_modeling package
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "des_system"))
sys.path.insert(0, str(_PROJECT_ROOT / "004_multicity"))
sys.path.insert(0, str(_PROJECT_ROOT / "005_multicity_des"))

from validation_config import (  # noqa: E402
    COVID_LIKE,
    COVID_BIOATTACK,
    EBOLA_LIKE,
    EBOLA_BIOATTACK,
)
from gravity_model import compute_distance_matrix  # noqa: E402
from city_des_extended import CityDES  # noqa: E402


# -- Data types ----------------------------------------------------------------

@dataclass
class SimulationParams:
    country: str = "Nigeria"
    scenario: str = "covid_natural"
    n_people: int = 5000
    avg_contacts: int = 10
    rewire_prob: float = 0.4
    daily_contact_rate: float = 0.5
    transmission_factor: float = 0.3
    gravity_scale: float = 0.01
    gravity_alpha: float = 2.0
    provider_density: float = 5.0
    screening_capacity: int = 20
    disclosure_prob: float = 0.5
    base_isolation_prob: float = 0.0
    advised_isolation_prob: float = 0.40
    advice_decay_prob: float = 0.05
    receptivity_override: float | None = None  # Override per-city receptivity
    days: int = 200
    seed_fraction: float = 0.002
    random_seed: int = 42
    incubation_days: float | None = None   # Override scenario default
    infectious_days: float | None = None
    r0_override: float | None = None


@dataclass
class DualViewResult:
    city_names: list[str]
    city_coords: list[tuple[float, float]]
    city_populations: list[int]
    t: np.ndarray
    actual_S: np.ndarray   # (n_cities, days+1)
    actual_E: np.ndarray
    actual_I: np.ndarray
    actual_R: np.ndarray
    observed_S: np.ndarray
    observed_E: np.ndarray
    observed_I: np.ndarray
    observed_R: np.ndarray
    seed_city_indices: list[int]
    n_people_per_city: int
    scenario_name: str
    provider_density: float
    incubation_days: float
    infectious_days: float
    ifr: float  # Infection fatality rate


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


def _score_to_receptivity(score: float) -> float:
    """Convert medical_services_score (0-100) to receptivity (0.2-0.8)."""
    return 0.2 + 0.6 * (score / 100.0)


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

    Two travel matrix modes:

    1. Real-population scale (des_scale_travel=False, default):
       The travel matrix uses real city populations. We scale injected
       exposures by (n_people / real_population) so the DES receives a
       proportional number. Works well at large N (e.g. 50,000).

    2. DES-population scale (des_scale_travel=True):
       The travel matrix was computed using n_people (uniform DES
       population) instead of real populations. The coupling rates are
       already at DES scale, so no population scaling is needed. This
       enables reliable coupling at small N (e.g. 5,000).

    In both modes, fractional exposures accumulate in ``exposure_debt``
    and inject whole persons when the debt reaches >= 1.
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
            # Travel matrix already at DES scale -- no population scaling
            exposure_debt[i] += daily
        else:
            # Scale from real population to DES population
            scale = city_sims[i].n_people / city_real_populations[i]
            exposure_debt[i] += daily * scale

    # Inject whole persons from accumulated debt
    for i in range(n):
        if exposure_debt[i] >= 1.0:
            n_inject = int(exposure_debt[i])
            exposure_debt[i] -= n_inject
            city_sims[i].inject_exposed(n_inject)


# -- Scenario configuration ----------------------------------------------------

BIOATTACK_SEED_CITIES = ["Cairo", "Lagos", "Nairobi", "Kinshasa", "Johannesburg"]


def _build_scenarios(largest_city_name: str) -> dict:
    """
    Build scenario mapping for the given country context.

    Each entry: scenario_key -> (EpidemicScenario, seed_city_names, ifr)
    """
    return {
        "covid_natural": (COVID_LIKE, [largest_city_name], 0.005),
        "covid_bioattack": (COVID_BIOATTACK, BIOATTACK_SEED_CITIES, 0.005),
        "ebola_natural": (EBOLA_LIKE, [largest_city_name], 0.50),
        "ebola_bioattack": (EBOLA_BIOATTACK, BIOATTACK_SEED_CITIES, 0.50),
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
    scenario, seed_city_names, ifr = scenarios[params.scenario]

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
        # Fallback to largest city if no bioattack seed cities exist in country
        seed_city_names_filtered = [largest_city_name]

    seed_indices = [city_names.index(name) for name in seed_city_names_filtered]

    # -- Compute travel matrix -------------------------------------------------
    _progress("initializing", 0, 0, f"Computing travel matrix for {n_cities} cities...")
    travel_matrix = _compute_des_travel_matrix(
        city_objs, params.n_people,
        alpha=params.gravity_alpha,
        scale=params.gravity_scale,
    )

    # -- Per-city receptivity from medical scores ------------------------------
    if params.receptivity_override is not None:
        per_city_receptivity = [params.receptivity_override] * n_cities
    else:
        per_city_receptivity = [
            _score_to_receptivity(float(c.get("medical_services_score", 0)))
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
            avg_contacts=params.avg_contacts,
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
        ))

    # -- Allocate time-series storage ------------------------------------------
    days = params.days
    n_people = params.n_people

    actual_S = np.zeros((n_cities, days + 1))
    actual_E = np.zeros((n_cities, days + 1))
    actual_I = np.zeros((n_cities, days + 1))
    actual_R = np.zeros((n_cities, days + 1))

    observed_S = np.zeros((n_cities, days + 1))
    observed_E = np.zeros((n_cities, days + 1))
    observed_I = np.zeros((n_cities, days + 1))
    observed_R = np.zeros((n_cities, days + 1))

    # Record initial state (day 0)
    for i in range(n_cities):
        actual_S[i, 0] = city_sims[i].S
        actual_E[i, 0] = city_sims[i].E
        actual_I[i, 0] = city_sims[i].I
        actual_R[i, 0] = city_sims[i].R
        # Observed: nothing detected yet on day 0
        observed_S[i, 0] = n_people
        observed_E[i, 0] = 0
        observed_I[i, 0] = 0
        observed_R[i, 0] = 0

    # Exposure debt accumulators
    exposure_debt = np.zeros(n_cities)

    # -- Daily stepping loop ---------------------------------------------------
    _progress("simulation", 0, days, "Starting simulation...")

    for day in range(1, days + 1):
        # Step 1: Advance each city's DES by 1 day
        for i in range(n_cities):
            city_sims[i].step(until=day)

        # Step 1.5: Provider screening (if providers deployed)
        for i in range(n_cities):
            city_sims[i].run_provider_screening()

        # Step 2: Apply inter-city travel coupling
        _apply_travel_coupling_des(
            city_sims, city_pops, travel_matrix, params.transmission_factor,
            exposure_debt, des_scale_travel=True,
        )

        # Step 3: Record ACTUAL snapshot
        for i in range(n_cities):
            actual_S[i, day] = city_sims[i].S
            actual_E[i, day] = city_sims[i].E
            actual_I[i, day] = city_sims[i].I
            actual_R[i, day] = city_sims[i].R

        # Step 4: Record OBSERVED snapshot
        for i in range(n_cities):
            obs_i = city_sims[i].observed_I
            obs_r = city_sims[i].observed_R

            # Estimate observed E: new_detections_today * incubation_days
            # Clamped to [0, n_people - obs_i - obs_r]
            obs_e_raw = city_sims[i].new_detections_today * incubation_days
            obs_e = max(0, min(int(obs_e_raw), n_people - obs_i - obs_r))

            obs_s = n_people - obs_i - obs_r - obs_e

            observed_S[i, day] = obs_s
            observed_E[i, day] = obs_e
            observed_I[i, day] = obs_i
            observed_R[i, day] = obs_r

        # Progress callback
        if day % 1 == 0:
            total_i = sum(city_sims[i].I for i in range(n_cities))
            _progress(
                "simulation", day, days,
                f"Day {day}/{days} | Total infectious: {total_i:,}",
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
        actual_R=actual_R,
        observed_S=observed_S,
        observed_E=observed_E,
        observed_I=observed_I,
        observed_R=observed_R,
        seed_city_indices=seed_indices,
        n_people_per_city=n_people,
        scenario_name=params.scenario,
        provider_density=params.provider_density,
        incubation_days=incubation_days,
        infectious_days=infectious_days,
        ifr=ifr,
    )
