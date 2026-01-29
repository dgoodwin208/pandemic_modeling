#!/usr/bin/env python3
"""
DES ↔ SEIR Convergence Validation.

Self-contained demo that:
1. Solves the SEIR ODE for a given epidemic scenario
2. Runs Monte Carlo DES simulations with matched parameters
3. Produces publication-quality comparison plots

Outputs saved to validation/results/ directory.

Usage (from project root):
    python validation/validation_des_seir.py
"""

import sys
from pathlib import Path

# Add des_system to path so we can import its modules
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "des_system"))

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import seaborn as sns

from seir_ode import solve_seir
from validation_config import COVID_LIKE, FLU_LIKE, EpidemicScenario
from monte_carlo import run_monte_carlo

# ── Plot Configuration ───────────────────────────────────────────
sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)
PALETTE = sns.color_palette("muted")
COLOR_S = PALETTE[0]  # blue
COLOR_E = PALETTE[1]  # orange
COLOR_I = PALETTE[3]  # red
COLOR_R = PALETTE[2]  # green

RESULTS_DIR = Path(__file__).parent / "results"


def ensure_results_dir():
    RESULTS_DIR.mkdir(exist_ok=True)


# ── Plot 1: SEIR Curves + DES Scatter (The Money Shot) ──────────

def plot_seir_vs_des(
    scenario: EpidemicScenario,
    population: int,
    n_runs: int,
    duration_days: int = 180,
    avg_contacts: int = 10,
):
    """
    Overlay smooth SEIR ODE curves with DES Monte Carlo scatter.

    This is the primary validation artifact: visual proof that the
    stochastic DES converges to the deterministic SEIR solution.
    """
    print(f"\n{'='*60}")
    print(f"Plot 1: SEIR vs DES — {scenario.name}")
    print(f"  N={population}, runs={n_runs}, duration={duration_days}d")
    print(f"{'='*60}")
    print(scenario.describe())

    # 1. Solve SEIR ODE
    seir_params = scenario.to_seir_params(population)
    ode = solve_seir(seir_params, days=duration_days, initial_infected=3)

    # 2. Run Monte Carlo DES
    def make_config(seed):
        return scenario.to_des_config(
            population=population,
            duration_days=duration_days,
            avg_contacts=avg_contacts,
            random_seed=seed,
        )

    mc = run_monte_carlo(make_config, n_runs=n_runs)

    # 3. Plot
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(
        f"DES ↔ SEIR Convergence — {scenario.name}\n"
        f"N={population:,}, R0={scenario.R0}, {n_runs} Monte Carlo runs",
        fontsize=14,
        fontweight="bold",
    )

    compartments = [
        ("S — Susceptible", ode["S"], mc.S, COLOR_S),
        ("E — Exposed", ode["E"], mc.E, COLOR_E),
        ("I — Infectious", ode["I"], mc.I, COLOR_I),
        ("R — Removed", ode["R"], mc.R, COLOR_R),
    ]

    for ax, (label, ode_curve, mc_data, color) in zip(axes.flat, compartments):
        # Normalize to fraction of population
        ode_frac = ode_curve / population
        mc_frac = mc_data / population

        # DES scatter: each run as semi-transparent dots
        for run_idx in range(mc.n_runs):
            ax.scatter(
                mc.t, mc_frac[run_idx],
                color=color, alpha=0.08, s=3, rasterized=True,
            )

        # DES mean as dashed line
        mc_mean = mc_frac.mean(axis=0)
        ax.plot(mc.t, mc_mean, color=color, linestyle="--", linewidth=1.5,
                label="DES mean", alpha=0.9)

        # SEIR ODE as solid line
        ax.plot(ode["t"], ode_frac, color="black", linewidth=2.0,
                label="SEIR ODE", alpha=0.85)

        ax.set_title(label, fontsize=12)
        ax.set_xlabel("Day")
        ax.set_ylabel("Fraction of Population")
        ax.legend(fontsize=9, loc="best")
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))

    plt.tight_layout(rect=[0, 0, 1, 0.93])

    fname = RESULTS_DIR / f"01_seir_vs_des_{scenario.name.lower().replace(' ', '_').replace('-', '_')}_N{population}.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"  Saved: {fname}")
    plt.close(fig)

    return ode, mc


