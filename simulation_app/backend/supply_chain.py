"""
Three-tier supply chain resource management for the pandemic DES.

Tiers:
  1. CitySupply — per-city resource tracking (beds, PPE, diagnostics, MCMs)
  2. CountrySupplyManager — redistributes resources across cities within a country
  3. ContinentSupplyManager — deploys strategic reserves to countries in need

Resources are tracked as integer counters at daily step boundaries.
Beds are capacity-limited (occupied/released); all other resources are consumed.
Replenishment uses Gamma-distributed lead times via PendingShipment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from supply_config import ResourceDefaults
    from event_log import EventLog

# Resource names that are consumable (not capacity-based)
CONSUMABLE_RESOURCES = ("ppe", "swabs", "reagents", "vaccines", "pills")


@dataclass
class PendingShipment:
    """A shipment in transit with a scheduled arrival day."""
    resource: str
    amount: int
    arrival_day: int
    source: str  # "country" or "continent"


class CitySupply:
    """Tracks resource levels for a single city in the DES.

    Beds are capacity-based (occupied/released).
    All other resources are consumed on use.
    """

    def __init__(
        self,
        beds_total: int,
        ppe: int = 0,
        swabs: int = 0,
        reagents: int = 0,
        vaccines: int = 0,
        pills: int = 0,
        n_days: int = 0,
    ):
        self.beds_total = beds_total
        self.beds_occupied = 0
        self.ppe = ppe
        self.swabs = swabs
        self.reagents = reagents
        self.vaccines = vaccines
        self.pills = pills

        # Initial stock levels (for threshold calculations)
        self._initial_ppe = ppe
        self._initial_swabs = swabs
        self._initial_reagents = reagents
        self._initial_vaccines = vaccines
        self._initial_pills = pills

        self._pending: list[PendingShipment] = []

        # Daily consumption tracking for burn-rate EMA
        self._daily_consumed: dict[str, int] = {r: 0 for r in CONSUMABLE_RESOURCES}
        self._burn_rate_ema: dict[str, float] = {r: 0.0 for r in CONSUMABLE_RESOURCES}

        # History arrays for visualization (allocated by simulation.py)
        self.n_days = n_days
        self.history_beds_occupied: list[int] = []
        self.history_beds_total: list[int] = []
        self.history_ppe: list[int] = []
        self.history_swabs: list[int] = []
        self.history_reagents: list[int] = []
        self.history_vaccines: list[int] = []
        self.history_pills: list[int] = []

    # -- Bed management --------------------------------------------------------

    def try_admit(self) -> bool:
        """Try to admit a patient to a bed. Returns True if bed available."""
        if self.beds_occupied < self.beds_total:
            self.beds_occupied += 1
            return True
        return False

    def release_bed(self) -> None:
        """Release a bed when patient exits care (R or D)."""
        self.beds_occupied = max(0, self.beds_occupied - 1)

    # -- Consumable resources --------------------------------------------------

    def try_consume(self, resource: str, amount: int = 1) -> bool:
        """Try to consume a resource. Returns True if sufficient stock."""
        current = getattr(self, resource)
        if current >= amount:
            setattr(self, resource, current - amount)
            self._daily_consumed[resource] += amount
            return True
        return False

    def add_resource(self, resource: str, amount: int) -> None:
        """Add resources (from shipment or redistribution)."""
        current = getattr(self, resource)
        setattr(self, resource, current + amount)

    # -- Shipments -------------------------------------------------------------

    def add_shipment(self, shipment: PendingShipment) -> None:
        """Queue a pending shipment."""
        self._pending.append(shipment)

    def receive_shipments(self, current_day: int) -> int:
        """Process arrived shipments. Returns total units received."""
        received = 0
        still_pending = []
        for s in self._pending:
            if s.arrival_day <= current_day:
                self.add_resource(s.resource, s.amount)
                received += s.amount
            else:
                still_pending.append(s)
        self._pending = still_pending
        return received

    # -- Daily recording -------------------------------------------------------

    def record_day(self) -> None:
        """Record current resource levels to history."""
        self.history_beds_occupied.append(self.beds_occupied)
        self.history_beds_total.append(self.beds_total)
        self.history_ppe.append(self.ppe)
        self.history_swabs.append(self.swabs)
        self.history_reagents.append(self.reagents)
        self.history_vaccines.append(self.vaccines)
        self.history_pills.append(self.pills)

    def reset_daily_consumption(self) -> None:
        """Reset daily consumption counters and update burn-rate EMA."""
        alpha = 2.0 / 8.0  # 7-day EMA
        for r in CONSUMABLE_RESOURCES:
            consumed = self._daily_consumed[r]
            self._burn_rate_ema[r] = alpha * consumed + (1 - alpha) * self._burn_rate_ema[r]
            self._daily_consumed[r] = 0

    def get_deficit_ratio(self, resource: str) -> float:
        """Get current stock as fraction of initial stock (0 if no initial)."""
        initial = getattr(self, f"_initial_{resource}", 0)
        if initial <= 0:
            return 1.0  # no initial stock, no deficit
        return getattr(self, resource) / initial


class CountrySupplyManager:
    """Manages resource redistribution across cities within a country.

    Each day:
    1. Update burn-rate EMAs for all cities
    2. Redistribute from surplus cities to deficit cities
    3. Order from external suppliers if total country stock is low
    """

    def __init__(
        self,
        city_supplies: dict[str, CitySupply],
        defaults: ResourceDefaults,
        rng: np.random.RandomState,
    ):
        self.cities = city_supplies
        self.defaults = defaults
        self._rng = rng
        self._orders_placed: dict[str, int] = {}  # track pending order counts

    def update_and_redistribute(self, day: int, elog: EventLog | None = None) -> None:
        """Run daily update: burn rates, redistribution, reorders."""
        # Update burn-rate EMAs
        for cs in self.cities.values():
            cs.reset_daily_consumption()

        # Redistribute consumables (including pills and vaccines)
        for resource in ("ppe", "swabs", "reagents", "pills", "vaccines"):
            self._redistribute_resource(resource, day, elog)

    def _redistribute_resource(self, resource: str, day: int, elog: EventLog | None = None) -> None:
        """Redistribute a single resource from surplus to deficit cities."""
        threshold = self.defaults.country_reorder_threshold

        surplus_cities: list[tuple[str, CitySupply, float]] = []
        deficit_cities: list[tuple[str, CitySupply, float]] = []

        surplus_thresh = self.defaults.surplus_threshold
        for name, cs in self.cities.items():
            ratio = cs.get_deficit_ratio(resource)
            if ratio > surplus_thresh:
                surplus_cities.append((name, cs, ratio))
            elif ratio < threshold:
                deficit_cities.append((name, cs, ratio))

        if not deficit_cities:
            return

        # Sort: worst deficit first
        deficit_cities.sort(key=lambda x: x[2])
        # Sort surplus: most surplus first
        surplus_cities.sort(key=lambda x: -x[2])

        for d_name, d_cs, d_ratio in deficit_cities:
            initial = getattr(d_cs, f"_initial_{resource}", 0)
            if initial <= 0:
                continue
            # Target: bring deficit city up to threshold
            target = int(initial * threshold)
            current = getattr(d_cs, resource)
            needed = target - current
            if needed <= 0:
                continue

            for s_name, s_cs, s_ratio in surplus_cities:
                s_initial = getattr(s_cs, f"_initial_{resource}", 0)
                s_current = getattr(s_cs, resource)
                # Only donate down to donation floor fraction of initial
                donatable = s_current - int(s_initial * self.defaults.donation_floor)
                if donatable <= 0:
                    continue
                transfer = min(needed, donatable)
                s_cs.add_resource(resource, -transfer)
                d_cs.add_resource(resource, transfer)
                if elog is not None and transfer > 0:
                    elog.log(day, d_name, "redistribution", "transfer",
                             resource=resource, quantity=transfer,
                             reason="deficit_below_threshold",
                             from_city=s_name)
                needed -= transfer
                if needed <= 0:
                    break

        # Check if country-wide stock is below threshold — order externally
        total_current = sum(getattr(cs, resource) for cs in self.cities.values())
        total_initial = sum(getattr(cs, f"_initial_{resource}", 0) for cs in self.cities.values())
        if total_initial > 0 and total_current / total_initial < threshold:
            order_amount = int(total_initial * self.defaults.country_order_fraction)
            if order_amount > 0:
                lead_time = max(1, int(self._rng.gamma(
                    self.defaults.lead_time_shape,
                    self.defaults.lead_time_mean_days / self.defaults.lead_time_shape,
                )))
                # Distribute order across deficit cities proportionally
                deficit_names = [name for name, cs, _ in deficit_cities]
                if not deficit_names:
                    deficit_names = list(self.cities.keys())
                per_city = max(1, order_amount // len(deficit_names))
                for name in deficit_names:
                    self.cities[name].add_shipment(PendingShipment(
                        resource=resource,
                        amount=per_city,
                        arrival_day=day + lead_time,
                        source="country",
                    ))


class ContinentSupplyManager:
    """Continental-level strategic reserve deployment.

    Holds reserve stockpiles of vaccines, pills, PPE.
    Deploys to countries that fall below critical thresholds.
    Runs weekly (every 7 days).
    """

    def __init__(
        self,
        country_managers: dict[str, CountrySupplyManager],
        reserves: dict[str, int],
        defaults: ResourceDefaults,
        rng: np.random.RandomState,
    ):
        self.countries = country_managers
        self.reserves = dict(reserves)  # mutable copy
        self.defaults = defaults
        self._rng = rng
        # Track cumulative deployments
        self.total_deployed: dict[str, int] = {r: 0 for r in reserves}

    def deploy_reserves(self, day: int, elog: EventLog | None = None) -> None:
        """Deploy reserves to countries below critical threshold."""
        threshold = self.defaults.continent_deploy_threshold

        for resource in ("ppe", "swabs", "reagents", "vaccines", "pills"):
            available = self.reserves.get(resource, 0)
            if available <= 0:
                continue

            # Find countries with severe deficits
            country_deficits: list[tuple[str, float, int]] = []
            for country_name, mgr in self.countries.items():
                total_current = sum(
                    getattr(cs, resource) for cs in mgr.cities.values()
                )
                total_initial = sum(
                    getattr(cs, f"_initial_{resource}", 0) for cs in mgr.cities.values()
                )
                if total_initial > 0:
                    ratio = total_current / total_initial
                    if ratio < threshold:
                        country_deficits.append((country_name, ratio, total_initial))

            if not country_deficits:
                continue

            # Sort by severity (worst first)
            country_deficits.sort(key=lambda x: x[1])

            # Deploy proportional to deficit severity
            total_deficit = sum(
                int(init * (threshold - ratio))
                for _, ratio, init in country_deficits
            )
            if total_deficit <= 0:
                continue

            deploy_total = min(available, total_deficit)
            for country_name, ratio, init in country_deficits:
                country_need = int(init * (threshold - ratio))
                if country_need <= 0:
                    continue
                share = int(deploy_total * country_need / total_deficit)
                if share <= 0:
                    continue

                lead_time = max(1, int(self._rng.gamma(
                    self.defaults.lead_time_shape,
                    self.defaults.continent_lead_time_mean / self.defaults.lead_time_shape,
                )))

                mgr = self.countries[country_name]
                # Distribute to cities in that country
                n_cities = len(mgr.cities)
                if n_cities == 0:
                    continue
                per_city = max(1, share // n_cities)
                for city_name, cs in mgr.cities.items():
                    cs.add_shipment(PendingShipment(
                        resource=resource,
                        amount=per_city,
                        arrival_day=day + lead_time,
                        source="continent",
                    ))

                self.reserves[resource] -= share
                self.total_deployed[resource] = self.total_deployed.get(resource, 0) + share
                if elog is not None:
                    elog.log(day, country_name, "deployment", "deploy",
                             resource=resource, quantity=share,
                             reason="below_continent_threshold",
                             deficit_ratio=round(ratio, 3),
                             lead_time=lead_time)
                if self.reserves[resource] <= 0:
                    self.reserves[resource] = 0
                    break

