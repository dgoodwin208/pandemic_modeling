"""
Multi-City DES vs ODE Validation.

Runs both the ODE multi-city simulation (module 004) and the DES multi-city
simulation (this module) with identical parameters, then overlays the infection
curves to confirm the DES coupling produces equivalent dynamics.

Produces:
    01 — DES (N=50K) vs ODE, uniform R₀, real-population gravity
    02 — DES (N=5K) vs ODE, uniform R₀, DES-scale gravity
    03 — DES (N=5K) vs ODE, health-modulated R₀, DES-scale gravity
    04 — Nigeria 51-city DES: provider density 1/1000 vs 5/1000
    05 — Nigeria 51-city DES: no providers vs 1/1000 vs 5/1000

Usage:
    cd 005_multicity_des && python validation_des_vs_ode.py
"""

import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "des_system"))
sys.path.insert(0, str(_PROJECT_ROOT / "004_multicity"))

from validation_config import COVID_LIKE

from city import load_cities
from gravity_model import compute_travel_matrix, compute_distance_matrix
from multicity_sim import run_multicity_simulation

from multicity_des_sim import run_multicity_des_simulation

# ── Configuration ────────────────────────────────────────────────────

DEMO_CITIES = ["Cairo", "Lagos", "Nairobi", "Johannesburg", "Kinshasa"]
SCENARIO = COVID_LIKE
DAYS = 400
SEED_CITY = "Cairo"

# Both ODE and DES seed the same fraction of their respective populations,
# ensuring comparable epidemic timing.  0.1% is large enough that the DES
# gets sufficient initial infected for reliable take-off.
SEED_FRACTION = 0.001

# Gravity model (real-population scale, for ODE and Fig 1 DES)
GRAVITY_ALPHA = 2.0
GRAVITY_SCALE = 1e-4
TRANSMISSION_FACTOR = 0.3

# DES parameters
N_PEOPLE_FIG1 = 50_000   # Fig 1: large N with real-population gravity
N_PEOPLE_FIG23 = 5_000   # Figs 2-3: small N with DES-scale gravity
N_MC_RUNS = 5             # Monte Carlo runs for DES
BASE_SEED = 42

# DES-scale gravity: computed using n_people^2 instead of real populations.
# Scale calibrated so coupling produces ~0.3-2 inject/day at peak infection.
DES_GRAVITY_SCALE = 10.0

# Health modulation (Fig 3)
ISOLATION_EFFECT = 0.3    # max 30% R₀ reduction at score=100

RESULTS_DIR = Path(__file__).parent / "results"
CITY_COLORS = ["#e63946", "#457b9d", "#2a9d8f", "#e9c46a", "#f4a261"]


def ensure_results_dir():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ── DES-scale gravity matrix ────────────────────────────────────────

def compute_des_scale_travel_matrix(
    cities: list,
    n_people: int,
    alpha: float = 2.0,
    scale: float = 10.0,
) -> np.ndarray:
    """
    Gravity model using uniform DES population instead of real populations.

    T_des[i,j] = scale * n_people^2 / dist_ij^alpha

    This produces coupling rates that work at small N (5,000) without
    needing the n_people/real_population scaling in the coupling function.
    All cities get the same coupling strength (distance-dependent only).
    """
    dist = compute_distance_matrix(cities)
    n = len(cities)
    travel = np.zeros((n, n))
    pop_product = n_people * n_people

    for i in range(n):
        for j in range(i + 1, n):
            if dist[i, j] > 0:
                rate = scale * pop_product / (dist[i, j] ** alpha)
                travel[i, j] = rate
                travel[j, i] = rate

    return travel


# ── ODE baselines ────────────────────────────────────────────────────

def run_ode_baseline(cities, travel_matrix, isolation_effect=0.0):
    """Run module 004 ODE simulation."""
    fresh_cities = load_cities(DEMO_CITIES)
    seed_idx = DEMO_CITIES.index(SEED_CITY)
    ode_initial = max(1, int(SEED_FRACTION * fresh_cities[seed_idx].population))

    return run_multicity_simulation(
        cities=fresh_cities,
        scenario=SCENARIO,
        travel_matrix=travel_matrix,
        days=DAYS,
        transmission_factor=TRANSMISSION_FACTOR,
        seed_city_index=seed_idx,
        initial_infected=ode_initial,
        isolation_effect=isolation_effect,
    )


# ── DES runs ─────────────────────────────────────────────────────────

def run_des_single(
    cities, travel_matrix, run_seed, n_people,
    des_scale_travel=False, isolation_effect=0.0, medical_scores=None,
    seed_city="Cairo",
):
    """Run one DES multi-city simulation."""
    city_names = [c.name for c in cities]
    seed_idx = city_names.index(seed_city)
    des_initial = max(1, int(SEED_FRACTION * n_people))

    return run_multicity_des_simulation(
        city_names=city_names,
        city_populations=[c.population for c in cities],
        city_coords=[(c.latitude, c.longitude) for c in cities],
        scenario=SCENARIO,
        travel_matrix=travel_matrix,
        days=DAYS,
        n_people=n_people,
        transmission_factor=TRANSMISSION_FACTOR,
        seed_city_index=seed_idx,
        initial_infected=des_initial,
        random_seed=run_seed,
        des_scale_travel=des_scale_travel,
        isolation_effect=isolation_effect,
        medical_scores=medical_scores,
    )


