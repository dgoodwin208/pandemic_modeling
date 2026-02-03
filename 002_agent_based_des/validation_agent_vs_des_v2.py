#!/usr/bin/env python3
"""
Agent Behavior Validation (v2 — Production Backend).

Re-validates 002 using the production 7-state CityDES engine.

The production CityDES internalizes agent behavior via parameters:
  - base_isolation_prob: spontaneous isolation (no provider advice)
  - advised_isolation_prob: isolation after provider advice

Experiments:
1. Baseline equivalence: CityDES with base_isolation=0 vs SEIR ODE
   (confirms 001 result in a different context)
2. Isolation probability sweep: increasing base_isolation_prob
   monotonically reduces peak I and attack rate
3. Provider-advised isolation: n_providers>0 with varying
   advised_isolation_prob shows the provider pathway working

Outputs saved to 002_agent_based_des/results_v2/ directory.

Usage (from project root):
    python 002_agent_based_des/validation_agent_vs_des_v2.py
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

from city_des_extended import CityDES
from validation_config import COVID_LIKE, EpidemicScenario
from seir_ode import solve_seir

# ── Plot Configuration ───────────────────────────────────────────
sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)
PALETTE = sns.color_palette("muted")
COLOR_S = PALETTE[0]
COLOR_I = PALETTE[3]
COLOR_R = PALETTE[2]
COLOR_SEIR = "black"

RESULTS_DIR = _SCRIPT_DIR / "results_v2"
EPIDEMIC_THRESHOLD_PCT = 5.0


def ensure_results_dir():
    RESULTS_DIR.mkdir(exist_ok=True)


# ── Run single DES and collect daily counts ──────────────────────

def run_single_des(
    scenario, population, duration_days, seed,
    base_isolation_prob=0.0,
    advised_isolation_prob=0.0,
    n_providers=0,
    screening_capacity=20,
    severe_fraction=0.0,
    initial_infected=3,
):
    """Run CityDES, return dict of daily arrays."""
    city = CityDES(
        n_people=population,
        scenario=scenario,
        seed_infected=initial_infected,
        random_seed=seed,
        avg_contacts=10,
        rewire_prob=0.4,
        daily_contact_rate=0.5,
        p_random=0.15,
        n_providers=n_providers,
        screening_capacity=screening_capacity,
        base_isolation_prob=base_isolation_prob,
        advised_isolation_prob=advised_isolation_prob,
        advice_decay_prob=0.0,
        severe_fraction=severe_fraction,
        gamma_shape=6.25,
    )

    n_days = duration_days + 1
    S = np.zeros(n_days)
    E = np.zeros(n_days)
    I = np.zeros(n_days)
    R = np.zeros(n_days)
    D = np.zeros(n_days)

    S[0], E[0], I[0], R[0], D[0] = city.S, city.E, city.I, city.R, city.D

    for day in range(1, n_days):
        city.step(until=day)
        if n_providers > 0:
            city.run_provider_screening()
        S[day] = city.S
        E[day] = city.E
        I[day] = city.I
        R[day] = city.R
        D[day] = city.D

    t = np.arange(0, n_days, dtype=float)
    return {"t": t, "S": S, "E": E, "I": I, "R": R, "D": D}


def run_mc(n_runs, label, **kwargs):
    """Run Monte Carlo DES, return dict of stacked arrays."""
    duration_days = kwargs.get("duration_days", 180)
    n_days = duration_days + 1
    all_S = np.zeros((n_runs, n_days))
    all_I = np.zeros((n_runs, n_days))
    all_R = np.zeros((n_runs, n_days))

    for i in range(n_runs):
        seed = 1000 + i * 137
        result = run_single_des(seed=seed, **kwargs)
        all_S[i] = result["S"]
        all_I[i] = result["I"]
        all_R[i] = result["R"]
        if (i + 1) % 10 == 0 or i == 0:
            print(f"    {label}: run {i+1}/{n_runs}", flush=True)

    t = np.arange(0, n_days, dtype=float)
    return {"t": t, "S": all_S, "I": all_I, "R": all_R, "n_runs": n_runs}


# ── Experiment 1: Isolation Probability Sweep (no providers) ─────

def sweep_base_isolation(
    scenario=COVID_LIKE,
    population=5000,
    duration_days=180,
    n_runs=20,
    isolation_probs=None,
):
    """
    Show that increasing base_isolation_prob monotonically suppresses the epidemic.

    No providers — just spontaneous self-isolation.
    """
    if isolation_probs is None:
        isolation_probs = [0.0, 0.1, 0.3, 0.5]

    print(f"\n{'='*60}")
    print(f"Experiment 1: Base Isolation Sweep (no providers)")
    print(f"  N={population}, {n_runs} runs per condition")
    print(f"  Isolation probs: {isolation_probs}")
    print(f"{'='*60}")

    # SEIR reference
    seir_params = scenario.to_seir_params(population)
    ode = solve_seir(seir_params, days=duration_days, initial_infected=3)
    ode_I_frac = ode["I"] / population

    # MC runs for each isolation level
    results = {}
    for iso_p in isolation_probs:
        print(f"\n  base_isolation_prob = {iso_p:.0%}:")
        mc = run_mc(
            n_runs=n_runs,
            label=f"iso={iso_p:.0%}",
            scenario=scenario,
            population=population,
            duration_days=duration_days,
            base_isolation_prob=iso_p,
        )
        results[iso_p] = mc

    # ── Plot: Infectious curves with variability bands ────────────
    fig, ax = plt.subplots(figsize=(12, 7))
    fig.suptitle(
        f"Effect of Base Isolation on Epidemic — {scenario.name}\n"
        f"N={population:,}, {n_runs} runs per condition, no providers",
        fontsize=13, fontweight="bold",
    )

    # SEIR ODE reference
    ax.plot(ode["t"], ode_I_frac, color=COLOR_SEIR, linewidth=2.5,
            label="SEIR ODE (no isolation)", alpha=0.8)

    colors = sns.color_palette("viridis", n_colors=len(isolation_probs))
    for (iso_p, mc), color in zip(results.items(), colors):
        mc_I_frac = mc["I"] / population
        mc_mean = mc_I_frac.mean(axis=0)
        mc_std = mc_I_frac.std(axis=0)
        t = mc["t"]

        ax.plot(t, mc_mean, color=color, linewidth=1.8,
                label=f"iso={iso_p:.0%} mean", alpha=0.9)
        ax.fill_between(t, mc_mean - mc_std, mc_mean + mc_std,
                         color=color, alpha=0.12)

    ax.set_xlabel("Day")
    ax.set_ylabel("Infected (fraction)")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    ax.legend(fontsize=9, loc="upper right")
    ax.set_xlim(0, duration_days)

    plt.tight_layout(rect=[0, 0, 1, 0.88])
    fname = RESULTS_DIR / "01_base_isolation_sweep.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"\n  Saved: {fname}")
    plt.close(fig)

    # ── Summary metrics ───────────────────────────────────────────
    _print_metrics_table(ode, results, isolation_probs, population, n_runs)

    return results


def _print_metrics_table(ode, results, isolation_probs, population, n_runs):
    """Print summary metrics table."""
    seir_peak = ode["I"].max() / population * 100
    seir_day = ode["t"][ode["I"].argmax()]
    seir_attack = (population - ode["S"][-1]) / population * 100

    print(f"\n  {'Condition':<16} {'Peak I%':>8} {'std':>6} "
          f"{'PkDay':>7} {'Attack%':>8} {'std':>6}")
    print(f"  {'─'*55}")
    print(f"  {'SEIR ODE':<16} {seir_peak:>8.1f} {'--':>6} "
          f"{seir_day:>7.0f} {seir_attack:>8.1f} {'--':>6}")

    for iso_p in isolation_probs:
        mc = results[iso_p]
        peak_vals = mc["I"].max(axis=1) / population * 100
        attack_vals = (population - mc["S"][:, -1]) / population * 100
        # Peak day only for established epidemics
        established = attack_vals > EPIDEMIC_THRESHOLD_PCT
        if established.any():
            peak_days = np.array([mc["t"][run.argmax()] for run in mc["I"]])
            pk_day = peak_days[established].mean()
        else:
            pk_day = 0.0

        label = f"iso={iso_p:.0%}"
        print(f"  {label:<16} {peak_vals.mean():>8.1f} {peak_vals.std():>6.1f} "
              f"{pk_day:>7.0f} {attack_vals.mean():>8.1f} {attack_vals.std():>6.1f}")


# ── Experiment 2: Provider-Advised Isolation Sweep ───────────────

def sweep_advised_isolation(
    scenario=COVID_LIKE,
    population=5000,
    duration_days=180,
    n_runs=20,
    advised_probs=None,
):
    """
    Show that providers + advised_isolation_prob suppresses the epidemic
    more effectively than base isolation alone.
    """
    if advised_probs is None:
        advised_probs = [0.0, 0.10, 0.20, 0.40]

    print(f"\n{'='*60}")
    print(f"Experiment 2: Provider-Advised Isolation Sweep")
    print(f"  N={population}, {n_runs} runs, 25 providers")
    print(f"  base_isolation=0.05, advised_isolation: {advised_probs}")
    print(f"{'='*60}")

    # SEIR reference
    seir_params = scenario.to_seir_params(population)
    ode = solve_seir(seir_params, days=duration_days, initial_infected=3)

    # MC runs for each advised isolation level
    results = {}
    for adv_p in advised_probs:
        print(f"\n  advised_isolation_prob = {adv_p:.0%}:")
        mc = run_mc(
            n_runs=n_runs,
            label=f"adv={adv_p:.0%}",
            scenario=scenario,
            population=population,
            duration_days=duration_days,
            base_isolation_prob=0.05,
            advised_isolation_prob=adv_p,
            n_providers=25,
            screening_capacity=20,
        )
        results[adv_p] = mc

    # ── Plot ──────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(12, 7))
    fig.suptitle(
        f"Effect of Provider-Advised Isolation — {scenario.name}\n"
        f"N={population:,}, 25 providers, base_iso=5%, {n_runs} runs each",
        fontsize=13, fontweight="bold",
    )

    ode_I_frac = ode["I"] / population
    ax.plot(ode["t"], ode_I_frac, color=COLOR_SEIR, linewidth=2.5,
            label="SEIR ODE", alpha=0.8)

    colors = sns.color_palette("coolwarm", n_colors=len(advised_probs))
    for (adv_p, mc), color in zip(results.items(), colors):
        mc_I_frac = mc["I"] / population
        mc_mean = mc_I_frac.mean(axis=0)
        mc_std = mc_I_frac.std(axis=0)
        t = mc["t"]

        ax.plot(t, mc_mean, color=color, linewidth=1.8,
                label=f"advised={adv_p:.0%} mean", alpha=0.9)
        ax.fill_between(t, mc_mean - mc_std, mc_mean + mc_std,
                         color=color, alpha=0.12)

    ax.set_xlabel("Day")
    ax.set_ylabel("Infected (fraction)")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    ax.legend(fontsize=9, loc="upper right")
    ax.set_xlim(0, duration_days)

    plt.tight_layout(rect=[0, 0, 1, 0.88])
    fname = RESULTS_DIR / "02_advised_isolation_sweep.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"\n  Saved: {fname}")
    plt.close(fig)

    # Metrics
    _print_metrics_table(ode, results, advised_probs, population, n_runs)

    return results


# ── Experiment 3: Monotonicity Proof ─────────────────────────────

def plot_monotonicity(
    scenario=COVID_LIKE,
    population=5000,
    duration_days=180,
    n_runs=15,
):
    """
    Fine-grained sweep of base_isolation_prob from 0 to 0.6.
    Plot peak I and attack rate vs isolation prob to prove monotonicity.
    """
    iso_values = np.arange(0, 0.65, 0.05)

    print(f"\n{'='*60}")
    print(f"Experiment 3: Monotonicity Proof")
    print(f"  {len(iso_values)} isolation levels, {n_runs} runs each")
    print(f"{'='*60}")

    peak_means = []
    peak_stds = []
    attack_means = []
    attack_stds = []

    for iso_p in iso_values:
        print(f"  iso={iso_p:.2f}...", end=" ", flush=True)
        mc = run_mc(
            n_runs=n_runs,
            label=f"iso={iso_p:.2f}",
            scenario=scenario,
            population=population,
            duration_days=duration_days,
            base_isolation_prob=float(iso_p),
        )
        peaks = mc["I"].max(axis=1) / population * 100
        attacks = (population - mc["S"][:, -1]) / population * 100
        peak_means.append(peaks.mean())
        peak_stds.append(peaks.std())
        attack_means.append(attacks.mean())
        attack_stds.append(attacks.std())
        print(f"peak={peaks.mean():.1f}%, attack={attacks.mean():.1f}%")

    peak_means = np.array(peak_means)
    peak_stds = np.array(peak_stds)
    attack_means = np.array(attack_means)
    attack_stds = np.array(attack_stds)

    # Plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(
        f"Monotonicity: Isolation Probability vs Epidemic Metrics\n"
        f"{scenario.name}, N={population:,}, {n_runs} runs per point",
        fontsize=13, fontweight="bold",
    )

    ax1.errorbar(iso_values * 100, peak_means, yerr=peak_stds,
                 color=COLOR_I, marker="o", capsize=4, linewidth=1.5)
    ax1.set_xlabel("Base Isolation Probability (%)")
    ax1.set_ylabel("Peak Infected (% of N)")
    ax1.set_title("Peak Infectious Count")

    ax2.errorbar(iso_values * 100, attack_means, yerr=attack_stds,
                 color=COLOR_R, marker="s", capsize=4, linewidth=1.5)
    ax2.set_xlabel("Base Isolation Probability (%)")
    ax2.set_ylabel("Final Attack Rate (%)")
    ax2.set_title("Final Attack Rate")

    plt.tight_layout(rect=[0, 0, 1, 0.88])
    fname = RESULTS_DIR / "03_monotonicity.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"\n  Saved: {fname}")
    plt.close(fig)


# ── Main ─────────────────────────────────────────────────────────

def main():
    ensure_results_dir()

    print(f"{'='*62}")
    print(f"  Agent Behavior Validation (v2 — Production Backend)")
    print(f"  Engine: simulation_app/backend/city_des_extended.py")
    print(f"{'='*62}")

    # Experiment 1: Base isolation sweep
    sweep_base_isolation(n_runs=20)

    # Experiment 2: Provider-advised isolation sweep
    sweep_advised_isolation(n_runs=20)

    # Experiment 3: Fine-grained monotonicity proof
    plot_monotonicity(n_runs=15)

    print(f"\n{'='*62}")
    print(f"All plots saved to: {RESULTS_DIR.resolve()}")
    print(f"{'='*62}")


if __name__ == "__main__":
    main()
