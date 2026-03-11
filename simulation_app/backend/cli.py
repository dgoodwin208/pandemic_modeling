#!/usr/bin/env python3
"""
CLI for running pandemic simulations without the web UI.

Usage:
    python cli.py --country Nigeria --scenario covid_natural --days 200
    python cli.py --country Kenya --scenario ebola_natural --n-people 10000
    python cli.py --help
"""

import argparse
import sys
import time

from simulation import SimulationParams, run_absdes_simulation


SCENARIOS = ["covid_natural", "covid_bioattack", "ebola_natural", "ebola_bioattack"]


def _progress(phase: str, current: int, total: int, message: str) -> None:
    sys.stderr.write(f"\r\033[K{message}")
    sys.stderr.flush()


def _fmt(n: int | float) -> str:
    if isinstance(n, float):
        return f"{n:,.1f}"
    return f"{n:,}"


def main():
    parser = argparse.ArgumentParser(
        description="Run ABS-DES pandemic simulation from the command line."
    )
    parser.add_argument("--country", default="Nigeria", help="Country to simulate (default: Nigeria)")
    parser.add_argument("--scenario", default="covid_natural", choices=SCENARIOS, help="Disease scenario")
    parser.add_argument("--days", type=int, default=200, help="Simulation days (default: 200)")
    parser.add_argument("--n-people", type=int, default=5000, help="DES agents per city (default: 5000)")
    parser.add_argument("--avg-contacts", type=int, default=None, help="Avg contacts (default: auto from household data)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--provider-density", type=float, default=5.0, help="Providers per 100k (default: 5.0)")
    parser.add_argument("--screening-capacity", type=int, default=20, help="Screenings per provider per day (default: 20)")
    _defaults = SimulationParams()
    parser.add_argument("--transmission-factor", type=float, default=_defaults.transmission_factor, help=f"Transmission factor (default: {_defaults.transmission_factor})")
    parser.add_argument("--seed-fraction", type=float, default=_defaults.seed_fraction, help=f"Initial infection fraction (default: {_defaults.seed_fraction})")
    parser.add_argument("--gravity-scale", type=float, default=_defaults.gravity_scale, help=f"Inter-city gravity scale (default: {_defaults.gravity_scale})")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress progress output")
    parser.add_argument("--per-city", action="store_true", help="Show per-city breakdown")
    parser.add_argument("--validate", action="store_true", help="Run conservation law checks after simulation")
    parser.add_argument("--events", action="store_true", help="Show notable simulation events")
    parser.add_argument("--supply-chain", action="store_true", help="Enable supply chain resources")

    args = parser.parse_args()

    params = SimulationParams(
        country=args.country,
        scenario=args.scenario,
        n_people=args.n_people,
        avg_contacts=args.avg_contacts,
        days=args.days,
        random_seed=args.seed,
        provider_density=args.provider_density,
        screening_capacity=args.screening_capacity,
        transmission_factor=args.transmission_factor,
        seed_fraction=args.seed_fraction,
        gravity_scale=args.gravity_scale,
        enable_supply_chain=args.supply_chain,
        debug_validation=args.validate,
    )

    callback = None if args.quiet else _progress
    t0 = time.time()
    result = run_absdes_simulation(params, progress_callback=callback)
    elapsed = time.time() - t0

    if not args.quiet:
        sys.stderr.write("\n")

    n_cities = len(result.city_names)
    last = result.actual_S.shape[1] - 1
    scale = [result.city_populations[i] / result.n_people_per_city for i in range(n_cities)]

    total_pop = sum(result.city_populations)
    total_infected = sum(
        (result.n_people_per_city - int(result.actual_S[i, last])) * scale[i]
        for i in range(n_cities)
    )
    total_deaths = sum(int(result.actual_D[i, last]) * scale[i] for i in range(n_cities))
    total_recovered = sum(int(result.actual_R[i, last]) * scale[i] for i in range(n_cities))
    total_active_i = sum(
        (int(result.actual_I_minor[i, last]) + int(result.actual_I_needs[i, last]) + int(result.actual_I_care[i, last])) * scale[i]
        for i in range(n_cities)
    )
    fatality_rate = total_deaths / total_infected if total_infected > 0 else 0

    agg_I = result.actual_I.sum(axis=0)
    peak_day = int(agg_I.argmax())
    peak_I = sum(int(result.actual_I[i, peak_day]) * scale[i] for i in range(n_cities))

    print(f"\n{'=' * 60}")
    print(f"  Pandemic Simulation — {args.country} / {args.scenario}")
    print(f"{'=' * 60}")
    print(f"  Cities:          {n_cities}")
    print(f"  Population:      {_fmt(total_pop)}")
    print(f"  Days simulated:  {args.days}")
    print(f"  Agents per city: {_fmt(args.n_people)}")
    print(f"  Runtime:         {elapsed:.1f}s")
    print(f"{'─' * 60}")
    print(f"  Total infected:  {_fmt(int(total_infected))}")
    print(f"  Total deaths:    {_fmt(int(total_deaths))}")
    print(f"  Total recovered: {_fmt(int(total_recovered))}")
    print(f"  Active cases:    {_fmt(int(total_active_i))}")
    print(f"  Fatality rate:   {fatality_rate:.2%}")
    print(f"  Peak infection:  Day {peak_day} ({_fmt(int(peak_I))} active)")
    print(f"  Reference IFR:   {result.ifr:.4f}")
    print(f"{'=' * 60}")

    if args.per_city:
        print(f"\n{'─' * 60}")
        print(f"  {'City':<20} {'Pop':>10} {'Infected':>10} {'Deaths':>8} {'Rate':>7}")
        print(f"  {'─'*20} {'─'*10} {'─'*10} {'─'*8} {'─'*7}")
        for i in range(n_cities):
            pop = result.city_populations[i]
            infected = int((result.n_people_per_city - int(result.actual_S[i, last])) * scale[i])
            deaths = int(int(result.actual_D[i, last]) * scale[i])
            rate = deaths / infected if infected > 0 else 0
            print(f"  {result.city_names[i]:<20} {_fmt(pop):>10} {_fmt(infected):>10} {_fmt(deaths):>8} {rate:>6.2%}")
        print(f"{'─' * 60}")

    # Validation report
    if args.validate:
        from tests.test_validation import run_all_validators
        print(f"\n{'=' * 60}")
        print(f"  Validation Report")
        print(f"{'=' * 60}")
        all_errors = run_all_validators(result)
        any_errors = False
        for check_name, errors in all_errors.items():
            status = "PASS" if not errors else "FAIL"
            print(f"  {check_name}: {status}")
            for err in errors:
                print(f"    - {err}")
                any_errors = True
        if not any_errors:
            print(f"\n  All checks passed.")
        print(f"{'=' * 60}")

    # Event summary
    if args.events and result.event_log is not None:
        elog = result.event_log
        summary = elog.summary()
        print(f"\n{'=' * 60}")
        print(f"  Event Summary ({summary['total_events']} total)")
        print(f"{'=' * 60}")
        if summary['total_events'] > 0:
            for cat, count in sorted(summary['by_category'].items(), key=lambda x: -x[1]):
                print(f"  {cat:<20} {count:>6}")
            print(f"{'─' * 60}")
            notable = elog.notable_events()
            if notable:
                print(f"  Notable events:")
                for e in notable:
                    detail = f"Day {e.day}: {e.category}/{e.action}"
                    if e.resource:
                        detail += f" — {e.resource}"
                    if e.quantity:
                        detail += f" ({e.quantity})"
                    detail += f" [{e.city}]"
                    if e.reason:
                        detail += f" ({e.reason})"
                    print(f"    {detail}")
        print(f"{'=' * 60}")

    print()


if __name__ == "__main__":
    main()
