#!/usr/bin/env python3
"""
Supply Chain Constraint Analysis: COVID Bioattack across Continental Africa.

Compares 4 configurations:
  A: Baseline           - standard healthcare, no supply chain tracking
  B: Behavioral AI      - AI provider agents, no supply chain tracking
  C: Supply + Rules     - AI providers + rule-based supply chain management
  D: Supply + AI        - AI providers + AI-optimized supply chain management

Generates:
  results/01_deaths_comparison.png     - Bar chart of total deaths by config
  results/02_epidemic_curves.png       - Active cases over time (4 panels)
  results/02b_resource_demand.png      - Shadow resource demand for Config B
  results/03_detection_and_supply.png  - Detection rate + stockout timeline
  results/04_supply_chain_events.png   - Event breakdown by category
  results/05_attack_rate_cfr.png       - Attack rate and CFR comparison

Usage:
    cd 008_supply_chain_constrained && python supply_chain_analysis.py
"""

import sys
import time
import json
from pathlib import Path

import numpy as np

# Path setup
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _PROJECT_ROOT / "simulation_app" / "backend"
sys.path.insert(0, str(_BACKEND))

from simulation import SimulationParams, run_absdes_simulation

RESULTS_DIR = Path(__file__).parent / "results"

# ── Scenario configuration ────────────────────────────────────────────────────

DAYS = 250
SCENARIO = "covid_bioattack"
COUNTRY = "ALL"

# Realistic limited stockpiles scaled to DES population
# DES: 442 cities x 5000 agents = 2.21M. Real Africa pop ~242M. Scale ~110x.
# 5M real vaccines -> ~45K DES-scale; 2M real pills -> ~18K DES-scale
CONTINENT_VACCINES = 45_000
CONTINENT_PILLS = 18_000

# AI behavioral parameters
AI_BEHAVIORAL = dict(
    provider_density=50.0,
    screening_capacity=200,
    advised_isolation_prob=0.55,
    disclosure_prob=0.80,
    receptivity_override=0.85,
)

CONFIGS = {
    "A": {
        "label": "Baseline",
        "description": "Standard healthcare, no supply chain",
        "overrides": {},
    },
    "B": {
        "label": "Behavioral AI",
        "description": "AI providers (10x density, 10x screening), no supply chain",
        "overrides": {**AI_BEHAVIORAL},
    },
    "C": {
        "label": "Supply + Rules",
        "description": "AI providers + rule-based supply chain",
        "overrides": {
            **AI_BEHAVIORAL,
            "enable_supply_chain": True,
            "allocation_strategy": "rule_based",
            "continent_vaccine_stockpile": CONTINENT_VACCINES,
            "continent_pill_stockpile": CONTINENT_PILLS,
        },
    },
    "D": {
        "label": "Supply + AI",
        "description": "AI providers + AI-optimized supply chain",
        "overrides": {
            **AI_BEHAVIORAL,
            "enable_supply_chain": True,
            "allocation_strategy": "ai_optimized",
            "continent_vaccine_stockpile": CONTINENT_VACCINES,
            "continent_pill_stockpile": CONTINENT_PILLS,
        },
    },
}


# ── Simulation runner with caching ────────────────────────────────────────────

