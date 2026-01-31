"""
Provider Coverage Sweep — Engineered Ebola Bioattack on Nigeria.

Sweeps healthcare provider density from 0 to 200/1000 to find the
minimal coverage that meaningfully reduces harm. Produces 3 figures:
    01 — Deaths vs provider density (dose-response curve)
    02 — Epidemic characteristics vs provider density
    03 — City-level heatmap of peak infection by density

Usage:
    cd 007_coverage_sweep && python coverage_sweep.py
"""

import csv
import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "des_system"))
sys.path.insert(0, str(_PROJECT_ROOT / "004_multicity"))
sys.path.insert(0, str(_PROJECT_ROOT / "005_multicity_des"))

from validation_config import EBOLA_BIOATTACK
from gravity_model import compute_distance_matrix
from multicity_des_sim import run_multicity_des_simulation

# ── Constants ────────────────────────────────────────────────────────

COUNTRY = "Nigeria"
SCENARIO = EBOLA_BIOATTACK  # R0=2.5, incubation=8d, infectious=10d
IFR = 0.50
SEED_CITIES = ["Lagos", "Kano", "Ibadan", "Abuja", "Kaduna"]

N_PEOPLE = 5_000
DAYS = 400
N_MC_RUNS = 3
BASE_SEED = 42

GRAVITY_SCALE = 0.01
GRAVITY_ALPHA = 2.0
TRANSMISSION_FACTOR = 0.3
SEED_FRACTION = 0.001

# Behavioral parameters (from module 003)
SCREENING_CAPACITY = 20
DISCLOSURE_PROB = 0.5
BASE_ISOLATION_PROB = 0.05
ADVISED_ISOLATION_PROB = 0.40
ADVICE_DECAY_PROB = 0.05

# Provider densities to sweep (per 1000 population)
PROVIDER_DENSITIES = [0, 1, 2, 5, 10, 15, 20, 30, 40, 50, 75, 100, 150, 200]

RESULTS_DIR = Path(__file__).parent / "results"


# ── City helper ──────────────────────────────────────────────────────

class _City:
    def __init__(self, row: dict):
        self.name = row["city"]
        self.population = int(row["population"])
        self.latitude = float(row["latitude"])
        self.longitude = float(row["longitude"])
        self.medical_services_score = float(row.get("medical_services_score", 0))


def _load_nigerian_cities() -> list[dict]:
    csv_path = _PROJECT_ROOT / "backend" / "data" / "african_cities.csv"
    cities = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["country"] == COUNTRY:
                cities.append(row)
    cities.sort(key=lambda x: int(x["population"]), reverse=True)
    return cities


def _score_to_receptivity(score: float) -> float:
    return 0.2 + 0.6 * (score / 100.0)


# ── DES-scale travel matrix ─────────────────────────────────────────

def _compute_des_travel_matrix(city_objs: list[_City]) -> np.ndarray:
    dist = compute_distance_matrix(city_objs)
    n = len(city_objs)
    travel = np.zeros((n, n))
    pop_product = N_PEOPLE * N_PEOPLE

    for i in range(n):
        for j in range(i + 1, n):
            if dist[i, j] > 0:
                rate = GRAVITY_SCALE * pop_product / (dist[i, j] ** GRAVITY_ALPHA)
                travel[i, j] = rate
                travel[j, i] = rate

    return travel


# ── Sweep runner ─────────────────────────────────────────────────────

