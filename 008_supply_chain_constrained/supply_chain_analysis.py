#!/usr/bin/env python3
"""
Supply Chain Analysis: Edge Cases, Dose-Response, Vaccine Targeting, and Behavioral Diagnosis.

Four sets of experiments:

PART 1 — Edge Cases (supply chain bounds)
  What is the death rate floor and ceiling?
  - NO_PROVIDERS + ZERO supplies → ceiling (worst possible)
  - AI_PROVIDERS + INFINITE supplies → floor (best possible)
  - AI_PROVIDERS + ZERO supplies → shows advice-only impact

PART 2 — Provider Dose-Response (AI healthworker density)
  Does more AI coverage reduce deaths regardless of supply level?
  Four densities × standard supplies:
  - 0, 1, 10, 50 providers per 1000

PART 3 — Vaccine Targeting (the key figure)
  With limited vaccines, does better surveillance improve targeting?
  - LOW providers (1/1000) → vaccines distributed randomly
  - HIGH providers (50/1000) → vaccines targeted via contact tracing

PART 4 — Behavioral Diagnosis (supply depletion resilience)
  When diagnostic supplies run out, can clinical assessment maintain surveillance?
  - Lab-only (behavioral_dx=0): detection drops to zero when supplies depleted
  - Behavioral dx (behavioral_dx=0.5): ~50% clinical assessment fills the gap

Outputs (in results/):
  fig_01_edge_cases.png            — Death rate bounds (bar + curves + cumulative deaths)
  fig_02_dose_response.png         — Provider density sweep
  fig_03_vaccine_targeting.png     — Same vaccines, different targeting
  fig_04_behavioral_diagnosis.png  — Supply depletion resilience via clinical assessment
  summary.md                       — Markdown results table

Usage:
    cd 008_supply_chain_constrained && python supply_chain_analysis.py
"""

import sys
import time
import json
from pathlib import Path
from dataclasses import dataclass

import numpy as np

# Path setup
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _PROJECT_ROOT / "simulation_app" / "backend"
sys.path.insert(0, str(_BACKEND))

from simulation import SimulationParams, run_absdes_simulation

RESULTS_DIR = Path(__file__).parent / "results"

# ── Configuration ────────────────────────────────────────────────────────────

DAYS = 180
SCENARIO = "covid_bioattack"
COUNTRY = "Nigeria"

# AI behavioral settings (from 003_absdes_providers sessions)
AI_SETTINGS = dict(
    advised_isolation_prob=0.55,
    disclosure_prob=0.80,
    receptivity_override=0.85,
    screening_capacity=200,
)

# ── Experiment definitions ────────────────────────────────────────────────────