def run_config(key: str) -> dict:
    """Run a single configuration. Caches full time-series to .npz."""
    cfg = CONFIGS[key]
    cache_path = RESULTS_DIR / f"config_{key}.npz"
    meta_path = RESULTS_DIR / f"config_{key}_meta.json"

    if cache_path.exists() and meta_path.exists():
        print(f"  Loading cached {cache_path.name}")
        data = np.load(cache_path)
        with open(meta_path) as f:
            meta = json.load(f)
        return {**{k: data[k] for k in data.files}, **meta}

    print(f"\n{'='*60}")
    print(f"  Running: {key}: {cfg['label']}")
    print(f"  {cfg['description']}")
    print(f"{'='*60}")

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

    # Compute daily aggregated time series (scaled to real populations)
    daily_I = np.zeros(DAYS + 1)
    daily_D = np.zeros(DAYS + 1)
    daily_S = np.zeros(DAYS + 1)
    daily_R = np.zeros(DAYS + 1)
    for d in range(DAYS + 1):
        daily_I[d] = sum(int(result.actual_I[i, d]) * scale[i] for i in range(n_cities))
        daily_D[d] = sum(int(result.actual_D[i, d]) * scale[i] for i in range(n_cities))
        daily_S[d] = sum(int(result.actual_S[i, d]) * scale[i] for i in range(n_cities))
        daily_R[d] = sum(int(result.actual_R[i, d]) * scale[i] for i in range(n_cities))

    # New infections per day
    daily_new = np.diff(np.concatenate([[0], daily_S[0] - daily_S]))
    daily_new = np.abs(daily_new)  # S decreases

    # Shadow demand: aggregate per-city daily demand → continent total (scaled)
    demand_ppe = np.zeros(DAYS + 1)
    demand_swabs = np.zeros(DAYS + 1)
    demand_reagents = np.zeros(DAYS + 1)
    demand_pills = np.zeros(DAYS + 1)
    demand_beds = np.zeros(DAYS + 1)
    demand_vaccines = np.zeros(DAYS + 1)
    if result.shadow_demand_ppe is not None:
        for d in range(DAYS + 1):
            demand_ppe[d] = sum(result.shadow_demand_ppe[i, d] * scale[i] for i in range(n_cities))
            demand_swabs[d] = sum(result.shadow_demand_swabs[i, d] * scale[i] for i in range(n_cities))
            demand_reagents[d] = sum(result.shadow_demand_reagents[i, d] * scale[i] for i in range(n_cities))
            demand_pills[d] = sum(result.shadow_demand_pills[i, d] * scale[i] for i in range(n_cities))
            demand_beds[d] = sum(result.shadow_demand_beds[i, d] * scale[i] for i in range(n_cities))
            demand_vaccines[d] = sum(result.shadow_demand_vaccines[i, d] * scale[i] for i in range(n_cities))

    # Detection rate over time
    daily_detection = np.zeros(DAYS + 1)
    for d in range(DAYS + 1):
        obs_total = sum(
            (result.observed_I[i, d] + result.observed_R[i, d] + result.observed_D[i, d])
            for i in range(n_cities)
        )
        act_total = sum(
            (result.n_people_per_city - int(result.actual_S[i, d]))
            for i in range(n_cities)
        )
        daily_detection[d] = obs_total / act_total if act_total > 0 else 0

    total_pop = sum(result.city_populations)
    total_infected = sum(
        (result.n_people_per_city - int(result.actual_S[i, last])) * scale[i]
        for i in range(n_cities)
    )
    total_deaths = float(daily_D[last])
    total_recovered = float(daily_R[last])

    peak_day = int(np.argmax(daily_I))
    peak_active = float(daily_I[peak_day])

    attack_rate = total_infected / total_pop
    cfr = total_deaths / total_infected if total_infected > 0 else 0
    detection_rate = float(daily_detection[last])

    # Event log summary
    elog = result.event_log
    summary = elog.summary() if elog else {}
    by_cat = summary.get("by_category", {})

    meta = {
        "key": key,
        "label": cfg["label"],
        "runtime": elapsed,
        "total_pop": int(total_pop),
        "total_infected": float(total_infected),
        "total_deaths": float(total_deaths),
        "total_recovered": float(total_recovered),
        "attack_rate": float(attack_rate),
        "cfr": float(cfr),
        "peak_day": peak_day,
        "peak_active": float(peak_active),
        "detection_rate": float(detection_rate),
        "stockout_events": int(by_cat.get("stockout", 0)),
        "redistribution_events": int(by_cat.get("redistribution", 0)),
        "deployment_events": int(by_cat.get("deployment", 0)),
        "vaccination_events": int(by_cat.get("vaccination", 0)),
        "total_events": int(summary.get("total_events", 0)),
    }

    # Save cache
    np.savez_compressed(
        cache_path,
        daily_I=daily_I,
        daily_D=daily_D,
        daily_S=daily_S,
        daily_R=daily_R,
        daily_new=daily_new,
        daily_detection=daily_detection,
        demand_ppe=demand_ppe,
        demand_swabs=demand_swabs,
        demand_reagents=demand_reagents,
        demand_pills=demand_pills,
        demand_beds=demand_beds,
        demand_vaccines=demand_vaccines,
    )
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"  Completed in {elapsed:.0f}s: deaths={int(total_deaths):,}, attack_rate={attack_rate:.1%}")
    return {**{
        "daily_I": daily_I,
        "daily_D": daily_D,
        "daily_S": daily_S,
        "daily_R": daily_R,
        "daily_new": daily_new,
        "daily_detection": daily_detection,
        "demand_ppe": demand_ppe,
        "demand_swabs": demand_swabs,
        "demand_reagents": demand_reagents,
        "demand_pills": demand_pills,
        "demand_beds": demand_beds,
        "demand_vaccines": demand_vaccines,
    }, **meta}


