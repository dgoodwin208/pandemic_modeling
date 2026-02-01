#!/usr/bin/env python3
"""
Calibration script: run simulations across representative African countries
and compare total deaths to real-world COVID-19 figure (~257,000 across Africa).

Real-world Africa COVID-19 (WHO, through end of pandemic):
  - Reported deaths: ~257,000
  - Estimated true deaths (excess mortality): ~500,000-1,200,000 (The Economist, IHME)
  - Total population: ~1.4 billion
  - Our city data: ~454 million (major cities only)
"""

import sys
import time
import sim_config

from simulation import SimulationParams, run_absdes_simulation, load_cities
import numpy as np


SAMPLE_COUNTRIES = [
    "Nigeria",
    "Egypt",
    "Congo (Kinshasa)",
    "South Africa",
    "Ethiopia",
    "Kenya",
    "Tanzania",
    "Algeria",
    "Ghana",
    "Morocco",
]


def get_total_city_population():
    all_cities = load_cities("ALL")
    return sum(int(c["population"]) for c in all_cities)


def patch_disease_params(severe_fraction=None, care_survival_prob=None,
                         base_daily_death_prob=None, death_prob_increase_per_day=None):
    original_load = sim_config._original_load if hasattr(sim_config, '_original_load') else sim_config.load_disease_params
    sim_config._original_load = original_load

    def patched_load():
        params = original_load()
        dp = params.get("covid_natural")
        if dp:
            if severe_fraction is not None:
                dp.severe_fraction = severe_fraction
            if care_survival_prob is not None:
                dp.care_survival_prob = care_survival_prob
            if base_daily_death_prob is not None:
                dp.base_daily_death_prob = base_daily_death_prob
            if death_prob_increase_per_day is not None:
                dp.death_prob_increase_per_day = death_prob_increase_per_day
        return params

    sim_config.load_disease_params = patched_load
    import simulation
    simulation.load_disease_params = patched_load


def run_country(country, days=365, n_people=5000, transmission_factor=0.3,
                seed_fraction=0.002, provider_density=5.0, screening_capacity=20,
                gravity_scale=0.01, seed=42):
    params = SimulationParams(
        country=country, scenario="covid_natural", n_people=n_people,
        days=days, random_seed=seed, transmission_factor=transmission_factor,
        seed_fraction=seed_fraction, provider_density=provider_density,
        screening_capacity=screening_capacity, gravity_scale=gravity_scale,
    )
    result = run_absdes_simulation(params)

    n_cities = len(result.city_names)
    last = result.actual_S.shape[1] - 1
    scale = [result.city_populations[i] / result.n_people_per_city for i in range(n_cities)]

    total_pop = sum(result.city_populations)
    total_infected = sum(
        (result.n_people_per_city - int(result.actual_S[i, last])) * scale[i]
        for i in range(n_cities)
    )
    total_deaths = sum(int(result.actual_D[i, last]) * scale[i] for i in range(n_cities))

    attack_rate = total_infected / total_pop if total_pop > 0 else 0
    fatality_rate = total_deaths / total_infected if total_infected > 0 else 0

    return {
        "country": country, "n_cities": n_cities, "population": total_pop,
        "infected": int(total_infected), "deaths": int(total_deaths),
        "attack_rate": attack_rate, "fatality_rate": fatality_rate,
    }