EXPERIMENTS = {
    # ── Part 1: Edge cases ──
    "CEILING": {
        "label": "No Providers, No Supplies",
        "group": "edge",
        "overrides": {
            "enable_supply_chain": True,
            "resource_multiplier": 0.01,
            "provider_density": 0.0,
        },
    },
    "ADVICE_ONLY": {
        "label": "AI Providers, No Supplies",
        "group": "edge",
        "overrides": {
            **AI_SETTINGS,
            "enable_supply_chain": True,
            "resource_multiplier": 0.01,
            "provider_density": 50.0,
        },
    },
    "FLOOR": {
        "label": "AI Providers, Infinite Supplies",
        "group": "edge",
        "overrides": {
            **AI_SETTINGS,
            "enable_supply_chain": True,
            "resource_multiplier": 1e6,
            "provider_density": 50.0,
        },
    },

    # ── Part 2: Provider dose-response (standard supplies) ──
    "DOSE_0": {
        "label": "0 providers/1000",
        "group": "dose",
        "overrides": {
            **AI_SETTINGS,
            "enable_supply_chain": True,
            "resource_multiplier": 1.0,
            "provider_density": 0.0,
        },
    },
    "DOSE_1": {
        "label": "1 provider/1000",
        "group": "dose",
        "overrides": {
            **AI_SETTINGS,
            "enable_supply_chain": True,
            "resource_multiplier": 1.0,
            "provider_density": 1.0,
        },
    },
    "DOSE_10": {
        "label": "10 providers/1000",
        "group": "dose",
        "overrides": {
            **AI_SETTINGS,
            "enable_supply_chain": True,
            "resource_multiplier": 1.0,
            "provider_density": 10.0,
        },
    },
    "DOSE_50": {
        "label": "50 providers/1000",
        "group": "dose",
        "overrides": {
            **AI_SETTINGS,
            "enable_supply_chain": True,
            "resource_multiplier": 1.0,
            "provider_density": 50.0,
        },
    },

    # ── Part 3: Vaccine targeting ──
    "VAX_LOW_PROVIDER": {
        "label": "Vaccines + 1 provider/1000",
        "group": "vax",
        "overrides": {
            **AI_SETTINGS,
            "enable_supply_chain": True,
            "resource_multiplier": 1.0,
            "provider_density": 1.0,
            "continent_vaccine_stockpile": 45_000,
            "continent_pill_stockpile": 18_000,
        },
    },
    "VAX_HIGH_PROVIDER": {
        "label": "Vaccines + 50 providers/1000",
        "group": "vax",
        "overrides": {
            **AI_SETTINGS,
            "enable_supply_chain": True,
            "resource_multiplier": 1.0,
            "provider_density": 50.0,
            "continent_vaccine_stockpile": 45_000,
            "continent_pill_stockpile": 18_000,
        },
    },

    # ── Part 4: Behavioral diagnosis (supply depletion resilience) ──
    "BEH_DX_OFF": {
        "label": "Lab-only (no behavioral dx)",
        "group": "behavioral",
        "overrides": {
            **AI_SETTINGS,
            "enable_supply_chain": True,
            "resource_multiplier": 1.0,
            "provider_density": 50.0,
            "behavioral_diagnosis_accuracy": 0.0,
        },
    },
    "BEH_DX_ON": {
        "label": "Behavioral dx (50% accuracy)",
        "group": "behavioral",
        "overrides": {
            **AI_SETTINGS,
            "enable_supply_chain": True,
            "resource_multiplier": 1.0,
            "provider_density": 50.0,
            "behavioral_diagnosis_accuracy": 0.5,
        },
    },
}


# ── Simulation runner ─────────────────────────────────────────────────────────

@dataclass
class ExperimentResult:
    key: str
    label: str
    runtime: float
    total_pop: int
    total_infected: int
    total_deaths: int
    total_recovered: int
    attack_rate: float
    cfr: float
    peak_day: int
    peak_active: int
    detection_rate_final: float
    daily_I: np.ndarray
    daily_D: np.ndarray
    daily_S: np.ndarray
    daily_R: np.ndarray
    daily_obs_I: np.ndarray | None = None  # Observed infectious (for detection analysis)


