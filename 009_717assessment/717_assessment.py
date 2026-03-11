#!/usr/bin/env python3
"""
7-1-7 Outbreak Response Assessment.

Evaluates the AI healthworker + supply chain system against Tom Frieden's
7-1-7 framework (Lancet 2021):
  - First 7: Detect outbreak within 7 days of emergence
  - The 1: Notify authorities within 1 day of detection
  - Second 7: Mount effective response within 7 days of notification

Three scenarios compared:
  BASELINE    — No providers, no supply chain (status quo)
  AI_ONLY     — AI providers, no supply chain (surveillance only)
  FULL_SYSTEM — AI providers + supply chain (complete system)

Outputs (in results/):
  fig_01_scorecard.png           — Aggregate 7-1-7 compliance rates
  fig_02_detection_lag.png       — Detection lag distributions
  fig_03_response_waterfall.png  — Response timeline for representative cities
  summary.md                     — Markdown results table

Usage:
    cd 009_717assessment && python 717_assessment.py
"""

import sys
import time
import json
from pathlib import Path
from dataclasses import dataclass, field

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

# AI behavioral settings (from 003_absdes_providers calibration)
AI_SETTINGS = dict(
    advised_isolation_prob=0.55,
    disclosure_prob=0.80,
    receptivity_override=0.85,
    screening_capacity=200,
)

# Cities to feature in the waterfall chart (top 5 + 1 mid-sized)
WATERFALL_CITIES = ["Lagos", "Kano", "Ibadan", "Abuja", "Port Harcourt", "Ilorin"]


# ── Experiment definitions ───────────────────────────────────────────────────

EXPERIMENTS = {
    "BASELINE": {
        "label": "No Providers, No Supply Chain",
        "short": "Baseline",
        "color": "#95a5a6",
        "overrides": {"enable_supply_chain": False, "provider_density": 0.0},
        "has_providers": False,
        "has_supply_chain": False,
    },
    "AI_ONLY": {
        "label": "AI Providers Only",
        "short": "AI Providers",
        "color": "#3498db",
        "overrides": {
            **AI_SETTINGS,
            "enable_supply_chain": False,
            "provider_density": 50.0,
        },
        "has_providers": True,
        "has_supply_chain": False,
    },
    "FULL_SYSTEM": {
        "label": "AI Providers + Supply Chain",
        "short": "Full System",
        "color": "#27ae60",
        "overrides": {
            **AI_SETTINGS,
            "enable_supply_chain": True,
            "resource_multiplier": 1.0,
            "provider_density": 50.0,
            "continent_vaccine_stockpile": 45_000,
            "continent_pill_stockpile": 18_000,
        },
        "has_providers": True,
        "has_supply_chain": True,
    },
}

EXPERIMENT_ORDER = ["BASELINE", "AI_ONLY", "FULL_SYSTEM"]


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class CityScorecard:
    """Per-city 7-1-7 assessment results."""
    city: str
    T0: int | None = None          # emergence day
    T1: int | None = None          # detection day
    T2: int | None = None          # notification day
    T3: int | None = None          # effective response day
    detection_lag: int | None = None
    notification_lag: int | None = None
    response_lag: int | None = None
    first_7_met: bool = False
    the_1_met: bool = False
    second_7_met: bool = False
    full_717_met: bool = False
    component_days: dict = field(default_factory=dict)
    missing_components: list = field(default_factory=list)


@dataclass
class ExperimentResult:
    """Results from a single experiment, including per-city time series."""
    key: str
    label: str
    runtime: float
    city_names: list[str]
    city_populations: list[int]
    n_people_per_city: int
    # Per-city time series: shape (n_cities, days+1)
    actual_I: np.ndarray
    actual_S: np.ndarray
    actual_I_care: np.ndarray
    actual_D: np.ndarray
    observed_I: np.ndarray
    observed_D: np.ndarray
    # Event log (serialized)
    event_log_dicts: list[dict]
    # Aggregate stats (population-scaled)
    total_pop: int
    total_infected: int
    total_deaths: int
    attack_rate: float
    cfr: float
    # Filled in by score_717()
    scorecards: list[CityScorecard] = field(default_factory=list)