def run_des_monte_carlo(
    cities, travel_matrix, n_people,
    des_scale_travel=False, isolation_effect=0.0, medical_scores=None,
    label="DES", seed_city="Cairo", n_mc_runs=None,
):
    """Run Monte Carlo DES simulations and return infection fraction array."""
    n_runs = n_mc_runs if n_mc_runs is not None else N_MC_RUNS
    n_cities = len(cities)
    des_I_runs = np.zeros((n_runs, n_cities, DAYS + 1))

    for run in range(n_runs):
        print(f"  {label} run {run + 1}/{n_runs}...", end="", flush=True)
        result = run_des_single(
            cities, travel_matrix, BASE_SEED + run * 100, n_people,
            des_scale_travel=des_scale_travel,
            isolation_effect=isolation_effect,
            medical_scores=medical_scores,
            seed_city=seed_city,
        )

        for i in range(n_cities):
            des_I_runs[run, i, :] = result.I[i] / n_people

        if run == 0:
            # Print top 5 cities by peak infection
            peaks = []
            for i in range(n_cities):
                frac = result.I[i] / n_people * 100
                peak_day = int(result.t[np.argmax(frac)])
                peak_val = frac.max()
                peaks.append((result.city_names[i], peak_day, peak_val))
            peaks.sort(key=lambda x: -x[2])
            for name, day, val in peaks[:min(10, n_cities)]:
                print(f"\n    {name}: peak day {day}, {val:.1f}%", end="")
            if n_cities > 10:
                print(f"\n    ... ({n_cities - 10} more cities)", end="")
        print()

    return des_I_runs


# ── Plotting helpers ─────────────────────────────────────────────────

def _plot_comparison(
    ax, ode_result, des_I_runs, n_people,
    ode_pop_source="real", show_r_eff=False,
):
    """Plot ODE vs DES curves on a single axes."""
    n_cities = len(ode_result.city_names)
    t = ode_result.t

    for i in range(n_cities):
        color = CITY_COLORS[i]
        name = ode_result.city_names[i]

        # ODE curve (solid)
        ode_frac = ode_result.I[i] / ode_result.city_populations[i] * 100
        ode_label = f"{name} (ODE)"
        if show_r_eff and hasattr(ode_result, 'city_r_eff'):
            ode_label = f"{name} (ODE, R₀={ode_result.city_r_eff[i]:.2f})"
        ax.plot(t, ode_frac, color=color, linewidth=2, label=ode_label)

        # DES mean + band (dashed + shading)
        des_frac = des_I_runs[:, i, :] * 100
        des_mean = des_frac.mean(axis=0)
        des_std = des_frac.std(axis=0)

        ax.plot(
            t, des_mean, color=color, linewidth=2,
            linestyle="--", alpha=0.8, label=f"{name} (DES mean)",
        )
        ax.fill_between(
            t, np.maximum(des_mean - des_std, 0), des_mean + des_std,
            color=color, alpha=0.15,
        )

    ax.set_xlabel("Day", fontsize=11)
    ax.set_ylabel("Infected (% of population)", fontsize=11)
    ax.legend(fontsize=8, loc="upper left", ncol=2)
    ax.set_xlim(0, DAYS)
    ax.grid(True, alpha=0.3)


def _print_comparison(ode_result, des_I_runs, n_people, label=""):
    """Print summary comparison table."""
    n_cities = len(ode_result.city_names)
    t = ode_result.t
    header = f"COMPARISON SUMMARY{f' ({label})' if label else ''}"
    print("\n" + "=" * 70)
    print(header)
    print("=" * 70)
    print(f"{'City':<18} {'ODE Peak Day':>12} {'ODE Peak%':>10} {'DES Peak Day':>13} {'DES Peak%':>10}")
    print("-" * 65)
    for i in range(n_cities):
        name = ode_result.city_names[i]
        ode_frac = ode_result.I[i] / ode_result.city_populations[i] * 100
        ode_peak_day = int(t[np.argmax(ode_frac)])
        ode_peak_pct = ode_frac.max()

        des_frac_mean = des_I_runs[:, i, :].mean(axis=0) * 100
        des_peak_day = int(t[np.argmax(des_frac_mean)])
        des_peak_pct = des_frac_mean.max()

        print(f"{name:<18} {ode_peak_day:>12} {ode_peak_pct:>10.1f} {des_peak_day:>13} {des_peak_pct:>10.1f}")


# ── Figure 1: DES (N=50K) vs ODE, real-population gravity ───────────

def figure_01(cities, travel_matrix):
    """Fig 1: Large-N DES with real-population gravity vs ODE."""
    n_people = N_PEOPLE_FIG1
    des_initial = max(1, int(SEED_FRACTION * n_people))

    print(f"\n{'='*70}")
    print(f"FIGURE 1: DES (N={n_people:,}) vs ODE, real-population gravity")
    print(f"{'='*70}")
    print(f"  DES seed: {des_initial:,} initial infected")

    print(f"\nRunning ODE baseline (uniform R₀={SCENARIO.R0})...")
    ode_result = run_ode_baseline(cities, travel_matrix, isolation_effect=0.0)
    print("  Done.")

    print(f"\nRunning DES ({N_MC_RUNS} MC runs, N={n_people:,}/city)...")
    des_I_runs = run_des_monte_carlo(
        cities, travel_matrix, n_people,
        des_scale_travel=False, label="Fig1",
    )

    _print_comparison(ode_result, des_I_runs, n_people, "uniform R₀, N=50K")

    fig, ax = plt.subplots(figsize=(14, 7))
    fig.suptitle(
        "Fig 1: Multi-City Validation — DES vs ODE (real-population gravity)\n"
        f"COVID-like (R₀={SCENARIO.R0}), {len(DEMO_CITIES)} cities, "
        f"N={n_people:,}/city, {N_MC_RUNS} MC runs, "
        f"seed fraction={SEED_FRACTION:.1%}",
        fontsize=12, fontweight="bold",
    )
    _plot_comparison(ax, ode_result, des_I_runs, n_people)

    fname = RESULTS_DIR / "01_des_vs_ode.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {fname.name}")


# ── Figure 2: DES (N=5K) vs ODE, DES-scale gravity ──────────────────