def _run_sweep_point(
    cities: list[dict],
    travel_matrix: np.ndarray,
    provider_density: float,
) -> dict:
    """Run one density level (3 MC runs), return aggregated metrics."""
    n_cities = len(cities)

    slug = f"sweep_{provider_density:.0f}"
    npz_path = RESULTS_DIR / f"{slug}.npz"

    if npz_path.exists():
        print(f"  Loading cached {npz_path.name}")
        data = np.load(npz_path)
        return {
            "density": provider_density,
            "peak_pcts": data["peak_pcts"],
            "peak_days": data["peak_days"],
            "attack_rates": data["attack_rates"],
        }

    city_names = [c["city"] for c in cities]
    city_pops = [int(c["population"]) for c in cities]
    city_coords = [(float(c["latitude"]), float(c["longitude"])) for c in cities]

    seed_indices = [city_names.index(s) for s in SEED_CITIES if s in city_names]
    per_city_receptivity = [
        _score_to_receptivity(float(c.get("medical_services_score", 0)))
        for c in cities
    ]
    des_initial = max(1, int(SEED_FRACTION * N_PEOPLE))

    all_I = np.zeros((N_MC_RUNS, n_cities, DAYS + 1))
    all_R_final = np.zeros((N_MC_RUNS, n_cities))

    for run in range(N_MC_RUNS):
        t0 = time.time()
        result = run_multicity_des_simulation(
            city_names=city_names,
            city_populations=city_pops,
            city_coords=city_coords,
            scenario=SCENARIO,
            travel_matrix=travel_matrix,
            days=DAYS,
            n_people=N_PEOPLE,
            transmission_factor=TRANSMISSION_FACTOR,
            seed_city_index=seed_indices,
            initial_infected=des_initial,
            random_seed=BASE_SEED + run * 100,
            des_scale_travel=True,
            isolation_effect=0.0,
            provider_density=provider_density,
            screening_capacity=SCREENING_CAPACITY,
            disclosure_prob=DISCLOSURE_PROB,
            receptivity=0.6,
            base_isolation_prob=BASE_ISOLATION_PROB,
            advised_isolation_prob=ADVISED_ISOLATION_PROB,
            advice_decay_prob=ADVICE_DECAY_PROB,
            per_city_receptivity=per_city_receptivity,
        )
        elapsed = time.time() - t0

        for i in range(n_cities):
            all_I[run, i, :] = result.I[i] / N_PEOPLE
            all_R_final[run, i] = result.R[i, -1] / N_PEOPLE

        print(f"    run {run + 1}/{N_MC_RUNS} [{elapsed:.0f}s]")

    peak_pcts = np.zeros(n_cities)
    peak_days = np.zeros(n_cities)
    attack_rates = np.zeros(n_cities)
    for i in range(n_cities):
        mean_frac = all_I[:, i, :].mean(axis=0)
        peak_pcts[i] = mean_frac.max() * 100
        peak_days[i] = np.argmax(mean_frac)
        attack_rates[i] = all_R_final[:, i].mean()

    np.savez_compressed(npz_path, peak_pcts=peak_pcts, peak_days=peak_days,
                        attack_rates=attack_rates)
    print(f"    saved {npz_path.name}")

    return {
        "density": provider_density,
        "peak_pcts": peak_pcts,
        "peak_days": peak_days,
        "attack_rates": attack_rates,
    }


# ── Figure 1: Deaths vs Provider Density ─────────────────────────────

def _generate_fig1(sweep_results: list[dict], real_pops: np.ndarray):
    densities = [r["density"] for r in sweep_results]
    deaths = []
    for r in sweep_results:
        infections = (r["attack_rates"] * real_pops).sum()
        deaths.append(infections * IFR)
    deaths = np.array(deaths)

    baseline_deaths = deaths[0]
    lives_saved = baseline_deaths - deaths

    fig, ax1 = plt.subplots(figsize=(12, 7))

    color_deaths = "#c0392b"
    color_saved = "#27ae60"

    ax1.plot(densities, deaths / 1e6, "o-", color=color_deaths, linewidth=2.5,
             markersize=8, label="Estimated deaths", zorder=3)
    ax1.set_xlabel("Healthcare Provider Density (per 1,000 population)", fontsize=12)
    ax1.set_ylabel("Estimated Deaths (millions)", fontsize=12, color=color_deaths)
    ax1.tick_params(axis="y", labelcolor=color_deaths)
    ax1.set_xscale("symlog", linthresh=1)
    ax1.set_xlim(-0.5, max(densities) * 1.1)
    ax1.grid(True, alpha=0.3)

    ax2 = ax1.twinx()
    ax2.fill_between(densities, 0, lives_saved / 1e6, alpha=0.15, color=color_saved)
    ax2.plot(densities, lives_saved / 1e6, "s--", color=color_saved, linewidth=1.5,
             markersize=6, label="Lives saved vs baseline", zorder=2)
    ax2.set_ylabel("Lives Saved vs No Providers (millions)", fontsize=12,
                    color=color_saved)
    ax2.tick_params(axis="y", labelcolor=color_saved)

    # Find the knee: where marginal reduction per unit density drops
    # Use the point where doubling density yields < 10% additional reduction
    knee_idx = None
    for i in range(1, len(deaths) - 1):
        if densities[i] == 0:
            continue
        reduction_here = (deaths[i - 1] - deaths[i]) / deaths[0] * 100
        reduction_next = (deaths[i] - deaths[i + 1]) / deaths[0] * 100
        if reduction_next < reduction_here * 0.3 and reduction_here > 1:
            knee_idx = i
            break

    if knee_idx is not None:
        kd = densities[knee_idx]
        kdeaths = deaths[knee_idx] / 1e6
        n_prov = int(kd * N_PEOPLE / 1000)
        ax1.axvline(kd, color="#7f8c8d", linestyle=":", linewidth=1.5, alpha=0.7)
        ax1.annotate(
            f"Diminishing returns\n≈ {kd:.0f}/1000 ({n_prov} providers/city)\n"
            f"{kdeaths:.1f}M deaths",
            xy=(kd, kdeaths), xytext=(kd * 1.8, kdeaths * 1.15),
            fontsize=10, fontweight="bold",
            arrowprops=dict(arrowstyle="->", color="#7f8c8d"),
            bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow",
                      edgecolor="#7f8c8d"),
        )

    # Add data labels for key points
    for i in [0, len(deaths) - 1]:
        ax1.annotate(
            f"{deaths[i]/1e6:.1f}M",
            xy=(densities[i], deaths[i] / 1e6),
            textcoords="offset points", xytext=(10, 10), fontsize=9,
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.8),
        )

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="center right", fontsize=10)

    fig.suptitle(
        f"Fig 1: Deaths vs Provider Density — Engineered Ebola on Nigeria\n"
        f"{SCENARIO.name} (R₀={SCENARIO.R0}), IFR={IFR*100:.0f}%, "
        f"{len(SEED_CITIES)} seed cities, N={N_PEOPLE:,}/city, {N_MC_RUNS} MC runs",
        fontsize=13, fontweight="bold",
    )

    fname = RESULTS_DIR / "01_deaths_vs_density.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {fname.name}")