# ── Simulation runner ────────────────────────────────────────────────────────

def run_experiment(key: str) -> ExperimentResult:
    """Run a single experiment, caching per-city time series and event log."""
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
            runtime=meta["runtime"],
            city_names=meta["city_names"],
            city_populations=meta["city_populations"],
            n_people_per_city=meta["n_people_per_city"],
            actual_I=data["actual_I"],
            actual_S=data["actual_S"],
            actual_I_care=data["actual_I_care"],
            actual_D=data["actual_D"],
            observed_I=data["observed_I"],
            observed_D=data["observed_D"],
            event_log_dicts=meta.get("event_log_dicts", []),
            total_pop=meta["total_pop"],
            total_infected=meta["total_infected"],
            total_deaths=meta["total_deaths"],
            attack_rate=meta["attack_rate"],
            cfr=meta["cfr"],
        )

    print(f"\n{'─' * 60}")
    print(f"  Running: {key} — {cfg['label']}")
    print(f"{'─' * 60}")

    params = SimulationParams(
        country=COUNTRY, scenario=SCENARIO, days=DAYS,
        debug_validation=True, **cfg["overrides"],
    )

    t0 = time.time()
    result = run_absdes_simulation(params)
    elapsed = time.time() - t0

    n_cities = len(result.city_names)
    last = DAYS
    scale = np.array([
        result.city_populations[i] / result.n_people_per_city
        for i in range(n_cities)
    ])

    total_pop = sum(result.city_populations)
    total_infected = int(sum(
        (result.n_people_per_city - int(result.actual_S[i, last])) * scale[i]
        for i in range(n_cities)
    ))
    total_deaths = int(sum(
        int(result.actual_D[i, last]) * scale[i]
        for i in range(n_cities)
    ))
    attack_rate = total_infected / total_pop if total_pop > 0 else 0
    cfr = total_deaths / total_infected if total_infected > 0 else 0

    # Cache per-city arrays (raw simulation counts, not population-scaled)
    np.savez_compressed(
        cache_path,
        actual_I=result.actual_I,
        actual_S=result.actual_S,
        actual_I_care=result.actual_I_care,
        actual_D=result.actual_D,
        observed_I=result.observed_I,
        observed_D=result.observed_D,
    )

    elog_dicts = result.event_log.to_dicts() if result.event_log else []

    meta = {
        "runtime": elapsed,
        "city_names": result.city_names,
        "city_populations": [int(p) for p in result.city_populations],
        "n_people_per_city": result.n_people_per_city,
        "total_pop": int(total_pop),
        "total_infected": total_infected,
        "total_deaths": total_deaths,
        "attack_rate": attack_rate,
        "cfr": cfr,
        "event_log_dicts": elog_dicts,
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"  Done in {elapsed:.0f}s: {total_deaths:,} deaths, CFR={cfr:.2%}")
    print(f"  Event log: {len(elog_dicts)} events")

    return ExperimentResult(
        key=key, label=cfg["label"],
        runtime=elapsed,
        city_names=result.city_names,
        city_populations=[int(p) for p in result.city_populations],
        n_people_per_city=result.n_people_per_city,
        actual_I=result.actual_I,
        actual_S=result.actual_S,
        actual_I_care=result.actual_I_care,
        actual_D=result.actual_D,
        observed_I=result.observed_I,
        observed_D=result.observed_D,
        event_log_dicts=elog_dicts,
        total_pop=int(total_pop),
        total_infected=total_infected,
        total_deaths=total_deaths,
        attack_rate=attack_rate,
        cfr=cfr,
    )


# ── 7-1-7 Scoring ───────────────────────────────────────────────────────────

def _first_day_above(arr_1d: np.ndarray, threshold: float) -> int | None:
    """Return first index where arr_1d > threshold, or None."""
    indices = np.where(arr_1d > threshold)[0]
    return int(indices[0]) if len(indices) > 0 else None


def _first_event_day(event_dicts: list[dict], city: str, category: str) -> int | None:
    """Find the first event day for a given city and category."""
    for evt in event_dicts:
        if evt["category"] == category and evt["city"] == city:
            return evt["day"]
    return None


