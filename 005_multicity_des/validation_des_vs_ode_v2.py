#!/usr/bin/env python3
"""
Nigeria Country-Scale Validation (v2 — Production Backend).

Re-validates 005 using run_absdes_simulation() from the production backend.

Runs all 51 Nigerian cities with the production DES engine and validates:
1. Deaths in COVID-like natural scenario should be in the 1-2K range
   for the first ~100 days (consistent with Nigeria's pandemic experience)
2. Provider intervention reduces deaths
3. Multiple runs show consistent results

Outputs saved to 005_multicity_des/results_v2/ directory.

Usage (from project root):
    python 005_multicity_des/validation_des_vs_ode_v2.py
"""

import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
_BACKEND_DIR = str(_PROJECT_ROOT / "simulation_app" / "backend")
_DES_SYSTEM_DIR = str(_PROJECT_ROOT / "des_system")

if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
if _DES_SYSTEM_DIR not in sys.path:
    sys.path.insert(1, _DES_SYSTEM_DIR)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import seaborn as sns

from simulation import SimulationParams, run_absdes_simulation, DualViewResult, load_cities

# ── Configuration ─────────────────────────────────────────────────
sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)
RESULTS_DIR = _SCRIPT_DIR / "results_v2"

COUNTRY = "Nigeria"
SCENARIO = "covid_natural"
N_PEOPLE = 5000
DAYS = 200
N_RUNS = 3


def ensure_results_dir():
    RESULTS_DIR.mkdir(exist_ok=True)


def run_nigeria(scenario="covid_natural", provider_density=5.0, seed=42):
    """Run Nigeria simulation with production backend."""
    params = SimulationParams(
        country=COUNTRY,
        scenario=scenario,
        n_people=N_PEOPLE,
        days=DAYS,
        random_seed=seed,
        provider_density=provider_density,
        seed_fraction=0.005,
    )
    return run_absdes_simulation(params)


def estimate_real_deaths(result, country="Nigeria"):
    """Scale DES deaths to real population."""
    raw_cities = load_cities(country)
    total_real_pop = sum(int(c["population"]) for c in raw_cities)
    n_cities = len(result.city_names)
    total_des_pop = result.n_people_per_city * n_cities
    scale = total_real_pop / total_des_pop
    des_deaths = result.actual_D.sum(axis=0)
    return des_deaths * scale, total_real_pop


# ── Figure 1: Nigeria Aggregate Dynamics ──────────────────────────

def plot_nigeria_aggregate(results_by_seed):
    """Overlay multiple MC runs of Nigeria aggregate dynamics."""
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle(
        f"Nigeria Country-Scale Dynamics — {SCENARIO}\n"
        f"{N_RUNS} runs, {N_PEOPLE}/city, production DES engine",
        fontsize=13, fontweight="bold",
    )

    for seed, result in results_by_seed.items():
        n_cities = len(result.city_names)
        N_total = result.n_people_per_city * n_cities
        t = result.t

        agg_I = result.actual_I.sum(axis=0) / N_total
        agg_D = result.actual_D.sum(axis=0)
        real_D, total_pop = estimate_real_deaths(result)

        axes[0].plot(t, agg_I, alpha=0.6, linewidth=1.5, label=f"seed={seed}")
        axes[1].plot(t, agg_D, alpha=0.6, linewidth=1.5, label=f"seed={seed}")
        axes[2].plot(t, real_D, alpha=0.6, linewidth=1.5, label=f"seed={seed}")

    axes[0].set_title("Aggregate Infectious (fraction)", fontsize=11)
    axes[0].set_ylabel("I / N_total")
    axes[0].yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))

    axes[1].set_title("DES Deaths (cumulative)", fontsize=11)
    axes[1].set_ylabel("DES deaths")

    axes[2].set_title("Estimated Real Deaths (scaled)", fontsize=11)
    axes[2].set_ylabel("Deaths")
    # Add reference line for Nigeria COVID first wave (~3000 total pandemic)
    axes[2].axhline(y=3000, color="gray", linestyle=":", linewidth=1.5,
                     label="Nigeria total COVID deaths (~3000)")

    for ax in axes:
        ax.set_xlabel("Day")
        ax.legend(fontsize=8)

    plt.tight_layout(rect=[0, 0, 1, 0.88])
    fname = RESULTS_DIR / "01_nigeria_aggregate.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"  Saved: {fname}")
    plt.close(fig)


# ── Figure 2: Provider Intervention Comparison ────────────────────

