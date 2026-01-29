#!/usr/bin/env python3
"""
Agent-Based DES vs Vanilla DES Validation.

Proves that IntelligentDiseaseModel with NullBehavior produces
bit-for-bit identical results to the original DiseaseModel,
then shows the behavioral delta when isolation is enabled.

Two experiments:
1. NullBehavior equivalence test (must match vanilla DES exactly)
2. StatisticalBehavior sweep (isolation_prob = 0.0, 0.1, 0.3, 0.5)
   with 100 Monte Carlo runs and variability bands

Usage (from project root):
    python 002_agent_based_des/validation_agent_vs_des.py
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "des_system"))
sys.path.insert(0, str(_PROJECT_ROOT / "agent_based_des"))

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import seaborn as sns

from config import SimulationConfig
from simulation import run_simulation
from agent_simulation import run_agent_simulation
from behavior import NullBehavior, StatisticalBehavior
from validation_config import COVID_LIKE
from seir_ode import solve_seir

# ── Plot Configuration ───────────────────────────────────────────
sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)
PALETTE = sns.color_palette("muted")
COLOR_VANILLA = PALETTE[0]   # blue
COLOR_SEIR = "black"

RESULTS_DIR = Path(__file__).parent / "results"

# Minimum attack rate (%) to consider an epidemic as "established"
# Below this, the epidemic died out and peak day is meaningless.
EPIDEMIC_THRESHOLD_PCT = 5.0


def ensure_results_dir():
    RESULTS_DIR.mkdir(exist_ok=True)


def _extract_daily_I(result, population: int) -> np.ndarray:
    """Extract daily infectious count (I = infectious + symptomatic) from snapshots."""
    counts = []
    for snap in result.daily_snapshots:
        sc = snap["state_counts"]
        counts.append(sc.get("infectious", 0) + sc.get("symptomatic", 0))
    return np.array(counts, dtype=float)


def _extract_daily_S(result, population: int) -> np.ndarray:
    """Extract daily susceptible count from snapshots."""
    return np.array(
        [snap["state_counts"].get("susceptible", 0) for snap in result.daily_snapshots],
        dtype=float,
    )


# ── Experiment 1: NullBehavior Equivalence ───────────────────────

def test_null_equivalence(
    population: int = 5000,
    duration_days: int = 180,
    n_seeds: int = 5,
):
    """
    Verify that IntelligentDiseaseModel + NullBehavior produces
    identical results to vanilla DiseaseModel.

    NullBehavior makes no random draws, so with the same seed the
    random state should be perfectly synchronized.

    Produces a figure overlaying vanilla and agent curves per seed.
    """
    print(f"\n{'='*60}")
    print(f"Experiment 1: NullBehavior Equivalence Test")
    print(f"  N={population}, duration={duration_days}d, {n_seeds} seeds")
    print(f"{'='*60}")

    all_pass = True
    seed_results = []  # (seed, vanilla_result, agent_result, match)

    for i in range(n_seeds):
        seed = 42 + i

        # Vanilla DES
        vanilla_config = COVID_LIKE.to_des_config(
            population=population,
            duration_days=duration_days,
            random_seed=seed,
        )
        vanilla_result = run_simulation(vanilla_config)

        # Agent DES with NullBehavior
        agent_config = COVID_LIKE.to_des_config(
            population=population,
            duration_days=duration_days,
            random_seed=seed,
        )
        agent_result = run_agent_simulation(
            agent_config,
            behavior_factory=lambda pid: NullBehavior(),
        )

        # Compare
        v_infections = vanilla_result.total_infections
        a_infections = agent_result.total_infections
        v_deaths = vanilla_result.total_deaths
        a_deaths = agent_result.total_deaths
        v_attack = vanilla_result.infection_rate
        a_attack = agent_result.infection_rate

        match = (v_infections == a_infections and v_deaths == a_deaths)
        status = "PASS" if match else "FAIL"
        if not match:
            all_pass = False

        seed_results.append((seed, vanilla_result, agent_result, match))

        print(f"  Seed {seed}: {status}")
        print(f"    Vanilla: infections={v_infections}, deaths={v_deaths}, attack={v_attack:.1f}%")
        print(f"    Agent:   infections={a_infections}, deaths={a_deaths}, attack={a_attack:.1f}%")

    print(f"\n  Overall: {'ALL PASS' if all_pass else 'SOME FAILED'}")

    # ── Equivalence figure ─────────────────────────────────────────
    _plot_equivalence(seed_results, population, duration_days)

    return all_pass


def _plot_equivalence(seed_results, population, duration_days):
    """
    Plot vanilla DES vs agent DES (NullBehavior) for each seed.

    Layout: one subplot per seed showing overlaid infectious curves,
    plus a residual (difference) trace to prove exact match.
    """
    n_seeds = len(seed_results)
    fig, axes = plt.subplots(2, n_seeds, figsize=(4 * n_seeds, 7),
                              gridspec_kw={"height_ratios": [3, 1]},
                              sharex=True)
    if n_seeds == 1:
        axes = axes.reshape(2, 1)

    fig.suptitle(
        "NullBehavior Equivalence: Vanilla DES vs Agent DES\n"
        f"N={population:,}, {duration_days} days — identical seeds",
        fontsize=13, fontweight="bold",
    )

    t = np.arange(1, duration_days + 1, dtype=float)

    for col, (seed, v_result, a_result, match) in enumerate(seed_results):
        ax_main = axes[0, col]
        ax_resid = axes[1, col]

        v_I = _extract_daily_I(v_result, population)
        a_I = _extract_daily_I(a_result, population)
        plot_len = min(len(t), len(v_I), len(a_I))

        v_frac = v_I[:plot_len] / population
        a_frac = a_I[:plot_len] / population
        residual = a_frac - v_frac

        # Main panel: overlaid curves
        ax_main.plot(t[:plot_len], v_frac, color=COLOR_VANILLA,
                     linewidth=2.5, label="Vanilla DES", alpha=0.9)
        ax_main.plot(t[:plot_len], a_frac, color="orangered",
                     linewidth=1.2, linestyle="--", label="Agent (Null)", alpha=0.9)

        status = "PASS" if match else "FAIL"
        status_color = "green" if match else "red"
        ax_main.set_title(f"Seed {seed}  [{status}]", fontsize=10,
                          color=status_color, fontweight="bold")
        ax_main.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))

        if col == 0:
            ax_main.set_ylabel("Infected fraction")
            ax_main.legend(fontsize=8, loc="upper right")

        # Residual panel: difference
        ax_resid.plot(t[:plot_len], residual, color="black", linewidth=0.8)
        ax_resid.axhline(0, color="gray", linewidth=0.5, linestyle=":")
        ax_resid.set_xlabel("Day")
        max_resid = np.max(np.abs(residual))
        if max_resid == 0:
            ax_resid.set_ylim(-0.001, 0.001)
            ax_resid.text(
                duration_days / 2, 0,
                "residual = 0 (exact match)",
                ha="center", va="center", fontsize=7, color="green",
                fontweight="bold",
            )
        else:
            ax_resid.set_ylim(-max_resid * 1.5, max_resid * 1.5)
        if col == 0:
            ax_resid.set_ylabel("Agent − Vanilla")

    plt.tight_layout(rect=[0, 0, 1, 0.90])
    fname = RESULTS_DIR / "00_null_equivalence.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"  Saved: {fname}")
    plt.close(fig)


# ── Run collection helper ────────────────────────────────────────

def _collect_runs(runner_fn, n_runs: int, label: str, population: int):
    """
    Run simulations and collect daily I and S arrays.

    Args:
        runner_fn: Callable(seed) -> SimulationResult
        n_runs: Number of MC runs
        label: Label for progress printing
        population: Population size

    Returns:
        (I_array, S_array) each shape (n_runs, n_days)
    """
    I_runs, S_runs = [], []
    for i in range(n_runs):
        if (i + 1) % 25 == 0 or i == 0:
            print(f"    {label}: run {i+1}/{n_runs}...", flush=True)
        result = runner_fn(i)
        I_runs.append(_extract_daily_I(result, population))
        S_runs.append(_extract_daily_S(result, population))

    return np.array(I_runs, dtype=float), np.array(S_runs, dtype=float)


# ── Metric extraction with die-out handling ──────────────────────

def _compute_metrics(I_arr, S_arr, t, population):
    """
    Compute peak I, peak day, and attack rate from MC arrays.

    Peak day is computed only from runs where the epidemic established
    (attack rate > EPIDEMIC_THRESHOLD_PCT). This prevents die-out runs
    from pulling the average peak day down to nonsense values.

    Returns dict with mean, std, and n_established for each metric.
    """
    n_runs = I_arr.shape[0]

    # Per-run metrics
    peak_I_vals = I_arr.max(axis=1) / population * 100
    peak_day_vals = np.array([t[run.argmax()] for run in I_arr])
    attack_vals = (population - S_arr[:, -1]) / population * 100

    # Identify established epidemics
    established = attack_vals > EPIDEMIC_THRESHOLD_PCT
    n_established = int(established.sum())

    # Peak day: only from established runs
    if n_established > 0:
        peak_day_mean = peak_day_vals[established].mean()
        peak_day_std = peak_day_vals[established].std()
    else:
        peak_day_mean = 0.0
        peak_day_std = 0.0

    return {
        "peak_I_mean": peak_I_vals.mean(),
        "peak_I_std": peak_I_vals.std(),
        "peak_day_mean": peak_day_mean,
        "peak_day_std": peak_day_std,
        "attack_mean": attack_vals.mean(),
        "attack_std": attack_vals.std(),
        "n_established": n_established,
        "n_runs": n_runs,
    }


# ── Experiment 2: Isolation Probability Sweep ────────────────────

def sweep_isolation(
    population: int = 5000,
    duration_days: int = 180,
    n_runs: int = 100,
    isolation_probs: list[float] = None,
):
    """
    Run agent DES with varying isolation probabilities and compare
    to vanilla DES and SEIR reference. Shows variability with +/-1 sigma bands.
    """
    if isolation_probs is None:
        isolation_probs = [0.0, 0.1, 0.3, 0.5]

    print(f"\n{'='*60}")
    print(f"Experiment 2: Isolation Probability Sweep")
    print(f"  N={population}, {n_runs} runs per condition")
    print(f"  Isolation probs: {isolation_probs}")
    print(f"  Epidemic threshold: {EPIDEMIC_THRESHOLD_PCT}% attack rate")
    print(f"{'='*60}")

    # SEIR reference
    seir_params = COVID_LIKE.to_seir_params(population)
    ode = solve_seir(seir_params, days=duration_days, initial_infected=3)
    ode_I_frac = ode["I"] / population

    # Vanilla DES reference
    print(f"\n  Vanilla DES:")
    vanilla_I, vanilla_S = _collect_runs(
        runner_fn=lambda i: run_simulation(COVID_LIKE.to_des_config(
            population=population,
            duration_days=duration_days,
            random_seed=1000 + i,
        )),
        n_runs=n_runs,
        label="Vanilla",
        population=population,
    )

    # Agent DES for each isolation probability
    agent_data = {}
    for iso_prob in isolation_probs:
        print(f"\n  Agent DES (isolation={iso_prob:.0%}):")
        agent_I, agent_S = _collect_runs(
            runner_fn=lambda i, p=iso_prob: run_agent_simulation(
                COVID_LIKE.to_des_config(
                    population=population,
                    duration_days=duration_days,
                    random_seed=2000 + i,
                ),
                behavior_factory=lambda pid, pp=p: StatisticalBehavior(
                    isolation_prob=pp,
                ),
            ),
            n_runs=n_runs,
            label=f"iso={iso_prob:.0%}",
            population=population,
        )
        agent_data[iso_prob] = {"I": agent_I, "S": agent_S}

    # Time axis (snapshots start at day 1)
    t = np.arange(1, duration_days + 1, dtype=float)

    # ── Plot 1: Infectious curves with variability bands ─────────
    _plot_sweep_curves(ode, ode_I_frac, vanilla_I, agent_data,
                       isolation_probs, t, population, n_runs, duration_days)

    # ── Plot 2: Summary metrics with error bars ──────────────────
    _plot_metrics(ode, vanilla_I, vanilla_S, agent_data,
                  isolation_probs, t, population, n_runs)

    return agent_data


def _plot_sweep_curves(ode, ode_I_frac, vanilla_I, agent_data,
                       isolation_probs, t, population, n_runs, duration_days):
    """Plot infectious curves with mean +/- 1 sigma bands."""
    fig, ax = plt.subplots(figsize=(12, 7))
    fig.suptitle(
        f"Effect of Behavioral Isolation on Epidemic Dynamics\n"
        f"COVID-like, N={population:,}, {n_runs} Monte Carlo runs each",
        fontsize=14,
        fontweight="bold",
    )

    # SEIR reference (no band — deterministic)
    ax.plot(ode["t"], ode_I_frac, color=COLOR_SEIR, linewidth=2.5,
            label="SEIR ODE", alpha=0.8, linestyle="-")

    # Vanilla DES mean + band
    v_mean = vanilla_I.mean(axis=0) / population
    v_std = vanilla_I.std(axis=0) / population
    plot_len = min(len(t), len(v_mean))
    ax.plot(t[:plot_len], v_mean[:plot_len],
            color=COLOR_VANILLA, linewidth=2.0, linestyle="--",
            label="Vanilla DES mean", alpha=0.9)
    ax.fill_between(t[:plot_len],
                     (v_mean - v_std)[:plot_len],
                     (v_mean + v_std)[:plot_len],
                     color=COLOR_VANILLA, alpha=0.15, label="Vanilla DES +/-1$\\sigma$")

    # Agent DES for each isolation level
    colors = sns.color_palette("YlOrRd", n_colors=len(isolation_probs) + 1)[1:]
    for (iso_prob, data), color in zip(agent_data.items(), colors):
        a_mean = data["I"].mean(axis=0) / population
        a_std = data["I"].std(axis=0) / population
        plot_len = min(len(t), len(a_mean))
        ax.plot(t[:plot_len], a_mean[:plot_len],
                color=color, linewidth=1.8,
                label=f"Agent iso={iso_prob:.0%} mean", alpha=0.9)
        ax.fill_between(t[:plot_len],
                         (a_mean - a_std)[:plot_len],
                         (a_mean + a_std)[:plot_len],
                         color=color, alpha=0.12)

    ax.set_xlabel("Day")
    ax.set_ylabel("Infected (fraction of population)")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    ax.legend(fontsize=9, loc="upper right")
    ax.set_xlim(0, duration_days)

    plt.tight_layout(rect=[0, 0, 1, 0.90])
    fname = RESULTS_DIR / "01_isolation_sweep.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"\n  Saved: {fname}")
    plt.close(fig)


def _plot_metrics(ode, vanilla_I, vanilla_S, agent_data,
                  isolation_probs, t, population, n_runs):
    """Plot summary metrics bar chart with error bars and die-out annotation."""

    # Compute metrics for each condition
    vanilla_m = _compute_metrics(vanilla_I, vanilla_S, t, population)

    agent_metrics = {}
    for iso_prob in isolation_probs:
        agent_metrics[iso_prob] = _compute_metrics(
            agent_data[iso_prob]["I"],
            agent_data[iso_prob]["S"],
            t, population,
        )

    # Conditions
    conditions = ["SEIR\nODE", "Vanilla\nDES"] + [
        f"iso={p:.0%}" for p in isolation_probs
    ]

    # SEIR ODE metrics (deterministic — no std)
    seir_peak_I = ode["I"].max() / population * 100
    seir_peak_day = ode["t"][ode["I"].argmax()]
    seir_attack = (population - ode["S"][-1]) / population * 100

    # Assemble arrays
    peak_means = [seir_peak_I, vanilla_m["peak_I_mean"]]
    peak_stds = [0.0, vanilla_m["peak_I_std"]]
    day_means = [seir_peak_day, vanilla_m["peak_day_mean"]]
    day_stds = [0.0, vanilla_m["peak_day_std"]]
    attack_means = [seir_attack, vanilla_m["attack_mean"]]
    attack_stds = [0.0, vanilla_m["attack_std"]]
    n_established_list = [n_runs, vanilla_m["n_established"]]

    for iso_prob in isolation_probs:
        m = agent_metrics[iso_prob]
        peak_means.append(m["peak_I_mean"])
        peak_stds.append(m["peak_I_std"])
        day_means.append(m["peak_day_mean"])
        day_stds.append(m["peak_day_std"])
        attack_means.append(m["attack_mean"])
        attack_stds.append(m["attack_std"])
        n_established_list.append(m["n_established"])

    metric_groups = [
        ("Peak Infected (%)", peak_means, peak_stds),
        ("Peak Day\n(established runs only)", day_means, day_stds),
        ("Attack Rate (%)", attack_means, attack_stds),
    ]

    colors = ["black", COLOR_VANILLA] + list(
        sns.color_palette("YlOrRd", n_colors=len(isolation_probs) + 1)[1:]
    )

    fig, axes = plt.subplots(1, 3, figsize=(16, 6))
    fig.suptitle(
        f"Behavioral Impact on Key Metrics — COVID-like (N={population:,}, {n_runs} runs)\n"
        f"Peak Day computed only from runs with >{EPIDEMIC_THRESHOLD_PCT:.0f}% attack rate",
        fontsize=13,
        fontweight="bold",
    )

    for ax, (label, means, stds) in zip(axes, metric_groups):
        x = range(len(conditions))
        bars = ax.bar(
            x, means,
            color=colors[:len(means)],
            edgecolor="black", linewidth=0.5, width=0.7,
        )

        # Error bars
        ax.errorbar(
            x, means, yerr=stds,
            fmt="none", color="black",
            capsize=5, capthick=1.0, linewidth=1.0,
        )

        ax.set_xticks(list(x))
        ax.set_xticklabels(conditions, fontsize=8)
        ax.set_title(label, fontsize=11)

        # Value labels
        for bar, val, std in zip(bars, means, stds):
            y_pos = bar.get_height() + std + 0.3
            ax.text(
                bar.get_x() + bar.get_width() / 2, y_pos,
                f"{val:.1f}",
                ha="center", va="bottom", fontsize=8, fontweight="bold",
            )

    # Annotate n_established on peak day panel
    ax_day = axes[1]
    for i, n_est in enumerate(n_established_list):
        if i < 2:
            continue  # Skip SEIR and Vanilla
        ax_day.text(
            i, -0.06 * ax_day.get_ylim()[1],
            f"{n_est}/{n_runs}\nest.",
            ha="center", va="top", fontsize=7, color="gray",
        )

    plt.tight_layout(rect=[0, 0.02, 1, 0.88])
    fname = RESULTS_DIR / "02_behavioral_metrics.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"  Saved: {fname}")
    plt.close(fig)

    # ── Print summary table ──────────────────────────────────────
    print(f"\n  {'Condition':<16} {'Peak I%':>8} {'(+/-1s)':>8} "
          f"{'PkDay':>7} {'(+/-1s)':>8} "
          f"{'Attack%':>8} {'(+/-1s)':>8} {'Est.':>6}")
    print(f"  {'─'*75}")

    all_data = zip(conditions, peak_means, peak_stds,
                   day_means, day_stds,
                   attack_means, attack_stds,
                   n_established_list)
    for cond, pm, ps, dm, ds, am, a_s, ne in all_data:
        cond_clean = cond.replace('\n', ' ')
        est_str = f"{ne}/{n_runs}" if ne < n_runs else "all"
        print(f"  {cond_clean:<16} {pm:>8.1f} {ps:>8.1f} "
              f"{dm:>7.1f} {ds:>8.1f} "
              f"{am:>8.1f} {a_s:>8.1f} {est_str:>6}")


# ── Main ─────────────────────────────────────────────────────────

def main():
    ensure_results_dir()

    population = 5000
    duration_days = 180

    # Experiment 1: Prove equivalence
    equiv_pass = test_null_equivalence(
        population=population,
        duration_days=duration_days,
        n_seeds=5,
    )

    if not equiv_pass:
        print("\n  WARNING: NullBehavior equivalence test FAILED.")
        print("  Agent DES does not reproduce vanilla DES exactly.")
        print("  Proceeding with sweep anyway for diagnostic purposes.\n")

    # Experiment 2: Isolation sweep (100 MC runs)
    sweep_isolation(
        population=population,
        duration_days=duration_days,
        n_runs=100,
        isolation_probs=[0.0, 0.1, 0.3, 0.5],
    )

    print(f"\n{'='*60}")
    print(f"All plots saved to: {RESULTS_DIR.resolve()}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