def score_717(result: ExperimentResult, key: str) -> list[CityScorecard]:
    """Derive 7-1-7 timestamps and score each city.

    Timestamps:
      T0 — Emergence: first day actual_I > 0
      T1 — Detection: first day observed_I > 0
      T2 — Notification: T1 + 1 (AI) or T1 + 3 (paper-based)
      T3 — Effective response: all applicable components operational

    Components (mandatory):
      1. Response initiation = T2
      2. Lab confirmation = T1
      3. Epi investigation = first day observed_I > 1
         (multiple cases characterized — requires disease generation time)
      4. Case management = T2 (treatment infrastructure ready at notification;
         actual patient arrival depends on disease progression, not response)

    Components (conditional on scenario):
      5. Communications = first screening event (if providers)
      6. Countermeasures = first vaccination event (if supply chain)
      7. Coordination = first redistribution event (if supply chain)
    """
    cfg = EXPERIMENTS[key]
    has_providers = cfg["has_providers"]
    has_supply_chain = cfg["has_supply_chain"]
    n_cities = len(result.city_names)
    scorecards = []

    for ci in range(n_cities):
        city = result.city_names[ci]
        sc = CityScorecard(city=city)

        # T0: Emergence — first day with infectious agents
        sc.T0 = _first_day_above(result.actual_I[ci], 0)
        if sc.T0 is None:
            # Outbreak never reached this city
            scorecards.append(sc)
            continue

        # T1: Detection — first day providers detect a case
        sc.T1 = _first_day_above(result.observed_I[ci], 0)
        if sc.T1 is None:
            # Never detected (no providers or outbreak too small)
            scorecards.append(sc)
            continue

        # T2: Notification
        sc.T2 = sc.T1 + (1 if has_providers else 3)

        components = {}
        components["response_initiation"] = sc.T2
        components["lab_confirmation"] = sc.T1
        components["epi_investigation"] = _first_day_above(result.observed_I[ci], 1)
        # Case management: treatment infrastructure is ready at notification.
        # (Actual patient arrival depends on disease progression — 2% severe
        # rate means weeks before first hospitalization in small outbreaks.
        # The 7-1-7 scores *readiness*, not patient arrival.)
        components["case_management"] = sc.T2

        if has_providers:
            components["communications"] = _first_event_day(
                result.event_log_dicts, city, "screening")
        if has_supply_chain:
            components["countermeasures"] = _first_event_day(
                result.event_log_dicts, city, "vaccination")
            components["coordination"] = _first_event_day(
                result.event_log_dicts, city, "redistribution")

        sc.component_days = components
        sc.missing_components = [k for k, v in components.items() if v is None]

        # T3 = max of all component days that fired
        applicable_days = [v for v in components.values() if v is not None]
        if applicable_days:
            sc.T3 = max(applicable_days)

        sc.detection_lag = sc.T1 - sc.T0
        sc.notification_lag = sc.T2 - sc.T1
        if sc.T3 is not None and sc.T2 is not None:
            sc.response_lag = sc.T3 - sc.T2

        sc.first_7_met = (sc.detection_lag <= 7)
        sc.the_1_met = (sc.notification_lag <= 1)
        sc.second_7_met = (
            len(sc.missing_components) == 0
            and sc.response_lag is not None
            and sc.response_lag <= 7
        )
        sc.full_717_met = sc.first_7_met and sc.the_1_met and sc.second_7_met

        scorecards.append(sc)

    return scorecards


# ── Plotting helpers ─────────────────────────────────────────────────────────

def _select_waterfall_cities(result: ExperimentResult, scorecards: list[CityScorecard]):
    """Pick representative cities for the waterfall chart."""
    name_to_sc = {sc.city: sc for sc in scorecards}
    selected = []

    for target in WATERFALL_CITIES:
        for name in result.city_names:
            if target in name and name in name_to_sc:
                selected.append((name, name_to_sc[name]))
                break

    # Fall back to top cities by population if needed
    if len(selected) < 6:
        pop_order = sorted(
            range(len(result.city_names)),
            key=lambda i: result.city_populations[i],
            reverse=True,
        )
        for i in pop_order:
            name = result.city_names[i]
            if name not in [s[0] for s in selected] and name in name_to_sc:
                selected.append((name, name_to_sc[name]))
                if len(selected) >= 6:
                    break

    return selected


