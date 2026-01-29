"""
Multi-City Metapopulation SEIR Simulation.

Each city runs an independent SEIR ODE per day, with discrete inter-city
coupling via a gravity-based transportation model.

Algorithm (daily discrete coupling):
    For each day:
        1. Record current state snapshot
        2. Solve each city's SEIR ODE for 1 day
        3. Compute inter-city infections from travel
        4. Inject new exposures (S→E) into destination cities

This is a standard metapopulation model. The key insight from modules 001-003
is that agent-based DES matches SEIR ODE curves, so we can use the cheaper ODE
per city and focus computational effort on the inter-city coupling.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.integrate import odeint

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "des_system"))

from seir_ode import SEIRParams, basic_seir_derivatives
from validation_config import EpidemicScenario

from city import CityState, seed_infection


@dataclass
class MultiCityResult:
    """Time-series results for all cities."""

    city_names: list[str]
    t: np.ndarray  # shape (days+1,)
    S: np.ndarray  # shape (n_cities, days+1)
    E: np.ndarray  # shape (n_cities, days+1)
    I: np.ndarray  # shape (n_cities, days+1)
    R: np.ndarray  # shape (n_cities, days+1)
    travel_matrix: np.ndarray  # shape (n_cities, n_cities)
    city_populations: list[int]
    city_coords: list[tuple[float, float]]  # (lat, lon)
    city_medical_scores: list[float]  # medical_services_score per city
    city_r_eff: list[float]  # effective R₀ per city


def _step_city_ode(city: CityState, params: SEIRParams) -> None:
    """
    Advance one city's SEIR state by 1 day using ODE integration.

    Modifies city.S, city.E, city.I, city.R in place.
    """
    y0 = np.array([city.S, city.E, city.I, city.R])
    t_span = np.array([0.0, 1.0])
    solution = odeint(basic_seir_derivatives, y0, t_span, args=(params,))
    city.S, city.E, city.I, city.R = solution[-1]


def _apply_travel_coupling(
    cities: list[CityState],
    travel_matrix: np.ndarray,
    transmission_factor: float,
) -> None:
    """
    Apply inter-city infection coupling.

    For each city pair (i, j), travelers from j arriving at i carry
    infection proportional to j's infection fraction:
        new_exposures_i += travel_matrix[j][i] * (I_j / N_j) * transmission_factor

    Moves people from S to E in destination cities.
    """
    n = len(cities)
    new_exposures = np.zeros(n)

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            travelers = travel_matrix[j, i]
            inf_frac = cities[j].infection_fraction
            new_exposures[i] += travelers * inf_frac * transmission_factor

    # Inject exposures
    for i in range(n):
        actual = min(new_exposures[i], cities[i].S)
        cities[i].S -= actual
        cities[i].E += actual


def _compute_effective_r0(
    base_r0: float,
    medical_services_score: float,
    isolation_effect: float,
) -> float:
    """
    Compute per-city effective R₀ from medical services capacity.

    Heuristic grounded in module 003's finding that healthcare provider advice
    shifts individual isolation compliance from ~5% (no provider) to ~40%
    (with provider). We map medical_services_score (0-100) into a continuous
    R₀ reduction:

        R_eff = R₀ × (1 - isolation_effect × score / 100)

    Args:
        base_r0: Baseline R₀ from the epidemic scenario.
        medical_services_score: City's health system capacity (0-100).
        isolation_effect: Maximum fractional R₀ reduction at score=100.
            Default 0.3 means a perfect health system reduces R₀ by 30%.

    Returns:
        Effective R₀ for the city. Always >= 0.
    """
    normalized = medical_services_score / 100.0
    return max(0.0, base_r0 * (1.0 - isolation_effect * normalized))


def run_multicity_simulation(
    cities: list[CityState],
    scenario: EpidemicScenario,
    travel_matrix: np.ndarray,
    days: int = 300,
    transmission_factor: float = 0.1,
    seed_city_index: int = 0,
    initial_infected: int = 10,
    isolation_effect: float = 0.3,
) -> MultiCityResult:
    """
    Run the coupled multi-city SEIR simulation.

    Args:
        cities: List of CityState objects (will be modified in place).
        scenario: Epidemic scenario (provides R0, incubation, infectious days).
        travel_matrix: n x n daily travel rates between cities.
        days: Simulation duration in days.
        transmission_factor: Probability a traveling infected person causes
            an exposure at their destination.
        seed_city_index: Index of the city where the epidemic starts.
        initial_infected: Number of initial infections in the seed city.
        isolation_effect: Maximum fractional R₀ reduction from health system
            capacity. A city with medical_services_score=100 has its R₀
            reduced by this fraction. Default 0.3 (30% reduction).

    Returns:
        MultiCityResult with full time series for all cities.
    """
    n = len(cities)

    # Seed the epidemic
    seed_infection(cities[seed_city_index], initial_infected)

    # Pre-compute SEIR params for each city with per-city effective R₀
    params_list = []
    for i in range(n):
        r_eff = _compute_effective_r0(
            scenario.R0, cities[i].medical_services_score, isolation_effect,
        )
        params_list.append(SEIRParams(
            R0=r_eff,
            incubation_days=scenario.incubation_days,
            infectious_days=scenario.infectious_days,
            population=cities[i].population,
        ))

    # Allocate time-series storage
    S = np.zeros((n, days + 1))
    E = np.zeros((n, days + 1))
    I = np.zeros((n, days + 1))
    R = np.zeros((n, days + 1))

    # Record initial state (day 0)
    for i in range(n):
        S[i, 0] = cities[i].S
        E[i, 0] = cities[i].E
        I[i, 0] = cities[i].I
        R[i, 0] = cities[i].R

    # Daily stepping loop
    for day in range(1, days + 1):
        # Step 1: Advance each city's ODE by 1 day
        for i in range(n):
            _step_city_ode(cities[i], params_list[i])

        # Step 2: Apply inter-city travel coupling
        _apply_travel_coupling(cities, travel_matrix, transmission_factor)

        # Step 3: Record snapshot
        for i in range(n):
            S[i, day] = cities[i].S
            E[i, day] = cities[i].E
            I[i, day] = cities[i].I
            R[i, day] = cities[i].R

    return MultiCityResult(
        city_names=[c.name for c in cities],
        t=np.arange(days + 1, dtype=float),
        S=S,
        E=E,
        I=I,
        R=R,
        travel_matrix=travel_matrix,
        city_populations=[c.population for c in cities],
        city_coords=[(c.latitude, c.longitude) for c in cities],
        city_medical_scores=[c.medical_services_score for c in cities],
        city_r_eff=[p.R0 for p in params_list],
    )
