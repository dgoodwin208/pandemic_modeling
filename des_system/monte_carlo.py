"""
Monte Carlo DES Runner for SEIR Validation.

Runs the DES simulation multiple times with different random seeds
and collects per-run daily time-series mapped to SEIR compartments.
"""

import sys
from dataclasses import dataclass, field

import numpy as np

from config import SimulationConfig
from simulation import run_simulation


@dataclass
class MonteCarloResult:
    """Results from multiple DES runs, mapped to SEIR compartments."""

    n_runs: int
    population: int
    days: int

    # Per-run time-series: shape (n_runs, days+1) for each compartment
    S: np.ndarray = field(repr=False)
    E: np.ndarray = field(repr=False)
    I: np.ndarray = field(repr=False)  # noqa: E741 - matches SEIR convention
    R: np.ndarray = field(repr=False)

    # Time array (shared across runs)
    t: np.ndarray = field(repr=False)

    @property
    def S_mean(self) -> np.ndarray:
        return self.S.mean(axis=0)

    @property
    def E_mean(self) -> np.ndarray:
        return self.E.mean(axis=0)

    @property
    def I_mean(self) -> np.ndarray:
        return self.I.mean(axis=0)

    @property
    def R_mean(self) -> np.ndarray:
        return self.R.mean(axis=0)

    @property
    def I_std(self) -> np.ndarray:
        return self.I.std(axis=0)


def _map_snapshot_to_seir(snapshot: dict, population: int) -> dict[str, int]:
    """
    Map 7 DES disease states to 4 SEIR compartments.

    Mapping:
        S = susceptible
        E = exposed
        I = infectious + symptomatic  (actively transmitting)
        R = recovered + deceased + hospitalized  (removed from transmission)

    Hospitalized maps to R because hospitalized patients are isolated
    from the contact network and cannot transmit.
    """
    sc = snapshot["state_counts"]
    return {
        "S": sc.get("susceptible", 0),
        "E": sc.get("exposed", 0),
        "I": sc.get("infectious", 0) + sc.get("symptomatic", 0),
        "R": sc.get("recovered", 0) + sc.get("deceased", 0) + sc.get("hospitalized", 0),
    }


def run_monte_carlo(
    config_factory,
    n_runs: int = 10,
    base_seed: int = 1000,
) -> MonteCarloResult:
    """
    Run the DES simulation multiple times and collect SEIR-mapped time-series.

    Args:
        config_factory: Callable(seed) -> SimulationConfig.
            Called once per run with a unique random seed.
        n_runs: Number of Monte Carlo iterations.
        base_seed: Starting seed (each run uses base_seed + i).

    Returns:
        MonteCarloResult with per-run SEIR compartment arrays.
    """
    all_S, all_E, all_I, all_R = [], [], [], []
    population = None
    n_days = None

    for i in range(n_runs):
        seed = base_seed + i
        config = config_factory(seed)

        if population is None:
            population = config.network.n_people
            n_days = int(config.duration_days)

        print(f"  Run {i + 1}/{n_runs} (seed={seed})...", end=" ", flush=True)
        result = run_simulation(config)

        # Extract daily SEIR compartments from snapshots
        run_S, run_E, run_I, run_R = [population], [0], [0], [0]  # day 0

        for snap in result.daily_snapshots:
            seir = _map_snapshot_to_seir(snap, population)
            run_S.append(seir["S"])
            run_E.append(seir["E"])
            run_I.append(seir["I"])
            run_R.append(seir["R"])

        # Pad or trim to exactly n_days+1 points
        target_len = n_days + 1
        for arr in [run_S, run_E, run_I, run_R]:
            while len(arr) < target_len:
                arr.append(arr[-1])

        all_S.append(run_S[:target_len])
        all_E.append(run_E[:target_len])
        all_I.append(run_I[:target_len])
        all_R.append(run_R[:target_len])

        # Report peak
        peak_I = max(run_I)
        peak_day = run_I.index(peak_I)
        final_attack = (population - run_S[-1]) / population * 100
        print(f"peak I={peak_I} on day {peak_day}, attack rate={final_attack:.1f}%")

    t = np.arange(n_days + 1, dtype=float)

    return MonteCarloResult(
        n_runs=n_runs,
        population=population,
        days=n_days,
        S=np.array(all_S, dtype=float),
        E=np.array(all_E, dtype=float),
        I=np.array(all_I, dtype=float),
        R=np.array(all_R, dtype=float),
        t=t,
    )


if __name__ == "__main__":
    from validation_config import COVID_LIKE

    population = 5000
    n_runs = 5

    print(f"Monte Carlo: {n_runs} runs, N={population}, {COVID_LIKE.name}")
    print(COVID_LIKE.describe())

    def make_config(seed):
        return COVID_LIKE.to_des_config(population=population, random_seed=seed)

    mc = run_monte_carlo(make_config, n_runs=n_runs)

    print(f"\nResults (as fraction of N={population}):")
    print(f"  Peak I mean: {mc.I_mean.max():.0f} ({mc.I_mean.max()/population*100:.1f}%)")
    print(f"  Peak I day:  {mc.t[mc.I_mean.argmax()]:.0f}")
    print(f"  Final attack rate: {(population - mc.S_mean[-1])/population*100:.1f}%")