def figure_02(cities, travel_matrix_real):
    """Fig 2: Small-N DES with DES-scale gravity vs ODE."""
    n_people = N_PEOPLE_FIG23

    print(f"\n{'='*70}")
    print(f"FIGURE 2: DES (N={n_people:,}) vs ODE, DES-scale gravity")
    print(f"{'='*70}")

    # Compute DES-scale travel matrix
    travel_des = compute_des_scale_travel_matrix(
        cities, n_people, alpha=GRAVITY_ALPHA, scale=DES_GRAVITY_SCALE,
    )

    # Show DES travel matrix
    print("\nDES-scale travel matrix (daily coupling rates):")
    for i in range(len(DEMO_CITIES)):
        for j in range(len(DEMO_CITIES)):
            if i != j:
                print(f"  {DEMO_CITIES[j]} -> {DEMO_CITIES[i]}: {travel_des[j, i]:.2f}/day")

    des_initial = max(1, int(SEED_FRACTION * n_people))
    print(f"\n  DES seed: {des_initial:,} initial infected")

    print(f"\nRunning ODE baseline (uniform R₀={SCENARIO.R0})...")
    ode_result = run_ode_baseline(cities, travel_matrix_real, isolation_effect=0.0)
    print("  Done.")

    print(f"\nRunning DES ({N_MC_RUNS} MC runs, N={n_people:,}/city, DES-scale gravity)...")
    des_I_runs = run_des_monte_carlo(
        cities, travel_des, n_people,
        des_scale_travel=True, label="Fig2",
    )

    _print_comparison(ode_result, des_I_runs, n_people, "uniform R₀, N=5K, DES-scale gravity")

    fig, ax = plt.subplots(figsize=(14, 7))
    fig.suptitle(
        "Fig 2: Multi-City Validation — DES (N=5K, DES-scale gravity) vs ODE\n"
        f"COVID-like (R₀={SCENARIO.R0}), {len(DEMO_CITIES)} cities, "
        f"N={n_people:,}/city, {N_MC_RUNS} MC runs, "
        f"seed fraction={SEED_FRACTION:.1%}",
        fontsize=12, fontweight="bold",
    )
    _plot_comparison(ax, ode_result, des_I_runs, n_people)

    fname = RESULTS_DIR / "02_des_5k_des_scale_gravity.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {fname.name}")


# ── Figure 3: DES (N=5K) vs ODE, health-modulated R₀ ────────────────

def figure_03(cities, travel_matrix_real):
    """Fig 3: Small-N DES with health modulation vs ODE."""
    n_people = N_PEOPLE_FIG23

    print(f"\n{'='*70}")
    print(f"FIGURE 3: DES (N={n_people:,}) vs ODE, health-modulated R₀")
    print(f"{'='*70}")

    # Compute DES-scale travel matrix
    travel_des = compute_des_scale_travel_matrix(
        cities, n_people, alpha=GRAVITY_ALPHA, scale=DES_GRAVITY_SCALE,
    )

    medical_scores = [c.medical_services_score for c in cities]
    print("\nPer-city health modulation:")
    for i, c in enumerate(cities):
        r_eff = max(0.0, SCENARIO.R0 * (1.0 - ISOLATION_EFFECT * c.medical_services_score / 100.0))
        print(f"  {c.name}: score={c.medical_services_score:.0f}, R_eff={r_eff:.2f}")

    des_initial = max(1, int(SEED_FRACTION * n_people))
    print(f"\n  DES seed: {des_initial:,} initial infected")

    print(f"\nRunning ODE baseline (health-modulated, isolation_effect={ISOLATION_EFFECT})...")
    ode_result = run_ode_baseline(cities, travel_matrix_real, isolation_effect=ISOLATION_EFFECT)
    print("  Done.")

    print(f"\nRunning DES ({N_MC_RUNS} MC runs, N={n_people:,}/city, health-modulated)...")
    des_I_runs = run_des_monte_carlo(
        cities, travel_des, n_people,
        des_scale_travel=True,
        isolation_effect=ISOLATION_EFFECT,
        medical_scores=medical_scores,
        label="Fig3",
    )

    _print_comparison(ode_result, des_I_runs, n_people, "health-modulated R₀, N=5K")

    fig, ax = plt.subplots(figsize=(14, 7))
    fig.suptitle(
        "Fig 3: Multi-City DES vs ODE — Health-Modulated R₀\n"
        f"COVID-like, isolation_effect={ISOLATION_EFFECT}, "
        f"N={n_people:,}/city, {N_MC_RUNS} MC runs",
        fontsize=12, fontweight="bold",
    )
    _plot_comparison(ax, ode_result, des_I_runs, n_people, show_r_eff=True)

    fname = RESULTS_DIR / "03_des_health_modulated.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {fname.name}")


# ── Figure 4: Nigeria 51-city provider density comparison ────────────

# Nigeria simulation parameters
NIGERIA_SEED_CITY = "Lagos"
NIGERIA_N_PEOPLE = 5_000
NIGERIA_N_MC_RUNS = 3       # 3 runs × 51 cities × 0.5s ≈ 77s per scenario
# Nigeria gravity scale: cities are ~100-500 km apart (vs 2000-6000 km for
# the 5-city demo), so gravity rates scale ~100-1000x higher at scale=10.
# Use 0.01 to produce ~1-25 travelers/day between Nigerian city pairs.
NIGERIA_GRAVITY_SCALE = 0.01

# Provider density scenarios (providers per 1000 population)
PROVIDER_DENSITY_LOW = 1.0   # 1/1000 → 5 providers per city (N=5000)
PROVIDER_DENSITY_HIGH = 5.0  # 5/1000 → 25 providers per city (N=5000)