# ── Figure 2: Epidemic Characteristics ────────────────────────────────

def _generate_fig2(sweep_results: list[dict], real_pops: np.ndarray):
    densities = [r["density"] for r in sweep_results]
    mean_peaks = [r["peak_pcts"].mean() for r in sweep_results]
    mean_peak_days = [r["peak_days"].mean() for r in sweep_results]
    pct_heavily_affected = [
        (r["peak_pcts"] > 5).sum() / len(r["peak_pcts"]) * 100
        for r in sweep_results
    ]

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    ax1, ax2, ax3 = axes

    ax1.plot(densities, mean_peaks, "o-", color="#2980b9", linewidth=2, markersize=7)
    ax1.set_xlabel("Provider Density (per 1,000)", fontsize=11)
    ax1.set_ylabel("Mean Peak Infection (%)", fontsize=11)
    ax1.set_title("(a) Peak Infection vs Coverage", fontsize=12, fontweight="bold")
    ax1.set_xscale("symlog", linthresh=1)
    ax1.grid(True, alpha=0.3)
    for i in [0, len(mean_peaks) - 1]:
        ax1.annotate(f"{mean_peaks[i]:.1f}%", xy=(densities[i], mean_peaks[i]),
                     textcoords="offset points", xytext=(8, 8), fontsize=9)

    ax2.plot(densities, mean_peak_days, "s-", color="#8e44ad", linewidth=2, markersize=7)
    ax2.set_xlabel("Provider Density (per 1,000)", fontsize=11)
    ax2.set_ylabel("Mean Peak Day", fontsize=11)
    ax2.set_title("(b) Peak Timing vs Coverage", fontsize=12, fontweight="bold")
    ax2.set_xscale("symlog", linthresh=1)
    ax2.grid(True, alpha=0.3)
    for i in [0, len(mean_peak_days) - 1]:
        ax2.annotate(f"day {mean_peak_days[i]:.0f}",
                     xy=(densities[i], mean_peak_days[i]),
                     textcoords="offset points", xytext=(8, 8), fontsize=9)

    ax3.plot(densities, pct_heavily_affected, "D-", color="#e67e22", linewidth=2,
             markersize=7)
    ax3.set_xlabel("Provider Density (per 1,000)", fontsize=11)
    ax3.set_ylabel("Cities with > 5% Peak (%)", fontsize=11)
    ax3.set_title("(c) Heavily Affected Cities", fontsize=12, fontweight="bold")
    ax3.set_xscale("symlog", linthresh=1)
    ax3.grid(True, alpha=0.3)
    ax3.set_ylim(-2, 105)
    for i in [0, len(pct_heavily_affected) - 1]:
        ax3.annotate(f"{pct_heavily_affected[i]:.0f}%",
                     xy=(densities[i], pct_heavily_affected[i]),
                     textcoords="offset points", xytext=(8, 8), fontsize=9)

    fig.suptitle(
        f"Fig 2: Epidemic Characteristics vs Provider Density — "
        f"Engineered Ebola on Nigeria",
        fontsize=13, fontweight="bold", y=1.02,
    )
    fig.tight_layout()

    fname = RESULTS_DIR / "02_epidemic_characteristics.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {fname.name}")


# ── Figure 3: City-level heatmap ─────────────────────────────────────

