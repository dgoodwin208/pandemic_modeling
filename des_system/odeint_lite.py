"""
Lightweight odeint replacement using 4th-order Runge-Kutta.

Drop-in substitute for scipy.integrate.odeint for simple ODE systems
(SEIR models). Avoids the ~150 MB scipy dependency for serverless
deployments where only basic ODE integration is needed.
"""

import numpy as np


def odeint(func, y0, t, args=()):
    """
    Integrate a system of ODEs using classical RK4.

    Mimics the scipy.integrate.odeint interface for the subset used by
    this project: func(y, t, *args) -> dydt.

    Args:
        func: Callable(y, t, *args) returning derivatives array.
        y0: Initial state vector (1-D array).
        t: Array of time points to solve for.
        args: Extra arguments passed to func.

    Returns:
        2-D array of shape (len(t), len(y0)) with solution at each time point.
    """
    y0 = np.asarray(y0, dtype=float)
    t = np.asarray(t, dtype=float)
    n_steps = len(t)
    n_vars = len(y0)

    result = np.empty((n_steps, n_vars))
    result[0] = y0
    y = y0.copy()

    for i in range(1, n_steps):
        dt = t[i] - t[i - 1]

        k1 = np.asarray(func(y, t[i - 1], *args), dtype=float)
        k2 = np.asarray(func(y + 0.5 * dt * k1, t[i - 1] + 0.5 * dt, *args), dtype=float)
        k3 = np.asarray(func(y + 0.5 * dt * k2, t[i - 1] + 0.5 * dt, *args), dtype=float)
        k4 = np.asarray(func(y + dt * k3, t[i], *args), dtype=float)

        y = y + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        result[i] = y

    return result
