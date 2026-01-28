"""
Pandemic Supply Chain Simulation using Discrete Event Simulation.

A DES-based model for simulating disease spread through a social network
with supply chain constraints (PPE, testing reagents, healthcare workers).

Components:
- des_core: Core DES primitives (Environment, Resource, Timeout)
- config: All configurable parameters (no magic numbers!)
- supply_chain: PPE, reagent, and healthcare worker modeling
- social_network: Watts-Strogatz small-world network
- disease_model: SEIR-like state machine with probabilistic transmission
- simulation: Main orchestrator tying everything together

Usage:
    from simulation import run_simulation
    from config import SimulationConfig

    # Use defaults
    result = run_simulation()
    print(result.summary())

    # Or customize
    config = SimulationConfig(random_seed=42)
    config.disease.transmission_prob = 0.25
    config.supply_chain.healthcare_workers = 30
    result = run_simulation(config)
"""

from .config import (
    SimulationConfig,
    SupplyChainConfig,
    NetworkConfig,
    DiseaseConfig,
    high_transmission_config,
    low_resources_config,
    elderly_population_config,
    dense_network_config,
)
from .simulation import PandemicSimulation, SimulationResult, run_simulation
from .des_core import Environment, Resource, Inventory
from .supply_chain import SupplyChain, create_supply_chain
from .social_network import SocialNetwork, Person, DiseaseState
from .disease_model import DiseaseModel

__all__ = [
    # Config
    "SimulationConfig",
    "SupplyChainConfig",
    "NetworkConfig",
    "DiseaseConfig",
    "high_transmission_config",
    "low_resources_config",
    "elderly_population_config",
    "dense_network_config",
    # Simulation
    "PandemicSimulation",
    "SimulationResult",
    "run_simulation",
    # DES Core
    "Environment",
    "Resource",
    "Inventory",
    # Supply Chain
    "SupplyChain",
    "create_supply_chain",
    # Network
    "SocialNetwork",
    "Person",
    "DiseaseState",
    # Disease
    "DiseaseModel",
]
