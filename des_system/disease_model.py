"""
Disease Model with Finite State Machine and Transmission.

Models disease progression through states:
SUSCEPTIBLE -> EXPOSED -> INFECTIOUS -> SYMPTOMATIC -> RECOVERED/HOSPITALIZED/DECEASED

Transmission occurs probabilistically through social contacts.
"""

import random
from typing import Generator, Optional

from des_core import Environment
from social_network import SocialNetwork, Person, DiseaseState
from supply_chain import SupplyChain
from config import DiseaseConfig, SupplyChainConfig


class DiseaseModel:
    """
    Manages disease progression and transmission.

    Each infected person is a DES process that:
    1. Progresses through disease states
    2. Attempts transmission to contacts
    3. Consumes healthcare resources when hospitalized
    """

    def __init__(
        self,
        env: Environment,
        network: SocialNetwork,
        supply_chain: SupplyChain,
        disease_config: Optional[DiseaseConfig] = None,
        supply_config: Optional[SupplyChainConfig] = None,
    ):
        self.env = env
        self.network = network
        self.supply_chain = supply_chain
        self.config = disease_config or DiseaseConfig()
        self.supply_config = supply_config or SupplyChainConfig()

        # Tracking
        self.transmission_events: list[dict] = []
        self.total_infections = 0
        self.total_hospitalizations = 0
        self.total_deaths = 0
        self.total_recoveries = 0

    def infect_person(self, person: Person, source: Optional[Person] = None) -> None:
        if person.state != DiseaseState.SUSCEPTIBLE:
            return

        person.state = DiseaseState.EXPOSED
        person.infected_at = self.env.now
        self.total_infections += 1

        # Record transmission event
        self.transmission_events.append({
            "time": self.env.now,
            "target_id": person.id,
            "target_name": person.name,
            "target_age": person.age,
            "source_id": source.id if source else None,
            "source_name": source.name if source else "initial_seed",
        })

        # Start disease progression process
        self.env.process(self._disease_progression(person))

    def _sample_duration(self, mean: float, cv: float, minimum: float) -> float:
        """Sample a duration from gaussian with given coefficient of variation."""
        std = mean * cv
        duration = random.gauss(mean, std)
        return max(minimum, duration)

    def _disease_progression(self, person: Person) -> Generator:
        """
        Disease progression state machine.

        EXPOSED -> INFECTIOUS -> SYMPTOMATIC -> outcome
        """
        # EXPOSED phase
        exposure_duration = self._sample_duration(
            self.config.exposure_period,
            self.config.exposure_cv,
            self.config.min_exposure,
        )
        yield self.env.timeout(exposure_duration)

        person.state = DiseaseState.INFECTIOUS

        # INFECTIOUS phase (pre-symptomatic, can spread)
        # Start transmission attempts
        self.env.process(self._transmission_process(person))

        infectious_duration = self._sample_duration(
            self.config.infectious_period,
            self.config.infectious_cv,
            self.config.min_infectious,
        )
        yield self.env.timeout(infectious_duration)

        person.state = DiseaseState.SYMPTOMATIC

        # SYMPTOMATIC phase
        symptomatic_duration = self._sample_duration(
            self.config.symptomatic_period,
            self.config.symptomatic_cv,
            self.config.min_symptomatic,
        )
        yield self.env.timeout(symptomatic_duration)

        # Determine outcome
        yield from self._determine_outcome(person)

    def _transmission_process(self, person: Person) -> Generator:
        """
        Attempt to spread disease to contacts while contagious.

        Contacts are split between network neighbors and random agents
        (mass-action mixing) controlled by config.p_random. This ensures
        epidemic dynamics are independent of population size N.

        Contacts are selected from ALL agents (not pre-filtered to
        susceptible), matching the ODE's implicit S/N factor — contacts
        with already-infected agents are "wasted", as in real life.
        """
        all_people = list(self.network.people.values())
        n_population = len(all_people)

        while person.is_contagious():
            # Wait one day between transmission attempts
            yield self.env.timeout(1.0)

            if not person.is_contagious():
                break

            # Total interactions for the day (based on full contact list size)
            all_contacts = self.network.get_contacts(person.id)
            n_interactions = max(
                1,
                int(len(all_contacts) * self.config.daily_contact_rate)
            )

            # Select contacts: mix of network neighbors and random agents
            p_random = self.config.p_random
            for _ in range(n_interactions):
                if p_random > 0 and random.random() < p_random:
                    # Random mass-action contact: pick ANY agent in population
                    contact = all_people[random.randrange(n_population)]
                    if contact.id == person.id:
                        continue
                else:
                    # Network neighbor contact: pick ANY neighbor (not just susceptible)
                    if not all_contacts:
                        continue
                    contact = random.choice(all_contacts)

                # Only transmit if target is susceptible
                if contact.is_susceptible():
                    if random.random() < self.config.transmission_prob:
                        self.infect_person(contact, source=person)

    def _determine_outcome(self, person: Person) -> Generator:
        # Calculate hospitalization probability (age-adjusted)
        hosp_prob = self.config.hospitalization_prob
        if person.age >= self.config.age_risk_threshold:
            hosp_prob *= self.config.age_risk_multiplier

        if random.random() < hosp_prob:
            # Hospitalization
            person.state = DiseaseState.HOSPITALIZED
            person.hospitalized_at = self.env.now
            self.total_hospitalizations += 1

            # Try to get healthcare worker
            req = self.supply_chain.healthcare_workers.request()
            yield req

            # Consume supplies
            self.supply_chain.use_ppe(
                self.supply_config.ppe_per_patient,
                consumer=f"patient_{person.id}"
            )
            self.supply_chain.use_reagent(
                self.supply_config.reagents_per_patient,
                consumer=f"patient_{person.id}"
            )

            # Hospital stay
            hospital_duration = self._sample_duration(
                self.config.hospital_stay,
                self.config.hospital_cv,
                self.config.min_hospital,
            )
            yield self.env.timeout(hospital_duration)

            # Release healthcare worker
            self.supply_chain.healthcare_workers.release(req)

            # Mortality check (age-adjusted)
            mort_prob = self.config.mortality_prob
            if person.age >= self.config.age_risk_threshold:
                mort_prob *= self.config.age_risk_multiplier

            if random.random() < mort_prob:
                person.state = DiseaseState.DECEASED
                person.deceased_at = self.env.now
                self.total_deaths += 1
            else:
                person.state = DiseaseState.RECOVERED
                person.recovered_at = self.env.now
                self.total_recoveries += 1
        else:
            # Direct recovery
            person.state = DiseaseState.RECOVERED
            person.recovered_at = self.env.now
            self.total_recoveries += 1

    def seed_infections(self, n: int = 3) -> list[Person]:
        infected = self.network.infect_random(n)
        for person in infected:
            person.state = DiseaseState.SUSCEPTIBLE  # Reset for proper infection
            self.infect_person(person, source=None)
        return infected

    def get_statistics(self) -> dict:
        network_stats = self.network.get_statistics()
        supply_stats = self.supply_chain.get_status()

        return {
            "time": self.env.now,
            "total_infections": self.total_infections,
            "total_hospitalizations": self.total_hospitalizations,
            "total_deaths": self.total_deaths,
            "total_recoveries": self.total_recoveries,
            "state_counts": network_stats["state_counts"],
            "supply_chain": supply_stats,
            "active_cases": (
                network_stats["state_counts"].get("exposed", 0) +
                network_stats["state_counts"].get("infectious", 0) +
                network_stats["state_counts"].get("symptomatic", 0) +
                network_stats["state_counts"].get("hospitalized", 0)
            ),
        }


# Backwards compatibility
DiseaseParameters = DiseaseConfig
