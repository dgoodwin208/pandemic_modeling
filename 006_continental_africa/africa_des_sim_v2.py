#!/usr/bin/env python3
"""
Continental Africa Validation (v2 — Production Backend).

Re-validates 006 using run_absdes_simulation() from the production backend.

Runs all African cities across 4 scenarios (covid natural/bioattack,
ebola natural/bioattack) at two provider densities. Validates:
1. Continental death estimates are reasonable
2. Provider intervention reduces deaths
3. COVID first-wave Africa target: ~65,602 deaths (Lancet reference)

Outputs saved to 006_continental_africa/results_v2/ directory.

Usage (from project root):
    python 006_continental_africa/africa_des_sim_v2.py
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

SCENARIOS = [
    ("covid_natural", "COVID Natural"),
    ("covid_bioattack", "COVID Bioattack"),
    ("ebola_natural", "Ebola Natural"),
    ("ebola_bioattack", "Ebola Bioattack"),
]

PROVIDER_DENSITIES = [1.0, 10.0]
N_PEOPLE = 5000
DAYS = 150


def ensure_results_dir():
    RESULTS_DIR.mkdir(exist_ok=True)


def run_africa(scenario, provider_density=5.0, seed=42):
    """Run all-Africa simulation."""
    params = SimulationParams(
        country="ALL",
        scenario=scenario,
        n_people=N_PEOPLE,
        days=DAYS,
        random_seed=seed,
        provider_density=provider_density,
        seed_fraction=0.005,
    )
    return run_absdes_simulation(params)


def estimate_real_deaths(result):
    """Scale DES deaths to real continental population."""
    raw_cities = load_cities("ALL")
    total_real_pop = sum(int(c["population"]) for c in raw_cities)
    n_cities = len(result.city_names)
    total_des_pop = result.n_people_per_city * n_cities
    scale = total_real_pop / total_des_pop
    des_deaths = result.actual_D.sum(axis=0)
    return des_deaths * scale, total_real_pop


# ── Run all scenarios ─────────────────────────────────────────────

def run_all_scenarios():
    """Run all scenario x provider density combinations."""
    results = {}
    for scenario_key, scenario_label in SCENARIOS:
        for density in PROVIDER_DENSITIES:
            label = f"{scenario_key}_d{density:.0f}"
            print(f"\n  Running {scenario_label} (density={density}/1000)...")
            try:
                result = run_africa(scenario_key, provider_density=density)
                results[label] = {
                    "result": result,
                    "scenario_key": scenario_key,
                    "scenario_label": scenario_label,
                    "density": density,
                }
                real_D = estimate_real_deaths(result)[0][-1]
                des_D = result.actual_D.sum(axis=0)[-1]
                print(f"    {len(result.city_names)} cities, "
                      f"DES deaths={des_D:.0f}, est real={real_D:,.0f}")
            except Exception as e:
                print(f"    ERROR: {e}")
    return results


# ── Figure 1: Scenario Comparison ─────────────────────────────────

def plot_scenario_comparison(results):
    """2x2 grid: each scenario showing low vs high provider density."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle(
        f"Continental Africa — 4 Scenarios x 2 Provider Densities\n"
        f"N={N_PEOPLE}/city, {DAYS} days, production DES engine",
        fontsize=14, fontweight="bold",
    )

    for idx, (scenario_key, scenario_label) in enumerate(SCENARIOS):
        ax = axes.flat[idx]

        for density in PROVIDER_DENSITIES:
            label = f"{scenario_key}_d{density:.0f}"
            if label not in results:
                continue
            result = results[label]["result"]
            t = result.t
            n_total = result.n_people_per_city * len(result.city_names)
            agg_I = result.actual_I.sum(axis=0) / n_total

            style = "-" if density == PROVIDER_DENSITIES[0] else "--"
            ax.plot(t, agg_I, linewidth=1.8, linestyle=style,
                    label=f"density={density:.0f}/1000")

        ax.set_title(scenario_label, fontsize=11)
        ax.set_xlabel("Day")
        ax.set_ylabel("Aggregate Infected")
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=1))
        ax.legend(fontsize=9)

    plt.tight_layout(rect=[0, 0, 1, 0.90])
    fname = RESULTS_DIR / "01_scenario_comparison.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"\n  Saved: {fname}")
    plt.close(fig)


# ── Figure 2: Death Estimates ─────────────────────────────────────