def run_experiment(key: str) -> ExperimentResult:
    """Run a single experiment configuration."""
    cfg = EXPERIMENTS[key]
    cache_path = RESULTS_DIR / f"{key}.npz"
    meta_path = RESULTS_DIR / f"{key}_meta.json"

    if cache_path.exists() and meta_path.exists():
        print(f"  Loading cached {key}")
        data = np.load(cache_path)
        with open(meta_path) as f:
            meta = json.load(f)
        return ExperimentResult(
            key=key, label=cfg["label"],
            runtime=meta["runtime"], total_pop=meta["total_pop"],
            total_infected=meta["total_infected"], total_deaths=meta["total_deaths"],
            total_recovered=meta["total_recovered"], attack_rate=meta["attack_rate"],
            cfr=meta["cfr"], peak_day=meta["peak_day"],
            peak_active=meta["peak_active"],
            detection_rate_final=meta["detection_rate_final"],
            daily_I=data["daily_I"], daily_D=data["daily_D"],
            daily_S=data["daily_S"], daily_R=data["daily_R"],
            daily_obs_I=data["daily_obs_I"] if "daily_obs_I" in data else None,
        )

    print(f"\n{'─'*60}")
    print(f"  Running: {key} — {cfg['label']}")
    print(f"{'─'*60}")

    params = SimulationParams(
        country=COUNTRY,
        scenario=SCENARIO,
        days=DAYS,
        debug_validation=True,
        **cfg["overrides"],
    )

    t0 = time.time()
    result = run_absdes_simulation(params)
    elapsed = time.time() - t0

    n_cities = len(result.city_names)
    last = result.actual_S.shape[1] - 1
    scale = np.array([
        result.city_populations[i] / result.n_people_per_city
        for i in range(n_cities)
    ])

    daily_I = np.zeros(DAYS + 1)
    daily_D = np.zeros(DAYS + 1)
    daily_S = np.zeros(DAYS + 1)
    daily_R = np.zeros(DAYS + 1)
    daily_obs_I = np.zeros(DAYS + 1)
    for d in range(DAYS + 1):
        daily_I[d] = sum(int(result.actual_I[i, d]) * scale[i] for i in range(n_cities))
        daily_D[d] = sum(int(result.actual_D[i, d]) * scale[i] for i in range(n_cities))
        daily_S[d] = sum(int(result.actual_S[i, d]) * scale[i] for i in range(n_cities))
        daily_R[d] = sum(int(result.actual_R[i, d]) * scale[i] for i in range(n_cities))
        daily_obs_I[d] = sum(int(result.observed_I[i, d]) * scale[i] for i in range(n_cities))

    obs_total = sum(
        (result.observed_I[i, last] + result.observed_R[i, last] + result.observed_D[i, last])
        for i in range(n_cities)
    )
    act_total = sum(
        (result.n_people_per_city - int(result.actual_S[i, last]))
        for i in range(n_cities)
    )
    detection_rate_final = obs_total / act_total if act_total > 0 else 0

    total_pop = sum(result.city_populations)
    total_infected = int(sum(
        (result.n_people_per_city - int(result.actual_S[i, last])) * scale[i]
        for i in range(n_cities)
    ))
    total_deaths = int(daily_D[last])
    total_recovered = int(daily_R[last])
    peak_day = int(np.argmax(daily_I))
    peak_active = int(daily_I[peak_day])
    attack_rate = total_infected / total_pop if total_pop > 0 else 0
    cfr = total_deaths / total_infected if total_infected > 0 else 0

    np.savez_compressed(cache_path, daily_I=daily_I, daily_D=daily_D,
                        daily_S=daily_S, daily_R=daily_R,
                        daily_obs_I=daily_obs_I)
    meta = {
        "runtime": elapsed, "total_pop": int(total_pop),
        "total_infected": total_infected, "total_deaths": total_deaths,
        "total_recovered": total_recovered, "attack_rate": attack_rate,
        "cfr": cfr, "peak_day": peak_day, "peak_active": peak_active,
        "detection_rate_final": detection_rate_final,
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"  Done in {elapsed:.0f}s: {total_deaths:,} deaths, CFR={cfr:.2%}, detect={detection_rate_final:.1%}")

    return ExperimentResult(key=key, label=cfg["label"], **meta,
                            daily_I=daily_I, daily_D=daily_D,
                            daily_S=daily_S, daily_R=daily_R,
                            daily_obs_I=daily_obs_I)


# ── Plotting ──────────────────────────────────────────────────────────────────