# ── Plotting functions ────────────────────────────────────────────────────────

def generate_fig1(results: dict):
    """Fig 1: Total deaths comparison — bar chart with lives saved annotations."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    keys = list(results.keys())
    labels = [f"{k}: {results[k]['label']}" for k in keys]
    deaths = [results[k]["total_deaths"] for k in keys]
    baseline_deaths = deaths[0]

    colors = ["#95a5a6", "#3498db", "#e67e22", "#e74c3c"]

    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.bar(range(len(keys)), [d / 1e6 for d in deaths], color=colors,
                  edgecolor="white", linewidth=1.5, width=0.6)

    # Annotate deaths and delta
    for i, (bar, d) in enumerate(zip(bars, deaths)):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.03,
                f"{d / 1e6:.2f}M", ha="center", va="bottom", fontsize=11, fontweight="bold")
        if i > 0:
            delta = (d / baseline_deaths - 1) * 100
            sign = "+" if delta > 0 else ""
            color = "#27ae60" if delta < 0 else "#c0392b"
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() / 2,
                    f"{sign}{delta:.1f}%", ha="center", va="center",
                    fontsize=10, color="white", fontweight="bold")

    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel("Total Deaths (millions)", fontsize=12)
    ax.set_title(
        "Fig 1: Total Deaths by Configuration\n"
        f"COVID Bioattack (R$_0$=3.5), Continental Africa, {DAYS} days",
        fontsize=13, fontweight="bold",
    )
    ax.grid(axis="y", alpha=0.3)
    ax.set_ylim(0, max(deaths) / 1e6 * 1.2)

    # Add annotation box
    lives_saved_b = int(baseline_deaths - deaths[1])
    ax.text(0.98, 0.95,
            f"Best: Config B\n"
            f"Lives saved vs baseline: {lives_saved_b:,}\n"
            f"Supply chain ON increases deaths\n"
            f"due to resource stockouts",
            transform=ax.transAxes, fontsize=9, va="top", ha="right",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="lightyellow", alpha=0.8))

    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "01_deaths_comparison.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved 01_deaths_comparison.png")


def generate_fig2(results: dict):
    """Fig 2: Epidemic curves — active cases over time (4 panels)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(16, 10), sharex=True, sharey=True)
    colors = {"A": "#95a5a6", "B": "#3498db", "C": "#e67e22", "D": "#e74c3c"}
    t = np.arange(DAYS + 1)

    for idx, (key, ax) in enumerate(zip(results.keys(), axes.flat)):
        r = results[key]
        ax.fill_between(t, r["daily_I"] / 1e6, alpha=0.3, color=colors[key])
        ax.plot(t, r["daily_I"] / 1e6, color=colors[key], linewidth=1.5)

        # Mark peak
        peak_d = r["peak_day"]
        peak_v = r["peak_active"] / 1e6
        ax.axvline(peak_d, color="gray", linestyle="--", alpha=0.5)
        ax.annotate(f"Peak: day {peak_d}\n{peak_v:.1f}M",
                    xy=(peak_d, peak_v), xytext=(peak_d + 20, peak_v * 0.8),
                    fontsize=8, arrowprops=dict(arrowstyle="->", color="gray"))

        ax.set_title(f"{key}: {r['label']}", fontsize=11, fontweight="bold")
        ax.set_ylabel("Active Cases (millions)" if idx % 2 == 0 else "")
        ax.set_xlabel("Day" if idx >= 2 else "")
        ax.grid(alpha=0.3)

    fig.suptitle(
        "Fig 2: Active Infection Curves by Configuration\n"
        f"COVID Bioattack (R$_0$=3.5), Continental Africa, 242M population",
        fontsize=13, fontweight="bold",
    )
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "02_epidemic_curves.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved 02_epidemic_curves.png")