# Behavioral parameters (from module 003 defaults)
SCREENING_CAPACITY = 20      # people screened per provider per day
DISCLOSURE_PROB = 0.5         # P(infectious person reveals symptoms)
BASE_ISOLATION_PROB = 0.05    # P(isolate/day) without provider advice
ADVISED_ISOLATION_PROB = 0.40 # P(isolate/day) after accepting advice
ADVICE_DECAY_PROB = 0.05     # P(revert to baseline/day) ≈ 14-day half-life

# medical_services_score → receptivity mapping
# Higher health system capacity → population more receptive to provider advice
def _score_to_receptivity(score: float) -> float:
    """Map medical_services_score (0-100) to receptivity (0.2-0.8)."""
    return 0.2 + 0.6 * (score / 100.0)


def _load_nigerian_cities():
    """Load all Nigerian cities from the CSV."""
    import csv
    csv_path = _PROJECT_ROOT / "backend" / "data" / "african_cities.csv"
    cities = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["country"] == "Nigeria":
                cities.append(row)
    # Sort by population descending for consistent ordering
    cities.sort(key=lambda x: int(x["population"]), reverse=True)
    return cities


def _run_nigeria_provider_scenario(ng_cities, travel_des, provider_density, label,
                                    n_runs_override=None):
    """Run one Nigeria DES scenario with provider agents, return peak stats."""
    n_people = NIGERIA_N_PEOPLE
    n_cities = len(ng_cities)

    # Per-city receptivity derived from medical_services_score
    per_city_receptivity = [
        _score_to_receptivity(float(c.get("medical_services_score", 0)))
        for c in ng_cities
    ]

    city_names = [c["city"] for c in ng_cities]
    city_pops = [int(c["population"]) for c in ng_cities]
    city_coords = [(float(c["latitude"]), float(c["longitude"])) for c in ng_cities]
    seed_idx = city_names.index(NIGERIA_SEED_CITY)
    des_initial = max(1, int(SEED_FRACTION * n_people))

    n_runs = n_runs_override if n_runs_override is not None else NIGERIA_N_MC_RUNS
    des_I_runs = np.zeros((n_runs, n_cities, DAYS + 1))
    des_R_final = np.zeros((n_runs, n_cities))  # final recovered fraction

    for run in range(n_runs):
        print(f"  {label} run {run + 1}/{n_runs}...", end="", flush=True)
        result = run_multicity_des_simulation(
            city_names=city_names,
            city_populations=city_pops,
            city_coords=city_coords,
            scenario=SCENARIO,
            travel_matrix=travel_des,
            days=DAYS,
            n_people=n_people,
            transmission_factor=TRANSMISSION_FACTOR,
            seed_city_index=seed_idx,
            initial_infected=des_initial,
            random_seed=BASE_SEED + run * 100,
            des_scale_travel=True,
            # No R₀ override — transmission reduction emerges from providers
            isolation_effect=0.0,
            # Provider parameters
            provider_density=provider_density,
            screening_capacity=SCREENING_CAPACITY,
            disclosure_prob=DISCLOSURE_PROB,
            receptivity=0.6,  # default, overridden by per_city
            base_isolation_prob=BASE_ISOLATION_PROB,
            advised_isolation_prob=ADVISED_ISOLATION_PROB,
            advice_decay_prob=ADVICE_DECAY_PROB,
            per_city_receptivity=per_city_receptivity,
        )

        for i in range(n_cities):
            des_I_runs[run, i, :] = result.I[i] / n_people
            des_R_final[run, i] = result.R[i, -1] / n_people

        if run == 0:
            peaks = []
            for i in range(n_cities):
                frac = result.I[i] / n_people * 100
                peak_day = int(result.t[np.argmax(frac)])
                peak_val = frac.max()
                peaks.append((result.city_names[i], peak_day, peak_val))
            peaks.sort(key=lambda x: -x[2])
            for name, day, val in peaks[:min(10, n_cities)]:
                print(f"\n    {name}: peak day {day}, {val:.1f}%", end="")
            if n_cities > 10:
                print(f"\n    ... ({n_cities - 10} more cities)", end="")
        print()

    # Compute per-city mean peak infection % and attack rate
    peak_pcts = np.zeros(n_cities)
    peak_days = np.zeros(n_cities)
    attack_rates = np.zeros(n_cities)  # mean final R fraction
    for i in range(n_cities):
        mean_frac = des_I_runs[:, i, :].mean(axis=0)
        peak_pcts[i] = mean_frac.max() * 100
        peak_days[i] = np.argmax(mean_frac)
        attack_rates[i] = des_R_final[:, i].mean()

    return peak_pcts, peak_days, attack_rates