def _generate_fig3(sweep_results: list[dict], cities: list[dict]):
    densities = [r["density"] for r in sweep_results]
    n_cities = len(cities)
    names = [c["city"] for c in cities]

    # Build matrix: cities × densities
    matrix = np.zeros((n_cities, len(densities)))
    for j, r in enumerate(sweep_results):
        matrix[:, j] = r["peak_pcts"]

    fig, ax = plt.subplots(figsize=(16, 14))

    vmax = max(matrix.max(), 1)
    im = ax.imshow(matrix, aspect="auto", cmap="YlOrRd", vmin=0, vmax=vmax,
                   interpolation="nearest")

    ax.set_xticks(range(len(densities)))
    ax.set_xticklabels([f"{d:.0f}" for d in densities], fontsize=9)
    ax.set_xlabel("Provider Density (per 1,000 population)", fontsize=12)

    ax.set_yticks(range(n_cities))
    ax.set_yticklabels(names, fontsize=7)
    ax.set_ylabel("City (sorted by population, largest at top)", fontsize=12)

    cbar = fig.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
    cbar.set_label("Peak Infection (% of city population)", fontsize=11)

    fig.suptitle(
        f"Fig 3: Peak Infection by City and Provider Density — "
        f"Engineered Ebola on Nigeria\n"
        f"{n_cities} cities, {SCENARIO.name} (R₀={SCENARIO.R0}), "
        f"IFR={IFR*100:.0f}%, {N_MC_RUNS} MC runs",
        fontsize=13, fontweight="bold",
    )

    fname = RESULTS_DIR / "03_city_heatmap.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {fname.name}")


# ── Main ─────────────────────────────────────────────────────────────

def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Provider Coverage Sweep — Engineered Ebola on Nigeria")
    print("=" * 70)

    print("\nLoading Nigerian cities...")
    raw_cities = _load_nigerian_cities()
    n_cities = len(raw_cities)
    print(f"  Loaded {n_cities} cities")
    for c in raw_cities[:5]:
        print(f"    {c['city']}: pop={int(c['population']):,}")

    city_objs = [_City(c) for c in raw_cities]

    print(f"\nComputing DES-scale gravity matrix for {n_cities} cities...")
    travel_matrix = _compute_des_travel_matrix(city_objs)
    print("  Done")

    real_pops = np.array([int(c["population"]) for c in raw_cities], dtype=float)
    total_pop = real_pops.sum()
    print(f"  Total Nigerian urban population: {total_pop:,.0f}")

    print(f"\n{'='*70}")
    print(f"Sweeping {len(PROVIDER_DENSITIES)} provider density levels")
    print(f"  Scenario: {SCENARIO.name} (R₀={SCENARIO.R0}), IFR={IFR*100:.0f}%")
    print(f"  Seeds: {SEED_CITIES}")
    print(f"  N={N_PEOPLE:,}/city, {DAYS} days, {N_MC_RUNS} MC runs each")
    print(f"  Densities: {PROVIDER_DENSITIES}")
    print(f"{'='*70}")

    sweep_results = []
    t_total = time.time()

    for density in PROVIDER_DENSITIES:
        n_prov = int(density * N_PEOPLE / 1000)
        daily_screens = n_prov * SCREENING_CAPACITY
        print(f"\n  Density {density}/1000 ({n_prov} providers, "
              f"{daily_screens} screens/day per city)")
        result = _run_sweep_point(raw_cities, travel_matrix, density)
        sweep_results.append(result)

        infections = (result["attack_rates"] * real_pops).sum()
        deaths = infections * IFR
        print(f"    Mean peak: {result['peak_pcts'].mean():.1f}%, "
              f"Deaths: {deaths:,.0f}")

    elapsed_total = time.time() - t_total
    print(f"\nAll sweep points completed in {elapsed_total:.0f}s")

    # Generate figures
    print("\nGenerating figures...")
    _generate_fig1(sweep_results, real_pops)
    _generate_fig2(sweep_results, real_pops)
    _generate_fig3(sweep_results, raw_cities)

    # Print summary table
    print(f"\n{'='*90}")
    print("SWEEP SUMMARY")
    print("=" * 90)
    print(f"{'Density':>8} {'Providers':>10} {'Screens/d':>10} "
          f"{'Mean Peak%':>11} {'Infections':>14} {'Deaths':>12} {'Lives Saved':>13}")
    print("-" * 80)

    baseline_deaths = None
    for r in sweep_results:
        density = r["density"]
        n_prov = int(density * N_PEOPLE / 1000)
        daily_screens = n_prov * SCREENING_CAPACITY
        infections = (r["attack_rates"] * real_pops).sum()
        deaths = infections * IFR

        if baseline_deaths is None:
            baseline_deaths = deaths
            saved_str = "---"
        else:
            saved = baseline_deaths - deaths
            saved_str = f"{saved:+,.0f}"

        print(f"{density:>7.0f} {n_prov:>10} {daily_screens:>10,} "
              f"{r['peak_pcts'].mean():>10.1f}% "
              f"{infections:>13,.0f} {deaths:>11,.0f} {saved_str:>13}")

    print(f"\n{'='*90}")
    print("Done.")


if __name__ == "__main__":
    main()