def plot_death_estimates(results):
    """Bar chart of estimated real deaths per scenario and density."""
    fig, ax = plt.subplots(figsize=(14, 7))
    fig.suptitle(
        "Estimated Continental Deaths by Scenario\n"
        "Scaled from DES to real population",
        fontsize=13, fontweight="bold",
    )

    labels = []
    low_deaths = []
    high_deaths = []

    for scenario_key, scenario_label in SCENARIOS:
        low_label = f"{scenario_key}_d{PROVIDER_DENSITIES[0]:.0f}"
        high_label = f"{scenario_key}_d{PROVIDER_DENSITIES[1]:.0f}"
        if low_label in results and high_label in results:
            labels.append(scenario_label)
            low_deaths.append(estimate_real_deaths(results[low_label]["result"])[0][-1])
            high_deaths.append(estimate_real_deaths(results[high_label]["result"])[0][-1])

    x = np.arange(len(labels))
    width = 0.35

    bars1 = ax.bar(x - width / 2, low_deaths, width, label=f"Low ({PROVIDER_DENSITIES[0]:.0f}/1000)",
                    color="#e63946", edgecolor="black")
    bars2 = ax.bar(x + width / 2, high_deaths, width, label=f"High ({PROVIDER_DENSITIES[1]:.0f}/1000)",
                    color="#2a9d8f", edgecolor="black")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel("Estimated Real Deaths")
    ax.legend(fontsize=10)

    # Value labels
    for bars in [bars1, bars2]:
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, h + h * 0.02,
                    f"{h:,.0f}", ha="center", va="bottom", fontsize=8)

    # Reference line for COVID first wave
    ax.axhline(y=65602, color="gray", linestyle=":", linewidth=1.5)
    ax.text(0.02, 65602 * 1.05, "Lancet ref: 65,602 (COVID 1st wave Africa)",
            fontsize=8, color="gray", transform=ax.get_yaxis_transform())

    plt.tight_layout(rect=[0, 0, 1, 0.90])
    fname = RESULTS_DIR / "02_death_estimates.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"  Saved: {fname}")
    plt.close(fig)


# ── Figure 3: Cumulative Deaths Over Time ─────────────────────────

def plot_cumulative_deaths(results):
    """Time series of cumulative estimated real deaths per scenario."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle(
        "Cumulative Estimated Deaths Over Time\n"
        f"Low density ({PROVIDER_DENSITIES[0]:.0f}/1000)",
        fontsize=13, fontweight="bold",
    )

    colors = ["#e63946", "#457b9d", "#e9c46a", "#2a9d8f"]

    for idx, (scenario_key, scenario_label) in enumerate(SCENARIOS):
        for ax, density in zip(axes, PROVIDER_DENSITIES):
            label = f"{scenario_key}_d{density:.0f}"
            if label not in results:
                continue
            result = results[label]["result"]
            real_D, total_pop = estimate_real_deaths(result)
            ax.plot(result.t, real_D, color=colors[idx], linewidth=1.8,
                    label=scenario_label)
            ax.set_title(f"Density={density:.0f}/1000", fontsize=11)

    for ax in axes:
        ax.set_xlabel("Day")
        ax.set_ylabel("Estimated Real Deaths")
        ax.legend(fontsize=9)
        # COVID first-wave reference
        ax.axhline(y=65602, color="gray", linestyle=":", linewidth=1.0)

    plt.tight_layout(rect=[0, 0, 1, 0.88])
    fname = RESULTS_DIR / "03_cumulative_deaths.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"  Saved: {fname}")
    plt.close(fig)


# ── Summary Table ─────────────────────────────────────────────────

def print_summary(results):
    """Print full summary table."""
    print(f"\n  {'Scenario':<20} {'Density':>8} {'Cities':>7} {'DES Deaths':>11} "
          f"{'Est Real Deaths':>16} {'Attack%':>8}")
    print(f"  {'─'*75}")

    for scenario_key, scenario_label in SCENARIOS:
        for density in PROVIDER_DENSITIES:
            label = f"{scenario_key}_d{density:.0f}"
            if label not in results:
                continue
            result = results[label]["result"]
            n_cities = len(result.city_names)
            des_D = result.actual_D.sum(axis=0)[-1]
            real_D = estimate_real_deaths(result)[0][-1]
            N_total = result.n_people_per_city * n_cities
            agg_attack = (N_total - result.actual_S.sum(axis=0)[-1]) / N_total * 100

            print(f"  {scenario_label:<20} {density:>7.0f} {n_cities:>7} {des_D:>11.0f} "
                  f"{real_D:>16,.0f} {agg_attack:>8.1f}")


# ── Main ─────────────────────────────────────────────────────────

def main():
    ensure_results_dir()

    raw_cities = load_cities("ALL")
    total_pop = sum(int(c["population"]) for c in raw_cities)

    print(f"{'='*62}")
    print(f"  Continental Africa Validation (v2 — Production Backend)")
    print(f"  {len(raw_cities)} cities, real pop={total_pop:,}")
    print(f"  N={N_PEOPLE}/city, {DAYS} days")
    print(f"  Scenarios: {[s[1] for s in SCENARIOS]}")
    print(f"  Provider densities: {PROVIDER_DENSITIES}")
    print(f"{'='*62}")

    results = run_all_scenarios()

    plot_scenario_comparison(results)
    plot_death_estimates(results)
    plot_cumulative_deaths(results)
    print_summary(results)

    print(f"\n{'='*62}")
    print(f"All plots saved to: {RESULTS_DIR.resolve()}")
    print(f"{'='*62}")


if __name__ == "__main__":
    main()
