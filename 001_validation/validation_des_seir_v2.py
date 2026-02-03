#!/usr/bin/env python3
"""
DES <-> SEIR Convergence Validation (v2 — Production Backend).

Re-validates 001 using the production 7-state CityDES engine from
simulation_app/backend/city_des_extended.py, proving the same
DES->SEIR convergence holds with the production code.

With severe_fraction=0 and n_providers=0, the 7-state model
reduces to S -> E -> I_minor -> R, exactly matching the SEIR ODE.

A secondary validation with severity enabled shows SEIR-D
convergence (S, E, I_total, R, D).

Outputs saved to 001_validation/results_v2/ directory.

Usage (from project root):
    python 001_validation/validation_des_seir_v2.py
"""

import sys
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
_BACKEND_DIR = str(_PROJECT_ROOT / "simulation_app" / "backend")
_DES_SYSTEM_DIR = str(_PROJECT_ROOT / "des_system")

# Production backend first, then des_system for shared EpidemicScenario/ODE
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
from seir_ode import SEIRParams, solve_seir

# Also define an SEIR-D ODE for the severity validation
from scipy.integrate import odeint

# ── Plot Configuration ───────────────────────────────────────────
sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)
PALETTE = sns.color_palette("muted")
COLOR_S = PALETTE[0]  # blue
COLOR_E = PALETTE[1]  # orange
COLOR_I = PALETTE[3]  # red
COLOR_R = PALETTE[2]  # green
COLOR_D = PALETTE[4]  # purple

RESULTS_DIR = _SCRIPT_DIR / "results_v2"


def ensure_results_dir():
    RESULTS_DIR.mkdir(exist_ok=True)


# ── Run single CityDES ──────────────────────────────────────────

def run_single_des(
    scenario: EpidemicScenario,
    population: int,
    duration_days: int,
    seed: int,
    avg_contacts: int = 10,
    severe_fraction: float = 0.0,
    initial_infected: int = 3,
):
    """
    Run a single CityDES simulation, recording compartment counts daily.

    Returns dict with arrays: t, S, E, I, I_minor, I_needs, I_care, R, D
    """
    city = CityDES(
        n_people=population,
        scenario=scenario,
        seed_infected=initial_infected,
        random_seed=seed,
        avg_contacts=avg_contacts,
        rewire_prob=0.4,
        daily_contact_rate=0.5,
        p_random=0.15,
        # Disable providers for pure SEIR comparison
        n_providers=0,
        # Severity parameters
        severe_fraction=severe_fraction,
        care_survival_prob=0.85,
        base_daily_death_prob=0.02,
        death_prob_increase_per_day=0.015,
        gamma_shape=6.25,
    )

    t = np.arange(0, duration_days + 1, dtype=float)
    S = np.zeros(duration_days + 1)
    E = np.zeros(duration_days + 1)
    I_minor = np.zeros(duration_days + 1)
    I_needs = np.zeros(duration_days + 1)
    I_care = np.zeros(duration_days + 1)
    R = np.zeros(duration_days + 1)
    D = np.zeros(duration_days + 1)

    # Day 0
    S[0] = city.S
    E[0] = city.E
    I_minor[0] = city.I_minor
    I_needs[0] = city.I_needs_care
    I_care[0] = city.I_receiving_care
    R[0] = city.R
    D[0] = city.D

    for day in range(1, duration_days + 1):
        city.step(until=day)
        S[day] = city.S
        E[day] = city.E
        I_minor[day] = city.I_minor
        I_needs[day] = city.I_needs_care
        I_care[day] = city.I_receiving_care
        R[day] = city.R
        D[day] = city.D

    return {
        "t": t,
        "S": S, "E": E,
        "I": I_minor + I_needs + I_care,  # Total infectious
        "I_minor": I_minor, "I_needs": I_needs, "I_care": I_care,
        "R": R, "D": D,
    }