def figure_04():
    """Fig 4: Nigeria 51-city — provider density 1/1000 vs 5/1000."""
    print(f"\n{'='*70}")
    print("FIGURE 4: Nigeria 51-city DES — Provider Density Comparison")
    print(f"{'='*70}")

    # Load Nigerian cities
    ng_cities = _load_nigerian_cities()
    n_cities = len(ng_cities)
    print(f"\nLoaded {n_cities} Nigerian cities")
    print(f"  Seed city: {NIGERIA_SEED_CITY}")
    print(f"  N per city: {NIGERIA_N_PEOPLE:,}")
    print(f"  MC runs: {NIGERIA_N_MC_RUNS}")

    # Show provider configuration
    score = float(ng_cities[0].get("medical_services_score", 0))
    receptivity = _score_to_receptivity(score)
    n_prov_low = max(0, int(PROVIDER_DENSITY_LOW * NIGERIA_N_PEOPLE / 1000))
    n_prov_high = max(0, int(PROVIDER_DENSITY_HIGH * NIGERIA_N_PEOPLE / 1000))
    print(f"\n  Provider mechanics (from module 003):")
    print(f"    All cities: medical_services_score={score:.0f} -> receptivity={receptivity:.2f}")
    print(f"    Low density:  {PROVIDER_DENSITY_LOW}/1000 -> {n_prov_low} providers/city")
    print(f"      daily screens: {n_prov_low * SCREENING_CAPACITY}")
    print(f"    High density: {PROVIDER_DENSITY_HIGH}/1000 -> {n_prov_high} providers/city")
    print(f"      daily screens: {n_prov_high * SCREENING_CAPACITY}")
    print(f"    disclosure_prob={DISCLOSURE_PROB}, base_iso={BASE_ISOLATION_PROB}, "
          f"advised_iso={ADVISED_ISOLATION_PROB}")
    half_life = math.log(2) / ADVICE_DECAY_PROB if ADVICE_DECAY_PROB > 0 else float('inf')
    print(f"    advice_decay_prob={ADVICE_DECAY_PROB} (half-life ≈ {half_life:.0f} days)")
    print(f"    No R0 override — transmission reduction emerges from agent behavior")

    # Build city objects for gravity computation
    class _City:
        def __init__(self, d):
            self.name = d["city"]
            self.population = int(d["population"])
            self.latitude = float(d["latitude"])
            self.longitude = float(d["longitude"])
            self.medical_services_score = float(d.get("medical_services_score", 0))

    city_objs = [_City(c) for c in ng_cities]

    # Compute DES-scale gravity matrix (Nigeria-specific scale)
    print("\nComputing DES-scale gravity matrix for 51 cities...")
    travel_des = compute_des_scale_travel_matrix(
        city_objs, NIGERIA_N_PEOPLE,
        alpha=GRAVITY_ALPHA, scale=NIGERIA_GRAVITY_SCALE,
    )

    # Diagnostic: check travel matrix
    nonzero = travel_des[travel_des > 0]
    print(f"  Travel matrix stats (daily travelers):")
    print(f"    min={nonzero.min():.1f}, median={np.median(nonzero):.1f}, "
          f"max={nonzero.max():.1f}, mean={nonzero.mean():.1f}")
    max_incoming = travel_des.sum(axis=0).max()
    print(f"    Max total incoming to any city: {max_incoming:.0f}/day "
          f"({max_incoming / NIGERIA_N_PEOPLE * 100:.1f}% of N={NIGERIA_N_PEOPLE})")

    # Run both provider density scenarios
    print(f"\n--- Low provider density ({PROVIDER_DENSITY_LOW}/1000) ---")
    peaks_low, days_low, _ = _run_nigeria_provider_scenario(
        ng_cities, travel_des, PROVIDER_DENSITY_LOW, "Low",
    )

    print(f"\n--- High provider density ({PROVIDER_DENSITY_HIGH}/1000) ---")
    peaks_high, days_high, _ = _run_nigeria_provider_scenario(
        ng_cities, travel_des, PROVIDER_DENSITY_HIGH, "High",
    )

    # Summary table (top 10 cities)
    print("\n" + "=" * 80)
    print("NIGERIA SUMMARY — Top 10 cities by population (provider-driven)")
    print("=" * 80)
    print(f"{'City':<20} {'Pop':>10} {'Low Peak%':>10} {'Low Day':>8} {'High Peak%':>11} {'High Day':>9}")
    print("-" * 70)
    for i in range(min(10, n_cities)):
        name = ng_cities[i]["city"]
        pop = int(ng_cities[i]["population"])
        print(f"{name:<20} {pop:>10,} {peaks_low[i]:>10.1f} {int(days_low[i]):>8} "
              f"{peaks_high[i]:>11.1f} {int(days_high[i]):>9}")

    # Reduction stats
    mean_reduction = (peaks_low.mean() - peaks_high.mean()) / peaks_low.mean() * 100
    print(f"\n  Mean peak reduction: {mean_reduction:.1f}% "
          f"(from {peaks_low.mean():.1f}% to {peaks_high.mean():.1f}%)")

    # ── Geographic network visualization ──────────────────────────────
    print("\nGenerating geographic network figure...")

    lons = np.array([float(c["longitude"]) for c in ng_cities])
    lats = np.array([float(c["latitude"]) for c in ng_cities])
    pops = np.array([int(c["population"]) for c in ng_cities])
    names = [c["city"] for c in ng_cities]

    # Node sizes proportional to population (sqrt scale for area)
    size_scale = np.sqrt(pops / pops.min()) * 30
    size_scale = np.clip(size_scale, 20, 300)

    # Determine edges to draw: top connections per city (by travel rate)
    edges = set()
    for i in range(n_cities):
        rates = [(travel_des[i, j], j) for j in range(n_cities) if i != j]
        rates.sort(reverse=True)
        for rate, j in rates[:3]:
            edge = (min(i, j), max(i, j))
            edges.add((edge[0], edge[1], travel_des[edge[0], edge[1]]))

    max_rate = max(r for _, _, r in edges) if edges else 1.0

    # Color map for peak infection — shared scale across both panels
    vmin = 0
    vmax = max(peaks_low.max(), peaks_high.max(), 1)
    cmap = plt.cm.YlOrRd

    fig, axes = plt.subplots(1, 2, figsize=(20, 12))
    fig.suptitle(
        "Fig 4: Nigeria 51-City — Provider Density: "
        f"{PROVIDER_DENSITY_LOW:.0f}/1000 vs {PROVIDER_DENSITY_HIGH:.0f}/1000\n"
        f"COVID-like (R0={SCENARIO.R0}), N={NIGERIA_N_PEOPLE:,}/city, "
        f"{NIGERIA_N_MC_RUNS} MC runs, seed={NIGERIA_SEED_CITY}, "
        f"receptivity={receptivity:.2f} (from score={score:.0f})",
        fontsize=13, fontweight="bold",
    )

    for ax_idx, (ax, peaks, peak_days, density, scenario_label) in enumerate([
        (axes[0], peaks_low, days_low, PROVIDER_DENSITY_LOW,
         f"Low Density ({PROVIDER_DENSITY_LOW:.0f}/1000 = {n_prov_low} providers)"),
        (axes[1], peaks_high, days_high, PROVIDER_DENSITY_HIGH,
         f"High Density ({PROVIDER_DENSITY_HIGH:.0f}/1000 = {n_prov_high} providers)"),
    ]):
        n_prov = max(0, int(density * NIGERIA_N_PEOPLE / 1000))
        ax.set_title(
            f"{scenario_label}\n"
            f"screens/day: {n_prov * SCREENING_CAPACITY}",
            fontsize=11,
        )

        # Draw edges
        for i, j, rate in edges:
            linewidth = 0.3 + 2.0 * (rate / max_rate)
            alpha = 0.15 + 0.35 * (rate / max_rate)
            ax.plot(
                [lons[i], lons[j]], [lats[i], lats[j]],
                color="#888888", linewidth=linewidth, alpha=alpha,
                zorder=1,
            )

        # Draw nodes
        norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
        ax.scatter(
            lons, lats, s=size_scale, c=peaks, cmap=cmap,
            norm=norm, edgecolors="black", linewidths=0.5,
            zorder=2,
        )

        # Label major cities (top 8 by population)
        for i in range(min(8, n_cities)):
            ax.annotate(
                names[i],
                (lons[i], lats[i]),
                textcoords="offset points",
                xytext=(5, 5),
                fontsize=7,
                fontweight="bold",
                zorder=3,
            )

        # Mark seed city
        seed_idx = names.index(NIGERIA_SEED_CITY)
        ax.scatter(
            [lons[seed_idx]], [lats[seed_idx]],
            s=size_scale[seed_idx] * 1.5,
            facecolors="none", edgecolors="blue",
            linewidths=2, zorder=3,
        )
        ax.annotate(
            f"{NIGERIA_SEED_CITY}\n(seed)",
            (lons[seed_idx], lats[seed_idx]),
            textcoords="offset points",
            xytext=(-15, -15),
            fontsize=8, fontweight="bold", color="blue",
            zorder=3,
        )

        # Axes
        ax.set_xlabel("Longitude", fontsize=10)
        ax.set_ylabel("Latitude", fontsize=10)
        ax.set_aspect("equal")
        lon_pad = (lons.max() - lons.min()) * 0.08
        lat_pad = (lats.max() - lats.min()) * 0.08
        ax.set_xlim(lons.min() - lon_pad, lons.max() + lon_pad)
        ax.set_ylim(lats.min() - lat_pad, lats.max() + lat_pad)
        ax.grid(True, alpha=0.2)

        # Stats annotation
        mean_peak = peaks.mean()
        max_peak_city = names[np.argmax(peaks)]
        max_peak_val = peaks.max()
        ax.text(
            0.02, 0.02,
            f"Mean peak: {mean_peak:.1f}%\n"
            f"Max peak: {max_peak_val:.1f}% ({max_peak_city})\n"
            f"Avg peak day: {peak_days.mean():.0f}",
            transform=ax.transAxes,
            fontsize=9, verticalalignment="bottom",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
        )

    # Shared colorbar
    cbar = fig.colorbar(
        plt.cm.ScalarMappable(norm=mcolors.Normalize(vmin=vmin, vmax=vmax), cmap=cmap),
        ax=axes, orientation="horizontal", fraction=0.04, pad=0.08,
    )
    cbar.set_label("Peak Infection (% of city population)", fontsize=11)

    fname = RESULTS_DIR / "04_nigeria_provider_density.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {fname.name}")