def plot_edge_cases(results: dict[str, ExperimentResult]):
    """Fig 1: Death rate bounds — floor, ceiling, and advice-only."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    keys = ["CEILING", "ADVICE_ONLY", "FLOOR"]
    labels = ["No providers\nNo supplies\n(ceiling)", "AI providers\nNo supplies\n(advice only)", "AI providers\nInfinite supplies\n(floor)"]
    deaths = [results[k].total_deaths for k in keys]
    cfrs = [results[k].cfr for k in keys]
    colors = ["#e74c3c", "#f39c12", "#27ae60"]

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    ax1, ax2, ax3 = axes

    # Panel 1: Bar chart of total deaths
    bars = ax1.bar(range(3), [d / 1e6 for d in deaths], color=colors,
                   edgecolor="white", width=0.6)
    for bar, d, cfr in zip(bars, deaths, cfrs):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                 f"{d/1e6:.2f}M\n({cfr:.1%} CFR)", ha="center", va="bottom",
                 fontsize=10, fontweight="bold")
    ax1.set_xticks(range(3))
    ax1.set_xticklabels(labels, fontsize=9)
    ax1.set_ylabel("Total Deaths (millions)", fontsize=11)
    ax1.set_title("Death Rate Bounds", fontsize=13, fontweight="bold")
    ax1.grid(axis="y", alpha=0.3)

    # Annotations
    lives_saved_advice = deaths[0] - deaths[1]
    lives_saved_supplies = deaths[1] - deaths[2]
    ax1.annotate(f"Advice alone\nsaves {lives_saved_advice/1e6:.2f}M",
                 xy=(0.5, (deaths[0] + deaths[1]) / 2 / 1e6),
                 xytext=(1.5, deaths[0] / 1e6 * 0.9),
                 fontsize=9, ha="center",
                 arrowprops=dict(arrowstyle="->", color="#666"))
    ax1.annotate(f"Supplies save\n{lives_saved_supplies/1e6:.2f}M more",
                 xy=(1.5, (deaths[1] + deaths[2]) / 2 / 1e6),
                 xytext=(2.3, deaths[1] / 1e6 * 0.9),
                 fontsize=9, ha="center",
                 arrowprops=dict(arrowstyle="->", color="#666"))

    # Panel 2: Active cases (infection dynamics — nearly identical for Advice & Floor)
    t = np.arange(DAYS + 1)
    for key, color, label in zip(keys, colors, ["Ceiling", "Advice only", "Floor"]):
        r = results[key]
        ax2.plot(t, r.daily_I / 1e6, color=color, linewidth=2, label=label)
    ax2.set_xlabel("Day", fontsize=11)
    ax2.set_ylabel("Active Cases (millions)", fontsize=11)
    ax2.set_title("Infection Dynamics\n(advice reduces transmission)", fontsize=12, fontweight="bold")
    ax2.legend(fontsize=9)
    ax2.grid(alpha=0.3)

    # Panel 3: Cumulative deaths (reveals the CFR difference)
    for key, color, label in zip(keys, colors, ["Ceiling", "Advice only", "Floor"]):
        r = results[key]
        ax3.plot(t, r.daily_D / 1e6, color=color, linewidth=2, label=label)
    ax3.set_xlabel("Day", fontsize=11)
    ax3.set_ylabel("Cumulative Deaths (millions)", fontsize=11)
    ax3.set_title("Mortality\n(supplies reduce case fatality)", fontsize=12, fontweight="bold")
    ax3.legend(fontsize=9)
    ax3.grid(alpha=0.3)

    fig.suptitle(
        f"Part 1: Death Rate Bounds — Advice Reduces Spread, Supplies Reduce Fatality\n"
        f"COVID Bioattack, {COUNTRY}, {DAYS} days",
        fontsize=14, fontweight="bold"
    )
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "fig_01_edge_cases.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved fig_01_edge_cases.png")


def plot_dose_response(results: dict[str, ExperimentResult]):
    """Fig 2: Provider density dose-response curve."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    keys = ["DOSE_0", "DOSE_1", "DOSE_10", "DOSE_50"]
    densities = [0, 1, 10, 50]
    deaths = [results[k].total_deaths for k in keys]
    detection = [results[k].detection_rate_final * 100 for k in keys]
    colors = ["#95a5a6", "#e74c3c", "#3498db", "#27ae60"]

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(16, 5.5))

    # Deaths vs density
    bars = ax1.bar(range(4), [d / 1e6 for d in deaths], color=colors,
                   edgecolor="white", width=0.6)
    for bar, d in zip(bars, deaths):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                 f"{d/1e6:.2f}M", ha="center", va="bottom", fontsize=10,
                 fontweight="bold")
    ax1.set_xticks(range(4))
    ax1.set_xticklabels([str(d) for d in densities], fontsize=10)
    ax1.set_xlabel("AI Providers per 1000", fontsize=10)
    ax1.set_ylabel("Total Deaths (millions)", fontsize=11)
    ax1.set_title("Deaths vs Provider Density", fontsize=12, fontweight="bold")
    ax1.grid(axis="y", alpha=0.3)

    # Detection rate
    bars = ax2.bar(range(4), detection, color=colors, edgecolor="white", width=0.6)
    for bar, d in zip(bars, detection):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                 f"{d:.0f}%", ha="center", va="bottom", fontsize=10,
                 fontweight="bold")
    ax2.set_xticks(range(4))
    ax2.set_xticklabels([str(d) for d in densities], fontsize=10)
    ax2.set_xlabel("AI Providers per 1000", fontsize=10)
    ax2.set_ylabel("Detection Rate (%)", fontsize=11)
    ax2.set_title("Detection vs Provider Density", fontsize=12, fontweight="bold")
    ax2.set_ylim(0, 110)
    ax2.grid(axis="y", alpha=0.3)

    # Epidemic curves
    t = np.arange(DAYS + 1)
    for key, color, d in zip(keys, colors, densities):
        r = results[key]
        ax3.plot(t, r.daily_I / 1e6, color=color, linewidth=2, label=f"{d}/1000")
    ax3.set_xlabel("Day", fontsize=11)
    ax3.set_ylabel("Active Cases (millions)", fontsize=11)
    ax3.set_title("Epidemic Curves", fontsize=12, fontweight="bold")
    ax3.legend(title="Providers", fontsize=9)
    ax3.grid(alpha=0.3)

    fig.suptitle(
        f"Part 2: AI Healthworker Dose-Response\n"
        f"COVID Bioattack, {COUNTRY}, {DAYS} days, Standard Supplies",
        fontsize=14, fontweight="bold"
    )
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "fig_02_dose_response.png", dpi=150,
                bbox_inches="tight")
    plt.close(fig)
    print("  Saved fig_02_dose_response.png")


