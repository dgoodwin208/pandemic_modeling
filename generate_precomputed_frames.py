#!/usr/bin/env python3
"""Generate pre-computed frame PNGs for the demo scenarios.

Run from the project root:
    python3 generate_precomputed_frames.py

Produces frames in frontend/public/precomputed/frames/{session_id}/.
"""

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# Set up sys.path — backend MUST be inserted last so it's first on sys.path
# (des_system/simulation.py would otherwise shadow simulation_app/backend/simulation.py)
for p in [
    str(PROJECT_ROOT / "des_system"),
    str(PROJECT_ROOT / "004_multicity"),
    str(PROJECT_ROOT / "005_multicity_des"),
    str(PROJECT_ROOT / "simulation_app" / "backend"),  # last insert = first on path
]:
    if p not in sys.path:
        sys.path.insert(0, p)

from simulation import run_absdes_simulation, SimulationParams
from renderer import render_all_frames, load_africa_boundaries

SCENARIOS = [
    {
        "session_id": "nigeria-covid-natural",
        "scenario": "covid_natural",
        "country": "Nigeria",
        "days": 150,
        "n_people": 5000,
        "seed_fraction": 0.005,
        "random_seed": 42,
        "enable_supply_chain": False,
    },
    {
        "session_id": "nigeria-covid-bioattack",
        "scenario": "covid_bioattack",
        "country": "Nigeria",
        "days": 150,
        "n_people": 5000,
        "seed_fraction": 0.005,
        "random_seed": 42,
        "enable_supply_chain": False,
    },
    {
        "session_id": "nigeria-supply-chain",
        "scenario": "covid_natural",
        "country": "Nigeria",
        "days": 150,
        "n_people": 5000,
        "seed_fraction": 0.005,
        "random_seed": 42,
        "enable_supply_chain": True,
    },
]

FRAMES_BASE = PROJECT_ROOT / "frontend" / "public" / "precomputed" / "frames"


def progress(phase, current, total, message=""):
    if total > 0:
        pct = current / total * 100
        print(f"\r  [{phase}] {current}/{total} ({pct:.0f}%) {message}", end="", flush=True)
    else:
        print(f"\r  [{phase}] {message}", end="", flush=True)


def main():
    africa_gdf = load_africa_boundaries()
    print(f"Loaded Africa boundaries ({len(africa_gdf)} features)")

    for scenario_cfg in SCENARIOS:
        sid = scenario_cfg["session_id"]
        output_dir = FRAMES_BASE / sid
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*60}")
        print(f"Scenario: {sid}")
        print(f"  Output: {output_dir}")

        # Check if frames already exist
        existing = list(output_dir.glob("actual_day*.png"))
        if len(existing) > 100:
            print(f"  Skipping — {len(existing)} frames already exist")
            continue

        params = SimulationParams(
            country=scenario_cfg["country"],
            scenario=scenario_cfg["scenario"],
            days=scenario_cfg["days"],
            n_people=scenario_cfg["n_people"],
            seed_fraction=scenario_cfg["seed_fraction"],
            random_seed=scenario_cfg["random_seed"],
            enable_supply_chain=scenario_cfg["enable_supply_chain"],
        )

        t0 = time.time()
        print("  Running simulation...")
        result = run_absdes_simulation(params, progress)
        print(f"\n  Simulation complete ({time.time() - t0:.1f}s)")

        t1 = time.time()
        print("  Rendering frames...")
        render_all_frames(
            result, africa_gdf, output_dir, progress,
            country=scenario_cfg["country"],
        )
        print(f"\n  Rendering complete ({time.time() - t1:.1f}s)")

        n_frames = len(list(output_dir.glob("*.png")))
        print(f"  Total frames: {n_frames}")

    print(f"\n{'='*60}")
    print("All scenarios complete!")
    print(f"Frames at: {FRAMES_BASE}")


if __name__ == "__main__":
    main()
