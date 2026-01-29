"""
SEIR ODE Solver.

Solves the classic S-E-I-R compartmental model using scipy's ODE integrator.
Structured to accept pluggable derivatives functions for future extensions
(e.g., detected/undetected split, vaccination compartments).
"""

from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np
from scipy.integrate import odeint


@dataclass
class SEIRParams:
    """Epidemiological parameters for the SEIR model."""
    R0: float               # Basic reproduction number
    incubation_days: float   # Mean latent period (E → I)
    infectious_days: float   # Mean infectious period (I → R)
    population: int          # Total population N

    @property
    def sigma(self) -> float:
        """E → I transition rate (1/day)."""
        return 1.0 / self.incubation_days

    @property
    def gamma(self) -> float:
        """I → R transition rate (1/day)."""
        return 1.0 / self.infectious_days

    @property
    def beta(self) -> float:
        """Transmission rate derived from R0: β = R0 × γ."""
        return self.R0 * self.gamma


# Type alias for derivatives functions
DerivativesFn = Callable[[np.ndarray, float, "SEIRParams"], np.ndarray]


def basic_seir_derivatives(y: np.ndarray, t: float, params: SEIRParams) -> np.ndarray:
    """
    Classic 4-compartment SEIR derivatives.

    State vector: [S, E, I, R]
    """
    S, E, I, R = y
    N = params.population

    force_of_infection = params.beta * S * I / N

    dS = -force_of_infection
    dE = force_of_infection - params.sigma * E
    dI = params.sigma * E - params.gamma * I
    dR = params.gamma * I

    return np.array([dS, dE, dI, dR])


def solve_seir(
    params: SEIRParams,
    days: int,
    initial_infected: int = 3,
    initial_exposed: int = 0,
    derivatives_fn: Optional[DerivativesFn] = None,
) -> dict[str, np.ndarray]:
    """
    Solve SEIR ODE system.

    Args:
        params: Epidemiological parameters
        days: Number of days to simulate
        initial_infected: Initial number in I compartment
        initial_exposed: Initial number in E compartment
        derivatives_fn: Custom derivatives function (default: basic 4-compartment SEIR)

    Returns:
        Dict with keys 't', 'S', 'E', 'I', 'R' (arrays of length days+1)
    """
    fn = derivatives_fn or basic_seir_derivatives

    # Initial conditions
    I0 = initial_infected
    E0 = initial_exposed
    R0 = 0
    S0 = params.population - I0 - E0 - R0
    y0 = np.array([S0, E0, I0, R0], dtype=float)

    # Time points (one per day)
    t = np.linspace(0, days, days + 1)

    # Solve
    solution = odeint(fn, y0, t, args=(params,))

    return {
        "t": t,
        "S": solution[:, 0],
        "E": solution[:, 1],
        "I": solution[:, 2],
        "R": solution[:, 3],
    }


if __name__ == "__main__":
    # Quick sanity check
    params = SEIRParams(R0=2.5, incubation_days=5.0, infectious_days=9.0, population=10000)
    result = solve_seir(params, days=180, initial_infected=3)

    peak_I = result["I"].max()
    peak_day = result["t"][result["I"].argmax()]
    final_attack_rate = (params.population - result["S"][-1]) / params.population * 100

    print(f"SEIR ODE Solution (N={params.population}, R0={params.R0})")
    print(f"  β={params.beta:.4f}, σ={params.sigma:.4f}, γ={params.gamma:.4f}")
    print(f"  Peak I: {peak_I:.0f} on day {peak_day:.0f}")
    print(f"  Final attack rate: {final_attack_rate:.1f}%")
