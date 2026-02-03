#!/usr/bin/env python3
"""
Multi-City Gravity Coupling Validation (v2 — Production Backend).

Re-validates 004 using run_absdes_simulation() from the production backend.

Demonstrates pandemic spread across 5 African cities using the production
DES engine with gravity-model travel coupling, proving wave propagation
timing correlates with geographic distance/connectivity.

Outputs saved to 004_multicity/results_v2/ directory.

Usage (from project root):
    python 004_multicity/validation_multicity_v2.py
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

from simulation import SimulationParams, run_absdes_simulation, DualViewResult

# ── Configuration ─────────────────────────────────────────────────
sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)
RESULTS_DIR = _SCRIPT_DIR / "results_v2"

# 5-city demo: use a small country with well-known cities
# We use "Nigeria" which has enough cities, and pick the top 5
DEMO_SCENARIO = "covid_natural"
DEMO_DAYS = 200
DEMO_N_PEOPLE = 5000

CITY_COLORS = ["#e63946", "#457b9d", "#2a9d8f", "#e9c46a", "#f4a261",
               "#264653", "#a8dadc", "#1d3557", "#f77f00", "#d62828"]


def ensure_results_dir():
    RESULTS_DIR.mkdir(exist_ok=True)


# ── Run simulation ────────────────────────────────────────────────

def run_demo(scenario="covid_natural", country="Nigeria", n_people=5000,
             days=200, seed=42):
    """Run a multi-city simulation using the production backend."""
    params = SimulationParams(
        country=country,
        scenario=scenario,
        n_people=n_people,
        days=days,
        random_seed=seed,
        provider_density=5.0,
        seed_fraction=0.005,
        # Use default seed schedule from scenario
    )
    result = run_absdes_simulation(params)
    return result


# ── Figure 1: Wave Propagation ────────────────────────────────────

def plot_wave_propagation(result: DualViewResult):
    """
    All cities' infection curves on one plot, showing wave spreading
    from seed city to others via gravity coupling.
    """
    n_cities = len(result.city_names)
    n_show = min(10, n_cities)  # Show top 10 cities

    fig, ax = plt.subplots(figsize=(14, 7))
    fig.suptitle(
        f"Epidemic Wave Propagation — {result.scenario_name}\n"
        f"{n_cities} cities, N={result.n_people_per_city}/city, "
        f"production DES engine",
        fontsize=13, fontweight="bold",
    )

    t = result.t
    for i in range(n_show):
        I_frac = result.actual_I[i] / result.n_people_per_city
        color = CITY_COLORS[i % len(CITY_COLORS)]
        peak_day = t[result.actual_I[i].argmax()]
        label = f"{result.city_names[i]} (peak day {peak_day:.0f})"
        ax.plot(t, I_frac, color=color, linewidth=1.5, label=label, alpha=0.85)

    ax.set_xlabel("Day")
    ax.set_ylabel("Infected (fraction)")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    ax.legend(fontsize=8, loc="upper right", ncol=2)
    ax.set_xlim(0, result.t[-1])

    plt.tight_layout(rect=[0, 0, 1, 0.90])
    fname = RESULTS_DIR / "01_wave_propagation.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"  Saved: {fname}")
    plt.close(fig)


# ── Figure 2: Per-City SEIR-D Curves ─────────────────────────────

def plot_per_city_seird(result: DualViewResult):
    """Full S, E, I, R, D curves for top 5 cities."""
    n_show = min(5, len(result.city_names))
    fig, axes = plt.subplots(n_show, 1, figsize=(14, 4 * n_show), sharex=True)
    if n_show == 1:
        axes = [axes]

    fig.suptitle(
        f"Per-City SEIR-D Dynamics — {result.scenario_name}\n"
        f"Production DES 7-state model",
        fontsize=13, fontweight="bold",
    )

    t = result.t
    N = result.n_people_per_city

    for i, ax in enumerate(axes):
        ax.plot(t, result.actual_S[i] / N, color="#457b9d", linewidth=1.5, label="S")
        ax.plot(t, result.actual_E[i] / N, color="#e9c46a", linewidth=1.5, label="E")
        ax.plot(t, result.actual_I[i] / N, color="#e63946", linewidth=1.5, label="I")
        ax.plot(t, result.actual_R[i] / N, color="#2a9d8f", linewidth=1.5, label="R")
        ax.plot(t, result.actual_D[i] / N, color="#264653", linewidth=1.5, label="D")

        peak_I = result.actual_I[i].max()
        peak_day = t[result.actual_I[i].argmax()]
        final_D = result.actual_D[i, -1]
        ax.set_title(f"{result.city_names[i]} — peak I={peak_I:.0f} (day {peak_day:.0f}), "
                      f"deaths={final_D:.0f}", fontsize=10)
        ax.set_ylabel("Fraction")
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
        if i == 0:
            ax.legend(fontsize=8, loc="right")

    axes[-1].set_xlabel("Day")

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    fname = RESULTS_DIR / "02_per_city_seird.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"  Saved: {fname}")
    plt.close(fig)


# ── Figure 3: Continent-wide Aggregate ────────────────────────────

def plot_aggregate(result: DualViewResult):
    """Aggregate S, E, I, R, D across all cities."""
    t = result.t
    N_total = result.n_people_per_city * len(result.city_names)

    agg_S = result.actual_S.sum(axis=0) / N_total
    agg_E = result.actual_E.sum(axis=0) / N_total
    agg_I = result.actual_I.sum(axis=0) / N_total
    agg_R = result.actual_R.sum(axis=0) / N_total
    agg_D = result.actual_D.sum(axis=0) / N_total

    fig, ax = plt.subplots(figsize=(12, 6))
    fig.suptitle(
        f"Aggregate SEIR-D — {result.scenario_name}\n"
        f"{len(result.city_names)} cities, {N_total:,} total DES agents",
        fontsize=13, fontweight="bold",
    )

    ax.plot(t, agg_S, color="#457b9d", linewidth=2, label="S")
    ax.plot(t, agg_E, color="#e9c46a", linewidth=2, label="E")
    ax.plot(t, agg_I, color="#e63946", linewidth=2, label="I")
    ax.plot(t, agg_R, color="#2a9d8f", linewidth=2, label="R")
    ax.plot(t, agg_D, color="#264653", linewidth=2, label="D")

    ax.set_xlabel("Day")
    ax.set_ylabel("Fraction of Total Population")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    ax.legend(fontsize=10, loc="right")

    plt.tight_layout(rect=[0, 0, 1, 0.90])
    fname = RESULTS_DIR / "03_aggregate_seird.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"  Saved: {fname}")
    plt.close(fig)


# ── Summary table ─────────────────────────────────────────────────

def print_summary(result: DualViewResult):
    """Print per-city metrics table."""
    N = result.n_people_per_city
    t = result.t

    print(f"\n  {'City':<20} {'Pop(DES)':>8} {'PeakI':>6} {'PkDay':>6} "
          f"{'Attack%':>8} {'Deaths':>7}")
    print(f"  {'─'*58}")

    for i in range(len(result.city_names)):
        peak_I = result.actual_I[i].max()
        peak_day = t[result.actual_I[i].argmax()]
        attack = (N - result.actual_S[i, -1]) / N * 100
        deaths = result.actual_D[i, -1]
        print(f"  {result.city_names[i]:<20} {N:>8} {peak_I:>6.0f} {peak_day:>6.0f} "
              f"{attack:>8.1f} {deaths:>7.0f}")


# ── Main ─────────────────────────────────────────────────────────

def main():
    ensure_results_dir()

    print(f"{'='*62}")
    print(f"  Multi-City Gravity Coupling Validation (v2 — Production Backend)")
    print(f"  Engine: simulation_app/backend/simulation.py")
    print(f"{'='*62}")

    # Run simulation
    print(f"\n  Running Nigeria covid_natural simulation...")
    result = run_demo(
        scenario="covid_natural",
        country="Nigeria",
        n_people=5000,
        days=200,
    )
    print(f"  Done: {len(result.city_names)} cities simulated")

    # Generate figures
    plot_wave_propagation(result)
    plot_per_city_seird(result)
    plot_aggregate(result)
    print_summary(result)

    # Also run bioattack for comparison
    print(f"\n  Running Nigeria covid_bioattack simulation...")
    result_bio = run_demo(
        scenario="covid_bioattack",
        country="Nigeria",
        n_people=5000,
        days=200,
    )
    print(f"  Done: {len(result_bio.city_names)} cities simulated")

    # Compare natural vs bioattack
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), sharey=True)
    fig.suptitle(
        "Natural vs Bioattack Seeding — Nigeria\n"
        "Aggregate Infectious Curve",
        fontsize=13, fontweight="bold",
    )

    for ax, res, title in [(ax1, result, "Natural (Lagos seed)"),
                            (ax2, result_bio, "Bioattack (5 cities)")]:
        agg_I = res.actual_I.sum(axis=0) / (res.n_people_per_city * len(res.city_names))
        ax.plot(res.t, agg_I, color="#e63946", linewidth=2)
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("Day")
        ax.set_ylabel("Aggregate Infected (fraction)")
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))

    plt.tight_layout(rect=[0, 0, 1, 0.88])
    fname = RESULTS_DIR / "04_natural_vs_bioattack.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"  Saved: {fname}")
    plt.close(fig)

    print(f"\n{'='*62}")
    print(f"All plots saved to: {RESULTS_DIR.resolve()}")
    print(f"{'='*62}")


if __name__ == "__main__":
    main()
