"""
Continental Africa DES Pandemic Simulation.

Runs 443 African cities across 4 disease scenarios x 2 healthcare provider
density levels, producing 4 spatial map figures with outcome tables.

Scenarios:
    01 — COVID Natural Origin (seed: Lagos)
    02 — COVID Bioattack (seeds: Cairo, Lagos, Nairobi, Kinshasa, Johannesburg)
    03 — Ebola Natural Origin (seed: Kinshasa)
    04 — Ebola Bioattack (seeds: Cairo, Lagos, Nairobi, Kinshasa, Johannesburg)

Usage:
    cd 006_continental_africa && python africa_des_sim.py
"""

import csv
import math
import sys
import time
from pathlib import Path

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "des_system"))
sys.path.insert(0, str(_PROJECT_ROOT / "004_multicity"))
sys.path.insert(0, str(_PROJECT_ROOT / "005_multicity_des"))

from validation_config import COVID_LIKE, COVID_BIOATTACK, EBOLA_LIKE, EBOLA_BIOATTACK
from gravity_model import compute_distance_matrix
from multicity_des_sim import run_multicity_des_simulation

# ── Constants ────────────────────────────────────────────────────────

N_PEOPLE = 5_000
DAYS = 400
N_MC_RUNS = 3
GRAVITY_SCALE = 0.01
GRAVITY_ALPHA = 2.0
TRANSMISSION_FACTOR = 0.3
SEED_FRACTION = 0.001
BASE_SEED = 42

PROVIDER_LOW = 1.0
PROVIDER_HIGH = 10.0

SCREENING_CAPACITY = 20
DISCLOSURE_PROB = 0.5
BASE_ISOLATION_PROB = 0.05
ADVISED_ISOLATION_PROB = 0.40
ADVICE_DECAY_PROB = 0.05

BIOATTACK_SEEDS = ["Cairo", "Lagos", "Nairobi", "Kinshasa", "Johannesburg"]
COVID_NATURAL_SEED = "Lagos"
EBOLA_NATURAL_SEED = "Kinshasa"

SCENARIOS = [
    ("COVID Natural",   COVID_LIKE,      0.005, [COVID_NATURAL_SEED]),
    ("COVID Bioattack", COVID_BIOATTACK, 0.005, BIOATTACK_SEEDS),
    ("Ebola Natural",   EBOLA_LIKE,      0.50,  [EBOLA_NATURAL_SEED]),
    ("Ebola Bioattack", EBOLA_BIOATTACK, 0.50,  BIOATTACK_SEEDS),
]

RESULTS_DIR = Path(__file__).parent / "results"


# ── City helper ──────────────────────────────────────────────────────

class _City:
    def __init__(self, row: dict):
        self.name = row["city"]
        self.population = int(row["population"])
        self.latitude = float(row["latitude"])
        self.longitude = float(row["longitude"])
        self.medical_services_score = float(row.get("medical_services_score", 0))

    def __repr__(self):
        return f"_City({self.name}, pop={self.population:,})"


def _load_all_african_cities() -> list[dict]:
    csv_path = _PROJECT_ROOT / "backend" / "data" / "african_cities.csv"
    cities = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cities.append(row)
    cities.sort(key=lambda x: int(x["population"]), reverse=True)
    return cities


def _score_to_receptivity(score: float) -> float:
    return 0.2 + 0.6 * (score / 100.0)


# ── DES-scale travel matrix ─────────────────────────────────────────

def _compute_des_travel_matrix(
    city_objs: list[_City],
    n_people: int,
    alpha: float = GRAVITY_ALPHA,
    scale: float = GRAVITY_SCALE,
) -> np.ndarray:
    dist = compute_distance_matrix(city_objs)
    n = len(city_objs)
    travel = np.zeros((n, n))
    pop_product = n_people * n_people

    for i in range(n):
        for j in range(i + 1, n):
            if dist[i, j] > 0:
                rate = scale * pop_product / (dist[i, j] ** alpha)
                travel[i, j] = rate
                travel[j, i] = rate

    return travel


# ── Scenario runner ──────────────────────────────────────────────────

