"""
Supply Chain Models for Pandemic Simulation.

Models three types of supplies:
- PPE (configurable sources with different production rates)
- Testing Reagents (configurable sources)
- Healthcare Workers (resource pool)
"""

from dataclasses import dataclass
from typing import Generator, Optional

from des_core import Environment, Inventory, Resource
from config import SupplyChainConfig


@dataclass
class SupplySource:
    """A source that produces supplies at a given rate."""
    name: str
    production_rate: float  # units per day
    inventory: Inventory
    batch_size: int = 10


def producer_process(
    env: Environment,
    source: SupplySource,
) -> Generator:
    """
    Generic production process.

    Produces batch_size units at intervals based on production_rate.
    """
    interval = source.batch_size / source.production_rate  # days between batches

    while True:
        yield env.timeout(interval)
        source.inventory.add(source.batch_size, source=source.name)


class SupplyChain:
    """
    Central supply chain manager for pandemic response.

    Tracks all inventories and healthcare worker availability.
    """

    def __init__(self, env: Environment, config: Optional[SupplyChainConfig] = None):
        self.env = env
        self.config = config or SupplyChainConfig()

        # PPE inventory (shared across all sources)
        self.ppe = Inventory(env, "PPE", initial=self.config.initial_ppe)

        # Testing reagents inventory
        self.reagents = Inventory(env, "Testing Reagents", initial=self.config.initial_reagents)

        # Healthcare workers as a resource pool
        self.healthcare_workers = Resource(env, capacity=self.config.healthcare_workers)

        # Track sources for reporting
        self.ppe_sources: list[SupplySource] = []
        self.reagent_sources: list[SupplySource] = []

    def add_ppe_source(self, name: str, production_rate: float) -> SupplySource:
        source = SupplySource(
            name=name,
            production_rate=production_rate,
            inventory=self.ppe,
            batch_size=self.config.ppe_batch_size,
        )
        self.ppe_sources.append(source)
        self.env.process(producer_process(self.env, source))
        return source

    def add_reagent_source(self, name: str, production_rate: float) -> SupplySource:
        source = SupplySource(
            name=name,
            production_rate=production_rate,
            inventory=self.reagents,
            batch_size=self.config.reagent_batch_size,
        )
        self.reagent_sources.append(source)
        self.env.process(producer_process(self.env, source))
        return source

    def use_ppe(self, quantity: int, consumer: str) -> bool:
        """Consume PPE for patient care. Returns True if available."""
        return self.ppe.consume(quantity, consumer)

    def use_reagent(self, quantity: int, consumer: str) -> bool:
        """Consume reagent for testing. Returns True if available."""
        return self.reagents.consume(quantity, consumer)

    def get_status(self) -> dict:
        return {
            "ppe_level": self.ppe.level,
            "reagent_level": self.reagents.level,
            "healthcare_workers_available": self.healthcare_workers.available,
            "healthcare_workers_busy": self.healthcare_workers.count,
            "healthcare_workers_total": self.healthcare_workers.capacity,
        }


def create_supply_chain(env: Environment, config: Optional[SupplyChainConfig] = None) -> SupplyChain:
    """
    Create supply chain from configuration.

    If no config provided, uses defaults:
    - 3 PPE sources (rates: 100, 50, 25 units/day)
    - 2 Reagent sources (rates: 200, 100 units/day)
    - 20 healthcare workers
    """
    config = config or SupplyChainConfig()
    chain = SupplyChain(env, config)

    for name, rate in config.ppe_sources:
        chain.add_ppe_source(name, rate)

    for name, rate in config.reagent_sources:
        chain.add_reagent_source(name, rate)

    return chain


# Backwards compatibility alias
create_default_supply_chain = create_supply_chain
