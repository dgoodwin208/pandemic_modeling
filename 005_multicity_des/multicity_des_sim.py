"""
Multi-City DES Metapopulation Simulation.

Each city runs an independent ABS-DES (SEIR on a social network), coupled
by the same gravity-based travel model used in module 004. The coupling
layer is model-agnostic: it reads infection_fraction and injects new
exposures, regardless of whether the within-city model is ODE or DES.

Daily coupling algorithm:
    1. Advance each city's DES by 1 day (SimPy step)
    2. Compute inter-city infections from travel
    3. Inject new exposures into destination cities
    4. Record state snapshot
"""

from dataclasses import dataclass

import numpy as np

from city_des import CityDES


@dataclass
class MultiCityDESResult:
    """Time-series results for all cities (DES version)."""

    city_names: list[str]
    t: np.ndarray             # shape (days+1,)
    S: np.ndarray             # shape (n_cities, days+1)
    E: np.ndarray             # shape (n_cities, days+1)
    I: np.ndarray             # shape (n_cities, days+1)
    R: np.ndarray             # shape (n_cities, days+1)
    travel_matrix: np.ndarray # shape (n_cities, n_cities)
    city_populations: list[int]
    city_coords: list[tuple[float, float]]
    n_people_per_city: int    # DES population size per city


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
            # Travel matrix already at DES scale — no population scaling
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


def run_multicity_des_simulation(
    city_names: list[str],
    city_populations: list[int],
    city_coords: list[tuple[float, float]],
    scenario,
    travel_matrix: np.ndarray,
    days: int = 300,
    n_people: int = 5000,
    transmission_factor: float = 0.1,
    seed_city_index: int | list[int] = 0,
    initial_infected: int = 10,
    random_seed: int = 42,
    des_scale_travel: bool = False,
    # R₀ override (figs 1-3, backward compatible)
    isolation_effect: float = 0.0,
    medical_scores: list[float] | None = None,
    # Provider parameters (fig 4+)
    provider_density: float = 0.0,
    screening_capacity: int = 20,
    disclosure_prob: float = 0.5,
    receptivity: float = 0.6,
    base_isolation_prob: float = 0.0,
    advised_isolation_prob: float = 0.40,
    advice_decay_prob: float = 0.0,
    per_city_receptivity: list[float] | None = None,
) -> MultiCityDESResult:
    """
    Run coupled multi-city DES simulation.

    Args:
        city_names: Names for each city.
        city_populations: Real populations (for scaling travel coupling).
        city_coords: (lat, lon) per city.
        scenario: EpidemicScenario (provides R0, incubation, infectious days).
        travel_matrix: n x n daily travel rates.
        days: Simulation duration.
        n_people: DES population size per city.
        transmission_factor: P(traveler causes exposure at destination).
        seed_city_index: Which city/cities start with infections (int or list).
        initial_infected: Number of initial infections in seed city.
        random_seed: Base random seed (each city gets seed + i).
        des_scale_travel: If True, travel matrix is at DES scale (no
            population scaling in coupling). If False (default), scales
            coupling by n_people/real_population.
        isolation_effect: Maximum fractional R₀ reduction at score=100.
            0.0 means uniform R₀ (default). 0.3 means 30% max reduction.
        medical_scores: Per-city medical_services_score (0-100). Required
            when isolation_effect > 0.
        provider_density: Healthcare providers per 1000 population.
            0.0 means no providers (default).
        screening_capacity: People screened per provider per day.
        disclosure_prob: P(infectious person reveals symptoms when screened).
        receptivity: Default P(person accepts provider advice). Overridden
            by per_city_receptivity if provided.
        base_isolation_prob: P(isolate per day) without provider advice.
        advised_isolation_prob: P(isolate per day) after accepting advice.
        advice_decay_prob: Daily P(advised person reverts to baseline).
            0.0 means no decay (default). 0.05 ≈ 14-day half-life.
        per_city_receptivity: Per-city receptivity values (e.g. derived
            from medical_services_score). If None, uses ``receptivity``
            for all cities.

    Returns:
        MultiCityDESResult with full time series.
    """
    n = len(city_names)

    # Compute per-city effective R₀ (if health modulation enabled)
    r0_overrides = [None] * n
    if isolation_effect > 0.0:
        if medical_scores is None:
            raise ValueError("medical_scores required when isolation_effect > 0")
        for i in range(n):
            normalized = medical_scores[i] / 100.0
            r0_overrides[i] = max(0.0, scenario.R0 * (1.0 - isolation_effect * normalized))

    # Compute provider count from density
    n_providers = max(0, int(provider_density * n_people / 1000))

    # Normalize seed city index to list for multi-seed support
    seed_indices = (
        [seed_city_index] if isinstance(seed_city_index, int)
        else list(seed_city_index)
    )

    # Create DES for each city
    city_sims = []
    for i in range(n):
        seed_count = initial_infected if i in seed_indices else 0
        city_receptivity = (per_city_receptivity[i] if per_city_receptivity
                            else receptivity)
        city_sims.append(CityDES(
            n_people=n_people,
            scenario=scenario,
            seed_infected=seed_count,
            random_seed=random_seed + i,
            r0_override=r0_overrides[i],
            n_providers=n_providers,
            screening_capacity=screening_capacity,
            disclosure_prob=disclosure_prob,
            receptivity=city_receptivity,
            base_isolation_prob=base_isolation_prob,
            advised_isolation_prob=advised_isolation_prob,
            advice_decay_prob=advice_decay_prob,
        ))

    # Allocate time-series storage (as fractions of n_people)
    S = np.zeros((n, days + 1))
    E = np.zeros((n, days + 1))
    I = np.zeros((n, days + 1))
    R = np.zeros((n, days + 1))

    # Record initial state (day 0)
    for i in range(n):
        S[i, 0] = city_sims[i].S
        E[i, 0] = city_sims[i].E
        I[i, 0] = city_sims[i].I
        R[i, 0] = city_sims[i].R

    # Exposure debt accumulators (fractional coupling that hasn't yet
    # produced a whole person to inject)
    exposure_debt = np.zeros(n)

    # Daily stepping loop
    for day in range(1, days + 1):
        # Step 1: Advance each city's DES by 1 day
        for i in range(n):
            city_sims[i].step(until=day)

        # Step 1.5: Provider screening (if providers deployed)
        for i in range(n):
            city_sims[i].run_provider_screening()

        # Step 2: Apply inter-city travel coupling
        _apply_travel_coupling_des(
            city_sims, city_populations, travel_matrix, transmission_factor,
            exposure_debt, des_scale_travel=des_scale_travel,
        )

        # Step 3: Record snapshot
        for i in range(n):
            S[i, day] = city_sims[i].S
            E[i, day] = city_sims[i].E
            I[i, day] = city_sims[i].I
            R[i, day] = city_sims[i].R

    return MultiCityDESResult(
        city_names=city_names,
        t=np.arange(days + 1, dtype=float),
        S=S, E=E, I=I, R=R,
        travel_matrix=travel_matrix,
        city_populations=city_populations,
        city_coords=city_coords,
        n_people_per_city=n_people,
    )