def _run_scenario(
    cities: list[dict],
    city_objs: list[_City],
    travel_matrix: np.ndarray,
    scenario,
    provider_density: float,
    seed_city_names: list[str],
    ifr: float,
    label: str,
    n_mc_runs: int = N_MC_RUNS,
):
    n_cities = len(cities)
    n_people = N_PEOPLE

    npz_slug = label.lower().replace(" ", "_").replace("/", "_")
    npz_path = RESULTS_DIR / f"{npz_slug}.npz"

    if npz_path.exists():
        print(f"  Loading cached results from {npz_path.name}")
        data = np.load(npz_path)
        return {
            "peak_pcts": data["peak_pcts"],
            "peak_days": data["peak_days"],
            "attack_rates": data["attack_rates"],
            "label": label,
        }

    city_names = [c["city"] for c in cities]
    city_pops = [int(c["population"]) for c in cities]
    city_coords = [(float(c["latitude"]), float(c["longitude"])) for c in cities]

    seed_indices = []
    for sn in seed_city_names:
        if sn in city_names:
            seed_indices.append(city_names.index(sn))
        else:
            print(f"  WARNING: seed city '{sn}' not found, skipping")
    if not seed_indices:
        raise ValueError(f"No valid seed cities found for {label}")

    per_city_receptivity = [
        _score_to_receptivity(float(c.get("medical_services_score", 0)))
        for c in cities
    ]

    des_initial = max(1, int(SEED_FRACTION * n_people))

    des_I_runs = np.zeros((n_mc_runs, n_cities, DAYS + 1))
    des_R_final = np.zeros((n_mc_runs, n_cities))

    for run in range(n_mc_runs):
        print(f"  {label} run {run + 1}/{n_mc_runs}...", end="", flush=True)
        t0 = time.time()
        result = run_multicity_des_simulation(
            city_names=city_names,
            city_populations=city_pops,
            city_coords=city_coords,
            scenario=scenario,
            travel_matrix=travel_matrix,
            days=DAYS,
            n_people=n_people,
            transmission_factor=TRANSMISSION_FACTOR,
            seed_city_index=seed_indices,
            initial_infected=des_initial,
            random_seed=BASE_SEED + run * 100,
            des_scale_travel=True,
            isolation_effect=0.0,
            provider_density=provider_density,
            screening_capacity=SCREENING_CAPACITY,
            disclosure_prob=DISCLOSURE_PROB,
            receptivity=0.6,
            base_isolation_prob=BASE_ISOLATION_PROB,
            advised_isolation_prob=ADVISED_ISOLATION_PROB,
            advice_decay_prob=ADVICE_DECAY_PROB,
            per_city_receptivity=per_city_receptivity,
        )
        elapsed = time.time() - t0

        for i in range(n_cities):
            des_I_runs[run, i, :] = result.I[i] / n_people
            des_R_final[run, i] = result.R[i, -1] / n_people

        if run == 0:
            peaks = []
            for i in range(n_cities):
                frac = result.I[i] / n_people * 100
                peak_day = int(result.t[np.argmax(frac)])
                peak_val = frac.max()
                peaks.append((result.city_names[i], peak_day, peak_val))
            peaks.sort(key=lambda x: -x[2])
            for name, day, val in peaks[:10]:
                print(f"\n    {name}: peak day {day}, {val:.1f}%", end="")
            if n_cities > 10:
                print(f"\n    ... ({n_cities - 10} more cities)", end="")
        print(f"  [{elapsed:.0f}s]")

    peak_pcts = np.zeros(n_cities)
    peak_days = np.zeros(n_cities)
    attack_rates = np.zeros(n_cities)
    for i in range(n_cities):
        mean_frac = des_I_runs[:, i, :].mean(axis=0)
        peak_pcts[i] = mean_frac.max() * 100
        peak_days[i] = np.argmax(mean_frac)
        attack_rates[i] = des_R_final[:, i].mean()

    np.savez_compressed(
        npz_path,
        peak_pcts=peak_pcts,
        peak_days=peak_days,
        attack_rates=attack_rates,
    )
    print(f"  Saved intermediate results to {npz_path.name}")

    return {
        "peak_pcts": peak_pcts,
        "peak_days": peak_days,
        "attack_rates": attack_rates,
        "label": label,
    }


# ── Africa boundary download ────────────────────────────────────────

def _download_africa_boundaries():
    import geopandas as gpd

    boundary_path = Path(__file__).parent / "africa_boundaries.geojson"
    if boundary_path.exists():
        print(f"  Loading Africa boundaries from {boundary_path.name}")
        return gpd.read_file(boundary_path)

    print("  Downloading Africa boundaries from Natural Earth...")
    url = "https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip"
    world = gpd.read_file(url)
    africa = world[world["CONTINENT"] == "Africa"]
    africa.to_file(boundary_path, driver="GeoJSON")
    print(f"  Saved to {boundary_path.name}")
    return africa