def run_monte_carlo_des(
    scenario: EpidemicScenario,
    population: int,
    duration_days: int,
    n_runs: int,
    avg_contacts: int = 10,
    severe_fraction: float = 0.0,
    initial_infected: int = 3,
):
    """
    Run multiple DES replicates using the production CityDES engine.

    Returns dict with arrays of shape (n_runs, duration_days+1) for each compartment.
    """
    n_days = duration_days + 1
    all_S = np.zeros((n_runs, n_days))
    all_E = np.zeros((n_runs, n_days))
    all_I = np.zeros((n_runs, n_days))
    all_R = np.zeros((n_runs, n_days))
    all_D = np.zeros((n_runs, n_days))
    t = np.arange(0, n_days, dtype=float)

    for i in range(n_runs):
        seed = 1000 + i * 137
        result = run_single_des(
            scenario=scenario,
            population=population,
            duration_days=duration_days,
            seed=seed,
            avg_contacts=avg_contacts,
            severe_fraction=severe_fraction,
            initial_infected=initial_infected,
        )
        all_S[i] = result["S"]
        all_E[i] = result["E"]
        all_I[i] = result["I"]
        all_R[i] = result["R"]
        all_D[i] = result["D"]
        print(f"    Run {i+1}/{n_runs} complete (peak I={result['I'].max():.0f})")

    return {"t": t, "S": all_S, "E": all_E, "I": all_I, "R": all_R, "D": all_D,
            "n_runs": n_runs}


# ── SEIR-D ODE (for severity validation) ─────────────────────────

def seird_derivatives(y, t, params, severe_fraction, care_survival_prob):
    """
    5-compartment SEIR-D derivatives.

    Same as SEIR but with severity branching:
    - Fraction (1-f) of I recovers directly
    - Fraction f needs care; of those, c survive and (1-c) die
    - Net: dR = gamma * [(1-f) + f*c] * I
            dD = gamma * f * (1-c) * I
    """
    S, E, I, R, D = y
    N = params.population

    force = params.beta * S * I / N

    dS = -force
    dE = force - params.sigma * E
    dI = params.sigma * E - params.gamma * I
    recovery_rate = params.gamma * ((1 - severe_fraction) + severe_fraction * care_survival_prob)
    death_rate = params.gamma * severe_fraction * (1 - care_survival_prob)
    dR = recovery_rate * I
    dD = death_rate * I

    return [dS, dE, dI, dR, dD]


def solve_seird(params, days, initial_infected=3, severe_fraction=0.15, care_survival_prob=0.85):
    """Solve SEIR-D ODE system."""
    S0 = params.population - initial_infected
    y0 = [S0, 0, initial_infected, 0, 0]
    t = np.linspace(0, days, days + 1)
    sol = odeint(seird_derivatives, y0, t,
                 args=(params, severe_fraction, care_survival_prob))
    return {"t": t, "S": sol[:, 0], "E": sol[:, 1], "I": sol[:, 2],
            "R": sol[:, 3], "D": sol[:, 4]}


# ── Plot 1: SEIR Curves + DES Scatter (Pure SEIR, no severity) ──

