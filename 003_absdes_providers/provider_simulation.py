"""
Provider Simulation — Agent-Based DES with Healthcare Providers.

Extends the AgentSimulation pattern by adding:
- A pool of StatisticalProvider objects that screen the population daily
- A HealthcareSystem that tracks detected vs true active cases
- A parallel DES process (_provider_screening_process) for daily screening

Usage:
    from provider_simulation import run_provider_simulation
    from rule_based_behavior import RuleBasedBehavior

    config = SimulationConfig(...)
    result = run_provider_simulation(
        config,
        n_providers=25,
        screening_capacity=20,
        behavior_factory=lambda pid: RuleBasedBehavior(),
    )
"""

import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "des_system"))
sys.path.insert(0, str(_PROJECT_ROOT / "agent_based_des"))

from des_core import Environment
from supply_chain import create_supply_chain
from social_network import SocialNetwork, DiseaseState
from config import SimulationConfig
from simulation import SimulationResult
from intelligent_disease_model import IntelligentDiseaseModel

from rule_based_behavior import RuleBasedBehavior
from provider import StatisticalProvider
from healthcare_system import HealthcareSystem


BehaviorFactory = Callable[[int], RuleBasedBehavior]


@dataclass
class ProviderResult:
    """Results from a provider simulation run."""
    sim_result: SimulationResult
    n_providers: int
    screening_capacity: int
    surveillance: list[dict]  # daily_surveillance from HealthcareSystem
    total_advice_given: int = 0
    total_advice_accepted: int = 0
    total_screened: int = 0
    total_detected: int = 0


class ProviderSimulation:
    """
    Agent-based pandemic simulation with healthcare providers.

    Identical to AgentSimulation except:
    - Creates a pool of StatisticalProvider objects
    - Runs a daily provider screening process as a parallel DES generator
    - Tracks surveillance accuracy via HealthcareSystem
    """

    def __init__(
        self,
        config: SimulationConfig,
        n_providers: int = 0,
        screening_capacity: int = 20,
        behavior_factory: Optional[BehaviorFactory] = None,
    ):
        self.config = config

        if config.random_seed is not None:
            random.seed(config.random_seed)

        self.env = Environment()
        self.supply_chain = create_supply_chain(self.env, config.supply_chain)
        self.network = SocialNetwork(config.network)

        factory = behavior_factory or (lambda pid: RuleBasedBehavior())
        self.behaviors: dict[int, RuleBasedBehavior] = {
            pid: factory(pid)
            for pid in self.network.people
        }

        self.disease = IntelligentDiseaseModel(
            env=self.env,
            network=self.network,
            supply_chain=self.supply_chain,
            behaviors=self.behaviors,
            disease_config=config.disease,
            supply_config=config.supply_chain,
        )

        self.providers = [
            StatisticalProvider(screening_capacity=screening_capacity)
            for _ in range(n_providers)
        ]
        self.n_providers = n_providers
        self.screening_capacity = screening_capacity
        self.healthcare_system = HealthcareSystem(config.network.n_people)

        self.daily_snapshots: list[dict] = []
        self.peak_active_cases = 0
        self.peak_day = 0.0
        self.min_ppe = config.supply_chain.initial_ppe
        self.min_reagents = config.supply_chain.initial_reagents

        self._total_screened = 0
        self._total_detected = 0
        self._total_advice_given = 0
        self._total_advice_accepted = 0

    def run(self) -> ProviderResult:
        self.disease.seed_infections(self.config.initial_infections)
        self.env.process(self._daily_monitor())
        if self.providers:
            self.env.process(self._provider_screening_process())
        self.env.run(until=self.config.duration_days)
        return self._compile_results()

    def _provider_screening_process(self):
        while True:
            yield self.env.timeout(1.0)

            for provider in self.providers:
                stats = provider.screen_daily(
                    people=self.network.people,
                    behaviors=self.behaviors,
                    healthcare_system=self.healthcare_system,
                    current_time=self.env.now,
                )
                self._total_screened += stats["screened"]
                self._total_detected += stats["detected"]
                self._total_advice_given += stats["advice_given"]
                self._total_advice_accepted += stats["advice_accepted"]

    def _daily_monitor(self):
        while True:
            yield self.env.timeout(self.config.snapshot_interval)
            stats = self.disease.get_statistics()
            self.daily_snapshots.append(stats)

            contagious_ids = {
                pid for pid, p in self.network.people.items()
                if p.is_contagious()
            }
            true_active = len(contagious_ids)
            self.healthcare_system.record_daily(
                time=self.env.now,
                true_active_count=true_active,
                contagious_ids=contagious_ids,
            )

            if stats["active_cases"] > self.peak_active_cases:
                self.peak_active_cases = stats["active_cases"]
                self.peak_day = self.env.now

            if stats["supply_chain"]["ppe_level"] < self.min_ppe:
                self.min_ppe = stats["supply_chain"]["ppe_level"]
            if stats["supply_chain"]["reagent_level"] < self.min_reagents:
                self.min_reagents = stats["supply_chain"]["reagent_level"]

    def _compile_results(self) -> ProviderResult:
        final_stats = self.disease.get_statistics()
        state_counts = final_stats["state_counts"]

        total_infected = self.disease.total_infections
        total_hosp = self.disease.total_hospitalizations
        total_deaths = self.disease.total_deaths

        sim_result = SimulationResult(
            config=self.config,
            total_infections=total_infected,
            total_hospitalizations=total_hosp,
            total_deaths=total_deaths,
            total_recoveries=self.disease.total_recoveries,
            peak_active_cases=self.peak_active_cases,
            peak_day=self.peak_day,
            final_susceptible=state_counts.get("susceptible", 0),
            final_recovered=state_counts.get("recovered", 0),
            final_deceased=state_counts.get("deceased", 0),
            infection_rate=total_infected / self.config.network.n_people * 100,
            hospitalization_rate=(
                total_hosp / total_infected * 100 if total_infected > 0 else 0
            ),
            case_fatality_rate=(
                total_deaths / total_infected * 100 if total_infected > 0 else 0
            ),
            final_ppe_level=final_stats["supply_chain"]["ppe_level"],
            final_reagent_level=final_stats["supply_chain"]["reagent_level"],
            min_ppe_level=self.min_ppe,
            min_reagent_level=self.min_reagents,
            daily_snapshots=self.daily_snapshots,
            transmission_events=self.disease.transmission_events,
        )

        return ProviderResult(
            sim_result=sim_result,
            n_providers=self.n_providers,
            screening_capacity=self.screening_capacity,
            surveillance=self.healthcare_system.daily_surveillance,
            total_screened=self._total_screened,
            total_detected=self._total_detected,
            total_advice_given=self._total_advice_given,
            total_advice_accepted=self._total_advice_accepted,
        )


def run_provider_simulation(
    config: SimulationConfig,
    n_providers: int = 0,
    screening_capacity: int = 20,
    behavior_factory: Optional[BehaviorFactory] = None,
) -> ProviderResult:
    """
    Convenience function to run a provider simulation.

    Args:
        config: Full simulation configuration.
        n_providers: Number of providers (0 = no providers).
        screening_capacity: People screened per provider per day.
        behavior_factory: Callable(person_id) -> RuleBasedBehavior.
    """
    sim = ProviderSimulation(
        config, n_providers, screening_capacity, behavior_factory,
    )
    return sim.run()