# ── Figure generation ────────────────────────────────────────────────

def _generate_figure(
    scenario_name: str,
    scenario,
    ifr: float,
    results_low: dict,
    results_high: dict,
    cities: list[dict],
    city_objs: list[_City],
    travel_matrix: np.ndarray,
    africa_gdf,
    fig_num: int,
    seed_city_names: list[str],
):
    n_cities = len(cities)
    names = [c["city"] for c in cities]
    lons = np.array([float(c["longitude"]) for c in cities])
    lats = np.array([float(c["latitude"]) for c in cities])
    pops = np.array([int(c["population"]) for c in cities], dtype=float)

    size_scale = np.sqrt(pops / pops.min()) * 15
    size_scale = np.clip(size_scale, 8, 200)

    edges = set()
    for i in range(n_cities):
        rates = [(travel_matrix[i, j], j) for j in range(n_cities) if i != j]
        rates.sort(reverse=True)
        for rate, j in rates[:2]:
            edge = (min(i, j), max(i, j))
            edges.add((edge[0], edge[1], travel_matrix[edge[0], edge[1]]))
    max_rate = max(r for _, _, r in edges) if edges else 1.0

    peaks_low = results_low["peak_pcts"]
    peaks_high = results_high["peak_pcts"]
    days_low = results_low["peak_days"]
    days_high = results_high["peak_days"]
    attack_low = results_low["attack_rates"]
    attack_high = results_high["attack_rates"]

    vmin = 0
    vmax = max(peaks_low.max(), peaks_high.max(), 1)
    cmap = plt.cm.YlOrRd

    real_pops = pops
    total_pop = real_pops.sum()

    infections_low = (attack_low * real_pops).sum()
    infections_high = (attack_high * real_pops).sum()
    deaths_low = infections_low * ifr
    deaths_high = infections_high * ifr
    lives_saved = deaths_low - deaths_high

    n_prov_low = max(0, int(PROVIDER_LOW * N_PEOPLE / 1000))
    n_prov_high = max(0, int(PROVIDER_HIGH * N_PEOPLE / 1000))

    fig = plt.figure(figsize=(22, 14))
    gs = GridSpec(2, 2, figure=fig, height_ratios=[3, 1], hspace=0.25, wspace=0.12)
    ax_left = fig.add_subplot(gs[0, 0])
    ax_right = fig.add_subplot(gs[0, 1])
    table_ax = fig.add_subplot(gs[1, :])

    fig.suptitle(
        f"Fig {fig_num}: Continental Africa — {scenario_name}\n"
        f"{scenario.name} (R0={scenario.R0}), N={N_PEOPLE:,}/city, "
        f"{N_MC_RUNS} MC runs, {n_cities} cities, IFR={ifr*100:.1f}%",
        fontsize=13, fontweight="bold", y=0.98,
    )

    seed_indices = []
    for sn in seed_city_names:
        if sn in names:
            seed_indices.append(names.index(sn))

    panel_configs = [
        (ax_left, peaks_low, days_low,
         f"Low Provider Density ({PROVIDER_LOW:.0f}/1000 = {n_prov_low} providers)\n"
         f"{n_prov_low * SCREENING_CAPACITY} screens/day per city"),
        (ax_right, peaks_high, days_high,
         f"High Provider Density ({PROVIDER_HIGH:.0f}/1000 = {n_prov_high} providers)\n"
         f"{n_prov_high * SCREENING_CAPACITY} screens/day per city"),
    ]

    for ax_idx, (ax, peaks, peak_days, title) in enumerate(panel_configs):
        ax.set_title(title, fontsize=10)

        africa_gdf.plot(ax=ax, color="#f0ede4", edgecolor="#333333",
                        linewidth=0.8, zorder=0)
        africa_gdf.boundary.plot(ax=ax, color="#333333", linewidth=0.8, zorder=0)

        for i, j, rate in edges:
            linewidth = 0.2 + 1.2 * (rate / max_rate)
            alpha = 0.08 + 0.20 * (rate / max_rate)
            ax.plot(
                [lons[i], lons[j]], [lats[i], lats[j]],
                color="#666666", linewidth=linewidth, alpha=alpha, zorder=1,
            )

        norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
        ax.scatter(
            lons, lats, s=size_scale, c=peaks, cmap=cmap,
            norm=norm, edgecolors="black", linewidths=0.3, zorder=2,
        )

        pop_order = np.argsort(-pops)
        for rank, i in enumerate(pop_order[:10]):
            ax.annotate(
                names[i], (lons[i], lats[i]),
                textcoords="offset points", xytext=(5, 5),
                fontsize=5, fontweight="bold", zorder=3,
                bbox=dict(boxstyle="round,pad=0.1", facecolor="white",
                          alpha=0.6, edgecolor="none"),
            )

        for si in seed_indices:
            ax.scatter(
                [lons[si]], [lats[si]],
                s=size_scale[si] * 1.8,
                facecolors="none", edgecolors="blue", linewidths=1.5, zorder=3,
            )

        bounds = africa_gdf.total_bounds
        pad = 2.0
        ax.set_xlim(bounds[0] - pad, bounds[2] + pad)
        ax.set_ylim(bounds[1] - pad, bounds[3] + pad)
        ax.set_aspect("equal")
        ax.set_xlabel("Longitude", fontsize=9)
        if ax_idx == 0:
            ax.set_ylabel("Latitude", fontsize=9)
        ax.tick_params(labelsize=7)

        mean_peak = peaks.mean()
        max_peak_city = names[np.argmax(peaks)]
        max_peak_val = peaks.max()
        ax.text(
            0.02, 0.02,
            f"Mean peak: {mean_peak:.1f}%\n"
            f"Max: {max_peak_val:.1f}% ({max_peak_city})\n"
            f"Avg peak day: {peak_days.mean():.0f}",
            transform=ax.transAxes, fontsize=8, verticalalignment="bottom",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.85),
        )

    cbar = fig.colorbar(
        plt.cm.ScalarMappable(norm=mcolors.Normalize(vmin=vmin, vmax=vmax), cmap=cmap),
        ax=[ax_left, ax_right], orientation="horizontal", fraction=0.035, pad=0.06,
        aspect=50,
    )
    cbar.set_label("Peak Infection (% of city population)", fontsize=10)

    table_ax.axis("off")

    col_labels = [
        "Provider\ndensity", "Providers\nper city", "Daily\nscreens",
        "Mean\npeak %", "Attack\nrate %", "Total\ninfections",
        "Estimated\ndeaths", "Lives saved\nvs low",
    ]
    mean_attack_low = (attack_low * real_pops).sum() / total_pop * 100
    mean_attack_high = (attack_high * real_pops).sum() / total_pop * 100

    table_data = [
        [
            f"Low ({PROVIDER_LOW:.0f}/1000)",
            f"{n_prov_low}",
            f"{n_prov_low * SCREENING_CAPACITY:,}",
            f"{peaks_low.mean():.1f}%",
            f"{mean_attack_low:.1f}%",
            f"{infections_low:,.0f}",
            f"{deaths_low:,.0f}",
            "---",
        ],
        [
            f"High ({PROVIDER_HIGH:.0f}/1000)",
            f"{n_prov_high}",
            f"{n_prov_high * SCREENING_CAPACITY:,}",
            f"{peaks_high.mean():.1f}%",
            f"{mean_attack_high:.1f}%",
            f"{infections_high:,.0f}",
            f"{deaths_high:,.0f}",
            f"{lives_saved:+,.0f}",
        ],
    ]

    table = table_ax.table(
        cellText=table_data,
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.0, 1.8)

    for j in range(len(col_labels)):
        cell = table[0, j]
        cell.set_facecolor("#2c3e50")
        cell.set_text_props(color="white", fontweight="bold")

    row_colors = ["#fff3cd", "#d4edda"]
    for i in range(len(table_data)):
        for j in range(len(col_labels)):
            table[i + 1, j].set_facecolor(row_colors[i])

    table_ax.set_title(
        f"Outcome Summary | {scenario_name} | "
        f"Total population: {total_pop:,.0f} ({n_cities} cities) | "
        f"IFR: {ifr*100:.1f}%",
        fontsize=11, fontweight="bold", pad=10,
    )

    scenario_slug = scenario_name.lower().replace(" ", "_")
    fname = RESULTS_DIR / f"{fig_num:02d}_{scenario_slug}.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {fname.name}")