def figure_05():
    """Fig 5: Nigeria spatial map — no providers vs 1/1000 vs 5/1000.

    Three-panel map with Nigeria country boundary, city network, and
    outcome table including estimated deaths.
    """
    import geopandas as gpd
    from matplotlib.gridspec import GridSpec

    # Infection fatality rate for COVID-like scenario
    IFR = 0.005  # 0.5% IFR (reasonable COVID-like estimate for Nigeria demographics)

    print(f"\n{'='*70}")
    print("FIGURE 5: Nigeria 51-city — Spatial Map with Outcomes")
    print(f"{'='*70}")

    ng_cities = _load_nigerian_cities()
    n_cities = len(ng_cities)
    print(f"\nLoaded {n_cities} Nigerian cities")

    # Load Nigeria boundary
    boundary_path = Path(__file__).parent / "nigeria_boundary.geojson"
    nigeria_gdf = gpd.read_file(boundary_path)
    print(f"  Loaded Nigeria boundary")

    # Build gravity matrix
    class _City:
        def __init__(self, d):
            self.name = d["city"]
            self.population = int(d["population"])
            self.latitude = float(d["latitude"])
            self.longitude = float(d["longitude"])
            self.medical_services_score = float(d.get("medical_services_score", 0))

    city_objs = [_City(c) for c in ng_cities]
    travel_des = compute_des_scale_travel_matrix(
        city_objs, NIGERIA_N_PEOPLE,
        alpha=GRAVITY_ALPHA, scale=NIGERIA_GRAVITY_SCALE,
    )

    # Three scenarios
    fig5_mc_runs = 5
    densities = [0.0, PROVIDER_DENSITY_LOW, PROVIDER_DENSITY_HIGH]
    labels = ["No Providers", "Low", "High"]
    all_peaks = []
    all_days = []
    all_attack_rates = []

    for density, label in zip(densities, labels):
        n_prov = max(0, int(density * NIGERIA_N_PEOPLE / 1000))
        print(f"\n--- {label} ({density:.0f}/1000 = {n_prov} providers) ---")
        peaks, days, attack_rates = _run_nigeria_provider_scenario(
            ng_cities, travel_des, density, label,
            n_runs_override=fig5_mc_runs,
        )
        all_peaks.append(peaks)
        all_days.append(days)
        all_attack_rates.append(attack_rates)

    # Compute deaths: attack_rate * real_population * IFR
    real_pops = np.array([int(c["population"]) for c in ng_cities])
    total_real_pop = real_pops.sum()
    deaths_by_scenario = []
    infections_by_scenario = []
    for attack_rates in all_attack_rates:
        total_infections = (attack_rates * real_pops).sum()
        total_deaths = total_infections * IFR
        infections_by_scenario.append(total_infections)
        deaths_by_scenario.append(total_deaths)

    # Summary table
    print("\n" + "=" * 90)
    print("FIGURE 5 — OUTCOME SUMMARY")
    print("=" * 90)
    print(f"  Total population across 51 cities: {total_real_pop:,.0f}")
    print(f"  Infection fatality rate (IFR): {IFR*100:.1f}%")
    print()
    print(f"  {'Scenario':<25} {'Mean Peak%':>10} {'Attack Rate':>12} "
          f"{'Infections':>14} {'Deaths':>12}")
    print("  " + "-" * 75)
    for i, (density, label) in enumerate(zip(densities, labels)):
        n_prov = max(0, int(density * NIGERIA_N_PEOPLE / 1000))
        scenario_name = f"{label} ({density:.0f}/1000)"
        mean_peak = all_peaks[i].mean()
        mean_attack = (all_attack_rates[i] * real_pops).sum() / total_real_pop * 100
        print(f"  {scenario_name:<25} {mean_peak:>9.1f}% {mean_attack:>11.1f}% "
              f"{infections_by_scenario[i]:>13,.0f} {deaths_by_scenario[i]:>11,.0f}")

    reduction_low_to_high = (deaths_by_scenario[0] - deaths_by_scenario[2])
    print(f"\n  Lives saved (no providers -> 5/1000): {reduction_low_to_high:,.0f}")

    # ── Figure layout: 3 map panels + outcome table ───────────────────
    print("\nGenerating spatial figure with country boundary...")

    lons = np.array([float(c["longitude"]) for c in ng_cities])
    lats = np.array([float(c["latitude"]) for c in ng_cities])
    pops = real_pops.astype(float)
    names = [c["city"] for c in ng_cities]

    size_scale = np.sqrt(pops / pops.min()) * 25
    size_scale = np.clip(size_scale, 15, 250)

    # Edges (top 3 connections per city)
    edges = set()
    for i in range(n_cities):
        rates = [(travel_des[i, j], j) for j in range(n_cities) if i != j]
        rates.sort(reverse=True)
        for rate, j in rates[:3]:
            edge = (min(i, j), max(i, j))
            edges.add((edge[0], edge[1], travel_des[edge[0], edge[1]]))
    max_rate = max(r for _, _, r in edges) if edges else 1.0

    # Shared color scale
    vmin = 0
    vmax = max(p.max() for p in all_peaks)
    vmax = max(vmax, 1)
    cmap = plt.cm.YlOrRd

    score = float(ng_cities[0].get("medical_services_score", 0))
    receptivity = _score_to_receptivity(score)
    half_life = math.log(2) / ADVICE_DECAY_PROB if ADVICE_DECAY_PROB > 0 else float('inf')

    # Layout: 3 map panels on top, outcome table below
    fig = plt.figure(figsize=(24, 14))
    gs = GridSpec(2, 3, figure=fig, height_ratios=[3, 1], hspace=0.25, wspace=0.15)
    map_axes = [fig.add_subplot(gs[0, i]) for i in range(3)]
    table_ax = fig.add_subplot(gs[1, :])

    fig.suptitle(
        "Fig 5: Nigeria 51-City — Healthcare Provider Impact on Epidemic Outcomes\n"
        f"COVID-like (R0={SCENARIO.R0}), N={NIGERIA_N_PEOPLE:,}/city, "
        f"{fig5_mc_runs} MC runs, seed={NIGERIA_SEED_CITY}, "
        f"receptivity={receptivity:.2f}, advice decay half-life={half_life:.0f}d, "
        f"IFR={IFR*100:.1f}%",
        fontsize=13, fontweight="bold", y=0.98,
    )

    n_prov_low = max(0, int(PROVIDER_DENSITY_LOW * NIGERIA_N_PEOPLE / 1000))
    n_prov_high = max(0, int(PROVIDER_DENSITY_HIGH * NIGERIA_N_PEOPLE / 1000))
    panel_titles = [
        "No Providers (0/1000)\nBaseline — no screening",
        f"Low Density ({PROVIDER_DENSITY_LOW:.0f}/1000 = {n_prov_low} providers)\n"
        f"{n_prov_low * SCREENING_CAPACITY} screens/day per city",
        f"High Density ({PROVIDER_DENSITY_HIGH:.0f}/1000 = {n_prov_high} providers)\n"
        f"{n_prov_high * SCREENING_CAPACITY} screens/day per city",
    ]

    # Draw the three map panels
    for ax_idx, (ax, peaks, peak_days) in enumerate(
        zip(map_axes, all_peaks, all_days)
    ):
        ax.set_title(panel_titles[ax_idx], fontsize=10)

        # Draw Nigeria boundary
        nigeria_gdf.boundary.plot(ax=ax, color="#333333", linewidth=1.5, zorder=0)
        nigeria_gdf.plot(ax=ax, color="#f0ede4", edgecolor="#333333",
                         linewidth=1.5, zorder=0)

        # Draw travel network edges
        for i, j, rate in edges:
            linewidth = 0.3 + 1.5 * (rate / max_rate)
            alpha = 0.12 + 0.25 * (rate / max_rate)
            ax.plot(
                [lons[i], lons[j]], [lats[i], lats[j]],
                color="#666666", linewidth=linewidth, alpha=alpha, zorder=1,
            )

        # Draw city nodes
        norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
        ax.scatter(
            lons, lats, s=size_scale, c=peaks, cmap=cmap,
            norm=norm, edgecolors="black", linewidths=0.5, zorder=2,
        )

        # Label major cities (top 8 by population)
        for i in range(min(8, n_cities)):
            ax.annotate(
                names[i], (lons[i], lats[i]),
                textcoords="offset points", xytext=(5, 5),
                fontsize=6, fontweight="bold", zorder=3,
                bbox=dict(boxstyle="round,pad=0.1", facecolor="white",
                          alpha=0.6, edgecolor="none"),
            )

        # Mark seed city
        seed_idx = names.index(NIGERIA_SEED_CITY)
        ax.scatter(
            [lons[seed_idx]], [lats[seed_idx]],
            s=size_scale[seed_idx] * 1.5,
            facecolors="none", edgecolors="blue", linewidths=2, zorder=3,
        )
        ax.annotate(
            f"{NIGERIA_SEED_CITY}\n(seed)",
            (lons[seed_idx], lats[seed_idx]),
            textcoords="offset points", xytext=(-15, -15),
            fontsize=7, fontweight="bold", color="blue", zorder=3,
        )

        # Set extent to Nigeria boundary with padding
        bounds = nigeria_gdf.total_bounds  # [minx, miny, maxx, maxy]
        pad = 0.5
        ax.set_xlim(bounds[0] - pad, bounds[2] + pad)
        ax.set_ylim(bounds[1] - pad, bounds[3] + pad)
        ax.set_aspect("equal")

        ax.set_xlabel("Longitude", fontsize=9)
        if ax_idx == 0:
            ax.set_ylabel("Latitude", fontsize=9)
        ax.tick_params(labelsize=7)

        # Stats box
        mean_peak = peaks.mean()
        max_peak_city = names[np.argmax(peaks)]
        max_peak_val = peaks.max()
        ax.text(
            0.02, 0.02,
            f"Mean peak: {mean_peak:.1f}%\n"
            f"Max: {max_peak_val:.1f}% ({max_peak_city})\n"
            f"Avg peak day: {peak_days.mean():.0f}",
            transform=ax.transAxes, fontsize=8, verticalalignment="bottom",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.85),
        )

    # Shared colorbar between maps and table
    cbar = fig.colorbar(
        plt.cm.ScalarMappable(norm=mcolors.Normalize(vmin=vmin, vmax=vmax), cmap=cmap),
        ax=map_axes, orientation="horizontal", fraction=0.035, pad=0.06,
        aspect=50,
    )
    cbar.set_label("Peak Infection (% of city population)", fontsize=10)

    # ── Outcome table ─────────────────────────────────────────────────
    table_ax.axis("off")

    # Build table data
    col_labels = [
        "Scenario", "Providers\nper city", "Daily\nscreens",
        "Mean\npeak %", "Attack\nrate %", "Total\ninfections",
        "Estimated\ndeaths", "Lives saved\nvs baseline",
    ]
    table_data = []
    for i, (density, label) in enumerate(zip(densities, labels)):
        n_prov = max(0, int(density * NIGERIA_N_PEOPLE / 1000))
        mean_attack = (all_attack_rates[i] * real_pops).sum() / total_real_pop * 100
        lives_saved = deaths_by_scenario[0] - deaths_by_scenario[i]
        table_data.append([
            f"{label} ({density:.0f}/1000)",
            f"{n_prov}",
            f"{n_prov * SCREENING_CAPACITY:,}",
            f"{all_peaks[i].mean():.1f}%",
            f"{mean_attack:.1f}%",
            f"{infections_by_scenario[i]:,.0f}",
            f"{deaths_by_scenario[i]:,.0f}",
            f"{lives_saved:+,.0f}" if i > 0 else "—",
        ])

    table = table_ax.table(
        cellText=table_data,
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.0, 1.8)

    # Style header row
    for j in range(len(col_labels)):
        cell = table[0, j]
        cell.set_facecolor("#2c3e50")
        cell.set_text_props(color="white", fontweight="bold")

    # Color-code rows by severity
    row_colors = ["#f8d7da", "#fff3cd", "#d4edda"]  # red-ish, yellow-ish, green-ish
    for i in range(len(table_data)):
        for j in range(len(col_labels)):
            table[i + 1, j].set_facecolor(row_colors[i])

    table_ax.set_title(
        f"Outcome Summary — Total population: {total_real_pop:,.0f} "
        f"(51 cities) | IFR: {IFR*100:.1f}%",
        fontsize=11, fontweight="bold", pad=10,
    )

    fname = RESULTS_DIR / "05_nigeria_provider_three_conditions.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {fname.name}")


# ── Main ─────────────────────────────────────────────────────────────

def main():
    ensure_results_dir()

    print("Loading cities...")
    cities = load_cities(DEMO_CITIES)
    for c in cities:
        print(f"  {c.name} ({c.country}): pop={c.population:,}, score={c.medical_services_score:.0f}")

    print("\nComputing real-population travel matrix...")
    travel_matrix_real = compute_travel_matrix(
        cities, alpha=GRAVITY_ALPHA, scale=GRAVITY_SCALE,
    )

    ode_initial = max(1, int(SEED_FRACTION * cities[DEMO_CITIES.index(SEED_CITY)].population))
    print(f"\nSeed fraction: {SEED_FRACTION:.1%}")
    print(f"  ODE: {ode_initial:,} initial infected in {SEED_CITY}")

    # Run all figures
    figure_01(cities, travel_matrix_real)
    figure_02(cities, travel_matrix_real)
    figure_03(cities, travel_matrix_real)
    figure_04()
    figure_05()

    print("\nAll done.")


if __name__ == "__main__":
    main()