def plot_seir_vs_des(
    scenario: EpidemicScenario,
    population: int,
    n_runs: int,
    duration_days: int = 180,
    avg_contacts: int = 10,
):
    """
    Overlay smooth SEIR ODE curves with production DES Monte Carlo scatter.

    severe_fraction=0 so the 7-state model reduces to pure S-E-I-R.
    This is the primary validation: visual proof that the production DES
    converges to the deterministic SEIR ODE.
    """
    print(f"\n{'='*60}")
    print(f"Plot 1: SEIR vs Production DES — {scenario.name}")
    print(f"  N={population}, runs={n_runs}, duration={duration_days}d")
    print(f"  severe_fraction=0 (pure SEIR mode)")
    print(f"{'='*60}")

    # 1. Solve SEIR ODE
    seir_params = scenario.to_seir_params(population)
    ode = solve_seir(seir_params, days=duration_days, initial_infected=3)

    # 2. Run Monte Carlo DES (production CityDES)
    print(f"  Running {n_runs} DES replicates...")
    mc = run_monte_carlo_des(
        scenario=scenario,
        population=population,
        duration_days=duration_days,
        n_runs=n_runs,
        avg_contacts=avg_contacts,
        severe_fraction=0.0,
    )

    # 3. Plot
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(
        f"Production DES <-> SEIR Convergence — {scenario.name}\n"
        f"N={population:,}, R0={scenario.R0}, {n_runs} Monte Carlo runs\n"
        f"(CityDES 7-state with severe_fraction=0)",
        fontsize=13,
        fontweight="bold",
    )

    compartments = [
        ("S - Susceptible", ode["S"], mc["S"], COLOR_S),
        ("E - Exposed", ode["E"], mc["E"], COLOR_E),
        ("I - Infectious", ode["I"], mc["I"], COLOR_I),
        ("R - Recovered", ode["R"], mc["R"], COLOR_R),
    ]

    for ax, (label, ode_curve, mc_data, color) in zip(axes.flat, compartments):
        ode_frac = ode_curve / population
        mc_frac = mc_data / population

        # DES scatter: each run as semi-transparent dots
        for run_idx in range(mc["n_runs"]):
            ax.scatter(
                mc["t"], mc_frac[run_idx],
                color=color, alpha=0.08, s=3, rasterized=True,
            )

        # DES mean as dashed line
        mc_mean = mc_frac.mean(axis=0)
        ax.plot(mc["t"], mc_mean, color=color, linestyle="--", linewidth=1.5,
                label="DES mean", alpha=0.9)

        # SEIR ODE as solid line
        ax.plot(ode["t"], ode_frac, color="black", linewidth=2.0,
                label="SEIR ODE", alpha=0.85)

        ax.set_title(label, fontsize=12)
        ax.set_xlabel("Day")
        ax.set_ylabel("Fraction of Population")
        ax.legend(fontsize=9, loc="best")
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))

    plt.tight_layout(rect=[0, 0, 1, 0.90])

    fname = RESULTS_DIR / f"01_seir_vs_des_{_scenario_slug(scenario)}_N{population}.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"  Saved: {fname}")
    plt.close(fig)

    return ode, mc


# ── Plot 2: Convergence by Population Size ───────────────────────

