#!/usr/bin/env python3
"""
Healthcare Coverage Dose-Response Sweep (v2 — Production Backend).

Re-validates 007 using run_absdes_simulation() from the production backend.

Sweeps provider density from 0 to 100/1000 for Ebola bioattack on Nigeria,
demonstrating dose-response relationship between healthcare coverage
and epidemic outcomes.

Outputs saved to 007_coverage_sweep/results_v2/ directory.

Usage (from project root):
    python 007_coverage_sweep/coverage_sweep_v2.py
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
SCENARIO = "ebola_bioattack"
N_PEOPLE = 5000
DAYS = 150
N_RUNS = 2

PROVIDER_DENSITIES = [0, 1, 2, 5, 10, 20, 30, 50, 75, 100]


def ensure_results_dir():
    RESULTS_DIR.mkdir(exist_ok=True)


def run_sweep_point(density, seed=42):
    """Run a single sweep point."""
    params = SimulationParams(
        country=COUNTRY,
        scenario=SCENARIO,
        n_people=N_PEOPLE,
        days=DAYS,
        random_seed=seed,
        provider_density=float(density),
        seed_fraction=0.005,
    )
    return run_absdes_simulation(params)


def estimate_real_deaths(result):
    """Scale DES deaths to real population."""
    raw_cities = load_cities(COUNTRY)
    total_real_pop = sum(int(c["population"]) for c in raw_cities)
    n_cities = len(result.city_names)
    total_des_pop = result.n_people_per_city * n_cities
    scale = total_real_pop / total_des_pop
    return result.actual_D.sum(axis=0)[-1] * scale, total_real_pop


# ── Run sweep ─────────────────────────────────────────────────────

def run_full_sweep():
    """Run all density x seed combinations."""
    sweep_data = {}

    for density in PROVIDER_DENSITIES:
        death_estimates = []
        attack_rates = []
        peak_I_vals = []
        peak_day_vals = []

        for run_idx in range(N_RUNS):
            seed = 42 + run_idx * 100
            print(f"  density={density}/1000, run {run_idx+1}/{N_RUNS}...", end=" ")
            result = run_sweep_point(density, seed=seed)
            n_cities = len(result.city_names)
            N_total = result.n_people_per_city * n_cities

            real_D, total_pop = estimate_real_deaths(result)
            attack = (N_total - result.actual_S.sum(axis=0)[-1]) / N_total * 100

            # Per-city peak stats
            for i in range(n_cities):
                peak_I_vals.append(result.actual_I[i].max() / result.n_people_per_city * 100)
                peak_day_vals.append(result.t[result.actual_I[i].argmax()])

            death_estimates.append(real_D)
            attack_rates.append(attack)
            print(f"deaths={real_D:,.0f}, attack={attack:.1f}%")

        sweep_data[density] = {
            "deaths_mean": np.mean(death_estimates),
            "deaths_std": np.std(death_estimates),
            "deaths_all": death_estimates,
            "attack_mean": np.mean(attack_rates),
            "attack_std": np.std(attack_rates),
            "peak_I_mean": np.mean(peak_I_vals),
            "peak_I_std": np.std(peak_I_vals),
            "peak_day_mean": np.mean(peak_day_vals),
            "peak_day_std": np.std(peak_day_vals),
        }

    return sweep_data


# ── Figure 1: Deaths vs Provider Density ──────────────────────────

def plot_deaths_vs_density(sweep_data):
    """Main dose-response curve: deaths vs provider density."""
    densities = list(sweep_data.keys())
    deaths_means = [sweep_data[d]["deaths_mean"] for d in densities]
    deaths_stds = [sweep_data[d]["deaths_std"] for d in densities]

    # Lives saved relative to baseline (density=0)
    baseline = deaths_means[0]
    lives_saved = [baseline - d for d in deaths_means]

    fig, ax1 = plt.subplots(figsize=(12, 7))
    fig.suptitle(
        f"Dose-Response: Provider Density vs Deaths — {SCENARIO}\n"
        f"Nigeria, N={N_PEOPLE}/city, {DAYS} days, {N_RUNS} runs",
        fontsize=13, fontweight="bold",
    )

    color1 = "#e63946"
    color2 = "#2a9d8f"

    ax1.errorbar(densities, [d / 1e6 for d in deaths_means],
                 yerr=[s / 1e6 for s in deaths_stds],
                 color=color1, marker="o", linewidth=2, capsize=5,
                 label="Est. Real Deaths (millions)")
    ax1.set_xlabel("Provider Density (per 1000 population)")
    ax1.set_ylabel("Estimated Deaths (millions)", color=color1)
    ax1.tick_params(axis="y", labelcolor=color1)

    ax2 = ax1.twinx()
    ax2.plot(densities, [ls / 1e6 for ls in lives_saved],
             color=color2, marker="s", linewidth=2, linestyle="--",
             label="Lives Saved (millions)")
    ax2.set_ylabel("Lives Saved vs Baseline (millions)", color=color2)
    ax2.tick_params(axis="y", labelcolor=color2)

    # Combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=10, loc="center right")

    plt.tight_layout(rect=[0, 0, 1, 0.88])
    fname = RESULTS_DIR / "01_deaths_vs_density.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"\n  Saved: {fname}")
    plt.close(fig)


# ── Figure 2: Epidemic Characteristics ────────────────────────────

def plot_epidemic_characteristics(sweep_data):
    """Three-panel: peak I%, peak day, attack rate vs density."""
    densities = list(sweep_data.keys())

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle(
        f"Epidemic Characteristics vs Coverage — {SCENARIO}",
        fontsize=13, fontweight="bold",
    )

    panels = [
        ("Mean Peak Infection (%)", "peak_I_mean", "peak_I_std", "#e63946"),
        ("Mean Peak Day", "peak_day_mean", "peak_day_std", "#457b9d"),
        ("Attack Rate (%)", "attack_mean", "attack_std", "#2a9d8f"),
    ]

    for ax, (title, mean_key, std_key, color) in zip(axes, panels):
        means = [sweep_data[d][mean_key] for d in densities]
        stds = [sweep_data[d][std_key] for d in densities]
        ax.errorbar(densities, means, yerr=stds,
                     color=color, marker="o", linewidth=1.8, capsize=4)
        ax.set_xlabel("Provider Density (per 1000)")
        ax.set_title(title, fontsize=11)

    plt.tight_layout(rect=[0, 0, 1, 0.88])
    fname = RESULTS_DIR / "02_epidemic_characteristics.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"  Saved: {fname}")
    plt.close(fig)


# ── Summary Table ─────────────────────────────────────────────────

def print_summary(sweep_data):
    """Print the dose-response table."""
    baseline_deaths = sweep_data[0]["deaths_mean"]

    print(f"\n  {'Density':>8} {'Deaths(M)':>10} {'std':>8} "
          f"{'Saved(M)':>10} {'Attack%':>8} {'PeakI%':>8} {'PkDay':>6}")
    print(f"  {'─'*65}")

    for density in sweep_data:
        d = sweep_data[density]
        saved = baseline_deaths - d["deaths_mean"]
        print(f"  {density:>8} {d['deaths_mean']/1e6:>10.2f} {d['deaths_std']/1e6:>8.2f} "
              f"{saved/1e6:>10.2f} {d['attack_mean']:>8.1f} "
              f"{d['peak_I_mean']:>8.1f} {d['peak_day_mean']:>6.0f}")


# ── Main ─────────────────────────────────────────────────────────

def main():
    ensure_results_dir()

    raw_cities = load_cities(COUNTRY)
    total_pop = sum(int(c["population"]) for c in raw_cities)

    print(f"{'='*62}")
    print(f"  Coverage Sweep Validation (v2 — Production Backend)")
    print(f"  {SCENARIO} on {COUNTRY}")
    print(f"  {len(raw_cities)} cities, real pop={total_pop:,}")
    print(f"  Densities: {PROVIDER_DENSITIES}")
    print(f"  N={N_PEOPLE}/city, {DAYS} days, {N_RUNS} runs each")
    print(f"{'='*62}")

    sweep_data = run_full_sweep()

    plot_deaths_vs_density(sweep_data)
    plot_epidemic_characteristics(sweep_data)
    print_summary(sweep_data)

    print(f"\n{'='*62}")
    print(f"All plots saved to: {RESULTS_DIR.resolve()}")
    print(f"{'='*62}")


if __name__ == "__main__":
    main()