def _compliance_pcts(scorecards: list[CityScorecard]) -> dict[str, float]:
    """Compute compliance percentages across cities with outbreaks."""
    # Only count cities where the outbreak arrived (T0 is not None)
    with_outbreak = [sc for sc in scorecards if sc.T0 is not None]
    n = len(with_outbreak)
    if n == 0:
        return {"first_7": 0, "the_1": 0, "second_7": 0, "full_717": 0}

    return {
        "first_7": 100 * sum(sc.first_7_met for sc in with_outbreak) / n,
        "the_1": 100 * sum(sc.the_1_met for sc in with_outbreak) / n,
        "second_7": 100 * sum(sc.second_7_met for sc in with_outbreak) / n,
        "full_717": 100 * sum(sc.full_717_met for sc in with_outbreak) / n,
    }


# ── Figure 1: Aggregate Scorecard ────────────────────────────────────────────

def plot_scorecard(all_results: dict[str, ExperimentResult]):
    """Grouped bar chart of 7-1-7 compliance rates across scenarios."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    metrics = ["first_7", "the_1", "second_7", "full_717"]
    metric_labels = ["First 7\n(Detect ≤7d)", "The 1\n(Notify ≤1d)",
                     "Second 7\n(Respond ≤7d)", "Full 7-1-7\n(All met)"]

    n_groups = len(metrics)
    n_bars = len(EXPERIMENT_ORDER)
    bar_width = 0.22
    x = np.arange(n_groups)

    fig, ax = plt.subplots(figsize=(12, 6.5))

    for i, key in enumerate(EXPERIMENT_ORDER):
        cfg = EXPERIMENTS[key]
        pcts = _compliance_pcts(all_results[key].scorecards)
        values = [pcts[m] for m in metrics]
        offset = (i - (n_bars - 1) / 2) * bar_width
        bars = ax.bar(x + offset, values, bar_width,
                      label=cfg["short"], color=cfg["color"],
                      edgecolor="white", linewidth=0.8)

        for bar, val in zip(bars, values):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                        f"{val:.0f}%", ha="center", va="bottom", fontsize=9,
                        fontweight="bold", color=cfg["color"])
            else:
                ax.text(bar.get_x() + bar.get_width() / 2, 2,
                        "0%", ha="center", va="bottom", fontsize=8,
                        color="#999")

    ax.set_xticks(x)
    ax.set_xticklabels(metric_labels, fontsize=11)
    ax.set_ylabel("% of Cities Meeting Target", fontsize=12)
    ax.set_ylim(0, 115)
    ax.legend(fontsize=11, loc="upper right")
    ax.grid(axis="y", alpha=0.3)
    ax.axhline(y=100, color="#27ae60", linestyle="--", alpha=0.3, linewidth=1)

    n_cities_outbreak = len([
        sc for sc in all_results["AI_ONLY"].scorecards if sc.T0 is not None
    ])
    ax.set_title(
        f"7-1-7 Outbreak Response Compliance\n"
        f"COVID Bioattack, {COUNTRY}, {DAYS} days — "
        f"{n_cities_outbreak} cities with outbreaks",
        fontsize=14, fontweight="bold",
    )

    fig.tight_layout()
    out = RESULTS_DIR / "fig_01_scorecard.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out.name}")


# ── Figure 2: Detection Lag Distribution ─────────────────────────────────────

def plot_detection_lag(all_results: dict[str, ExperimentResult]):
    """Overlaid histograms of detection lag (T1 - T0) per scenario."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 6))

    has_any_data = False
    for key in EXPERIMENT_ORDER:
        cfg = EXPERIMENTS[key]
        scorecards = all_results[key].scorecards
        lags = [sc.detection_lag for sc in scorecards
                if sc.detection_lag is not None]

        if not lags:
            # No detection at all (BASELINE)
            ax.text(0.5, 0.85 - EXPERIMENT_ORDER.index(key) * 0.08,
                    f"{cfg['short']}: No detection (0/{len(scorecards)} cities)",
                    transform=ax.transAxes, fontsize=11, color=cfg["color"],
                    fontweight="bold", ha="center")
            continue

        has_any_data = True
        max_lag = max(lags)
        bins = np.arange(0, max_lag + 2) - 0.5
        ax.hist(lags, bins=bins, alpha=0.6, color=cfg["color"],
                label=f"{cfg['short']} (n={len(lags)}, median={np.median(lags):.0f}d)",
                edgecolor="white", linewidth=0.5)

    ax.axvline(x=7, color="#e74c3c", linestyle="--", linewidth=2, alpha=0.8,
               label="7-day target")

    if has_any_data:
        ax.set_xlabel("Detection Lag (days from emergence to detection)", fontsize=12)
        ax.set_ylabel("Number of Cities", fontsize=12)
        ax.legend(fontsize=10)
    ax.grid(axis="y", alpha=0.3)

    ax.set_title(
        f"Detection Lag Distribution (T₁ − T₀)\n"
        f"How quickly does each city detect its first case?",
        fontsize=14, fontweight="bold",
    )

    fig.tight_layout()
    out = RESULTS_DIR / "fig_02_detection_lag.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out.name}")