def plot_convergence_by_N(
    scenario: EpidemicScenario,
    populations: list,
    n_runs: int = 10,
    duration_days: int = 180,
    avg_contacts: int = 10,
):
    """
    Show DES variance shrinking toward SEIR as N increases.
    Proves: DES -> SEIR as N -> infinity.
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
        f"Production DES Convergence to SEIR — {scenario.name} (R0={scenario.R0})\n"
        f"Infectious (I) compartment, {n_runs} runs each",
        fontsize=13,
        fontweight="bold",
    )

    for ax, N in zip(axes, populations):
        # SEIR ODE
        seir_params = scenario.to_seir_params(N)
        ode = solve_seir(seir_params, days=duration_days, initial_infected=3)
        ode_I_frac = ode["I"] / N

        # Monte Carlo DES
        print(f"\n  N={N:,}:")
        mc = run_monte_carlo_des(
            scenario=scenario,
            population=N,
            duration_days=duration_days,
            n_runs=n_runs,
            avg_contacts=avg_contacts,
            severe_fraction=0.0,
        )
        mc_I_frac = mc["I"] / N

        # Plot each run
        for run_idx in range(mc["n_runs"]):
            ax.plot(mc["t"], mc_I_frac[run_idx], color=COLOR_I, alpha=0.2, linewidth=0.8)

        # DES mean +/- std band
        mc_mean = mc_I_frac.mean(axis=0)
        mc_std = mc_I_frac.std(axis=0)
        ax.fill_between(mc["t"], mc_mean - mc_std, mc_mean + mc_std,
                         color=COLOR_I, alpha=0.15, label="DES +/-1s")
        ax.plot(mc["t"], mc_mean, color=COLOR_I, linestyle="--", linewidth=1.5,
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

    plt.tight_layout(rect=[0, 0, 1, 0.88])

    fname = RESULTS_DIR / f"02_convergence_by_N_{_scenario_slug(scenario)}.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"\n  Saved: {fname}")
    plt.close(fig)


# ── Plot 3: Key Metrics Comparison ───────────────────────────────

def plot_metrics_comparison(
    scenario: EpidemicScenario,
    ode: dict,
    mc: dict,
    population: int,
):
    """
    Bar chart comparing key epidemic metrics: SEIR ODE vs Production DES.
    """
    print(f"\n{'='*60}")
    print(f"Plot 3: Metrics Comparison — {scenario.name}")
    print(f"{'='*60}")

    # SEIR metrics
    seir_peak_I = ode["I"].max() / population * 100
    seir_peak_day = ode["t"][ode["I"].argmax()]
    seir_attack = (population - ode["S"][-1]) / population * 100

    # DES metrics (per-run)
    des_peak_I_vals = mc["I"].max(axis=1) / population * 100
    des_peak_day_vals = np.array([mc["t"][run.argmax()] for run in mc["I"]])
    des_attack_vals = (population - mc["S"][:, -1]) / population * 100

    metrics = [
        ("Peak Infected\n(% of N)", seir_peak_I, des_peak_I_vals),
        ("Peak Day", seir_peak_day, des_peak_day_vals),
        ("Final Attack Rate\n(%)", seir_attack, des_attack_vals),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    fig.suptitle(
        f"Key Metrics — {scenario.name} (N={population:,}, R0={scenario.R0})\n"
        f"Production CityDES (7-state, severe_fraction=0)",
        fontsize=13,
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
    print(f"\n  {'Metric':<25} {'SEIR':>10} {'DES Mean':>10} {'DES Std':>10} {'Delta%':>10}")
    print(f"  {'─'*65}")
    for label, seir_val, des_vals in metrics:
        clean_label = label.replace('\n', ' ')
        des_mean = des_vals.mean()
        des_std = des_vals.std()
        delta = abs(seir_val - des_mean) / seir_val * 100 if seir_val != 0 else 0
        print(f"  {clean_label:<25} {seir_val:>10.1f} {des_mean:>10.1f} {des_std:>10.1f} {delta:>9.1f}%")

    plt.tight_layout(rect=[0, 0, 1, 0.88])

    fname = RESULTS_DIR / f"03_metrics_{_scenario_slug(scenario)}_N{population}.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"  Saved: {fname}")
    plt.close(fig)


# ── Plot 4: SEIR-D Convergence (with severity enabled) ──────────

def plot_seird_validation(
    scenario: EpidemicScenario,
    population: int,
    n_runs: int,
    duration_days: int = 180,
    severe_fraction: float = 0.15,
    care_survival_prob: float = 0.85,
):
    """
    Validate DES with severity enabled against the SEIR-D ODE.

    This is the stronger test: the 7-state model's severity branching
    (I_minor -> I_needs_care -> D or I_receiving_care -> R/D) should
    produce aggregate S, E, I_total, R, D curves matching the SEIR-D ODE.

    Note: The DES has escalating daily death probability for untreated
    patients, which the simple SEIR-D ODE approximates as a constant
    fraction. Expect slightly more variance here than in the pure SEIR case.
    """
    print(f"\n{'='*60}")
    print(f"Plot 4: SEIR-D Validation — {scenario.name}")
    print(f"  N={population}, runs={n_runs}, severe_fraction={severe_fraction}")
    print(f"{'='*60}")

    # 1. Solve SEIR-D ODE
    seir_params = scenario.to_seir_params(population)
    ode = solve_seird(
        seir_params, days=duration_days, initial_infected=3,
        severe_fraction=severe_fraction, care_survival_prob=care_survival_prob,
    )

    # 2. Run Monte Carlo DES with severity
    print(f"  Running {n_runs} DES replicates with severity...")
    mc = run_monte_carlo_des(
        scenario=scenario,
        population=population,
        duration_days=duration_days,
        n_runs=n_runs,
        severe_fraction=severe_fraction,
    )

    # 3. Plot: 5-panel (S, E, I, R, D)
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle(
        f"Production DES <-> SEIR-D Convergence — {scenario.name}\n"
        f"N={population:,}, R0={scenario.R0}, severe_fraction={severe_fraction}, {n_runs} runs",
        fontsize=13,
        fontweight="bold",
    )

    compartments = [
        ("S - Susceptible", ode["S"], mc["S"], COLOR_S),
        ("E - Exposed", ode["E"], mc["E"], COLOR_E),
        ("I - Infectious (total)", ode["I"], mc["I"], COLOR_I),
        ("R - Recovered", ode["R"], mc["R"], COLOR_R),
        ("D - Dead", ode["D"], mc["D"], COLOR_D),
    ]

    for idx, (label, ode_curve, mc_data, color) in enumerate(compartments):
        ax = axes.flat[idx]
        ode_frac = ode_curve / population
        mc_frac = mc_data / population

        # DES mean +/- std
        mc_mean = mc_frac.mean(axis=0)
        mc_std = mc_frac.std(axis=0)
        ax.fill_between(mc["t"], mc_mean - mc_std, mc_mean + mc_std,
                         color=color, alpha=0.15, label="DES +/-1s")
        ax.plot(mc["t"], mc_mean, color=color, linestyle="--", linewidth=1.5,
                label="DES mean", alpha=0.9)

        # SEIR-D ODE
        ax.plot(ode["t"], ode_frac, color="black", linewidth=2.0,
                label="SEIR-D ODE", alpha=0.85)

        ax.set_title(label, fontsize=12)
        ax.set_xlabel("Day")
        ax.set_ylabel("Fraction of Population")
        ax.legend(fontsize=9, loc="best")
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))

    # Hide the 6th subplot
    axes.flat[5].set_visible(False)

    # Print D-compartment metrics
    ode_final_D = ode["D"][-1]
    des_final_D = mc["D"][:, -1]
    print(f"\n  Final Deaths:")
    print(f"    SEIR-D ODE:  {ode_final_D:.0f} ({ode_final_D/population*100:.2f}%)")
    print(f"    DES mean:    {des_final_D.mean():.0f} +/- {des_final_D.std():.0f}")
    print(f"    DES range:   [{des_final_D.min():.0f}, {des_final_D.max():.0f}]")

    plt.tight_layout(rect=[0, 0, 1, 0.88])

    fname = RESULTS_DIR / f"04_seird_validation_{_scenario_slug(scenario)}_N{population}.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"  Saved: {fname}")
    plt.close(fig)


# ── Helpers ──────────────────────────────────────────────────────

def _scenario_slug(scenario: EpidemicScenario) -> str:
    return scenario.name.lower().replace(" ", "_").replace("-", "_")


# ── Main ─────────────────────────────────────────────────────────

def main():
    ensure_results_dir()

    scenario = COVID_LIKE
    population = 5000
    n_runs = 15
    duration_days = 180
    avg_contacts = 10

    print(f"{'='*62}")
    print(f"  DES <-> SEIR Convergence Validation (v2 — Production Backend)")
    print(f"  Engine: simulation_app/backend/city_des_extended.py (CityDES)")
    print(f"  Scenario: {scenario.name}")
    print(f"  Population: {population:,}")
    print(f"  Monte Carlo runs: {n_runs}")
    print(f"{'='*62}")
    print(scenario.describe())

    # -- Plot 1: The Money Shot (pure SEIR, no severity) ──────────
    ode, mc = plot_seir_vs_des(
        scenario=scenario,
        population=population,
        n_runs=n_runs,
        duration_days=duration_days,
        avg_contacts=avg_contacts,
    )

    # -- Plot 2: Convergence by N (pure SEIR) ─────────────────────
    plot_convergence_by_N(
        scenario=scenario,
        populations=[500, 2000, 5000, 10000],
        n_runs=10,
        duration_days=duration_days,
        avg_contacts=avg_contacts,
    )

    # -- Plot 3: Metrics Comparison (pure SEIR) ───────────────────
    plot_metrics_comparison(
        scenario=scenario,
        ode=ode,
        mc=mc,
        population=population,
    )

    # -- Plot 4: SEIR-D Validation (with severity enabled) ────────
    plot_seird_validation(
        scenario=scenario,
        population=population,
        n_runs=15,
        duration_days=duration_days,
        severe_fraction=0.15,
        care_survival_prob=0.85,
    )

    print(f"\n{'='*62}")
    print(f"All plots saved to: {RESULTS_DIR.resolve()}")
    print(f"{'='*62}")


if __name__ == "__main__":
    main()
