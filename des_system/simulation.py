"""
Main Pandemic Simulation.

Ties together:
- DES engine (des_core)
- Supply chain (configurable PPE sources, reagent sources, healthcare workers)
- Social network (configurable population)
- Disease model (state machine + transmission)
"""

import random
from dataclasses import dataclass
from typing import Optional

from des_core import Environment
from supply_chain import create_supply_chain, SupplyChain
from social_network import SocialNetwork
from disease_model import DiseaseModel
from config import SimulationConfig, SupplyChainConfig, NetworkConfig, DiseaseConfig


@dataclass
class SimulationResult:
    """Results from a pandemic simulation run."""
    # Configuration used
    config: SimulationConfig

    # Totals
    total_infections: int
    total_hospitalizations: int
    total_deaths: int
    total_recoveries: int
    peak_active_cases: int
    peak_day: float

    # Final state
    final_susceptible: int
    final_recovered: int
    final_deceased: int

    # Rates
    infection_rate: float  # % of population infected
    hospitalization_rate: float  # % of infected hospitalized
    case_fatality_rate: float  # % of infected who died

    # Supply chain
    final_ppe_level: int
    final_reagent_level: int
    min_ppe_level: int
    min_reagent_level: int

    # Time series (sampled daily)
    daily_snapshots: list[dict]

    # Transmission chain
    transmission_events: list[dict]

    def summary(self) -> str:
        """Return human-readable summary."""
        return f"""
╔══════════════════════════════════════════════════════════════╗
║                     SIMULATION RESULTS                        ║
╠══════════════════════════════════════════════════════════════╣
║ EPIDEMIC OUTCOMES                                             ║
║   Total infected: {self.total_infections:>4} ({self.infection_rate:.1f}% of population)           ║
║   Peak active cases: {self.peak_active_cases:>4} (day {self.peak_day:.0f})                        ║
║   Hospitalizations: {self.total_hospitalizations:>4} ({self.hospitalization_rate:.1f}% of infected)          ║
║   Deaths: {self.total_deaths:>4} ({self.case_fatality_rate:.1f}% CFR)                              ║
║   Recoveries: {self.total_recoveries:>4}                                          ║
╠══════════════════════════════════════════════════════════════╣
║ FINAL STATE                                                   ║
║   Susceptible: {self.final_susceptible:>4}  │  Recovered: {self.final_recovered:>4}  │  Deceased: {self.final_deceased:>4}  ║
╠══════════════════════════════════════════════════════════════╣
║ SUPPLY CHAIN                                                  ║
║   Final PPE: {self.final_ppe_level:>6}  │  Min PPE: {self.min_ppe_level:>6}                   ║
║   Final Reagents: {self.final_reagent_level:>6}  │  Min Reagents: {self.min_reagent_level:>6}           ║
╚══════════════════════════════════════════════════════════════╝
"""


class PandemicSimulation:
    """
    Main simulation orchestrator.

    Usage:
        config = SimulationConfig()
        config.disease.transmission_prob = 0.25  # Modify as needed
        sim = PandemicSimulation(config)
        result = sim.run()
    """

    def __init__(self, config: Optional[SimulationConfig] = None):
        self.config = config or SimulationConfig()

        # Set random seed for reproducibility
        if self.config.random_seed is not None:
            random.seed(self.config.random_seed)

        # Initialize components
        self.env = Environment()
        self.supply_chain = create_supply_chain(self.env, self.config.supply_chain)
        self.network = SocialNetwork(self.config.network)
        self.disease = DiseaseModel(
            env=self.env,
            network=self.network,
            supply_chain=self.supply_chain,
            disease_config=self.config.disease,
            supply_config=self.config.supply_chain,
        )

        # Tracking
        self.daily_snapshots: list[dict] = []
        self.peak_active_cases = 0
        self.peak_day = 0.0
        self.min_ppe = self.config.supply_chain.initial_ppe
        self.min_reagents = self.config.supply_chain.initial_reagents

    def run(self) -> SimulationResult:
        """Run the simulation and return results."""
        # Seed initial infections
        self.disease.seed_infections(self.config.initial_infections)

        # Start daily monitoring process
        self.env.process(self._daily_monitor())

        # Run simulation
        self.env.run(until=self.config.duration_days)

        # Compile results
        return self._compile_results()

    def _daily_monitor(self):
        """Monitor and record statistics daily."""
        while True:
            yield self.env.timeout(self.config.snapshot_interval)

            stats = self.disease.get_statistics()
            self.daily_snapshots.append(stats)

            # Track peak
            if stats["active_cases"] > self.peak_active_cases:
                self.peak_active_cases = stats["active_cases"]
                self.peak_day = self.env.now

            # Track supply minimums
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


def run_simulation(config: Optional[SimulationConfig] = None) -> SimulationResult:
    """
    Convenience function to run a simulation.

    Args:
        config: Full simulation configuration (uses defaults if None)

    Returns:
        SimulationResult with all outcomes
    """
    sim = PandemicSimulation(config)
    return sim.run()


if __name__ == "__main__":
    from config import SimulationConfig

    # Create config and show it
    config = SimulationConfig(random_seed=42)
    print(config.summary())

    # Run simulation
    result = run_simulation(config)
    print(result.summary())

    print(f"\nTransmission chain ({len(result.transmission_events)} events):")
    print("First 5 transmissions:")
    for event in result.transmission_events[:5]:
        source = event["source_name"]
        print(f"  Day {event['time']:.1f}: {source} -> {event['target_name']} (age {event['target_age']})")