def generate_fig2b(results: dict):
    """Fig 2b: Shadow resource demand for Config B — screening vs care breakdown."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    r = results["B"]
    t = np.arange(DAYS + 1)

    # Check if demand data exists
    if "demand_ppe" not in r or np.sum(r["demand_ppe"]) == 0:
        print("  SKIP 02b_resource_demand.png (no shadow demand data — delete config_B cache and re-run)")
        return

    def smooth(arr, w=7):
        kernel = np.ones(w) / w
        return np.convolve(arr, kernel, mode="same")

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # ── Top-left: Daily screening resource demand ──
    ax1 = axes[0, 0]
    ax1.plot(t, smooth(r["demand_swabs"]) / 1e6, color="#3498db", linewidth=2,
             label="Swabs (= Reagents)")
    ax1.plot(t, smooth(r["demand_ppe"] - r["demand_swabs"]) / 1e6,
             color="#e74c3c", linewidth=2, alpha=0.7,
             label="PPE for care (2/patient/day)", linestyle="--")
    # Note: screening PPE ≈ swabs since 1:1; total PPE = screening + care
    ax1.fill_between(t, 0, smooth(r["demand_swabs"]) / 1e6,
                     alpha=0.15, color="#3498db")
    ax1.set_xlabel("Day", fontsize=10)
    ax1.set_ylabel("Daily Units (millions, 7-day avg)", fontsize=10)
    ax1.set_title("Screening Resources: Daily Demand", fontsize=11, fontweight="bold")
    ax1.legend(fontsize=9)
    ax1.grid(alpha=0.3)

    # Total annotation
    total_swabs = np.sum(r["demand_swabs"])
    total_ppe = np.sum(r["demand_ppe"])
    ax1.text(0.97, 0.95,
             f"250-day totals:\n"
             f"Swabs/Reagents: {total_swabs/1e9:.1f}B each\n"
             f"PPE (total): {total_ppe/1e9:.1f}B\n"
             f"  screening: {total_swabs/1e9:.1f}B\n"
             f"  care: {(total_ppe-total_swabs)/1e6:.0f}M",
             transform=ax1.transAxes, fontsize=8, va="top", ha="right",
             family="monospace",
             bbox=dict(boxstyle="round,pad=0.4", facecolor="lightyellow", alpha=0.9))

    # ── Top-right: Beds needed over time ──
    ax2 = axes[0, 1]
    beds_demand = r["demand_beds"]
    ax2.fill_between(t, 0, beds_demand / 1e3, alpha=0.3, color="#8e44ad")
    ax2.plot(t, beds_demand / 1e3, color="#8e44ad", linewidth=2, label="Beds needed")

    # Overlay actual bed supply from dataset
    # Africa has ~262K beds total (from dataset)
    ax2.axhline(262, color="#2ecc71", linewidth=2, linestyle="--",
                label="Available beds (262K)", alpha=0.8)

    peak_beds_day = int(np.argmax(beds_demand))
    peak_beds = beds_demand[peak_beds_day]
    ax2.annotate(f"Peak: {peak_beds/1e3:.0f}K beds\n(day {peak_beds_day})",
                 xy=(peak_beds_day, peak_beds / 1e3),
                 xytext=(peak_beds_day + 30, peak_beds / 1e3 * 1.1),
                 fontsize=9, color="#8e44ad", fontweight="bold",
                 arrowprops=dict(arrowstyle="->", color="#8e44ad"))

    ax2.set_xlabel("Day", fontsize=10)
    ax2.set_ylabel("Beds (thousands)", fontsize=10)
    ax2.set_title("Hospital Beds: Demand vs Supply", fontsize=11, fontweight="bold")
    ax2.legend(fontsize=9)
    ax2.grid(alpha=0.3)

    # ── Bottom-left: Pills demand over time ──
    ax3 = axes[1, 0]
    ax3.fill_between(t, 0, r["demand_pills"] / 1e3, alpha=0.3, color="#27ae60")
    ax3.plot(t, r["demand_pills"] / 1e3, color="#27ae60", linewidth=2,
             label="Pills needed/day")
    ax3.set_xlabel("Day", fontsize=10)
    ax3.set_ylabel("Pills (thousands/day)", fontsize=10)
    ax3.set_title("Therapeutic Pills: Daily Demand", fontsize=11, fontweight="bold")
    ax3.legend(fontsize=9)
    ax3.grid(alpha=0.3)

    cum_pills = np.cumsum(r["demand_pills"])
    ax3.text(0.97, 0.95,
             f"Total pills: {cum_pills[-1]/1e6:.1f}M courses\n"
             f"Continent reserve: 2M courses\n"
             f"Deficit: {(cum_pills[-1] - 2e6)/1e6:.1f}M",
             transform=ax3.transAxes, fontsize=9, va="top", ha="right",
             family="monospace",
             bbox=dict(boxstyle="round,pad=0.4", facecolor="lightyellow", alpha=0.9))

    # ── Bottom-right: Summary bar chart — total demand vs available ──
    ax4 = axes[1, 1]

    categories = ["PPE\n(sets)", "Swabs", "Reagents", "Pills\n(courses)", "Beds\n(peak)"]
    demand_vals = [
        total_ppe,
        total_swabs,
        np.sum(r["demand_reagents"]),
        cum_pills[-1],
        peak_beds,
    ]
    # Available supply (from dataset / initial seeding)
    # PPE: 500/facility × 62K facilities = 31M
    # Swabs: 1000/lab × 422 labs = 422K
    # Reagents: 2000/lab × 422 labs = 844K
    # Pills: continent reserve 2M
    # Beds: 262K total
    supply_vals = [
        31e6,     # PPE
        422e3,    # Swabs
        844e3,    # Reagents
        2e6,      # Pills
        262e3,    # Beds
    ]
    ratios = [d / s if s > 0 else 0 for d, s in zip(demand_vals, supply_vals)]

    x = np.arange(len(categories))
    bars = ax4.bar(x, ratios, color=["#e74c3c", "#3498db", "#2980b9", "#27ae60", "#8e44ad"],
                   edgecolor="white", width=0.6)

    for bar, ratio in zip(bars, ratios):
        label = f"{ratio:.0f}×" if ratio >= 1 else f"{ratio:.1f}×"
        ax4.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(ratios) * 0.01,
                 label, ha="center", va="bottom", fontsize=10, fontweight="bold")

    ax4.set_xticks(x)
    ax4.set_xticklabels(categories, fontsize=10)
    ax4.set_ylabel("Demand / Available Supply", fontsize=10)
    ax4.set_title("Resource Gap: Demand ÷ Supply", fontsize=11, fontweight="bold")
    ax4.axhline(1, color="black", linestyle=":", alpha=0.5, label="Supply = Demand")
    ax4.set_yscale("log")
    ax4.legend(fontsize=9)
    ax4.grid(axis="y", alpha=0.3)

    fig.suptitle(
        "Fig 2b: Resource Demand Under Unconstrained Behavioral AI (Config B)\n"
        "COVID Bioattack (R$_0$=3.5), Continental Africa — shadow accounting, no supply limits applied",
        fontsize=13, fontweight="bold",
    )
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "02b_resource_demand.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved 02b_resource_demand.png")


def generate_fig3(results: dict):
    """Fig 3: Detection rate and cumulative deaths over time — dual-axis."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    t = np.arange(DAYS + 1)
    colors = {"A": "#95a5a6", "B": "#3498db", "C": "#e67e22", "D": "#e74c3c"}

    # Left panel: Detection rate
    ax1 = axes[0]
    for key in results:
        r = results[key]
        ax1.plot(t, r["daily_detection"] * 100, color=colors[key],
                 linewidth=1.5, label=f"{key}: {r['label']}")
    ax1.set_xlabel("Day", fontsize=11)
    ax1.set_ylabel("Detection Rate (%)", fontsize=11)
    ax1.set_title("Detection Rate Over Time", fontsize=11, fontweight="bold")
    ax1.legend(fontsize=9, loc="upper right")
    ax1.grid(alpha=0.3)
    ax1.set_ylim(0, 105)

    # Right panel: Cumulative deaths
    ax2 = axes[1]
    for key in results:
        r = results[key]
        ax2.plot(t, r["daily_D"] / 1e6, color=colors[key],
                 linewidth=1.5, label=f"{key}: {r['label']}")
    ax2.set_xlabel("Day", fontsize=11)
    ax2.set_ylabel("Cumulative Deaths (millions)", fontsize=11)
    ax2.set_title("Cumulative Deaths Over Time", fontsize=11, fontweight="bold")
    ax2.legend(fontsize=9, loc="upper left")
    ax2.grid(alpha=0.3)

    fig.suptitle(
        "Fig 3: Detection Collapse and Mortality Under Supply Constraints\n"
        f"COVID Bioattack (R$_0$=3.5), Continental Africa",
        fontsize=13, fontweight="bold",
    )
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "03_detection_and_deaths.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved 03_detection_and_deaths.png")


