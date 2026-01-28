"""
Comprehensive Configuration for Pandemic Simulation.

All magic numbers factored into dataclasses for easy exploration and modification.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SupplyChainConfig:
    """Configuration for supply chain parameters."""

    # Units for each field (for display purposes)
    UNITS: dict = field(default_factory=lambda: {
        "initial_ppe": "units",
        "initial_reagents": "units",
        "healthcare_workers": "people",
        "ppe_batch_size": "units/batch",
        "reagent_batch_size": "units/batch",
        "ppe_sources": "units/day",
        "reagent_sources": "units/day",
        "ppe_per_patient": "units/patient/day",
        "reagents_per_patient": "units/patient/day",
    }, repr=False)

    # Initial inventory levels
    initial_ppe: int = 100
    initial_reagents: int = 200

    # Healthcare workforce
    healthcare_workers: int = 20

    # Production batch sizes
    ppe_batch_size: int = 10
    reagent_batch_size: int = 50

    # PPE sources (name, production_rate in units/day)
    ppe_sources: list[tuple[str, float]] = field(default_factory=lambda: [
        ("PPE Factory Alpha", 100.0),
        ("PPE Factory Beta", 50.0),
        ("PPE Import Source", 25.0),
    ])

    # Reagent sources (name, production_rate in units/day)
    reagent_sources: list[tuple[str, float]] = field(default_factory=lambda: [
        ("Reagent Lab Primary", 200.0),
        ("Reagent Lab Secondary", 100.0),
    ])

    # Resource consumption per hospitalized patient
    ppe_per_patient: int = 5
    reagents_per_patient: int = 2

    def get_unit(self, field_name: str) -> str:
        """Get the unit for a field, or empty string if not defined."""
        return self.UNITS.get(field_name, "")

    @property
    def total_ppe_production_rate(self) -> float:
        """Total PPE units produced per day."""
        return sum(rate for _, rate in self.ppe_sources)

    @property
    def total_reagent_production_rate(self) -> float:
        """Total reagent units produced per day."""
        return sum(rate for _, rate in self.reagent_sources)


@dataclass
class NetworkConfig:
    """Configuration for social network topology."""

    # Units for each field (for display purposes)
    UNITS: dict = field(default_factory=lambda: {
        "n_people": "people",
        "min_age": "years",
        "max_age": "years",
        "avg_contacts": "contacts/person",
        "rewire_prob": "probability",
    }, repr=False)

    # Population
    n_people: int = 100
    min_age: int = 18
    max_age: int = 80

    # Watts-Strogatz small-world parameters
    avg_contacts: int = 6      # k: each node connected to k nearest neighbors
    rewire_prob: float = 0.3   # p: probability of rewiring each edge

    def get_unit(self, field_name: str) -> str:
        """Get the unit for a field, or empty string if not defined."""
        return self.UNITS.get(field_name, "")


@dataclass
class DiseaseConfig:
    """Configuration for disease dynamics."""

    # Units for each field (for display purposes)
    UNITS: dict = field(default_factory=lambda: {
        "transmission_prob": "probability",
        "daily_contact_rate": "fraction/day",
        "exposure_period": "days",
        "infectious_period": "days",
        "symptomatic_period": "days",
        "hospital_stay": "days",
        "exposure_cv": "CV",
        "infectious_cv": "CV",
        "symptomatic_cv": "CV",
        "hospital_cv": "CV",
        "min_exposure": "days",
        "min_infectious": "days",
        "min_symptomatic": "days",
        "min_hospital": "days",
        "hospitalization_prob": "probability",
        "mortality_prob": "probability",
        "age_risk_threshold": "years",
        "age_risk_multiplier": "multiplier",
    }, repr=False)

    # Transmission
    transmission_prob: float = 0.15   # Per-contact transmission probability
    daily_contact_rate: float = 0.5   # Fraction of contacts interacted with daily

    # State durations (days) - means
    exposure_period: float = 3.0      # Days in EXPOSED before INFECTIOUS
    infectious_period: float = 2.0    # Days INFECTIOUS before SYMPTOMATIC
    symptomatic_period: float = 7.0   # Days SYMPTOMATIC before outcome
    hospital_stay: float = 7.0        # Days in hospital

    # Duration variability (coefficient of variation)
    exposure_cv: float = 0.2          # 20% std dev
    infectious_cv: float = 0.2
    symptomatic_cv: float = 0.3
    hospital_cv: float = 0.29         # std=2.0 for mean=7.0

    # Minimum durations (days)
    min_exposure: float = 1.0
    min_infectious: float = 0.5
    min_symptomatic: float = 2.0
    min_hospital: float = 3.0

    # Outcome probabilities
    hospitalization_prob: float = 0.15   # Base probability of hospitalization
    mortality_prob: float = 0.02         # Base probability of death (if hospitalized)

    # Age-based risk factors
    age_risk_threshold: int = 60         # Age above which risk increases
    age_risk_multiplier: float = 2.0     # Risk multiplier for elderly

    def get_unit(self, field_name: str) -> str:
        """Get the unit for a field, or empty string if not defined."""
        return self.UNITS.get(field_name, "")


@dataclass
class SimulationConfig:
    """Master configuration combining all subsystems."""

    # Units for each field (for display purposes)
    UNITS: dict = field(default_factory=lambda: {
        "initial_infections": "people",
        "duration_days": "days",
        "random_seed": "",
        "snapshot_interval": "days",
    }, repr=False)

    # Subsystem configs
    supply_chain: SupplyChainConfig = field(default_factory=SupplyChainConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    disease: DiseaseConfig = field(default_factory=DiseaseConfig)

    # Simulation parameters
    initial_infections: int = 3
    duration_days: float = 90.0
    random_seed: Optional[int] = None

    # Monitoring
    snapshot_interval: float = 1.0   # Days between status snapshots

    def get_unit(self, field_name: str) -> str:
        """Get the unit for a field, or empty string if not defined."""
        return self.UNITS.get(field_name, "")

    def summary(self) -> str:
        """Return a human-readable summary of the configuration."""
        return f"""