def plot_provider_comparison():
    """Compare low vs high provider density on Nigeria deaths."""
    print(f"\n  Running low provider density (1/1000)...")
    result_low = run_nigeria(provider_density=1.0, seed=42)

    print(f"  Running high provider density (10/1000)...")
    result_high = run_nigeria(provider_density=10.0, seed=42)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(
        f"Provider Intervention Impact — Nigeria {SCENARIO}\n"
        f"Low (1/1000) vs High (10/1000) provider density",
        fontsize=13, fontweight="bold",
    )

    for ax, result, label in [(axes[0], result_low, "Low (1/1000)"),
                                (axes[1], result_high, "High (10/1000)")]:
        t = result.t
        real_D, total_pop = estimate_real_deaths(result)
        agg_I = result.actual_I.sum(axis=0) / (result.n_people_per_city * len(result.city_names))

        ax2 = ax.twinx()
        ax.plot(t, agg_I, color="#e63946", linewidth=2, label="Infectious")
        ax2.plot(t, real_D, color="#264653", linewidth=2, linestyle="--", label="Est. Deaths")

        ax.set_title(f"{label}\nEst. deaths: {real_D[-1]:,.0f}", fontsize=11)
        ax.set_xlabel("Day")
        ax.set_ylabel("Infectious (fraction)", color="#e63946")
        ax2.set_ylabel("Est. Deaths (scaled)", color="#264653")
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))

    plt.tight_layout(rect=[0, 0, 1, 0.86])
    fname = RESULTS_DIR / "02_provider_comparison.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"  Saved: {fname}")
    plt.close(fig)

    # Print comparison
    low_D = estimate_real_deaths(result_low)[0][-1]
    high_D = estimate_real_deaths(result_high)[0][-1]
    print(f"\n  Deaths comparison:")
    print(f"    Low density (1/1000):  {low_D:,.0f} estimated real deaths")
    print(f"    High density (10/1000): {high_D:,.0f} estimated real deaths")
    print(f"    Lives saved:            {low_D - high_D:,.0f}")


# ── Figure 3: Wave Arrival Per City ───────────────────────────────

def plot_wave_arrival(result):
    """Show peak timing across all Nigerian cities."""
    n_cities = len(result.city_names)
    peak_days = []
    peak_I_pct = []

    for i in range(n_cities):
        peak_I = result.actual_I[i].max()
        peak_day = result.t[result.actual_I[i].argmax()]
        peak_days.append(peak_day)
        peak_I_pct.append(peak_I / result.n_people_per_city * 100)

    fig, ax = plt.subplots(figsize=(12, 6))
    fig.suptitle(
        f"Wave Arrival Timing — Nigeria {SCENARIO}\n"
        f"{n_cities} cities",
        fontsize=13, fontweight="bold",
    )

    colors = sns.color_palette("flare", n_colors=n_cities)
    sorted_idx = np.argsort(peak_days)

    for rank, i in enumerate(sorted_idx[:20]):  # Show top 20
        ax.barh(rank, peak_days[i], color=colors[rank % len(colors)],
                edgecolor="black", linewidth=0.3)
        ax.text(peak_days[i] + 1, rank, f"{result.city_names[i]} ({peak_I_pct[i]:.1f}%)",
                va="center", fontsize=8)

    ax.set_xlabel("Peak Infection Day")
    ax.set_ylabel("City (sorted by arrival)")
    ax.invert_yaxis()

    plt.tight_layout(rect=[0, 0, 1, 0.90])
    fname = RESULTS_DIR / "03_wave_arrival.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"  Saved: {fname}")
    plt.close(fig)


# ── Main ─────────────────────────────────────────────────────────

def main():
    ensure_results_dir()

    raw_cities = load_cities(COUNTRY)
    total_real_pop = sum(int(c["population"]) for c in raw_cities)

    print(f"{'='*62}")
    print(f"  Nigeria Country-Scale Validation (v2 — Production Backend)")
    print(f"  {len(raw_cities)} cities, real pop={total_real_pop:,}")
    print(f"  N={N_PEOPLE}/city, {DAYS} days, {N_RUNS} runs")
    print(f"{'='*62}")

    # MC runs
    results = {}
    for i in range(N_RUNS):
        seed = 42 + i * 100
        print(f"\n  Run {i+1}/{N_RUNS} (seed={seed})...")
        results[seed] = run_nigeria(seed=seed)
        real_D = estimate_real_deaths(results[seed])[0][-1]
        print(f"    Est. real deaths: {real_D:,.0f}")

    # Figures
    plot_nigeria_aggregate(results)
    plot_provider_comparison()

    # Wave arrival from first run
    first_result = list(results.values())[0]
    plot_wave_arrival(first_result)

    # Summary
    all_real_deaths = [estimate_real_deaths(r)[0][-1] for r in results.values()]
    print(f"\n  Summary (across {N_RUNS} runs):")
    print(f"    Mean est. real deaths: {np.mean(all_real_deaths):,.0f}")
    print(f"    Range: [{min(all_real_deaths):,.0f}, {max(all_real_deaths):,.0f}]")
    print(f"    Target: ~1,000-3,000 for Nigeria COVID first wave")

    print(f"\n{'='*62}")
    print(f"All plots saved to: {RESULTS_DIR.resolve()}")
    print(f"{'='*62}")


if __name__ == "__main__":
    main()