def generate_fig4(results: dict):
    """Fig 4: Supply chain event breakdown — stacked bars for C and D."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 6))

    categories = ["Stockouts", "Redistributions", "Deployments", "Vaccinations"]
    c_vals = [
        results["C"]["stockout_events"],
        results["C"]["redistribution_events"],
        results["C"]["deployment_events"],
        results["C"]["vaccination_events"],
    ]
    d_vals = [
        results["D"]["stockout_events"],
        results["D"]["redistribution_events"],
        results["D"]["deployment_events"],
        results["D"]["vaccination_events"],
    ]

    x = np.arange(len(categories))
    width = 0.35

    bars1 = ax.bar(x - width / 2, c_vals, width, label="C: Supply + Rules",
                   color="#e67e22", edgecolor="white")
    bars2 = ax.bar(x + width / 2, d_vals, width, label="D: Supply + AI",
                   color="#e74c3c", edgecolor="white")

    for bars in [bars1, bars2]:
        for bar in bars:
            h = bar.get_height()
            if h > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, h,
                        f"{int(h):,}", ha="center", va="bottom", fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=11)
    ax.set_ylabel("Event Count", fontsize=11)
    ax.set_title(
        "Fig 4: Supply Chain Events — Rule-Based vs AI-Optimized\n"
        "COVID Bioattack (R$_0$=3.5), Continental Africa",
        fontsize=13, fontweight="bold",
    )
    ax.legend(fontsize=10)
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "04_supply_chain_events.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved 04_supply_chain_events.png")


def generate_fig5(results: dict):
    """Fig 5: Attack rate and CFR comparison — grouped bars."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    keys = list(results.keys())
    labels = [f"{k}: {results[k]['label']}" for k in keys]
    attack_rates = [results[k]["attack_rate"] * 100 for k in keys]
    cfrs = [results[k]["cfr"] * 100 for k in keys]
    colors = ["#95a5a6", "#3498db", "#e67e22", "#e74c3c"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Attack rate
    bars1 = ax1.bar(range(len(keys)), attack_rates, color=colors, edgecolor="white", width=0.6)
    for bar, val in zip(bars1, attack_rates):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                 f"{val:.1f}%", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax1.set_xticks(range(len(keys)))
    ax1.set_xticklabels(labels, fontsize=9, rotation=15)
    ax1.set_ylabel("Attack Rate (%)", fontsize=11)
    ax1.set_title("Attack Rate by Configuration", fontsize=11, fontweight="bold")
    ax1.set_ylim(0, 110)
    ax1.grid(axis="y", alpha=0.3)

    # CFR
    bars2 = ax2.bar(range(len(keys)), cfrs, color=colors, edgecolor="white", width=0.6)
    for bar, val in zip(bars2, cfrs):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                 f"{val:.3f}%", ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax2.set_xticks(range(len(keys)))
    ax2.set_xticklabels(labels, fontsize=9, rotation=15)
    ax2.set_ylabel("Case Fatality Rate (%)", fontsize=11)
    ax2.set_title("Case Fatality Rate by Configuration", fontsize=11, fontweight="bold")
    ax2.grid(axis="y", alpha=0.3)

    fig.suptitle(
        "Fig 5: Attack Rate and Case Fatality Rate\n"
        f"COVID Bioattack (R$_0$=3.5), Continental Africa",
        fontsize=13, fontweight="bold",
    )
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "05_attack_rate_cfr.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved 05_attack_rate_cfr.png")