def run_calibration(label="", days=365, n_people=5000, transmission_factor=0.3,
                    seed_fraction=0.002, provider_density=5.0,
                    screening_capacity=20, gravity_scale=0.01,
                    severe_fraction=None, care_survival_prob=None,
                    base_daily_death_prob=None, death_prob_increase_per_day=None):

    if any(v is not None for v in [severe_fraction, care_survival_prob,
                                    base_daily_death_prob, death_prob_increase_per_day]):
        patch_disease_params(
            severe_fraction=severe_fraction,
            care_survival_prob=care_survival_prob,
            base_daily_death_prob=base_daily_death_prob,
            death_prob_increase_per_day=death_prob_increase_per_day,
        )

    total_city_pop = get_total_city_population()
    africa_pop = 1_400_000_000

    print(f"\n{'=' * 74}")
    print(f"  {label or 'Calibration Run'}")
    print(f"  tf={transmission_factor}, days={days}, n_people={n_people}")
    print(f"{'=' * 74}")

    results = []
    sample_pop = 0
    sample_deaths = 0
    sample_infected = 0
    t0 = time.time()

    for country in SAMPLE_COUNTRIES:
        ct0 = time.time()
        r = run_country(
            country, days=days, n_people=n_people,
            transmission_factor=transmission_factor,
            seed_fraction=seed_fraction,
            provider_density=provider_density,
            screening_capacity=screening_capacity,
            gravity_scale=gravity_scale,
        )
        elapsed = time.time() - ct0
        results.append(r)
        sample_pop += r["population"]
        sample_deaths += r["deaths"]
        sample_infected += r["infected"]
        print(f"  {r['country']:<22} pop={r['population']:>11,}  "
              f"inf={r['infected']:>10,} ({r['attack_rate']:5.1%})  "
              f"deaths={r['deaths']:>8,} ({r['fatality_rate']:.2%})  "
              f"[{elapsed:.1f}s]")

    total_elapsed = time.time() - t0

    if sample_pop > 0:
        death_rate_per_capita = sample_deaths / sample_pop
        extrapolated_dataset = int(death_rate_per_capita * total_city_pop)
        non_city_pop = africa_pop - total_city_pop
        rural_deaths = int(death_rate_per_capita * 0.4 * non_city_pop)
        extrapolated_africa = extrapolated_dataset + rural_deaths
    else:
        extrapolated_dataset = 0
        extrapolated_africa = 0

    sample_attack = sample_infected / sample_pop if sample_pop > 0 else 0
    sample_cfr = sample_deaths / sample_infected if sample_infected > 0 else 0

    print(f"\n{'─' * 74}")
    print(f"  Sample:               {sample_pop:,} pop, {sample_infected:,} inf ({sample_attack:.1%})")
    print(f"  Sample deaths:        {sample_deaths:,} ({sample_cfr:.2%} CFR)")
    print(f"  Extrapolated (cities): {extrapolated_dataset:,}")
    print(f"  Extrapolated (Africa): {extrapolated_africa:,}")
    print(f"  TARGET (reported):     257,000")
    print(f"  TARGET (excess mort):  500,000 - 1,200,000")
    ratio_rep = extrapolated_africa / 257_000 if extrapolated_africa > 0 else 0
    ratio_mid = extrapolated_africa / 750_000 if extrapolated_africa > 0 else 0
    print(f"  Ratio to reported:     {ratio_rep:.1f}x")
    print(f"  Ratio to excess mid:   {ratio_mid:.1f}x")
    print(f"  Runtime: {total_elapsed:.1f}s")
    print(f"{'=' * 74}\n")

    return extrapolated_africa


if __name__ == "__main__":
    # All at 5k agents (the default)

    # Current CSV: sf=0.010 → gave 1.2M. Need ~0.62x reduction → try sf=0.007
    run_calibration(
        label="RUN A: sf=0.007, bdp=0.003, dpi=0.002, csp=0.93",
        severe_fraction=0.007,
        base_daily_death_prob=0.003,
        death_prob_increase_per_day=0.002,
        care_survival_prob=0.93,
    )

    # Slightly higher
    run_calibration(
        label="RUN B: sf=0.008, bdp=0.003, dpi=0.002, csp=0.93",
        severe_fraction=0.008,
        base_daily_death_prob=0.003,
        death_prob_increase_per_day=0.002,
        care_survival_prob=0.93,
    )

    # Try keeping sf=0.010 but raising care survival very high
    run_calibration(
        label="RUN C: sf=0.010, bdp=0.003, dpi=0.002, csp=0.95",
        severe_fraction=0.010,
        base_daily_death_prob=0.003,
        death_prob_increase_per_day=0.002,
        care_survival_prob=0.95,
    )