╔══════════════════════════════════════════════════════════════╗
║                    SIMULATION CONFIGURATION                   ║
╠══════════════════════════════════════════════════════════════╣
║ POPULATION                                                    ║
║   People: {self.network.n_people:>4}  │  Age range: {self.network.min_age}-{self.network.max_age}                  ║
║   Avg contacts: {self.network.avg_contacts}  │  Rewire prob: {self.network.rewire_prob:.1%}                ║
╠══════════════════════════════════════════════════════════════╣
║ DISEASE PARAMETERS                                            ║
║   Transmission prob: {self.disease.transmission_prob:.1%}                                 ║
║   Exposure period: {self.disease.exposure_period:.1f} days                                ║
║   Infectious period: {self.disease.infectious_period:.1f} days                              ║
║   Symptomatic period: {self.disease.symptomatic_period:.1f} days                             ║
║   Hospitalization: {self.disease.hospitalization_prob:.1%}  │  Mortality: {self.disease.mortality_prob:.1%}         ║
║   Age risk threshold: {self.disease.age_risk_threshold}  │  Multiplier: {self.disease.age_risk_multiplier:.1f}x          ║
╠══════════════════════════════════════════════════════════════╣
║ SUPPLY CHAIN                                                  ║
║   Healthcare workers: {self.supply_chain.healthcare_workers}                                  ║
║   Initial PPE: {self.supply_chain.initial_ppe}  │  Production: {self.supply_chain.total_ppe_production_rate:.0f}/day          ║
║   Initial reagents: {self.supply_chain.initial_reagents}  │  Production: {self.supply_chain.total_reagent_production_rate:.0f}/day        ║
║   PPE/patient: {self.supply_chain.ppe_per_patient}  │  Reagents/patient: {self.supply_chain.reagents_per_patient}             ║
╠══════════════════════════════════════════════════════════════╣
║ SIMULATION                                                    ║
║   Duration: {self.duration_days:.0f} days  │  Seed infections: {self.initial_infections}                ║
║   Random seed: {str(self.random_seed) if self.random_seed else 'None':>10}                                    ║
╚══════════════════════════════════════════════════════════════╝
"""


# Preset configurations for different scenarios
def high_transmission_config() -> SimulationConfig:
    """Configuration for high transmission scenario (like measles)."""
    config = SimulationConfig()
    config.disease.transmission_prob = 0.35
    config.disease.exposure_period = 2.0
    return config


def low_resources_config() -> SimulationConfig:
    """Configuration for resource-constrained scenario."""
    config = SimulationConfig()
    config.supply_chain.initial_ppe = 50
    config.supply_chain.initial_reagents = 100
    config.supply_chain.healthcare_workers = 10
    config.supply_chain.ppe_sources = [
        ("PPE Factory Alpha", 50.0),
    ]
    return config


def elderly_population_config() -> SimulationConfig:
    """Configuration for population with more elderly (higher risk)."""
    config = SimulationConfig()
    config.network.min_age = 50
    config.network.max_age = 90
    config.disease.age_risk_threshold = 65
    return config


def dense_network_config() -> SimulationConfig:
    """Configuration for highly connected population."""
    config = SimulationConfig()
    config.network.avg_contacts = 12
    config.disease.daily_contact_rate = 0.7
    return config