# ── Main ─────────────────────────────────────────────────────────────

def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Continental Africa DES Pandemic Simulation")
    print("=" * 70)

    print("\nLoading African cities...")
    raw_cities = _load_all_african_cities()
    n_cities = len(raw_cities)
    print(f"  Loaded {n_cities} cities")
    for c in raw_cities[:10]:
        print(f"    {c['city']} ({c['country']}): pop={int(c['population']):,}, "
              f"score={float(c.get('medical_services_score', 0)):.0f}")
    if n_cities > 10:
        print(f"    ... ({n_cities - 10} more)")

    city_objs = [_City(c) for c in raw_cities]

    print(f"\nComputing DES-scale gravity matrix for {n_cities} cities...")
    t0 = time.time()
    travel_matrix = _compute_des_travel_matrix(city_objs, N_PEOPLE)
    elapsed = time.time() - t0
    print(f"  Done in {elapsed:.1f}s")

    nonzero = travel_matrix[travel_matrix > 0]
    print(f"  Travel matrix stats (daily coupling rates):")
    print(f"    min={nonzero.min():.4f}, median={np.median(nonzero):.4f}, "
          f"max={nonzero.max():.2f}, mean={nonzero.mean():.4f}")
    max_incoming = travel_matrix.sum(axis=0).max()
    print(f"    Max total incoming to any city: {max_incoming:.0f}/day")

    print("\nDownloading/loading Africa boundaries...")
    africa_gdf = _download_africa_boundaries()

    print(f"\n{'='*70}")
    print(f"Running 4 scenarios x 2 provider densities = 8 conditions")
    print(f"  N={N_PEOPLE:,}/city, {DAYS} days, {N_MC_RUNS} MC runs each")
    print(f"  Provider densities: {PROVIDER_LOW}/1000, {PROVIDER_HIGH}/1000")
    half_life = math.log(2) / ADVICE_DECAY_PROB if ADVICE_DECAY_PROB > 0 else float('inf')
    print(f"  Advice decay half-life: {half_life:.0f} days")
    print(f"{'='*70}")

    grand_summary = []

    for fig_num, (scenario_name, scenario, ifr, seed_names) in enumerate(SCENARIOS, start=1):
        print(f"\n{'='*70}")
        print(f"SCENARIO {fig_num}: {scenario_name}")
        print(f"  {scenario.name}, R0={scenario.R0}, IFR={ifr*100:.1f}%")
        print(f"  Seeds: {seed_names}")
        print(f"{'='*70}")

        t_scenario = time.time()

        label_low = f"{scenario_name} low_{PROVIDER_LOW}"
        label_high = f"{scenario_name} high_{PROVIDER_HIGH}"

        print(f"\n--- Low provider density ({PROVIDER_LOW}/1000) ---")
        results_low = _run_scenario(
            raw_cities, city_objs, travel_matrix, scenario,
            PROVIDER_LOW, seed_names, ifr, label_low,
        )

        print(f"\n--- High provider density ({PROVIDER_HIGH}/1000) ---")
        results_high = _run_scenario(
            raw_cities, city_objs, travel_matrix, scenario,
            PROVIDER_HIGH, seed_names, ifr, label_high,
        )

        print(f"\nGenerating figure {fig_num}...")
        _generate_figure(
            scenario_name, scenario, ifr,
            results_low, results_high,
            raw_cities, city_objs, travel_matrix,
            africa_gdf, fig_num, seed_names,
        )

        elapsed_scenario = time.time() - t_scenario
        print(f"  Scenario {fig_num} completed in {elapsed_scenario:.0f}s")

        real_pops = np.array([int(c["population"]) for c in raw_cities], dtype=float)
        for density_label, res in [("Low", results_low), ("High", results_high)]:
            infections = (res["attack_rates"] * real_pops).sum()
            deaths = infections * ifr
            grand_summary.append({
                "scenario": scenario_name,
                "density": density_label,
                "mean_peak": res["peak_pcts"].mean(),
                "infections": infections,
                "deaths": deaths,
            })

    print(f"\n\n{'='*90}")
    print("GRAND SUMMARY — All 8 Conditions")
    print("=" * 90)
    print(f"{'Scenario':<22} {'Density':<8} {'Mean Peak%':>10} "
          f"{'Infections':>14} {'Deaths':>12}")
    print("-" * 68)
    for row in grand_summary:
        print(f"{row['scenario']:<22} {row['density']:<8} {row['mean_peak']:>9.1f}% "
              f"{row['infections']:>13,.0f} {row['deaths']:>11,.0f}")

    print(f"\n{'='*90}")
    print("All done.")


if __name__ == "__main__":
    main()