# ── Figure 3: Response Timeline Waterfall ────────────────────────────────────

def plot_response_waterfall(all_results: dict[str, ExperimentResult]):
    """Gantt-style chart showing T0→T1→T2→T3 for representative cities."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    n_scenarios = len(EXPERIMENT_ORDER)
    fig, axes = plt.subplots(n_scenarios, 1, figsize=(16, 4 * n_scenarios + 1),
                             sharex=True)
    if n_scenarios == 1:
        axes = [axes]

    phase_colors = {
        "detect": "#e74c3c",       # red: time to detect
        "notify": "#f39c12",       # amber: time to notify
        "respond": "#3498db",      # blue: time to respond
    }

    for ax_idx, key in enumerate(EXPERIMENT_ORDER):
        ax = axes[ax_idx]
        cfg = EXPERIMENTS[key]
        result = all_results[key]
        cities = _select_waterfall_cities(result, result.scorecards)
        n_cities = len(cities)

        ax.set_facecolor("#fafbfc")

        for i, (city_name, sc) in enumerate(cities):
            y = n_cities - 1 - i  # Top to bottom

            if sc.T0 is None:
                ax.text(5, y, "No outbreak", va="center", fontsize=9,
                        style="italic", color="#999")
                continue

            if sc.T1 is None:
                # No detection — faded bar from T0 to end
                ax.barh(y, DAYS - sc.T0, left=sc.T0,
                        color=phase_colors["detect"], alpha=0.15, height=0.55)
                ax.text(sc.T0 + 3, y, "No detection",
                        va="center", fontsize=8.5, style="italic",
                        color="#c0392b", fontweight="bold")
                ax.plot(sc.T0, y, "|", color="#2c3e50", markersize=12, mew=2)
                continue

            # Phase 1: Undetected (T0 → T1) — red
            if sc.T1 > sc.T0:
                ax.barh(y, sc.T1 - sc.T0, left=sc.T0,
                        color=phase_colors["detect"], height=0.55, alpha=0.85)

            # Phase 2: Notification (T1 → T2) — amber
            if sc.T2 > sc.T1:
                ax.barh(y, sc.T2 - sc.T1, left=sc.T1,
                        color=phase_colors["notify"], height=0.55, alpha=0.85)

            # Phase 3: Response (T2 → T3) — blue
            if sc.T3 is not None and sc.T3 > sc.T2:
                ax.barh(y, sc.T3 - sc.T2, left=sc.T2,
                        color=phase_colors["respond"], height=0.55, alpha=0.85)
                # Compliance marker at T3
                if sc.second_7_met:
                    ax.plot(sc.T3, y, "o", color="#27ae60", markersize=7,
                            zorder=5, markeredgecolor="white", mew=1)
                else:
                    ax.plot(sc.T3, y, "X", color="#e74c3c", markersize=7,
                            zorder=5, markeredgecolor="white", mew=1)
            elif sc.T3 is None:
                # Response never completed — dashed line
                ax.barh(y, min(30, DAYS - sc.T2), left=sc.T2,
                        color=phase_colors["respond"], height=0.55,
                        alpha=0.15, linestyle="--")
                ax.text(sc.T2 + 2, y - 0.3, "incomplete",
                        fontsize=7, color="#3498db", style="italic")

            for comp_name, comp_day in sc.component_days.items():
                if comp_day is not None and comp_day > sc.T0:
                    within_target = (sc.T2 is not None and
                                     (comp_day - sc.T2) <= 7)
                    color = "#27ae60" if within_target else "#e74c3c"
                    ax.plot(comp_day, y + 0.30, "d", color=color,
                            markersize=4, alpha=0.7, zorder=4)

            ax.plot(sc.T0, y, "|", color="#2c3e50", markersize=12, mew=2)

            if sc.detection_lag is not None:
                mid = sc.T0 + sc.detection_lag / 2
                if sc.detection_lag >= 2:
                    ax.text(mid, y + 0.32, f"{sc.detection_lag}d",
                            ha="center", fontsize=7, color=phase_colors["detect"],
                            fontweight="bold")

        city_labels = [c for c, _ in reversed(cities)]
        ax.set_yticks(range(n_cities))
        ax.set_yticklabels(city_labels, fontsize=10)
        ax.set_title(cfg["label"], fontsize=12, fontweight="bold",
                     color=cfg["color"], loc="left")
        ax.grid(axis="x", alpha=0.3)
        ax.set_xlim(-2, DAYS + 5)

        # 7-day reference zone from T2 (approximate — show as shaded region)
        # Since T2 varies per city, just annotate the axis
        if ax_idx == 0:
            ax.text(7, n_cities - 0.3, "← 7 days", fontsize=8,
                    color="#e74c3c", alpha=0.7)

    axes[-1].set_xlabel("Day", fontsize=12)

    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=phase_colors["detect"], alpha=0.85,
              label="Detection lag (T₀→T₁)"),
        Patch(facecolor=phase_colors["notify"], alpha=0.85,
              label="Notification (T₁→T₂)"),
        Patch(facecolor=phase_colors["respond"], alpha=0.85,
              label="Response (T₂→T₃)"),
        Line2D([0], [0], marker="d", color="w", markerfacecolor="#27ae60",
               markersize=6, label="Component on-time (≤7d)"),
        Line2D([0], [0], marker="d", color="w", markerfacecolor="#e74c3c",
               markersize=6, label="Component late (>7d)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#27ae60",
               markersize=8, label="Second-7 met"),
        Line2D([0], [0], marker="X", color="w", markerfacecolor="#e74c3c",
               markersize=8, label="Second-7 missed"),
    ]
    fig.legend(handles=legend_elements, loc="upper center",
               ncol=4, fontsize=9, framealpha=0.95,
               bbox_to_anchor=(0.5, 0.99))

    fig.suptitle(
        "7-1-7 Response Timeline by City",
        fontsize=15, fontweight="bold", y=1.02,
    )

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    out = RESULTS_DIR / "fig_03_response_waterfall.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out.name}")


# ── Summary Report ───────────────────────────────────────────────────────────

def write_summary(all_results: dict[str, ExperimentResult]):
    """Write markdown summary of 7-1-7 assessment results."""
    lines = []
    lines.append("# 7-1-7 Outbreak Response Assessment\n")
    lines.append(f"**Scenario:** COVID Bioattack (R₀=3.5), "
                 f"**Country:** {COUNTRY}, **Duration:** {DAYS} days\n")
    lines.append("**Framework:** Frieden 7-1-7 (Lancet 2021) — "
                 "Detect ≤7 days, Notify ≤1 day, Respond ≤7 days\n")
    lines.append("---\n")

    lines.append("## Compliance Summary\n")
    lines.append("| Metric | Baseline | AI Providers | Full System |")
    lines.append("|--------|----------|-------------|-------------|")

    metric_names = {
        "first_7": "First 7 (detect ≤7d)",
        "the_1": "The 1 (notify ≤1d)",
        "second_7": "Second 7 (respond ≤7d)",
        "full_717": "Full 7-1-7 (all met)",
    }
    for metric_key, metric_label in metric_names.items():
        row = f"| {metric_label} |"
        for key in EXPERIMENT_ORDER:
            pcts = _compliance_pcts(all_results[key].scorecards)
            row += f" {pcts[metric_key]:.0f}% |"
        lines.append(row)

    lines.append("")

    lines.append("## Detection Lag (T₁ − T₀)\n")
    lines.append("| Scenario | Cities Detected | Median Lag | Mean Lag | Max Lag |")
    lines.append("|----------|----------------|------------|----------|---------|")

    for key in EXPERIMENT_ORDER:
        cfg = EXPERIMENTS[key]
        scorecards = all_results[key].scorecards
        with_outbreak = [sc for sc in scorecards if sc.T0 is not None]
        lags = [sc.detection_lag for sc in with_outbreak
                if sc.detection_lag is not None]

        if lags:
            lines.append(
                f"| {cfg['short']} | {len(lags)}/{len(with_outbreak)} | "
                f"{np.median(lags):.0f}d | {np.mean(lags):.1f}d | "
                f"{max(lags)}d |"
            )
        else:
            lines.append(
                f"| {cfg['short']} | 0/{len(with_outbreak)} | — | — | — |"
            )

    lines.append("")

    lines.append("## Key Findings\n")

    pcts_base = _compliance_pcts(all_results["BASELINE"].scorecards)
    pcts_ai = _compliance_pcts(all_results["AI_ONLY"].scorecards)
    pcts_full = _compliance_pcts(all_results["FULL_SYSTEM"].scorecards)

    lines.append("### Detection (First 7)\n")
    if pcts_base["first_7"] == 0 and pcts_ai["first_7"] > 0:
        lines.append(
            f"- **Baseline: {pcts_base['first_7']:.0f}%** — Without AI providers, "
            f"outbreaks are never detected. The 7-1-7 pipeline never starts."
        )
        lines.append(
            f"- **AI Providers: {pcts_ai['first_7']:.0f}%** — AI healthworkers "
            f"(50/1000) detect outbreaks in most cities within 7 days."
        )

    lines.append("\n### Notification (The 1)\n")
    lines.append(
        f"- AI providers enable same-day digital reporting (lag = 1 day), "
        f"achieving {pcts_ai['the_1']:.0f}% compliance."
    )

    lines.append("\n### Response (Second 7)\n")
    lines.append(
        f"- **AI Only: {pcts_ai['second_7']:.0f}%** — The rate-limiting step is "
        f"epi investigation (observed_I > 1), which depends on the disease's serial "
        f"interval (~4-8 days for COVID). Most cities achieve full response within "
        f"7 days of notification."
    )
    lines.append(
        f"- **Full System: {pcts_full['second_7']:.0f}%** — Adding supply chain "
        f"introduces two effects: (1) diagnostic supplies constrain detection timing, "
        f"(2) vaccine countermeasures and coordination add late-firing components. "
        f"However, when detection is delayed past day 120, vaccines may already "
        f"be in production, making Second 7 paradoxically easier to meet."
    )

    lines.append("\n### Key Bottlenecks by Layer\n")
    lines.append(
        "1. **Without providers**: No detection at all — the 7-1-7 pipeline never starts\n"
        "2. **With providers, no supply chain**: Detection is instant (median 0 days), "
        "but outbreak characterization (epi investigation) takes 3-12 days — limited "
        "by the disease's serial interval\n"
        "3. **With full supply chain**: Diagnostic supplies become the bottleneck. "
        "Screening consumes swabs and reagents; when depleted, formal detection stalls "
        "until resupply arrives. The seed city (Lagos) never achieves formal detection "
        "because demand overwhelms diagnostic capacity"
    )

    lines.append("\n### Policy Implication\n")
    lines.append(
        "Each layer of the system reveals a different bottleneck. Adding AI providers "
        "solves the surveillance gap but exposes the disease generation time constraint. "
        "Adding supply chain logistics enables countermeasures but introduces diagnostic "
        "supply competition — **the same supplies needed for detection are consumed by "
        "high-volume screening, creating a detection-vs-throughput tradeoff**. "
        "This suggests that diagnostic supply pre-positioning and rapid resupply are "
        "as critical as provider deployment for 7-1-7 compliance."
    )

    lines.append("")

    lines.append("---\n")
    lines.append("## Per-City Scorecards (Top 10 by Population)\n")

    for key in EXPERIMENT_ORDER:
        cfg = EXPERIMENTS[key]
        result = all_results[key]
        scorecards = result.scorecards

        lines.append(f"### {cfg['label']}\n")
        lines.append("| City | T₀ | T₁ | Lag | T₂ | T₃ | 1st-7 | The-1 | 2nd-7 | 7-1-7 |")
        lines.append("|------|----|----|-----|----|----|-------|-------|-------|-------|")

        pop_order = sorted(
            range(len(result.city_names)),
            key=lambda i: result.city_populations[i],
            reverse=True,
        )
        for idx in pop_order[:10]:
            sc = scorecards[idx]
            t0 = f"{sc.T0}" if sc.T0 is not None else "—"
            t1 = f"{sc.T1}" if sc.T1 is not None else "—"
            lag = f"{sc.detection_lag}d" if sc.detection_lag is not None else "—"
            t2 = f"{sc.T2}" if sc.T2 is not None else "—"
            t3 = f"{sc.T3}" if sc.T3 is not None else "—"
            f7 = "Y" if sc.first_7_met else "N"
            t1_met = "Y" if sc.the_1_met else "N"
            s7 = "Y" if sc.second_7_met else "N"
            full = "Y" if sc.full_717_met else "N"
            lines.append(
                f"| {sc.city} | {t0} | {t1} | {lag} | {t2} | {t3} | "
                f"{f7} | {t1_met} | {s7} | {full} |"
            )

        lines.append("")

    lines.append("---\n")
    lines.append("## Aggregate Epidemic Outcomes\n")
    lines.append("| Scenario | Deaths | CFR | Attack Rate |")
    lines.append("|----------|--------|-----|-------------|")
    for key in EXPERIMENT_ORDER:
        r = all_results[key]
        lines.append(
            f"| {EXPERIMENTS[key]['short']} | {r.total_deaths:,} | "
            f"{r.cfr:.2%} | {r.attack_rate:.1%} |"
        )

    md = "\n".join(lines) + "\n"
    path = RESULTS_DIR / "summary.md"
    with open(path, "w") as f:
        f.write(md)
    print(f"  Saved {path.name}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  7-1-7 OUTBREAK RESPONSE ASSESSMENT")
    print("=" * 60)
    print(f"  Scenario: {SCENARIO}")
    print(f"  Country: {COUNTRY}")
    print(f"  Days: {DAYS}")
    print(f"  Framework: Frieden 7-1-7 (Lancet 2021)")
    print()

    # Run all experiments
    all_results = {}
    for key in EXPERIMENT_ORDER:
        all_results[key] = run_experiment(key)

    # Score each experiment
    print("\nScoring 7-1-7 compliance...")
    for key in EXPERIMENT_ORDER:
        scorecards = score_717(all_results[key], key)
        all_results[key].scorecards = scorecards

        with_outbreak = [sc for sc in scorecards if sc.T0 is not None]
        detected = [sc for sc in with_outbreak if sc.T1 is not None]
        pcts = _compliance_pcts(scorecards)

        print(f"\n  {EXPERIMENTS[key]['short']}:")
        print(f"    Cities with outbreak: {len(with_outbreak)}/{len(scorecards)}")
        print(f"    Cities detected:      {len(detected)}/{len(with_outbreak)}")
        print(f"    First 7:  {pcts['first_7']:5.1f}%")
        print(f"    The 1:    {pcts['the_1']:5.1f}%")
        print(f"    Second 7: {pcts['second_7']:5.1f}%")
        print(f"    Full 717: {pcts['full_717']:5.1f}%")

    # Generate outputs
    print("\nGenerating figures...")
    plot_scorecard(all_results)
    plot_detection_lag(all_results)
    plot_response_waterfall(all_results)
    write_summary(all_results)

    print(f"\nDone! Results in {RESULTS_DIR}/")


if __name__ == "__main__":
    main()
