"""
Social Network Graph for Pandemic Simulation.

Creates an undirected graph of people with social connections.
Uses a small-world network model (Watts-Strogatz) for realistic structure.
"""

import random
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

from config import NetworkConfig


class DiseaseState(Enum):
    """Disease states for the finite state machine."""
    SUSCEPTIBLE = "susceptible"
    EXPOSED = "exposed"
    INFECTIOUS = "infectious"
    SYMPTOMATIC = "symptomatic"
    HOSPITALIZED = "hospitalized"
    RECOVERED = "recovered"
    DECEASED = "deceased"


@dataclass
class Person:
    """A person in the social network."""
    id: int
    name: str
    age: int
    state: DiseaseState = DiseaseState.SUSCEPTIBLE
    contacts: list[int] = field(default_factory=list)

    # Disease timing (set when infected)
    infected_at: Optional[float] = None
    exposed_until: Optional[float] = None
    infectious_until: Optional[float] = None

    # Outcomes
    recovered_at: Optional[float] = None
    hospitalized_at: Optional[float] = None
    deceased_at: Optional[float] = None

    def is_contagious(self) -> bool:
        return self.state in (
            DiseaseState.INFECTIOUS,
            DiseaseState.SYMPTOMATIC,
        )

    def is_susceptible(self) -> bool:
        return self.state == DiseaseState.SUSCEPTIBLE


class SocialNetwork:
    """
    Undirected graph representing social connections.

    Uses Watts-Strogatz small-world model:
    - Each person connected to k nearest neighbors
    - Random rewiring with probability p
    """

    def __init__(self, config: Optional[NetworkConfig] = None):
        """
        Create social network from configuration.

        Args:
            config: Network configuration (uses defaults if None)
        """
        self.config = config or NetworkConfig()
        self.people: dict[int, Person] = {}
        self._build_network()

    def _build_network(self) -> None:
        """Build Watts-Strogatz small-world network."""
        n = self.config.n_people
        k = self.config.avg_contacts
        p = self.config.rewire_prob

        first_names = [
            "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley",
            "Quinn", "Avery", "Parker", "Sage", "Drew", "Jamie",
            "Reese", "Skyler", "Dakota", "Finley", "Hayden", "Blake",
            "Charlie", "Emery", "Rowan", "Phoenix", "River", "Kai",
        ]

        for i in range(n):
            name = f"{random.choice(first_names)}_{i}"
            age = random.randint(self.config.min_age, self.config.max_age)
            self.people[i] = Person(id=i, name=name, age=age)

        # Build ring lattice: each node connected to k/2 neighbors on each side
        half_k = k // 2
        for i in range(n):
            for j in range(1, half_k + 1):
                neighbor = (i + j) % n
                self._add_edge(i, neighbor)

        # Rewire edges with probability p
        for i in range(n):
            for j in range(1, half_k + 1):
                if random.random() < p:
                    neighbor = (i + j) % n
                    self._remove_edge(i, neighbor)
                    new_neighbor = random.randint(0, n - 1)
                    attempts = 0
                    while (
                        new_neighbor == i
                        or new_neighbor in self.people[i].contacts
                    ) and attempts < 10:
                        new_neighbor = random.randint(0, n - 1)
                        attempts += 1
                    if attempts < 10:
                        self._add_edge(i, new_neighbor)

    def _add_edge(self, a: int, b: int) -> None:
        """Add undirected edge between two people."""
        if b not in self.people[a].contacts:
            self.people[a].contacts.append(b)
        if a not in self.people[b].contacts:
            self.people[b].contacts.append(a)

    def _remove_edge(self, a: int, b: int) -> None:
        """Remove undirected edge between two people."""
        if b in self.people[a].contacts:
            self.people[a].contacts.remove(b)
        if a in self.people[b].contacts:
            self.people[b].contacts.remove(a)

    def get_contacts(self, person_id: int) -> list[Person]:
        contact_ids = self.people[person_id].contacts
        return [self.people[cid] for cid in contact_ids]

    def get_susceptible_contacts(self, person_id: int) -> list[Person]:
        return [p for p in self.get_contacts(person_id) if p.is_susceptible()]

    def count_by_state(self) -> dict[DiseaseState, int]:
        counts = {state: 0 for state in DiseaseState}
        for person in self.people.values():
            counts[person.state] += 1
        return counts

    def get_age_distribution(self) -> dict:
        ages = [p.age for p in self.people.values()]
        return {
            "min": min(ages),
            "max": max(ages),
            "mean": sum(ages) / len(ages),
            "elderly_count": sum(1 for a in ages if a >= 60),
            "elderly_pct": sum(1 for a in ages if a >= 60) / len(ages) * 100,
        }

    def get_statistics(self) -> dict:
        degrees = [len(p.contacts) for p in self.people.values()]
        counts = self.count_by_state()
        age_stats = self.get_age_distribution()

        return {
            "n_people": len(self.people),
            "avg_contacts": sum(degrees) / len(degrees) if degrees else 0,
            "min_contacts": min(degrees) if degrees else 0,
            "max_contacts": max(degrees) if degrees else 0,
            "state_counts": {s.value: c for s, c in counts.items()},
            "age_distribution": age_stats,
        }

    def infect_random(self, n: int = 3) -> list[Person]:
        """Infect n random susceptible people as initial seeds."""
        susceptible = [p for p in self.people.values() if p.is_susceptible()]
        if len(susceptible) < n:
            n = len(susceptible)

        infected = random.sample(susceptible, n)
        for person in infected:
            person.state = DiseaseState.EXPOSED
        return infected
