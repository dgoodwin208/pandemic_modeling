"""
Agent-Based Pandemic Simulation.

Thin wrapper around PandemicSimulation that swaps DiseaseModel for
IntelligentDiseaseModel. All other infrastructure (DES engine, network,
supply chain, monitoring) is inherited unchanged.

Usage:
    from agent_simulation import run_agent_simulation
    from behavior import NullBehavior, StatisticalBehavior

    config = SimulationConfig(...)

    # Exact equivalence to vanilla DES:
    result = run_agent_simulation(config, behavior_factory=lambda pid: NullBehavior())

    # With 30% isolation probability:
    result = run_agent_simulation(
        config,
        behavior_factory=lambda pid: StatisticalBehavior(isolation_prob=0.3),
    )
"""

import random
import sys
from pathlib import Path
from typing import Callable, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "des_system"))

from des_core import Environment
from supply_chain import create_supply_chain
from social_network import SocialNetwork
from config import SimulationConfig
from simulation import SimulationResult

from behavior import BehaviorStrategy, NullBehavior
from intelligent_disease_model import IntelligentDiseaseModel


BehaviorFactory = Callable[[int], BehaviorStrategy]
"""Factory that takes person_id and returns a BehaviorStrategy."""


class AgentSimulation:
    """
    Agent-based pandemic simulation.

    Identical to PandemicSimulation except:
    - Uses IntelligentDiseaseModel instead of DiseaseModel
    - Assigns a BehaviorStrategy to each person via a factory function

    All monitoring, result compilation, and event scheduling are inherited
    from the same infrastructure.
    """

    def __init__(
        self,
        config: SimulationConfig,
        behavior_factory: Optional[BehaviorFactory] = None,
    ):
        self.config = config

        # Set random seed for reproducibility
        if config.random_seed is not None:
            random.seed(config.random_seed)

        # Initialize components (same as PandemicSimulation)
        self.env = Environment()
        self.supply_chain = create_supply_chain(self.env, config.supply_chain)
        self.network = SocialNetwork(config.network)

        # Build behavior map
        factory = behavior_factory or (lambda pid: NullBehavior())
        behaviors = {
            pid: factory(pid)
            for pid in self.network.people
        }

        # Use IntelligentDiseaseModel instead of DiseaseModel
        self.disease = IntelligentDiseaseModel(
            env=self.env,
            network=self.network,
            supply_chain=self.supply_chain,
            behaviors=behaviors,
            disease_config=config.disease,
            supply_config=config.supply_chain,
        )

        # Tracking (same as PandemicSimulation)
        self.daily_snapshots: list[dict] = []
        self.peak_active_cases = 0
        self.peak_day = 0.0
        self.min_ppe = config.supply_chain.initial_ppe
        self.min_reagents = config.supply_chain.initial_reagents

    def run(self) -> SimulationResult:
        """Run the simulation and return results."""
        self.disease.seed_infections(self.config.initial_infections)
        self.env.process(self._daily_monitor())
        self.env.run(until=self.config.duration_days)
        return self._compile_results()

    def _daily_monitor(self):
        """Monitor and record statistics daily."""
        while True:
            yield self.env.timeout(self.config.snapshot_interval)
            stats = self.disease.get_statistics()
            self.daily_snapshots.append(stats)

            if stats["active_cases"] > self.peak_active_cases:
                self.peak_active_cases = stats["active_cases"]
                self.peak_day = self.env.now

            if stats["supply_chain"]["ppe_level"] < self.min_ppe:
                self.min_ppe = stats["supply_chain"]["ppe_level"]
            if stats["supply_chain"]["reagent_level"] < self.min_reagents:
                self.min_reagents = stats["supply_chain"]["reagent_level"]

    def _compile_results(self) -> SimulationResult:
        """Compile final results from simulation."""
        final_stats = self.disease.get_statistics()
        state_counts = final_stats["state_counts"]

        total_infected = self.disease.total_infections
        total_hosp = self.disease.total_hospitalizations
        total_deaths = self.disease.total_deaths

        return SimulationResult(
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


def run_agent_simulation(
    config: SimulationConfig,
    behavior_factory: Optional[BehaviorFactory] = None,
) -> SimulationResult:
    """
    Convenience function to run an agent-based simulation.

    Args:
        config: Full simulation configuration.
        behavior_factory: Callable(person_id) -> BehaviorStrategy.
            Defaults to NullBehavior for all persons.

    Returns:
        SimulationResult with all outcomes.
    """
    sim = AgentSimulation(config, behavior_factory)
    return sim.run()
