"""
Stepping DES for one city — SEIR epidemic on a social network.

Designed for day-by-day stepping in the multi-city coupling loop.
Each city maintains a SimPy environment that can be advanced to any
time point, paused, have external exposures injected, then resumed.

Disease parameters are derived from EpidemicScenario using the same
β = transmission_prob × daily_contact_rate × avg_contacts mapping
validated in modules 001-003.

Provider mechanics (from module 003, with decay extension):
    Healthcare providers screen the population daily, detect infectious
    cases (if disclosed), and give advice that shifts isolation behavior.
    Advised persons isolate with P=0.40 vs baseline P=0.05 — transmission
    reduction emerges from agent behavior.  Advice decays: each day,
    advised persons revert to baseline with P=advice_decay_prob.
"""

import math
import random

import networkx as nx
import numpy as np
import simpy


# Default network parameters (same as to_des_config defaults)
DEFAULT_AVG_CONTACTS = 10
DEFAULT_REWIRE_PROB = 0.4
DEFAULT_DAILY_CONTACT_RATE = 0.5


class CityDES:
    """
    Stepping SEIR simulation on a Watts-Strogatz social network.

    Usage:
        city = CityDES(n_people=5000, scenario=COVID_LIKE, seed_infected=10)
        for day in range(1, 301):
            city.step(until=day)
            # read city.S, city.E, city.I, city.R, city.infection_fraction
            # optionally inject external exposures:
            city.inject_exposed(n)
    """

    def __init__(
        self,
        n_people: int,
        scenario,
        seed_infected: int = 1,
        random_seed: int | None = None,
        avg_contacts: int = DEFAULT_AVG_CONTACTS,
        rewire_prob: float = DEFAULT_REWIRE_PROB,
        daily_contact_rate: float = DEFAULT_DAILY_CONTACT_RATE,
        r0_override: float | None = None,
        # Provider parameters (0 providers = no behavioral intervention)
        n_providers: int = 0,
        screening_capacity: int = 20,
        # Behavioral parameters (defaults from module 003)
        disclosure_prob: float = 0.5,
        receptivity: float = 0.6,
        base_isolation_prob: float = 0.0,
        advised_isolation_prob: float = 0.40,
        advice_decay_prob: float = 0.0,
    ):
        # Seed RNGs
        self._rng = random.Random(random_seed)
        self._np_rng = np.random.RandomState(random_seed)

        self.n_people = n_people
        self.env = simpy.Environment()

        # Disease parameters (same derivation as validation_config.to_des_config)
        # r0_override allows per-city effective R₀ (e.g. health modulation)
        r0 = r0_override if r0_override is not None else scenario.R0
        self.incubation_days = scenario.incubation_days
        self.infectious_days = scenario.infectious_days
        gamma = 1.0 / scenario.infectious_days
        beta = r0 * gamma
        self.transmission_prob = beta / (daily_contact_rate * avg_contacts)
        self.daily_contact_rate = daily_contact_rate

        if self.transmission_prob > 1.0:
            raise ValueError(
                f"Cannot achieve R0={scenario.R0} with avg_contacts={avg_contacts}, "
                f"daily_contact_rate={daily_contact_rate}. "
                f"Derived transmission_prob={self.transmission_prob:.3f} > 1.0."
            )

        # Provider parameters
        self._n_providers = n_providers
        self._screening_capacity = screening_capacity
        self._disclosure_prob = disclosure_prob
        self._receptivity = receptivity
        self._base_isolation_prob = base_isolation_prob
        self._advised_isolation_prob = advised_isolation_prob
        self._advice_decay_prob = advice_decay_prob

        # Per-agent behavioral state: has this person accepted provider advice?
        # Reverts to False each day with P=advice_decay_prob (0 = no decay).
        self._provider_advised = np.zeros(n_people, dtype=np.bool_)

        # Build social network (Watts-Strogatz small-world)
        G = nx.watts_strogatz_graph(
            n_people, k=avg_contacts, p=rewire_prob,
            seed=random_seed,
        )
        self._neighbors = [list(G.neighbors(i)) for i in range(n_people)]

        # Agent states: 0=S, 1=E, 2=I, 3=R
        self._states = np.zeros(n_people, dtype=np.int8)

        # Compartment counts
        self._counts = [n_people, 0, 0, 0]  # [S, E, I, R]

        # Seed initial infections (directly to I, matching ODE seeding)
        indices = self._rng.sample(range(n_people), min(seed_infected, n_people))
        for idx in indices:
            self._states[idx] = 2  # I
            self._counts[0] -= 1  # S--
            self._counts[2] += 1  # I++
            self.env.process(self._infectious_process(idx))

    # ── State readouts ────────────────────────────────────────────────

    @property
    def S(self) -> int:
        return self._counts[0]

    @property
    def E(self) -> int:
        return self._counts[1]

    @property
    def I(self) -> int:  # noqa: E743
        return self._counts[2]

    @property
    def R(self) -> int:
        return self._counts[3]

    @property
    def infection_fraction(self) -> float:
        return self._counts[2] / self.n_people if self.n_people > 0 else 0.0

    @property
    def advised_fraction(self) -> float:
        """Fraction of population that has accepted provider advice."""
        return self._provider_advised.sum() / self.n_people if self.n_people > 0 else 0.0

    # ── Stepping interface ────────────────────────────────────────────

    def step(self, until: float) -> None:
        """Advance the SimPy environment to the given time."""
        self.env.run(until=until)

    def inject_exposed(self, n_exposed: float) -> None:
        """
        Inject external exposures from inter-city travel coupling.

        Uses stochastic rounding to preserve expected value:
        floor(n) + Bernoulli(n - floor(n)).
        """
        n_int = int(n_exposed)
        if self._rng.random() < (n_exposed - n_int):
            n_int += 1
        if n_int <= 0:
            return

        susceptible = np.where(self._states == 0)[0]
        if len(susceptible) == 0:
            return
        n_int = min(n_int, len(susceptible))

        chosen = self._np_rng.choice(susceptible, size=n_int, replace=False)
        for idx in chosen:
            self._states[idx] = 1  # E
            self._counts[0] -= 1  # S--
            self._counts[1] += 1  # E++
            self.env.process(self._exposed_process(idx))

    # ── Provider screening ──────────────────────────────────────────────

    def run_provider_screening(self) -> dict:
        """
        Run one day of provider screening (called from multi-city loop).

        Two phases each day:

        1. **Decay**: Each currently-advised person reverts to baseline with
           P=advice_decay_prob. This models compliance fatigue — people forget
           or stop following advice over time.

        2. **Screening**: Each provider screens ``screening_capacity`` random
           people. Detection: infectious + discloses. Advice: accepted with
           P=receptivity, flipping ``_provider_advised`` to True.

        Decay before screening means providers must continuously reinforce
        advice to maintain population-level compliance.

        Returns dict with screening stats.
        """
        # Phase 1: Advice decay (compliance fatigue)
        decayed = 0
        if self._advice_decay_prob > 0:
            advised_indices = np.where(self._provider_advised)[0]
            if len(advised_indices) > 0:
                decay_rolls = self._np_rng.random(len(advised_indices))
                revert_mask = decay_rolls < self._advice_decay_prob
                for idx in advised_indices[revert_mask]:
                    self._provider_advised[idx] = False
                decayed = int(revert_mask.sum())

        # Phase 2: Provider screening
        if self._n_providers <= 0:
            return {"screened": 0, "detected": 0, "advice_accepted": 0,
                    "decayed": decayed}

        capacity = self._n_providers * self._screening_capacity
        sample_size = min(capacity, self.n_people)
        sample = self._rng.sample(range(self.n_people), sample_size)

        detected = 0
        advice_accepted = 0
        for pid in sample:
            # Detection: infectious + discloses
            if (self._states[pid] == 2
                    and self._rng.random() < self._disclosure_prob):
                detected += 1
            # Advice: offered to everyone screened
            if not self._provider_advised[pid]:
                if self._rng.random() < self._receptivity:
                    self._provider_advised[pid] = True
                    advice_accepted += 1

        return {
            "screened": sample_size,
            "detected": detected,
            "advice_accepted": advice_accepted,
            "decayed": decayed,
        }

    # ── Disease processes ─────────────────────────────────────────────

    def _exposed_process(self, idx: int):
        """E -> I -> R progression starting from exposed state."""
        # Incubation period (exponentially distributed)
        duration = self._rng.expovariate(1.0 / self.incubation_days)
        yield self.env.timeout(duration)

        # E -> I
        if self._states[idx] != 1:
            return  # state changed externally (shouldn't happen, but defensive)
        self._states[idx] = 2
        self._counts[1] -= 1  # E--
        self._counts[2] += 1  # I++

        # Run infectious phase
        yield from self._infectious_process(idx)

    def _is_isolating(self, idx: int) -> bool:
        """Daily stochastic isolation check (module 003 semantics).

        Advised persons isolate with ``advised_isolation_prob`` (default 0.40),
        others with ``base_isolation_prob`` (default 0.0).  When isolating,
        the person makes zero contacts that day.
        """
        prob = (self._advised_isolation_prob if self._provider_advised[idx]
                else self._base_isolation_prob)
        return self._rng.random() < prob

    def _infectious_process(self, idx: int):
        """Make contacts during infectious period, then recover.

        Outer loop checks isolation at each day boundary (binary: zero
        contacts or full contacts that day).  Inner loop is the unchanged
        Poisson contact process from the validated DES.
        """
        neighbors = self._neighbors[idx]
        if not neighbors:
            # Isolated node: just wait and recover
            duration = self._rng.expovariate(1.0 / self.infectious_days)
            yield self.env.timeout(duration)
        else:
            # Contact rate: expected contacts/day = daily_contact_rate * degree
            contact_rate = self.daily_contact_rate * len(neighbors)
            recovery_time = self.env.now + self._rng.expovariate(
                1.0 / self.infectious_days,
            )

            while self.env.now < recovery_time:
                current_day = int(self.env.now)
                day_end = min(float(current_day + 1), recovery_time)

                # Daily isolation check (module 003 semantics)
                if self._is_isolating(idx):
                    # Zero contacts today — skip to next day boundary
                    wait = day_end - self.env.now
                    if wait > 0:
                        yield self.env.timeout(wait)
                    continue

                # Not isolating: Poisson contacts until day_end
                while self.env.now < day_end:
                    yield self.env.timeout(self._rng.expovariate(contact_rate))
                    if self.env.now >= day_end:
                        break

                    # Pick random neighbor and attempt transmission
                    neighbor = self._rng.choice(neighbors)
                    if (self._states[neighbor] == 0
                            and self._rng.random() < self.transmission_prob):
                        self._states[neighbor] = 1  # S -> E
                        self._counts[0] -= 1  # S--
                        self._counts[1] += 1  # E++
                        self.env.process(self._exposed_process(neighbor))

        # I -> R
        self._states[idx] = 3
        self._counts[2] -= 1  # I--
        self._counts[3] += 1  # R++