def plot_vaccine_targeting(results: dict[str, ExperimentResult]):
    """Fig 3: Vaccine targeting — same supply, different outcomes."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    keys = ["VAX_LOW_PROVIDER", "VAX_HIGH_PROVIDER"]
    labels = ["1 provider/1000\n(poor targeting)", "50 providers/1000\n(contact-traced targeting)"]
    deaths = [results[k].total_deaths for k in keys]
    detection = [results[k].detection_rate_final * 100 for k in keys]
    colors = ["#e74c3c", "#27ae60"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Deaths comparison
    bars = ax1.bar(range(2), [d / 1e6 for d in deaths], color=colors,
                   edgecolor="white", width=0.5)
    for bar, d in zip(bars, deaths):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                 f"{d/1e6:.2f}M", ha="center", va="bottom", fontsize=13,
                 fontweight="bold")
    ax1.set_xticks(range(2))
    ax1.set_xticklabels(labels, fontsize=10)
    ax1.set_ylabel("Total Deaths (millions)", fontsize=12)
    ax1.set_title("Same Vaccines, Different Targeting", fontsize=13,
                  fontweight="bold")
    ax1.grid(axis="y", alpha=0.3)

    lives_saved = deaths[0] - deaths[1]
    if lives_saved > 0:
        ax1.text(0.5, max(deaths) / 1e6 * 0.5,
                 f"Better targeting saves\n{lives_saved:,} lives",
                 ha="center", fontsize=12, fontweight="bold", color="#2c3e50",
                 transform=ax1.get_xaxis_transform())

    # Epidemic curves
    t = np.arange(DAYS + 1)
    for key, color, label in zip(keys, colors,
                                  ["1/1000 (random vax)", "50/1000 (targeted vax)"]):
        r = results[key]
        ax2.plot(t, r.daily_D / 1e6, color=color, linewidth=2, label=label)
    ax2.set_xlabel("Day", fontsize=11)
    ax2.set_ylabel("Cumulative Deaths (millions)", fontsize=11)
    ax2.set_title("Death Trajectories", fontsize=13, fontweight="bold")
    ax2.legend(fontsize=10)
    ax2.grid(alpha=0.3)

    fig.suptitle(
        f"Part 3: Provider-Driven Vaccine Targeting\n"
        f"COVID Bioattack, {COUNTRY}, {DAYS} days — Same vaccine supply, different AI coverage",
        fontsize=14, fontweight="bold"
    )
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "fig_03_vaccine_targeting.png", dpi=150,
                bbox_inches="tight")
    plt.close(fig)
    print("  Saved fig_03_vaccine_targeting.png")


def plot_behavioral_diagnosis(results: dict[str, ExperimentResult]):
    """Fig 4: Behavioral diagnosis — supply depletion resilience."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    r_off = results["BEH_DX_OFF"]
    r_on = results["BEH_DX_ON"]
    t = np.arange(DAYS + 1)

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(18, 6))

    # Panel 1: Detection over time (observed_I vs actual_I)
    if r_off.daily_obs_I is not None and r_on.daily_obs_I is not None:
        # Detection rate = observed_I / actual_I (clamped)
        with np.errstate(divide="ignore", invalid="ignore"):
            rate_off = np.where(r_off.daily_I > 0,
                                r_off.daily_obs_I / r_off.daily_I, 0)
            rate_on = np.where(r_on.daily_I > 0,
                               r_on.daily_obs_I / r_on.daily_I, 0)
        ax1.plot(t, rate_off * 100, color="#e74c3c", linewidth=2,
                 label="Lab-only (dx=0%)")
        ax1.plot(t, rate_on * 100, color="#27ae60", linewidth=2,
                 label="Behavioral dx (50%)")
        ax1.set_ylabel("Detection Rate (%)", fontsize=11)
        ax1.set_xlabel("Day", fontsize=11)
        ax1.set_title("Surveillance Coverage\n(observed / actual infectious)",
                       fontsize=12, fontweight="bold")
        ax1.set_ylim(-2, 105)
        ax1.axhline(y=0, color="#999", linewidth=0.5)
        ax1.legend(fontsize=10)
        ax1.grid(alpha=0.3)

        # Annotate the gap
        mid = DAYS // 2
        ax1.annotate(
            f"Without behavioral dx,\ndetection drops to 0%\nwhen supplies deplete",
            xy=(mid, rate_off[mid] * 100),
            xytext=(mid + 20, 40),
            fontsize=9, ha="center",
            arrowprops=dict(arrowstyle="->", color="#666"))
    else:
        ax1.text(0.5, 0.5, "No observed data\n(re-run to populate cache)",
                 transform=ax1.transAxes, ha="center", va="center", fontsize=12)
        ax1.set_title("Surveillance Coverage", fontsize=12, fontweight="bold")

    # Panel 2: Deaths comparison (bar chart)
    keys = ["BEH_DX_OFF", "BEH_DX_ON"]
    labels = ["Lab-only\n(dx accuracy = 0%)", "Behavioral dx\n(dx accuracy = 50%)"]
    deaths = [results[k].total_deaths for k in keys]
    colors = ["#e74c3c", "#27ae60"]

    bars = ax2.bar(range(2), [d / 1e6 for d in deaths], color=colors,
                   edgecolor="white", width=0.5)
    for bar, d, k in zip(bars, deaths, keys):
        r = results[k]
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                 f"{d/1e6:.2f}M\n({r.cfr:.1%} CFR)", ha="center", va="bottom",
                 fontsize=10, fontweight="bold")
    ax2.set_xticks(range(2))
    ax2.set_xticklabels(labels, fontsize=10)
    ax2.set_ylabel("Total Deaths (millions)", fontsize=11)
    ax2.set_title("Mortality Impact", fontsize=12, fontweight="bold")
    ax2.grid(axis="y", alpha=0.3)

    lives_saved = deaths[0] - deaths[1]
    if lives_saved > 0:
        ax2.text(0.5, max(deaths) / 1e6 * 0.5,
                 f"Behavioral dx saves\n{lives_saved:,} lives",
                 ha="center", fontsize=11, fontweight="bold", color="#2c3e50",
                 transform=ax2.get_xaxis_transform())

    # Panel 3: Observed vs Actual epidemic curves
    ax3.plot(t, r_on.daily_I / 1e6, color="#3498db", linewidth=2,
             label="Actual infectious", linestyle="-")
    if r_on.daily_obs_I is not None:
        ax3.plot(t, r_on.daily_obs_I / 1e6, color="#27ae60", linewidth=2,
                 label="Observed (behavioral dx)", linestyle="-")
    if r_off.daily_obs_I is not None:
        ax3.plot(t, r_off.daily_obs_I / 1e6, color="#e74c3c", linewidth=1.5,
                 label="Observed (lab-only)", linestyle="--")
    ax3.set_xlabel("Day", fontsize=11)
    ax3.set_ylabel("Cases (millions)", fontsize=11)
    ax3.set_title("Actual vs Observed Cases\n(behavioral dx tracks the epidemic)",
                   fontsize=12, fontweight="bold")
    ax3.legend(fontsize=9)
    ax3.grid(alpha=0.3)

    fig.suptitle(
        f"Part 4: Behavioral Diagnosis — Resilience When Diagnostic Supplies Deplete\n"
        f"COVID Bioattack, {COUNTRY}, {DAYS} days — 50 AI providers/1000, standard supplies",
        fontsize=14, fontweight="bold"
    )
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "fig_04_behavioral_diagnosis.png", dpi=150,
                bbox_inches="tight")
    plt.close(fig)
    print("  Saved fig_04_behavioral_diagnosis.png")


