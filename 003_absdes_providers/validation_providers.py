#!/usr/bin/env python3
"""
Healthcare Provider Impact Validation.

Sweeps provider density (0–50 per 1000 population) and demonstrates:
1. More providers → better surveillance accuracy (true vs estimated sick)
2. More providers → faster detection & higher cumulative detection
3. More providers → reduced epidemic severity (via behavioral modification)

Four figures:
    01_surveillance_accuracy.png — Observe-only (receptivity=0): true vs detected
    02_outreach_efficacy.png     — Receptivity sweep (10% vs 40%) at 0/1/5 density
    03_surveillance_metrics.png  — Detection error, delay, and coverage
    04_epidemic_outcomes.png     — Peak I%, Peak Day, Attack Rate

Usage (from project root):
    python 003_absdes_providers/validation_providers.py
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "des_system"))
sys.path.insert(0, str(_PROJECT_ROOT / "agent_based_des"))
sys.path.insert(0, str(_PROJECT_ROOT / "003_absdes_providers"))

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import seaborn as sns

from config import SimulationConfig
from validation_config import COVID_LIKE
from provider_simulation import run_provider_simulation, ProviderResult
from rule_based_behavior import RuleBasedBehavior

# ── Configuration ─────────────────────────────────────────────────
sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)

RESULTS_DIR = Path(__file__).parent / "results"

N_PEOPLE = 5000
N_RUNS = 50
DURATION = 180
SCREENING_CAPACITY = 20  # per provider per day
PROVIDER_DENSITIES = [0, 1, 5, 10, 20, 50]  # per 1000 population

# Outreach efficacy figure: subset of densities × receptivity levels
OUTREACH_DENSITIES = [0, 1, 5]  # per 1000 population
OUTREACH_RECEPTIVITIES = [0.10, 0.40]

# RuleBasedBehavior defaults for all persons
BEHAVIOR_DEFAULTS = dict(
    disclosure_prob=0.5,
    receptivity=0.6,
    base_isolation_prob=0.05,
    advised_isolation_prob=0.4,
    base_care_prob=0.0,
    advised_care_prob=0.5,
)

# Epidemic die-out threshold
EPIDEMIC_THRESHOLD_PCT = 5.0


def ensure_results_dir():
    RESULTS_DIR.mkdir(exist_ok=True)


def _n_providers(density_per_1000: float) -> int:
    """Convert density per 1000 to absolute provider count."""
    return int(N_PEOPLE * density_per_1000 / 1000)


def _make_behavior_factory(**overrides):
    """Create a behavior factory with optional parameter overrides."""
    kwargs = {**BEHAVIOR_DEFAULTS, **overrides}
    def factory(pid: int) -> RuleBasedBehavior:
        return RuleBasedBehavior(**kwargs)
    return factory


# ── Data Collection ───────────────────────────────────────────────

def _extract_daily_I(result: ProviderResult) -> np.ndarray:
    """Extract daily infectious count from snapshots."""
    counts = []
    for snap in result.sim_result.daily_snapshots:
        sc = snap["state_counts"]
        counts.append(sc.get("infectious", 0) + sc.get("symptomatic", 0))
    return np.array(counts, dtype=float)


def _extract_daily_S(result: ProviderResult) -> np.ndarray:
    """Extract daily susceptible count from snapshots."""
    return np.array(
        [snap["state_counts"].get("susceptible", 0)
         for snap in result.sim_result.daily_snapshots],
        dtype=float,
    )


def _extract_surveillance(result: ProviderResult) -> tuple[np.ndarray, np.ndarray]:
    """Extract daily true_active and detected_active from surveillance."""
    true_active = np.array(
        [s["true_active"] for s in result.surveillance], dtype=float,
    )
    detected_active = np.array(
        [s["detected_active"] for s in result.surveillance], dtype=float,
    )
    return true_active, detected_active


def collect_runs(
    density: float,
    n_runs: int,
    behavior_overrides: dict | None = None,
    seed_base: int = 3000,
    label: str = "",
) -> list[ProviderResult]:
    """Run n_runs simulations at given provider density."""
    n_prov = _n_providers(density)
    factory = _make_behavior_factory(**(behavior_overrides or {}))
    desc = label or f"density={density}/1000 ({n_prov} providers)"
    results = []
    for i in range(n_runs):
        if (i + 1) % 10 == 0 or i == 0:
            print(f"      {desc}: run {i+1}/{n_runs}...", flush=True)
        config = COVID_LIKE.to_des_config(
            population=N_PEOPLE,
            duration_days=DURATION,
            random_seed=seed_base + int(density * 1000) + i,
        )
        result = run_provider_simulation(
            config,
            n_providers=n_prov,
            screening_capacity=SCREENING_CAPACITY,
            behavior_factory=factory,
        )
        results.append(result)
    return results


# ── Metric Computation ────────────────────────────────────────────

def compute_surveillance_metrics(results: list[ProviderResult]) -> dict:
    """
    Compute surveillance accuracy metrics across MC runs.

    Returns dict with mean ± std for:
        - mean_abs_error: average daily |detected - true| / N
        - detection_delay: days until detected > 50% of true (or NaN)
        - cumulative_rate: % of total infections ever detected
    """
    errors = []
    delays = []
    cum_rates = []

    for r in results:
        if not r.surveillance:
            errors.append(1.0)
            delays.append(float(DURATION))
            cum_rates.append(0.0)
            continue

        # Mean absolute estimation error for this run
        daily_errors = [s["estimation_error"] for s in r.surveillance]
        errors.append(np.mean(daily_errors) * 100)  # as % of N

        # Detection delay: first day where detected_active > 0.5 * true_active
        delay_found = False
        for s in r.surveillance:
            if s["true_active"] > 0 and s["detected_active"] >= 0.5 * s["true_active"]:
                delays.append(s["day"])
                delay_found = True
                break
        if not delay_found:
            delays.append(float(DURATION))

        # Cumulative detection rate
        total_inf = r.sim_result.total_infections
        if total_inf > 0:
            cum_rates.append(r.total_detected / total_inf * 100)
        else:
            cum_rates.append(0.0)

    return {
        "error_mean": np.mean(errors),
        "error_std": np.std(errors),
        "delay_mean": np.mean(delays),
        "delay_std": np.std(delays),
        "cum_rate_mean": np.mean(cum_rates),
        "cum_rate_std": np.std(cum_rates),
    }


def compute_epidemic_metrics(results: list[ProviderResult]) -> dict:
    """Compute epidemic outcome metrics across MC runs."""
    peak_I_vals = []
    peak_day_vals = []
    attack_vals = []

    for r in results:
        I_arr = _extract_daily_I(r)
        S_arr = _extract_daily_S(r)
        peak_I_vals.append(I_arr.max() / N_PEOPLE * 100)
        peak_day_vals.append(I_arr.argmax() + 1)  # +1 for 1-indexed days
        attack = (N_PEOPLE - S_arr[-1]) / N_PEOPLE * 100
        attack_vals.append(attack)

    peak_I = np.array(peak_I_vals)
    peak_day = np.array(peak_day_vals)
    attack = np.array(attack_vals)

    # Filter peak day to established epidemics
    established = attack > EPIDEMIC_THRESHOLD_PCT
    n_est = int(established.sum())

    return {
        "peak_I_mean": peak_I.mean(),
        "peak_I_std": peak_I.std(),
        "peak_day_mean": peak_day[established].mean() if n_est > 0 else 0.0,
        "peak_day_std": peak_day[established].std() if n_est > 0 else 0.0,
        "attack_mean": attack.mean(),
        "attack_std": attack.std(),
        "n_established": n_est,
        "n_runs": len(results),
    }


# ── Figure 1: Surveillance Accuracy (Observe Only) ──────────────

def plot_surveillance_accuracy(all_results: dict[float, list[ProviderResult]]):
    """
    2×3 grid: true vs detected active cases over time per density.
    Observe-only mode: receptivity=0, providers detect but don't change behavior.
    """
    fig, axes = plt.subplots(2, 3, figsize=(16, 9), sharex=True, sharey=True)
    axes_flat = axes.flatten()

    fig.suptitle(
        "Surveillance Accuracy: True vs Detected Active Cases\n"
        f"Observe only (receptivity = 0) — N={N_PEOPLE:,}, {N_RUNS} MC runs, "
        f"screening={SCREENING_CAPACITY}/provider/day",
        fontsize=14, fontweight="bold",
    )

    for idx, density in enumerate(PROVIDER_DENSITIES):
        ax = axes_flat[idx]
        results = all_results[density]

        # Collect surveillance time series across runs
        true_arrays = []
        detected_arrays = []
        for r in results:
            if r.surveillance:
                true_a, det_a = _extract_surveillance(r)
                true_arrays.append(true_a)
                detected_arrays.append(det_a)

        if not true_arrays:
            ax.set_title(f"{density}/1000 — no surveillance data")
            continue

        # Pad to same length
        max_len = max(len(a) for a in true_arrays)
        true_mat = np.zeros((len(true_arrays), max_len))
        det_mat = np.zeros((len(detected_arrays), max_len))
        for i, (ta, da) in enumerate(zip(true_arrays, detected_arrays)):
            true_mat[i, :len(ta)] = ta
            det_mat[i, :len(da)] = da

        t = np.arange(1, max_len + 1)

        true_mean = true_mat.mean(axis=0)
        true_std = true_mat.std(axis=0)
        det_mean = det_mat.mean(axis=0)
        det_std = det_mat.std(axis=0)

        # Plot
        ax.plot(t, true_mean, color="steelblue", linewidth=1.8, label="True active")
        ax.fill_between(t, true_mean - true_std, true_mean + true_std,
                         color="steelblue", alpha=0.15)
        ax.plot(t, det_mean, color="orangered", linewidth=1.8,
                linestyle="--", label="Detected active")
        ax.fill_between(t, det_mean - det_std, det_mean + det_std,
                         color="orangered", alpha=0.15)

        # Compute mean error for title
        surv_m = compute_surveillance_metrics(results)
        n_prov = _n_providers(density)
        ax.set_title(
            f"{density}/1000 ({n_prov} providers)\n"
            f"Mean error: {surv_m['error_mean']:.2f}% of N",
            fontsize=10,
        )

        ax.legend(fontsize=8, loc="upper right")
        if idx >= 3:
            ax.set_xlabel("Day")
        if idx % 3 == 0:
            ax.set_ylabel("Active cases")

    plt.tight_layout(rect=[0, 0, 1, 0.90])
    fname = RESULTS_DIR / "01_surveillance_accuracy.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"\n  Saved: {fname}")
    plt.close(fig)


# ── Figure 2: Outreach Efficacy ─────────────────────────────────

def plot_outreach_efficacy(
    outreach_data: dict[tuple[float, float], list[ProviderResult]],
):
    """
    2×3 grid: true vs detected active cases.
    Top row: receptivity=10%, Bottom row: receptivity=40%.
    Columns: density 0, 1, 5 per 1000.
    """
    fig, axes = plt.subplots(2, 3, figsize=(16, 9), sharex=True, sharey=True)

    fig.suptitle(
        "Outreach Efficacy: Impact of Provider Advice Receptivity\n"
        f"N={N_PEOPLE:,}, {N_RUNS} MC runs, screening={SCREENING_CAPACITY}/provider/day",
        fontsize=14, fontweight="bold",
    )

    for row_idx, recep in enumerate(OUTREACH_RECEPTIVITIES):
        for col_idx, density in enumerate(OUTREACH_DENSITIES):
            ax = axes[row_idx, col_idx]
            results = outreach_data[(density, recep)]

            # Collect surveillance time series
            true_arrays = []
            detected_arrays = []
            for r in results:
                if r.surveillance:
                    true_a, det_a = _extract_surveillance(r)
                    true_arrays.append(true_a)
                    detected_arrays.append(det_a)

            if not true_arrays:
                ax.set_title(f"{density}/1000, recep={recep:.0%} — no data")
                continue

            max_len = max(len(a) for a in true_arrays)
            true_mat = np.zeros((len(true_arrays), max_len))
            det_mat = np.zeros((len(detected_arrays), max_len))
            for i, (ta, da) in enumerate(zip(true_arrays, detected_arrays)):
                true_mat[i, :len(ta)] = ta
                det_mat[i, :len(da)] = da

            t = np.arange(1, max_len + 1)
            true_mean = true_mat.mean(axis=0)
            true_std = true_mat.std(axis=0)
            det_mean = det_mat.mean(axis=0)
            det_std = det_mat.std(axis=0)

            ax.plot(t, true_mean, color="steelblue", linewidth=1.8,
                    label="True active")
            ax.fill_between(t, true_mean - true_std, true_mean + true_std,
                             color="steelblue", alpha=0.15)
            ax.plot(t, det_mean, color="orangered", linewidth=1.8,
                    linestyle="--", label="Detected active")
            ax.fill_between(t, det_mean - det_std, det_mean + det_std,
                             color="orangered", alpha=0.15)

            n_prov = _n_providers(density)
            surv_m = compute_surveillance_metrics(results)
            ax.set_title(
                f"{density}/1000 ({n_prov} prov), receptivity={recep:.0%}\n"
                f"Mean error: {surv_m['error_mean']:.2f}% of N",
                fontsize=10,
            )

            ax.legend(fontsize=8, loc="upper right")
            if row_idx == 1:
                ax.set_xlabel("Day")
            if col_idx == 0:
                ax.set_ylabel("Active cases")

    plt.tight_layout(rect=[0, 0, 1, 0.90])
    fname = RESULTS_DIR / "02_outreach_efficacy.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"  Saved: {fname}")
    plt.close(fig)


# ── Figure 3: Surveillance Metrics ───────────────────────────────

def plot_surveillance_metrics(all_results: dict[float, list[ProviderResult]]):
    """
    3-panel bar chart: estimation error, detection delay, cumulative rate.
    """
    metrics_by_density = {}
    for density in PROVIDER_DENSITIES:
        metrics_by_density[density] = compute_surveillance_metrics(all_results[density])

    conditions = [f"{d}/1000" for d in PROVIDER_DENSITIES]
    colors = sns.color_palette("viridis", n_colors=len(PROVIDER_DENSITIES))

    metric_groups = [
        ("Mean Estimation Error",
         "Error (% of population)",
         [metrics_by_density[d]["error_mean"] for d in PROVIDER_DENSITIES],
         [metrics_by_density[d]["error_std"] for d in PROVIDER_DENSITIES]),
        ("Detection Delay",
         "Days to 50% detected",
         [metrics_by_density[d]["delay_mean"] for d in PROVIDER_DENSITIES],
         [metrics_by_density[d]["delay_std"] for d in PROVIDER_DENSITIES]),
        ("Cumulative Detection Rate",
         "Detection rate (%)",
         [metrics_by_density[d]["cum_rate_mean"] for d in PROVIDER_DENSITIES],
         [metrics_by_density[d]["cum_rate_std"] for d in PROVIDER_DENSITIES]),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(16, 6))
    fig.suptitle(
        f"Surveillance Performance vs Provider Density\n"
        f"N={N_PEOPLE:,}, {N_RUNS} MC runs, {SCREENING_CAPACITY}/provider/day",
        fontsize=13, fontweight="bold",
    )

    for ax, (label, ylabel, means, stds) in zip(axes, metric_groups):
        x = range(len(conditions))
        bars = ax.bar(x, means, color=colors, edgecolor="black",
                      linewidth=0.5, width=0.7)
        ax.errorbar(x, means, yerr=stds, fmt="none", color="black",
                    capsize=5, capthick=1.0, linewidth=1.0)
        ax.set_xticks(list(x))
        ax.set_xticklabels(conditions, fontsize=9)
        ax.set_xlabel("Provider density (per 1000)")
        ax.set_ylabel(ylabel, fontsize=10)
        ax.set_title(label, fontsize=11)

        for bar, val in zip(bars, means):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.5,
                    f"{val:.1f}", ha="center", va="bottom",
                    fontsize=8, fontweight="bold")

    plt.tight_layout(rect=[0, 0, 1, 0.88])
    fname = RESULTS_DIR / "03_surveillance_metrics.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"  Saved: {fname}")
    plt.close(fig)


# ── Figure 4: Epidemic Outcomes ───────────────────────────────────

def plot_epidemic_outcomes(all_results: dict[float, list[ProviderResult]]):
    """
    3-panel bar chart: Peak I%, Peak Day, Attack Rate by density.
    """
    epi_metrics = {}
    for density in PROVIDER_DENSITIES:
        epi_metrics[density] = compute_epidemic_metrics(all_results[density])

    conditions = [f"{d}/1000" for d in PROVIDER_DENSITIES]
    colors = sns.color_palette("viridis", n_colors=len(PROVIDER_DENSITIES))

    metric_groups = [
        ("Peak Infected",
         "Infected (% of population)",
         [epi_metrics[d]["peak_I_mean"] for d in PROVIDER_DENSITIES],
         [epi_metrics[d]["peak_I_std"] for d in PROVIDER_DENSITIES]),
        ("Peak Day (established runs)",
         "Day",
         [epi_metrics[d]["peak_day_mean"] for d in PROVIDER_DENSITIES],
         [epi_metrics[d]["peak_day_std"] for d in PROVIDER_DENSITIES]),
        ("Attack Rate",
         "Attack rate (% of population)",
         [epi_metrics[d]["attack_mean"] for d in PROVIDER_DENSITIES],
         [epi_metrics[d]["attack_std"] for d in PROVIDER_DENSITIES]),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(16, 6))
    fig.suptitle(
        f"Epidemic Outcomes vs Provider Density\n"
        f"N={N_PEOPLE:,}, {N_RUNS} MC runs, "
        f"RuleBasedBehavior(iso_base={BEHAVIOR_DEFAULTS['base_isolation_prob']:.0%}, "
        f"iso_advised={BEHAVIOR_DEFAULTS['advised_isolation_prob']:.0%})",
        fontsize=13, fontweight="bold",
    )

    for ax, (label, ylabel, means, stds) in zip(axes, metric_groups):
        x = range(len(conditions))
        bars = ax.bar(x, means, color=colors, edgecolor="black",
                      linewidth=0.5, width=0.7)
        ax.errorbar(x, means, yerr=stds, fmt="none", color="black",
                    capsize=5, capthick=1.0, linewidth=1.0)
        ax.set_xticks(list(x))
        ax.set_xticklabels(conditions, fontsize=9)
        ax.set_xlabel("Provider density (per 1000)")
        ax.set_ylabel(ylabel, fontsize=10)
        ax.set_title(label, fontsize=11)

        for bar, val in zip(bars, means):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.5,
                    f"{val:.1f}", ha="center", va="bottom",
                    fontsize=8, fontweight="bold")

    # Annotate n_established on peak day
    ax_day = axes[1]
    for i, density in enumerate(PROVIDER_DENSITIES):
        m = epi_metrics[density]
        ax_day.text(i, -0.06 * ax_day.get_ylim()[1],
                    f"{m['n_established']}/{m['n_runs']}\nest.",
                    ha="center", va="top", fontsize=7, color="gray")

    plt.tight_layout(rect=[0, 0.02, 1, 0.86])
    fname = RESULTS_DIR / "04_epidemic_outcomes.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"  Saved: {fname}")
    plt.close(fig)


# ── Print Summary ─────────────────────────────────────────────────

def print_summary(all_results: dict[float, list[ProviderResult]]):
    """Print tabular summary of all conditions."""
    print(f"\n  {'Density':<10} {'Providers':>10} {'Screen/d':>10} "
          f"{'EstErr%':>8} {'Delay_d':>8} {'DetRate%':>9} "
          f"{'PeakI%':>8} {'PkDay':>7} {'Attack%':>9}")
    print(f"  {'─' * 90}")

    for density in PROVIDER_DENSITIES:
        n_prov = _n_providers(density)
        surv = compute_surveillance_metrics(all_results[density])
        epi = compute_epidemic_metrics(all_results[density])
        print(
            f"  {density:<10} {n_prov:>10} {n_prov * SCREENING_CAPACITY:>10} "
            f"{surv['error_mean']:>8.2f} {surv['delay_mean']:>8.1f} "
            f"{surv['cum_rate_mean']:>9.1f} "
            f"{epi['peak_I_mean']:>8.1f} {epi['peak_day_mean']:>7.0f} "
            f"{epi['attack_mean']:>9.1f}"
        )


# ── Main ──────────────────────────────────────────────────────────

def main():
    ensure_results_dir()

    print(f"\n{'='*60}")
    print(f"Healthcare Provider Impact Validation")
    print(f"  N={N_PEOPLE:,}, {N_RUNS} MC runs per condition, {DURATION} days")
    print(f"  Provider densities: {PROVIDER_DENSITIES} per 1000")
    print(f"  Screening capacity: {SCREENING_CAPACITY}/provider/day")
    print(f"  Behavior: {BEHAVIOR_DEFAULTS}")
    print(f"{'='*60}")

    # ── Phase 1: Observe-only sweep (receptivity=0) for Figure 1 ──
    print(f"\n  Phase 1: Observe-only sweep (receptivity=0)...")
    observe_results: dict[float, list[ProviderResult]] = {}
    for density in PROVIDER_DENSITIES:
        print(f"\n  [observe] density={density}/1000...")
        observe_results[density] = collect_runs(
            density, N_RUNS,
            behavior_overrides={"receptivity": 0.0},
            seed_base=4000,
            label=f"observe density={density}/1000",
        )

    # ── Phase 2: Outreach sweep (receptivity=10%/40%) for Figure 2 ──
    print(f"\n  Phase 2: Outreach efficacy sweep...")
    outreach_results: dict[tuple[float, float], list[ProviderResult]] = {}
    for recep in OUTREACH_RECEPTIVITIES:
        for density in OUTREACH_DENSITIES:
            print(f"\n  [outreach] density={density}/1000, recep={recep:.0%}...")
            outreach_results[(density, recep)] = collect_runs(
                density, N_RUNS,
                behavior_overrides={"receptivity": recep},
                seed_base=5000 + int(recep * 100),
                label=f"outreach d={density}/1000 r={recep:.0%}",
            )

    # ── Phase 3: Full sweep (default behavior) for Figures 3 & 4 ──
    print(f"\n  Phase 3: Full sweep (default behavior)...")
    full_results: dict[float, list[ProviderResult]] = {}
    for density in PROVIDER_DENSITIES:
        print(f"\n  [full] density={density}/1000...")
        full_results[density] = collect_runs(
            density, N_RUNS,
            seed_base=3000,
        )

    # ── Generate figures ──
    print(f"\n  Generating figures...")
    plot_surveillance_accuracy(observe_results)
    plot_outreach_efficacy(outreach_results)
    plot_surveillance_metrics(full_results)
    plot_epidemic_outcomes(full_results)

    # Summary table (from full sweep)
    print_summary(full_results)

    print(f"\n{'='*60}")
    print(f"All plots saved to: {RESULTS_DIR.resolve()}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
