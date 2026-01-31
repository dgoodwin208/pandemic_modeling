"""
Multi-City Metapopulation SEIR Validation.

Demonstrates pandemic spread across 5 African cities using:
- SEIR ODE per city (validated by modules 001-003)
- Gravity model inter-city coupling
- Daily discrete coupling

Produces 4 figures:
    01 — Epidemic Wave Propagation (per-city I(t)/N curves)
    02 — Geographic Spread (map snapshots at multiple time points)
    03 — Per-City SEIR Curves (full S/E/I/R per city)
    04 — Travel Matrix Heatmap

Usage:
    cd 004_multicity && python validation_multicity.py
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "des_system"))

from validation_config import COVID_LIKE

from city import load_cities
from gravity_model import compute_travel_matrix, compute_distance_matrix
from multicity_sim import run_multicity_simulation, MultiCityResult

# ── Configuration ────────────────────────────────────────────────────

DEMO_CITIES = ["Cairo", "Lagos", "Nairobi", "Johannesburg", "Kinshasa"]
SCENARIO = COVID_LIKE
DAYS = 300
SEED_CITY = "Cairo"
INITIAL_INFECTED = 100

# Gravity model parameters
GRAVITY_ALPHA = 2.0
GRAVITY_SCALE = 1e-4

# Inter-city transmission
TRANSMISSION_FACTOR = 0.3

# Health system effect on R₀
# Heuristic: R_eff = R₀ × (1 - ISOLATION_EFFECT × medical_services_score / 100)
# Grounded in module 003: provider advice shifts isolation from 5% to 40%.
ISOLATION_EFFECT = 0.3  # max 30% R₀ reduction at score=100

RESULTS_DIR = Path(__file__).parent / "results"

# City colors for consistent styling
CITY_COLORS = ["#e63946", "#457b9d", "#2a9d8f", "#e9c46a", "#f4a261"]


def ensure_results_dir():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ── Figure 1: Epidemic Wave Propagation ──────────────────────────────

def plot_wave_propagation(result: MultiCityResult):
    """
    All cities' infection curves on one plot.

    Shows the pandemic wave spreading from the seed city to others
    with time delays proportional to connectivity.
    """
    fig, ax = plt.subplots(figsize=(12, 6))
    fig.suptitle(
        "Epidemic Wave Propagation Across African Cities\n"
        f"COVID-like (R₀={SCENARIO.R0}), seeded in {SEED_CITY}, "
        f"health-modulated R_eff per city",
        fontsize=13, fontweight="bold",
    )

    n_cities = len(result.city_names)
    for i in range(n_cities):
        # Infection fraction over time
        inf_frac = result.I[i] / result.city_populations[i] * 100
        peak_day = int(result.t[np.argmax(inf_frac)])
        peak_val = inf_frac.max()
        r_eff = result.city_r_eff[i]

        ax.plot(
            result.t, inf_frac,
            color=CITY_COLORS[i],
            linewidth=2,
            label=(f"{result.city_names[i]} "
                   f"(R_eff={r_eff:.2f}, peak: day {peak_day}, {peak_val:.1f}%)"),
        )
        # Mark peak
        ax.axvline(peak_day, color=CITY_COLORS[i], linestyle=":", alpha=0.4)

    ax.set_xlabel("Day", fontsize=11)
    ax.set_ylabel("Infected (% of city population)", fontsize=11)
    ax.legend(fontsize=9, loc="upper right")
    ax.set_xlim(0, DAYS)
    ax.grid(True, alpha=0.3)

    fname = RESULTS_DIR / "01_wave_propagation.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {fname.name}")


# ── Figure 2: Geographic Spread ──────────────────────────────────────

def plot_geographic_spread(result: MultiCityResult):
    """
    Map panels showing infection spread geographically at time snapshots.

    Scatter on lon/lat, circle size ∝ population, color ∝ infection fraction.
    Lines between cities with thickness ∝ travel rate.
    """
    snapshot_days = [0, 60, 120, 180, 240, 270]
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    fig.suptitle(
        "Geographic Spread of Pandemic Across African Cities\n"
        f"COVID-like (R₀={SCENARIO.R0}), seeded in {SEED_CITY}",
        fontsize=13, fontweight="bold",
    )

    n_cities = len(result.city_names)
    lats = [c[0] for c in result.city_coords]
    lons = [c[1] for c in result.city_coords]
    pops = result.city_populations

    # Normalize population for marker sizing
    max_pop = max(pops)
    marker_sizes = [p / max_pop * 800 + 50 for p in pops]

    # Normalize travel rates for line thickness
    max_travel = result.travel_matrix.max()

    for idx, day in enumerate(snapshot_days):
        ax = axes[idx // 3, idx % 3]
        day_idx = min(day, len(result.t) - 1)

        # Draw travel connections
        for i in range(n_cities):
            for j in range(i + 1, n_cities):
                rate = result.travel_matrix[i, j]
                if rate > 0:
                    lw = rate / max_travel * 3 + 0.3
                    ax.plot(
                        [lons[i], lons[j]], [lats[i], lats[j]],
                        color="gray", linewidth=lw, alpha=0.3, zorder=1,
                    )

        # Draw cities
        inf_fracs = [result.I[i, day_idx] / pops[i] for i in range(n_cities)]
        scatter = ax.scatter(
            lons, lats,
            s=marker_sizes,
            c=inf_fracs,
            cmap="YlOrRd",
            vmin=0, vmax=0.15,
            edgecolors="black", linewidths=0.5,
            zorder=2,
        )

        # Label cities
        for i in range(n_cities):
            ax.annotate(
                result.city_names[i],
                (lons[i], lats[i]),
                textcoords="offset points",
                xytext=(8, 8),
                fontsize=7,
                fontweight="bold",
            )

        ax.set_title(f"Day {day}", fontsize=10)
        ax.set_xlabel("Longitude", fontsize=8)
        ax.set_ylabel("Latitude", fontsize=8)
        ax.tick_params(labelsize=7)

    # Colorbar
    cbar = fig.colorbar(scatter, ax=axes, shrink=0.6, pad=0.02)
    cbar.set_label("Infection fraction (I/N)", fontsize=10)

    fig.subplots_adjust(right=0.88, top=0.88, hspace=0.3, wspace=0.25)
    fname = RESULTS_DIR / "02_geographic_spread.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {fname.name}")


# ── Figure 3: Per-City SEIR Curves ──────────────────────────────────

def plot_per_city_seir(result: MultiCityResult):
    """
    One subplot per city showing full S/E/I/R dynamics.
    """
    n_cities = len(result.city_names)
    fig, axes = plt.subplots(1, n_cities, figsize=(4 * n_cities, 4), sharey=False)
    fig.suptitle(
        "SEIR Dynamics Per City (Health-Modulated R_eff)\n"
        f"COVID-like (R₀={SCENARIO.R0}), seeded in {SEED_CITY}",
        fontsize=13, fontweight="bold",
    )

    if n_cities == 1:
        axes = [axes]

    for i, ax in enumerate(axes):
        pop = result.city_populations[i]
        ax.plot(result.t, result.S[i] / pop * 100, label="S", color="#4361ee")
        ax.plot(result.t, result.E[i] / pop * 100, label="E", color="#f77f00")
        ax.plot(result.t, result.I[i] / pop * 100, label="I", color="#d62828")
        ax.plot(result.t, result.R[i] / pop * 100, label="R", color="#2a9d8f")

        r_eff = result.city_r_eff[i]
        score = result.city_medical_scores[i]
        ax.set_title(
            f"{result.city_names[i]}\n(pop: {pop:,}, score: {score:.0f}, R_eff: {r_eff:.2f})",
            fontsize=9,
        )
        ax.set_xlabel("Day", fontsize=9)
        if i == 0:
            ax.set_ylabel("% of city population", fontsize=9)
        ax.legend(fontsize=7, loc="right")
        ax.set_xlim(0, DAYS)
        ax.grid(True, alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.90])
    fname = RESULTS_DIR / "03_per_city_seir.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {fname.name}")


# ── Figure 4: Travel Matrix Heatmap ─────────────────────────────────

def plot_travel_matrix(result: MultiCityResult):
    """
    Heatmap of daily travel rates between cities.
    """
    fig, ax = plt.subplots(figsize=(8, 6))
    fig.suptitle(
        "Gravity Model: Daily Travel Rates Between Cities\n"
        f"α={GRAVITY_ALPHA}, scale={GRAVITY_SCALE:.0e}",
        fontsize=13, fontweight="bold",
    )

    n = len(result.city_names)
    im = ax.imshow(result.travel_matrix, cmap="YlOrBr", aspect="equal")

    # Annotate cells
    for i in range(n):
        for j in range(n):
            val = result.travel_matrix[i, j]
            text = f"{val:.0f}" if val >= 1 else (f"{val:.1f}" if val > 0 else "—")
            color = "white" if val > result.travel_matrix.max() * 0.6 else "black"
            ax.text(j, i, text, ha="center", va="center", fontsize=9, color=color)

    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(result.city_names, fontsize=9, rotation=30, ha="right")
    ax.set_yticklabels(result.city_names, fontsize=9)
    ax.set_xlabel("Destination", fontsize=10)
    ax.set_ylabel("Origin", fontsize=10)

    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Daily travelers", fontsize=10)

    fname = RESULTS_DIR / "04_travel_matrix.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {fname.name}")


# ── Summary ──────────────────────────────────────────────────────────

def print_summary(result: MultiCityResult):
    """Print summary table to console."""
    n = len(result.city_names)

    print("\n" + "=" * 80)
    print("MULTI-CITY SIMULATION SUMMARY")
    print("=" * 80)
    print(f"Scenario: {SCENARIO.name} (R₀={SCENARIO.R0})")
    print(f"Seed city: {SEED_CITY} ({INITIAL_INFECTED} initial infections)")
    print(f"Duration: {DAYS} days")
    print(f"Gravity model: α={GRAVITY_ALPHA}, scale={GRAVITY_SCALE:.0e}")
    print(f"Transmission factor: {TRANSMISSION_FACTOR}")
    print(f"Isolation effect: {ISOLATION_EFFECT} (max R₀ reduction at score=100)")
    print()

    # Distance matrix
    cities_for_dist = [type("C", (), {"latitude": c[0], "longitude": c[1]})() for c in result.city_coords]
    dist = compute_distance_matrix(cities_for_dist)

    print(f"{'City':<18} {'Pop':>12} {'Score':>7} {'R_eff':>7} {'Peak Day':>10} {'Peak I%':>10} {'Attack%':>10}")
    print("-" * 82)
    for i in range(n):
        pop = result.city_populations[i]
        inf_frac = result.I[i] / pop * 100
        peak_day = int(result.t[np.argmax(inf_frac)])
        peak_pct = inf_frac.max()
        attack_rate = (pop - result.S[i, -1]) / pop * 100
        score = result.city_medical_scores[i]
        r_eff = result.city_r_eff[i]
        print(f"{result.city_names[i]:<18} {pop:>12,} {score:>7.0f} {r_eff:>7.2f} {peak_day:>10} {peak_pct:>10.1f} {attack_rate:>10.1f}")

    print()
    print("Travel Matrix (daily travelers):")
    header = f"{'':>18}" + "".join(f"{name:>14}" for name in result.city_names)
    print(header)
    for i in range(n):
        row = f"{result.city_names[i]:>18}"
        for j in range(n):
            val = result.travel_matrix[i, j]
            row += f"{val:>14.0f}" if val >= 1 else f"{'—':>14}"

        print(row)

    print()
    print("Distance Matrix (km):")
    header = f"{'':>18}" + "".join(f"{name:>14}" for name in result.city_names)
    print(header)
    for i in range(n):
        row = f"{result.city_names[i]:>18}"
        for j in range(n):
            row += f"{dist[i, j]:>14.0f}" if i != j else f"{'—':>14}"
        print(row)
    print()


# ── Main ─────────────────────────────────────────────────────────────

def main():
    ensure_results_dir()

    print("Loading cities...")
    cities = load_cities(DEMO_CITIES)
    for c in cities:
        print(f"  {c.name} ({c.country}): pop={c.population:,}, "
              f"lat={c.latitude:.2f}, lon={c.longitude:.2f}, "
              f"medical_score={c.medical_services_score:.0f}")

    print("\nComputing travel matrix (gravity model)...")
    travel_matrix = compute_travel_matrix(
        cities, alpha=GRAVITY_ALPHA, scale=GRAVITY_SCALE,
    )

    seed_idx = DEMO_CITIES.index(SEED_CITY)
    print(f"\nRunning simulation ({DAYS} days, seed={SEED_CITY})...")
    result = run_multicity_simulation(
        cities=cities,
        scenario=SCENARIO,
        travel_matrix=travel_matrix,
        days=DAYS,
        transmission_factor=TRANSMISSION_FACTOR,
        seed_city_index=seed_idx,
        initial_infected=INITIAL_INFECTED,
        isolation_effect=ISOLATION_EFFECT,
    )

    # Conservation check
    for i in range(len(cities)):
        totals = result.S[i] + result.E[i] + result.I[i] + result.R[i]
        max_deviation = np.abs(totals - result.city_populations[i]).max()
        if max_deviation > 1.0:
            print(f"  WARNING: {result.city_names[i]} conservation error: {max_deviation:.2f}")
        else:
            print(f"  {result.city_names[i]}: conservation OK (max deviation {max_deviation:.4f})")

    print("\nGenerating figures...")
    plot_wave_propagation(result)
    plot_geographic_spread(result)
    plot_per_city_seir(result)
    plot_travel_matrix(result)

    print_summary(result)

    print("Done.")


if __name__ == "__main__":
    main()