def write_summary(results: dict[str, ExperimentResult]):
    """Write markdown summary."""
    r = results

    # Computed values
    lives_advice = r["CEILING"].total_deaths - r["ADVICE_ONLY"].total_deaths
    lives_supplies = r["ADVICE_ONLY"].total_deaths - r["FLOOR"].total_deaths
    lives_total = r["CEILING"].total_deaths - r["FLOOR"].total_deaths
    lives_vax_targeting = r["VAX_LOW_PROVIDER"].total_deaths - r["VAX_HIGH_PROVIDER"].total_deaths
    lives_beh_dx = r["BEH_DX_OFF"].total_deaths - r["BEH_DX_ON"].total_deaths

    md = f"""# Supply Chain Analysis

**Scenario:** COVID Bioattack (R₀=3.5), **Country:** {COUNTRY}, **Duration:** {DAYS} days

---

## Part 1: Death Rate Bounds

| Scenario | Providers | Supplies | Deaths | CFR |
|----------|-----------|----------|--------|-----|
| Ceiling | 0 | 0.01× | {r['CEILING'].total_deaths:,} | {r['CEILING'].cfr:.2%} |
| Advice only | 50/1000 AI | 0.01× | {r['ADVICE_ONLY'].total_deaths:,} | {r['ADVICE_ONLY'].cfr:.2%} |
| Floor | 50/1000 AI | ∞ | {r['FLOOR'].total_deaths:,} | {r['FLOOR'].cfr:.2%} |

- **Advice alone** (no supplies) saves **{lives_advice:,}** lives ({lives_advice/r['CEILING'].total_deaths:.0%} reduction)
- **Supplies** (on top of advice) save **{lives_supplies:,}** additional lives
- **Total gap** (ceiling to floor): **{lives_total:,}** lives

## Part 2: Provider Dose-Response (AI Healthworkers)

| Providers/1000 | Deaths | Detection | CFR | Peak Day |
|----------------|--------|-----------|-----|----------|
| 0 | {r['DOSE_0'].total_deaths:,} | {r['DOSE_0'].detection_rate_final:.1%} | {r['DOSE_0'].cfr:.2%} | {r['DOSE_0'].peak_day} |
| 1 | {r['DOSE_1'].total_deaths:,} | {r['DOSE_1'].detection_rate_final:.1%} | {r['DOSE_1'].cfr:.2%} | {r['DOSE_1'].peak_day} |
| 10 | {r['DOSE_10'].total_deaths:,} | {r['DOSE_10'].detection_rate_final:.1%} | {r['DOSE_10'].cfr:.2%} | {r['DOSE_10'].peak_day} |
| 50 | {r['DOSE_50'].total_deaths:,} | {r['DOSE_50'].detection_rate_final:.1%} | {r['DOSE_50'].cfr:.2%} | {r['DOSE_50'].peak_day} |

## Part 3: Vaccine Targeting

Same vaccine supply ({45_000:,} doses), different provider coverage:

| Scenario | Deaths | Detection | Lives Saved vs Low |
|----------|--------|-----------|-------------------|
| 1/1000 (random targeting) | {r['VAX_LOW_PROVIDER'].total_deaths:,} | {r['VAX_LOW_PROVIDER'].detection_rate_final:.1%} | — |
| 50/1000 (contact-traced) | {r['VAX_HIGH_PROVIDER'].total_deaths:,} | {r['VAX_HIGH_PROVIDER'].detection_rate_final:.1%} | {lives_vax_targeting:,} |

**Key insight:** With 50× more AI providers, contact tracing identifies high-risk
individuals, enabling targeted vaccination that saves **{lives_vax_targeting:,}** additional lives
with the exact same vaccine supply.

## Part 4: Behavioral Diagnosis (Supply Depletion Resilience)

When diagnostic supplies (swabs, reagents, PPE) deplete, can clinical assessment maintain surveillance?

| Scenario | Deaths | Detection | CFR | Lives Saved |
|----------|--------|-----------|-----|-------------|
| Lab-only (behavioral dx = 0%) | {r['BEH_DX_OFF'].total_deaths:,} | {r['BEH_DX_OFF'].detection_rate_final:.1%} | {r['BEH_DX_OFF'].cfr:.2%} | — |
| Behavioral dx (50% accuracy) | {r['BEH_DX_ON'].total_deaths:,} | {r['BEH_DX_ON'].detection_rate_final:.1%} | {r['BEH_DX_ON'].cfr:.2%} | {lives_beh_dx:,} |

**Key insight:** With standard supplies, high provider density (50/1000) depletes diagnostic
supplies rapidly. Without behavioral diagnosis, detection drops to zero and the surveillance
system goes blind. With 50% clinical assessment accuracy, providers maintain tracking of the
epidemic even after supply depletion — saving **{lives_beh_dx:,}** lives through sustained
contact tracing and targeted interventions.
"""
    path = RESULTS_DIR / "summary.md"
    with open(path, "w") as f:
        f.write(md)
    print(f"  Saved {path.name}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  SUPPLY CHAIN ANALYSIS")
    print("=" * 60)
    print(f"  Scenario: {SCENARIO}")
    print(f"  Country: {COUNTRY}")
    print(f"  Days: {DAYS}")
    print(f"  AI settings: isolation={AI_SETTINGS['advised_isolation_prob']}, "
          f"disclosure={AI_SETTINGS['disclosure_prob']}")
    print()

    # Run all experiments
    results = {}
    for key in EXPERIMENTS:
        results[key] = run_experiment(key)

    # Summary table
    print("\n" + "=" * 90)
    print("  RESULTS SUMMARY")
    print("=" * 90)
    print(f"\n  {'Config':<20} {'Deaths':>10} {'CFR':>8} {'Detection':>10} {'Peak':>6}")
    print(f"  {'─'*20} {'─'*10} {'─'*8} {'─'*10} {'─'*6}")
    for key, r in results.items():
        print(f"  {key:<20} {r.total_deaths:>10,} {r.cfr:>8.2%} "
              f"{r.detection_rate_final:>9.1%} {r.peak_day:>6}")

    # Generate plots
    print("\nGenerating plots...")
    plot_edge_cases(results)
    plot_dose_response(results)
    plot_vaccine_targeting(results)
    plot_behavioral_diagnosis(results)
    write_summary(results)

    print("\nDone!")


if __name__ == "__main__":
    main()