# ── Plot 2: Convergence by Population Size ───────────────────────

def plot_convergence_by_N(
    scenario: EpidemicScenario,
    populations: list[int],
    n_runs: int = 10,
    duration_days: int = 180,
    avg_contacts: int = 10,
):
    """
    Show DES variance shrinking toward SEIR as N increases.

    Proves: DES → SEIR as N → ∞.
    """
    print(f"\n{'='*60}")
    print(f"Plot 2: Convergence by N — {scenario.name}")
    print(f"  Populations: {populations}")
    print(f"{'='*60}")

    fig, axes = plt.subplots(1, len(populations), figsize=(5 * len(populations), 5),
                             sharey=True)
    if len(populations) == 1:
        axes = [axes]

    fig.suptitle(
        f"DES Convergence to SEIR — {scenario.name} (R0={scenario.R0})\n"
        f"Infectious (I) compartment, {n_runs} runs each",
        fontsize=14,
        fontweight="bold",
    )

    for ax, N in zip(axes, populations):
        # SEIR ODE
        seir_params = scenario.to_seir_params(N)
        ode = solve_seir(seir_params, days=duration_days, initial_infected=3)
        ode_I_frac = ode["I"] / N

        # Monte Carlo DES
        def make_config(seed, pop=N):
            return scenario.to_des_config(
                population=pop,
                duration_days=duration_days,
                avg_contacts=avg_contacts,
                random_seed=seed,
            )

        print(f"\n  N={N:,}:")
        mc = run_monte_carlo(make_config, n_runs=n_runs)
        mc_I_frac = mc.I / N

        # Plot each run
        for run_idx in range(mc.n_runs):
            ax.plot(mc.t, mc_I_frac[run_idx], color=COLOR_I, alpha=0.2, linewidth=0.8)

        # DES mean ± std band
        mc_mean = mc_I_frac.mean(axis=0)
        mc_std = mc_I_frac.std(axis=0)
        ax.fill_between(mc.t, mc_mean - mc_std, mc_mean + mc_std,
                         color=COLOR_I, alpha=0.15, label="DES ±1σ")
        ax.plot(mc.t, mc_mean, color=COLOR_I, linestyle="--", linewidth=1.5,
                label="DES mean")

        # SEIR ODE
        ax.plot(ode["t"], ode_I_frac, color="black", linewidth=2.0,
                label="SEIR ODE")

        ax.set_title(f"N = {N:,}", fontsize=12)
        ax.set_xlabel("Day")
        if ax == axes[0]:
            ax.set_ylabel("Infected (fraction)")
        ax.legend(fontsize=8, loc="upper right")
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))

    plt.tight_layout(rect=[0, 0, 1, 0.90])

    fname = RESULTS_DIR / f"02_convergence_by_N_{scenario.name.lower().replace(' ', '_').replace('-', '_')}.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"\n  Saved: {fname}")
    plt.close(fig)


# ── Plot 3: Key Metrics Comparison ───────────────────────────────