def print_summary_table(results: dict):
    """Print formatted comparison table."""
    keys = list(results.keys())
    short = [f"{k}:{results[k]['label'][:6]}" for k in keys]

    print(f"\n{'='*90}")
    print(f"  ALL-AFRICA COVID BIOATTACK: 4-CONFIG SUPPLY CHAIN COMPARISON")
    print(f"{'='*90}")

    print(f"\n  {'Metric':<32}", end="")
    for s in short:
        print(f" {s:>14}", end="")
    print()
    print(f"  {'─'*32}", end="")
    for _ in short:
        print(f" {'─'*14}", end="")
    print()

    def fmt(n):
        if isinstance(n, float) and n > 1000:
            return f"{n:,.0f}"
        if isinstance(n, float):
            return f"{n:,.1f}"
        return f"{n:,}"

    rows = [
        ("Total infected", lambda r: fmt(r["total_infected"])),
        ("Total deaths", lambda r: fmt(r["total_deaths"])),
        ("Attack rate", lambda r: f"{r['attack_rate']:.1%}"),
        ("Case fatality rate", lambda r: f"{r['cfr']:.3%}"),
        ("Peak day", lambda r: str(r["peak_day"])),
        ("Peak active (millions)", lambda r: f"{r['peak_active']/1e6:.1f}"),
        ("Detection rate (final)", lambda r: f"{r['detection_rate']:.1%}"),
        ("Stockout events", lambda r: fmt(r["stockout_events"])),
        ("Redistributions", lambda r: fmt(r["redistribution_events"])),
        ("Deployments", lambda r: fmt(r["deployment_events"])),
        ("Vaccinations", lambda r: fmt(r["vaccination_events"])),
        ("Runtime (s)", lambda r: f"{r['runtime']:.0f}"),
    ]

    for metric_name, extractor in rows:
        print(f"  {metric_name:<32}", end="")
        for key in keys:
            print(f" {extractor(results[key]):>14}", end="")
        print()

    # Lives saved vs baseline
    baseline_d = results["A"]["total_deaths"]
    print(f"\n  {'Lives saved vs baseline':<32}", end="")
    for key in keys:
        saved = int(baseline_d - results[key]["total_deaths"])
        print(f" {saved:>14,}", end="")
    print()

    print(f"\n{'='*90}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Running 4-config supply chain constraint analysis...")
    print(f"  Scenario: {SCENARIO}, Country: {COUNTRY}, Days: {DAYS}")
    print(f"  Continent vaccines: {CONTINENT_VACCINES:,}, pills: {CONTINENT_PILLS:,}")

    # Run all configs
    results = {}
    for key in CONFIGS:
        results[key] = run_config(key)

    # Print summary table
    print_summary_table(results)

    # Generate figures
    print("\nGenerating figures...")
    generate_fig1(results)
    generate_fig2(results)
    generate_fig2b(results)
    generate_fig3(results)
    generate_fig4(results)
    generate_fig5(results)

    print("\nAll figures saved to results/")
    print("Done.")


if __name__ == "__main__":
    main()
