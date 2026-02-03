#!/usr/bin/env python3
"""
Healthcare Provider Impact Validation (v2 — Production Backend).

Re-validates 003 using the production CityDES engine with its built-in
70/30 targeted screening (random + contact-based).

Four experiments:
1. Surveillance accuracy: detected vs true active at varying provider density
2. Provider density sweep: epidemic outcomes vs density (0–50 per 1000)
3. Observed vs actual epidemic: how well does provider detection track reality
4. Severity validation: providers with severity enabled (the full 7-state model)

Outputs saved to 003_absdes_providers/results_v2/ directory.

Usage (from project root):
    python 003_absdes_providers/validation_providers_v2.py
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
from validation_config import COVID_LIKE

# ── Configuration ─────────────────────────────────────────────────
sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)
PALETTE = sns.color_palette("muted")

RESULTS_DIR = _SCRIPT_DIR / "results_v2"
N_PEOPLE = 5000
DURATION = 180
SCREENING_CAPACITY = 20
PROVIDER_DENSITIES = [0, 1, 5, 10, 20, 50]  # per 1000 pop
N_RUNS = 30
EPIDEMIC_THRESHOLD_PCT = 5.0


def ensure_results_dir():
    RESULTS_DIR.mkdir(exist_ok=True)


def _n_providers(density_per_1000):
    return int(N_PEOPLE * density_per_1000 / 1000)


# ── Run single CityDES with provider tracking ────────────────────

def run_single(
    seed, n_providers=0, screening_capacity=SCREENING_CAPACITY,
    severe_fraction=0.0, base_isolation_prob=0.05,
    advised_isolation_prob=0.20, disclosure_prob=0.5,
    receptivity=0.6,
):
    """Run a single CityDES simulation with full tracking."""
    city = CityDES(
        n_people=N_PEOPLE,
        scenario=COVID_LIKE,
        seed_infected=3,
        random_seed=seed,
        avg_contacts=10,
        rewire_prob=0.4,
        daily_contact_rate=0.5,
        p_random=0.15,
        n_providers=n_providers,
        screening_capacity=screening_capacity,
        disclosure_prob=disclosure_prob,
        receptivity=receptivity,
        base_isolation_prob=base_isolation_prob,
        advised_isolation_prob=advised_isolation_prob,
        advice_decay_prob=0.05,
        severe_fraction=severe_fraction,
        gamma_shape=6.25,
    )

    n_days = DURATION + 1
    S = np.zeros(n_days)
    I = np.zeros(n_days)
    R = np.zeros(n_days)
    D = np.zeros(n_days)
    obs_I = np.zeros(n_days)
    obs_R = np.zeros(n_days)
    obs_D = np.zeros(n_days)
    total_detected = np.zeros(n_days)
    daily_screened = np.zeros(n_days)
    daily_detected = np.zeros(n_days)

    S[0], I[0], R[0], D[0] = city.S, city.I, city.R, city.D
    obs_I[0] = city.observed_I

    for day in range(1, n_days):
        city.step(until=day)

        if n_providers > 0:
            stats = city.run_provider_screening()
            daily_screened[day] = stats["screened"]
            daily_detected[day] = stats["detected"]

        S[day] = city.S
        I[day] = city.I
        R[day] = city.R
        D[day] = city.D
        obs_I[day] = city.observed_I
        obs_R[day] = city.observed_R
        obs_D[day] = city.observed_D
        total_detected[day] = city.total_detected

    t = np.arange(0, n_days, dtype=float)
    return {
        "t": t, "S": S, "I": I, "R": R, "D": D,
        "obs_I": obs_I, "obs_R": obs_R, "obs_D": obs_D,
        "total_detected": total_detected,
        "daily_screened": daily_screened,
        "daily_detected": daily_detected,
    }


def run_mc(n_runs, label, **kwargs):
    """Run Monte Carlo, return stacked arrays."""
    n_days = DURATION + 1
    keys = ["S", "I", "R", "D", "obs_I", "obs_R", "obs_D",
            "total_detected", "daily_screened", "daily_detected"]
    stacked = {k: np.zeros((n_runs, n_days)) for k in keys}

    for i in range(n_runs):
        seed = 1000 + i * 137
        result = run_single(seed=seed, **kwargs)
        for k in keys:
            stacked[k][i] = result[k]
        if (i + 1) % 10 == 0 or i == 0:
            print(f"    {label}: run {i+1}/{n_runs}", flush=True)

    stacked["t"] = np.arange(0, n_days, dtype=float)
    stacked["n_runs"] = n_runs
    return stacked


# ── Figure 1: Surveillance Accuracy ──────────────────────────────

def plot_surveillance_accuracy():
    """True active vs detected active at each provider density."""
    print(f"\n{'='*60}")
    print(f"Figure 1: Surveillance Accuracy")
    print(f"{'='*60}")

    fig, axes = plt.subplots(2, 3, figsize=(16, 9), sharex=True, sharey=True)
    fig.suptitle(
        "Surveillance Accuracy: True vs Detected Active Cases\n"
        f"N={N_PEOPLE:,}, {N_RUNS} MC runs, 70/30 targeted screening",
        fontsize=13, fontweight="bold",
    )

    all_mc = {}
    for idx, density in enumerate(PROVIDER_DENSITIES):
        n_prov = _n_providers(density)
        print(f"\n  density={density}/1000 ({n_prov} providers):")
        mc = run_mc(N_RUNS, f"d={density}", n_providers=n_prov)
        all_mc[density] = mc

        ax = axes.flat[idx]
        t = mc["t"]

        true_mean = mc["I"].mean(axis=0)
        true_std = mc["I"].std(axis=0)
        det_mean = mc["obs_I"].mean(axis=0)
        det_std = mc["obs_I"].std(axis=0)

        ax.plot(t, true_mean, color="steelblue", linewidth=1.8, label="True active (I)")
        ax.fill_between(t, true_mean - true_std, true_mean + true_std,
                         color="steelblue", alpha=0.15)
        ax.plot(t, det_mean, color="orangered", linewidth=1.8,
                linestyle="--", label="Detected active")
        ax.fill_between(t, det_mean - det_std, det_mean + det_std,
                         color="orangered", alpha=0.15)

        # Mean detection gap
        gap = np.mean(np.abs(true_mean - det_mean))
        ax.set_title(f"{density}/1000 ({n_prov} prov)\ngap={gap:.0f} agents", fontsize=10)
        ax.legend(fontsize=8, loc="upper right")
        if idx >= 3:
            ax.set_xlabel("Day")
        if idx % 3 == 0:
            ax.set_ylabel("Active cases")

    plt.tight_layout(rect=[0, 0, 1, 0.88])
    fname = RESULTS_DIR / "01_surveillance_accuracy.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"\n  Saved: {fname}")
    plt.close(fig)

    return all_mc


# ── Figure 2: Epidemic Outcomes vs Density ───────────────────────

def plot_epidemic_outcomes(all_mc):
    """Peak I, peak day, attack rate, final deaths by provider density."""
    print(f"\n{'='*60}")
    print(f"Figure 2: Epidemic Outcomes vs Provider Density")
    print(f"{'='*60}")

    densities = list(all_mc.keys())
    conditions = [f"{d}/1000" for d in densities]
    colors = sns.color_palette("viridis", n_colors=len(densities))

    # Compute metrics
    peak_I_m, peak_I_s = [], []
    attack_m, attack_s = [], []
    peak_day_m, peak_day_s = [], []

    for d in densities:
        mc = all_mc[d]
        peaks = mc["I"].max(axis=1) / N_PEOPLE * 100
        attacks = (N_PEOPLE - mc["S"][:, -1]) / N_PEOPLE * 100
        peak_days = np.array([mc["t"][run.argmax()] for run in mc["I"]])

        established = attacks > EPIDEMIC_THRESHOLD_PCT
        n_est = established.sum()

        peak_I_m.append(peaks.mean())
        peak_I_s.append(peaks.std())
        attack_m.append(attacks.mean())
        attack_s.append(attacks.std())
        if n_est > 0:
            peak_day_m.append(peak_days[established].mean())
            peak_day_s.append(peak_days[established].std())
        else:
            peak_day_m.append(0)
            peak_day_s.append(0)

    metric_groups = [
        ("Peak Infected (%)", peak_I_m, peak_I_s),
        ("Peak Day (est. runs)", peak_day_m, peak_day_s),
        ("Attack Rate (%)", attack_m, attack_s),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(16, 6))
    fig.suptitle(
        f"Epidemic Outcomes vs Provider Density\n"
        f"N={N_PEOPLE:,}, {N_RUNS} runs, base_iso=5%, advised_iso=20%",
        fontsize=13, fontweight="bold",
    )

    for ax, (label, means, stds) in zip(axes, metric_groups):
        x = range(len(conditions))
        bars = ax.bar(x, means, color=colors, edgecolor="black",
                      linewidth=0.5, width=0.7)
        ax.errorbar(x, means, yerr=stds, fmt="none", color="black",
                    capsize=5, capthick=1.0)
        ax.set_xticks(list(x))
        ax.set_xticklabels(conditions, fontsize=9)
        ax.set_xlabel("Provider density (per 1000)")
        ax.set_title(label, fontsize=11)

        for bar, val in zip(bars, means):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.5,
                    f"{val:.1f}", ha="center", va="bottom",
                    fontsize=8, fontweight="bold")

    plt.tight_layout(rect=[0, 0, 1, 0.86])
    fname = RESULTS_DIR / "02_epidemic_outcomes.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"  Saved: {fname}")
    plt.close(fig)

    # Print summary table
    print(f"\n  {'Density':<10} {'Providers':>10} {'PeakI%':>8} {'std':>6} "
          f"{'PkDay':>7} {'Attack%':>8} {'std':>6}")
    print(f"  {'─'*55}")
    for i, d in enumerate(densities):
        print(f"  {d:<10} {_n_providers(d):>10} {peak_I_m[i]:>8.1f} {peak_I_s[i]:>6.1f} "
              f"{peak_day_m[i]:>7.0f} {attack_m[i]:>8.1f} {attack_s[i]:>6.1f}")


# ── Figure 3: Observed vs Actual Epidemic ────────────────────────

def plot_observed_vs_actual():
    """
    At moderate provider density (10/1000), show observed vs actual
    epidemic curves for all compartments.
    """
    print(f"\n{'='*60}")
    print(f"Figure 3: Observed vs Actual Epidemic (10/1000 density)")
    print(f"{'='*60}")

    density = 10
    n_prov = _n_providers(density)
    mc = run_mc(N_RUNS, f"obs_vs_actual", n_providers=n_prov, severe_fraction=0.15)

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle(
        f"Observed vs Actual Epidemic — {density}/1000 ({n_prov} providers)\n"
        f"N={N_PEOPLE:,}, {N_RUNS} MC runs",
        fontsize=13, fontweight="bold",
    )

    t = mc["t"]
    panels = [
        ("Infectious", mc["I"], mc["obs_I"], "steelblue", "orangered"),
        ("Recovered", mc["R"], mc["obs_R"], "seagreen", "orange"),
        ("Dead", mc["D"], mc["obs_D"], "mediumpurple", "crimson"),
    ]

    for ax, (label, actual, observed, c_act, c_obs) in zip(axes, panels):
        act_mean = actual.mean(axis=0)
        obs_mean = observed.mean(axis=0)
        act_std = actual.std(axis=0)
        obs_std = observed.std(axis=0)

        ax.plot(t, act_mean, color=c_act, linewidth=1.8, label=f"Actual {label}")
        ax.fill_between(t, act_mean - act_std, act_mean + act_std,
                         color=c_act, alpha=0.15)
        ax.plot(t, obs_mean, color=c_obs, linewidth=1.8, linestyle="--",
                label=f"Observed {label}")
        ax.fill_between(t, obs_mean - obs_std, obs_mean + obs_std,
                         color=c_obs, alpha=0.15)

        ax.set_xlabel("Day")
        ax.set_ylabel("Count")
        ax.set_title(label, fontsize=11)
        ax.legend(fontsize=9, loc="best")

    plt.tight_layout(rect=[0, 0, 1, 0.86])
    fname = RESULTS_DIR / "03_observed_vs_actual.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"  Saved: {fname}")
    plt.close(fig)


# ── Figure 4: Full 7-state with severity ─────────────────────────

def plot_severity_with_providers():
    """
    Show provider impact with severity enabled (severe_fraction=0.15).
    Compare 0 vs 10 vs 25 providers: deaths should decrease with more providers
    because more patients get detected and transition to I_receiving_care.
    """
    print(f"\n{'='*60}")
    print(f"Figure 4: Severity + Providers (7-state model)")
    print(f"{'='*60}")

    densities_test = [0, 5, 10, 50]
    n_runs = 20

    fig, axes = plt.subplots(1, len(densities_test), figsize=(5 * len(densities_test), 5),
                             sharey=True)
    fig.suptitle(
        f"Deaths vs Provider Density (severe_fraction=0.15)\n"
        f"N={N_PEOPLE:,}, {n_runs} runs each",
        fontsize=13, fontweight="bold",
    )

    death_means = []
    death_stds = []

    for ax, density in zip(axes, densities_test):
        n_prov = _n_providers(density)
        print(f"\n  density={density}/1000 ({n_prov} providers):")
        mc = run_mc(n_runs, f"sev_d={density}",
                    n_providers=n_prov,
                    severe_fraction=0.15)

        t = mc["t"]
        D_mean = mc["D"].mean(axis=0)
        D_std = mc["D"].std(axis=0)
        I_mean = mc["I"].mean(axis=0)

        ax.plot(t, D_mean, color="mediumpurple", linewidth=1.8, label="Deaths (mean)")
        ax.fill_between(t, D_mean - D_std, D_mean + D_std,
                         color="mediumpurple", alpha=0.15)
        ax.plot(t, I_mean, color="orangered", linewidth=1.2, linestyle="--",
                label="Infectious (mean)", alpha=0.7)

        final_D = mc["D"][:, -1]
        death_means.append(final_D.mean())
        death_stds.append(final_D.std())

        ax.set_title(f"{density}/1000 ({n_prov} prov)\nDeaths: {final_D.mean():.0f}+/-{final_D.std():.0f}",
                      fontsize=10)
        ax.set_xlabel("Day")
        if ax == axes[0]:
            ax.set_ylabel("Count")
        ax.legend(fontsize=8, loc="best")

    plt.tight_layout(rect=[0, 0, 1, 0.86])
    fname = RESULTS_DIR / "04_severity_with_providers.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    print(f"\n  Saved: {fname}")
    plt.close(fig)

    # Print death summary
    print(f"\n  Provider density vs Final Deaths:")
    for d, dm, ds in zip(densities_test, death_means, death_stds):
        print(f"    {d}/1000: {dm:.0f} +/- {ds:.0f} deaths")


# ── Main ─────────────────────────────────────────────────────────

def main():
    ensure_results_dir()

    print(f"{'='*62}")
    print(f"  Provider Screening Validation (v2 — Production Backend)")
    print(f"  Engine: simulation_app/backend/city_des_extended.py")
    print(f"  70/30 targeted screening, {N_RUNS} MC runs")
    print(f"{'='*62}")

    # Figure 1: Surveillance accuracy
    all_mc = plot_surveillance_accuracy()

    # Figure 2: Epidemic outcomes vs density
    plot_epidemic_outcomes(all_mc)

    # Figure 3: Observed vs actual
    plot_observed_vs_actual()

    # Figure 4: Severity + providers
    plot_severity_with_providers()

    print(f"\n{'='*62}")
    print(f"All plots saved to: {RESULTS_DIR.resolve()}")
    print(f"{'='*62}")


if __name__ == "__main__":
    main()