def plot_metrics_comparison(
    scenario: EpidemicScenario,
    ode: dict,
    mc,
    population: int,
):
    """
    Bar chart comparing key epidemic metrics: SEIR vs DES.

    Metrics: peak I day, peak I count, final attack rate.
    """
    print(f"\n{'='*60}")
    print(f"Plot 3: Metrics Comparison — {scenario.name}")
    print(f"{'='*60}")

    # SEIR metrics
    seir_peak_I = ode["I"].max() / population * 100
    seir_peak_day = ode["t"][ode["I"].argmax()]
    seir_attack = (population - ode["S"][-1]) / population * 100

    # DES metrics (per-run)
    des_peak_I_vals = mc.I.max(axis=1) / population * 100
    des_peak_day_vals = np.array([mc.t[run.argmax()] for run in mc.I])
    des_attack_vals = (population - mc.S[:, -1]) / population * 100

    metrics = [
        ("Peak Infected\n(% of N)", seir_peak_I, des_peak_I_vals),
        ("Peak Day", seir_peak_day, des_peak_day_vals),
        ("Final Attack Rate\n(%)", seir_attack, des_attack_vals),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    fig.suptitle(
        f"Key Metrics — {scenario.name} (N={population:,}, R0={scenario.R0})",
        fontsize=14,
        fontweight="bold",
    )

    for ax, (label, seir_val, des_vals) in zip(axes, metrics):
        des_mean = des_vals.mean()
        des_std = des_vals.std()

        bars = ax.bar(
            ["SEIR ODE", "DES Mean"],
            [seir_val, des_mean],
            color=[COLOR_S, COLOR_I],
            edgecolor="black",
            linewidth=0.8,
            width=0.5,
        )

        # Error bar on DES
        ax.errorbar(1, des_mean, yerr=des_std, fmt="none", color="black",
                     capsize=8, capthick=1.5, linewidth=1.5)

        # Value labels
        for bar, val in zip(bars, [seir_val, des_mean]):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                    f"{val:.1f}", ha="center", va="bottom", fontsize=10,
                    fontweight="bold")

        ax.set_ylabel(label)
        ax.set_title(label, fontsize=11)

    # Print summary table
    print(f"\n  {'Metric':<25} {'SEIR':>10} {'DES Mean':>10} {'DES Std':>10} {'Δ%':>10}")
    print(f"  {'─'*65}")
    for label, seir_val, des_vals in metrics:
        clean_label = label.replace('\n', ' ')
        des_mean = des_vals.mean()
        des_std = des_vals.std()
        delta = abs(seir_val - des_mean) / seir_val * 100 if seir_val != 0 else 0
        print(f"  {clean_label:<25} {seir_val:>10.1f} {des_mean:>10.1f} {des_std:>10.1f} {delta:>9.1f}%")

    plt.tight_layout(rect=[0, 0, 1, 0.90])

    fname = RESULTS_DIR / f"03_metrics_{scenario.name.lower().replace(' ', '_').replace('-', '_')}_N{population}.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"  Saved: {fname}")
    plt.close(fig)


# ── Main ─────────────────────────────────────────────────────────

def main():
    ensure_results_dir()

    # ── Configuration ────────────────────────────────────────────
    scenario = COVID_LIKE
    population = 5000
    n_runs = 15
    duration_days = 180
    avg_contacts = 10

    print(f"╔{'═'*58}╗")
    print(f"║  DES ↔ SEIR Convergence Validation                       ║")
    print(f"║  Scenario: {scenario.name:<46} ║")
    print(f"║  Population: {population:<44,} ║")
    print(f"║  Monte Carlo runs: {n_runs:<38} ║")
    print(f"╚{'═'*58}╝")

    # ── Plot 1: The Money Shot ───────────────────────────────────
    ode, mc = plot_seir_vs_des(
        scenario=scenario,
        population=population,
        n_runs=n_runs,
        duration_days=duration_days,
        avg_contacts=avg_contacts,
    )

    # ── Plot 2: Convergence by N ─────────────────────────────────
    plot_convergence_by_N(
        scenario=scenario,
        populations=[500, 2000, 10000],
        n_runs=10,
        duration_days=duration_days,
        avg_contacts=avg_contacts,
    )

    # ── Plot 3: Metrics Comparison ───────────────────────────────
    plot_metrics_comparison(
        scenario=scenario,
        ode=ode,
        mc=mc,
        population=population,
    )

    print(f"\n{'='*60}")
    print(f"All plots saved to: {RESULTS_DIR.resolve()}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
