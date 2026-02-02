"""
Allocation strategy module for the pandemic simulation supply chain.

Provides a strategy pattern for resource allocation decisions, replacing
hardcoded thresholds with pluggable strategies:

  - RuleBasedStrategy: reproduces the existing hardcoded logic exactly
  - AIOptimizedStrategy: epidemic-aware allocation using growth rates,
    network centrality, and burn-rate projections

Phase 2a of the supply chain optimisation plan.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONSUMABLE_RESOURCES = ("ppe", "swabs", "reagents", "pills", "vaccines")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(arr: np.ndarray) -> np.ndarray:
    """Normalize an array to [0, 1] by dividing by its max.

    Returns zeros if the array is all-zero (avoids division by zero).
    """
    mx = np.max(arr)
    if mx == 0:
        return np.zeros_like(arr, dtype=float)
    return arr / mx


# ---------------------------------------------------------------------------
# Snapshot & decision dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EpidemicSnapshot:
    """Read-only view of the current simulation state, passed to strategies
    each day."""

    day: int
    n_cities: int
    city_names: list[str]

    # Per-city arrays (length n_cities)
    active_cases: np.ndarray            # current I (all sub-states)
    new_cases_today: np.ndarray         # daily new infections
    cumulative_cases: np.ndarray        # total ever infected = N - S
    deaths_today: np.ndarray            # D[today] - D[yesterday]
    susceptible_fraction: np.ndarray    # S / N per city
    beds_occupied: np.ndarray
    beds_total: np.ndarray
    populations: np.ndarray             # real city populations (for weighting)

    # Per-resource stock levels and burn rates
    stock_levels: dict[str, np.ndarray]     # resource_name -> per-city array
    initial_stock: dict[str, np.ndarray]    # resource_name -> per-city initial values
    burn_rates: dict[str, np.ndarray]       # resource_name -> per-city EMA burn rates

    # Aggregate trajectory (for trend detection)
    recent_active_trajectory: np.ndarray    # last 7 days of continent-wide total active I

    # Network centrality (pre-computed once from travel matrix)
    city_centrality: np.ndarray             # normalized eigenvector centrality scores


@dataclass
class VaccineAllocation:
    """Per-city vaccine dose allocation for today."""
    doses_per_city: np.ndarray  # length n_cities, how many doses each city gets


@dataclass
class RedistributionPlan:
    """Resource transfers within a country."""
    # Each tuple: (from_city_idx, to_city_idx, resource, amount)
    transfers: list[tuple[int, int, str, int]]


@dataclass
class DeploymentDecision:
    """Whether to deploy continental reserves and how."""
    deploy: bool
    # Per-resource allocation to countries: resource -> {country_name: amount}
    allocations: dict[str, dict[str, int]]


@dataclass
class ReorderDecision:
    """How much to order from external suppliers."""
    orders: dict[str, int]  # resource -> amount


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class AllocationStrategy(ABC):
    """Interface for pluggable allocation strategies."""

    @abstractmethod
    def allocate_vaccines(
        self,
        snapshot: EpidemicSnapshot,
        available_per_city: np.ndarray,
        max_daily_per_city: np.ndarray,
    ) -> VaccineAllocation:
        """Decide vaccine distribution across cities."""
        ...

    @abstractmethod
    def plan_redistribution(
        self,
        snapshot: EpidemicSnapshot,
        country_city_indices: list[int],
    ) -> RedistributionPlan:
        """Plan resource redistribution within a country."""
        ...

    @abstractmethod
    def should_deploy_reserves(
        self,
        snapshot: EpidemicSnapshot,
        reserves: dict[str, int],
    ) -> DeploymentDecision:
        """Decide whether to deploy continental reserves."""
        ...

    @abstractmethod
    def compute_reorder(
        self,
        snapshot: EpidemicSnapshot,
        resource: str,
        total_current: int,
        total_initial: int,
    ) -> ReorderDecision:
        """Decide reorder quantity."""
        ...


# ---------------------------------------------------------------------------
# Rule-based strategy (reproduces existing hardcoded behaviour)
# ---------------------------------------------------------------------------

class RuleBasedStrategy(AllocationStrategy):
    """Reproduces the exact behaviour of the original hardcoded supply chain
    logic.

    Thresholds (matching ``supply_config.ResourceDefaults``):
      - surplus_threshold: 0.6
      - donation_floor: 0.4
      - country_reorder_threshold: 0.3
      - country_order_fraction: 0.5
      - continent_deploy_threshold: 0.15
    """

    def __init__(
        self,
        surplus_threshold: float = 0.6,
        donation_floor: float = 0.4,
        reorder_threshold: float = 0.3,
        order_fraction: float = 0.5,
        deploy_threshold: float = 0.15,
    ) -> None:
        self.surplus_threshold = surplus_threshold
        self.donation_floor = donation_floor
        self.reorder_threshold = reorder_threshold
        self.order_fraction = order_fraction
        self.deploy_threshold = deploy_threshold

    # -- Vaccines (uniform, capped at max_daily) ----------------------------

    def allocate_vaccines(
        self,
        snapshot: EpidemicSnapshot,
        available_per_city: np.ndarray,
        max_daily_per_city: np.ndarray,
    ) -> VaccineAllocation:
        """Uniform distribution: each city gets min(available, max_daily)."""
        doses = np.minimum(available_per_city, max_daily_per_city).astype(int)
        return VaccineAllocation(doses_per_city=doses)

    # -- Redistribution (surplus -> deficit, threshold-based) ---------------

    def plan_redistribution(
        self,
        snapshot: EpidemicSnapshot,
        country_city_indices: list[int],
    ) -> RedistributionPlan:
        """Replicate CountrySupplyManager._redistribute_resource() for all
        consumable resources across the given city indices."""
        transfers: list[tuple[int, int, str, int]] = []

        for resource in CONSUMABLE_RESOURCES:
            stock = snapshot.stock_levels[resource]
            initial = snapshot.initial_stock[resource]

            # Compute stock-to-initial ratio per city
            init_vals = initial[country_city_indices]
            safe_init = np.where(init_vals > 0, init_vals, 1.0)
            ratios = np.where(
                init_vals > 0,
                stock[country_city_indices] / safe_init,
                1.0,
            )

            # Identify surplus and deficit cities (within this country)
            surplus_local: list[tuple[int, float]] = []   # (local_idx, ratio)
            deficit_local: list[tuple[int, float]] = []

            for local_idx, ratio in enumerate(ratios):
                if ratio > self.surplus_threshold:
                    surplus_local.append((local_idx, float(ratio)))
                elif ratio < self.reorder_threshold:
                    deficit_local.append((local_idx, float(ratio)))

            if not deficit_local:
                continue

            # Sort: worst deficit first, most surplus first
            deficit_local.sort(key=lambda x: x[1])
            surplus_local.sort(key=lambda x: -x[1])

            for d_local, d_ratio in deficit_local:
                d_global = country_city_indices[d_local]
                d_initial = initial[d_global]
                if d_initial <= 0:
                    continue
                target = int(d_initial * self.reorder_threshold)
                current = int(stock[d_global])
                needed = target - current
                if needed <= 0:
                    continue

                for s_local, s_ratio in surplus_local:
                    s_global = country_city_indices[s_local]
                    s_initial = initial[s_global]
                    s_current = int(stock[s_global])
                    donatable = s_current - int(s_initial * self.donation_floor)
                    if donatable <= 0:
                        continue
                    transfer = min(needed, donatable)
                    if transfer > 0:
                        transfers.append((s_global, d_global, resource, transfer))
                    needed -= transfer
                    if needed <= 0:
                        break

        return RedistributionPlan(transfers=transfers)

    # -- Continental deployment (weekly, proportional to deficit) ------------

    def should_deploy_reserves(
        self,
        snapshot: EpidemicSnapshot,
        reserves: dict[str, int],
    ) -> DeploymentDecision:
        """Deploy reserves to any resource where a country falls below the
        deploy threshold (15% of initial).

        Allocation is proportional to deficit severity, matching the original
        ContinentSupplyManager.deploy_reserves() logic.
        """
        allocations: dict[str, dict[str, int]] = {}
        should_deploy = False

        # We need to group cities by country.  The snapshot doesn't carry
        # country assignments directly, so the caller is expected to invoke
        # this once with the full snapshot and provide reserves.  The original
        # code iterates country managers; here we replicate the aggregate
        # logic at the strategy level.
        #
        # Because the strategy operates on the flat snapshot, the continent
        # manager that *calls* this method is responsible for iterating
        # countries.  We provide a simplified version that computes the
        # whole-continent decision: for each resource, find cities below
        # threshold and allocate proportionally.

        for resource in CONSUMABLE_RESOURCES:
            available = reserves.get(resource, 0)
            if available <= 0:
                continue

            stock = snapshot.stock_levels[resource]
            initial = snapshot.initial_stock[resource]
            total_initial = float(np.sum(initial))

            # "Push" resources (vaccines, pills): no initial city stock,
            # deploy based on epidemic pressure (active cases) when
            # epidemic is detected.
            if total_initial <= 0:
                # Only deploy push resources when there are active cases
                total_active = float(np.sum(snapshot.active_cases))
                if total_active <= 0:
                    continue
                # Allocate proportionally to active cases
                deploy_total = min(available, available // 7)  # deploy ~1/7 per week
                if deploy_total <= 0:
                    continue
                city_allocs: dict[str, int] = {}
                for i in range(snapshot.n_cities):
                    if snapshot.active_cases[i] <= 0:
                        continue
                    share = int(deploy_total * snapshot.active_cases[i] / total_active)
                    if share > 0:
                        city_allocs[snapshot.city_names[i]] = share
                if city_allocs:
                    allocations[resource] = city_allocs
                    should_deploy = True
                continue

            total_current = float(np.sum(stock))
            continent_ratio = total_current / total_initial
            if continent_ratio >= self.deploy_threshold:
                continue

            # Proportional allocation to cities below threshold
            safe_initial = np.where(initial > 0, initial, 1.0)
            ratios = np.where(initial > 0, stock / safe_initial, 1.0)
            deficit_mask = ratios < self.deploy_threshold
            if not np.any(deficit_mask):
                continue

            deficits = np.where(
                deficit_mask,
                initial * (self.deploy_threshold - ratios),
                0.0,
            ).astype(float)
            total_deficit = float(np.sum(deficits))
            if total_deficit <= 0:
                continue

            deploy_total = min(available, int(total_deficit))
            city_allocs2: dict[str, int] = {}
            for i in range(snapshot.n_cities):
                if deficits[i] <= 0:
                    continue
                share = int(deploy_total * deficits[i] / total_deficit)
                if share > 0:
                    city_allocs2[snapshot.city_names[i]] = share

            if city_allocs2:
                allocations[resource] = city_allocs2
                should_deploy = True

        return DeploymentDecision(deploy=should_deploy, allocations=allocations)

    # -- Reorder (30% threshold, order 50% of initial) ----------------------

    def compute_reorder(
        self,
        snapshot: EpidemicSnapshot,
        resource: str,
        total_current: int,
        total_initial: int,
    ) -> ReorderDecision:
        """Order when country stock < 30% of initial; order 50% of initial."""
        if total_initial <= 0:
            return ReorderDecision(orders={})

        ratio = total_current / total_initial
        if ratio < self.reorder_threshold:
            order_amount = int(total_initial * self.order_fraction)
            if order_amount > 0:
                return ReorderDecision(orders={resource: order_amount})

        return ReorderDecision(orders={})


# ---------------------------------------------------------------------------
# AI-optimised strategy (epidemic-aware allocation)
# ---------------------------------------------------------------------------

class AIOptimizedStrategy(AllocationStrategy):
    """Epidemic-aware allocation strategy that uses growth rates, network
    centrality, bed strain, and burn-rate projections to make smarter
    decisions than the fixed-threshold rule-based approach.

    Parameters
    ----------
    lead_time_days : float
        Expected supply lead time in days (used for reorder calculations).
    deploy_stock_days_threshold : float
        Deploy continental reserves when aggregate stock falls below this
        many days of supply.
    """

    # Vaccine priority weights
    W_TRANSMISSION = 0.30
    W_CENTRALITY = 0.25
    W_GROWTH = 0.25
    W_BED_STRAIN = 0.20

    # Redistribution thresholds (in days of stock)
    CRITICAL_DAYS = 7.0
    SURPLUS_DAYS = 21.0
    BUFFER_DAYS = 14.0

    def __init__(
        self,
        lead_time_days: float = 7.0,
        deploy_stock_days_threshold: float = 14.0,
    ) -> None:
        self.lead_time_days = lead_time_days
        self.deploy_stock_days_threshold = deploy_stock_days_threshold

    # -- Vaccines (priority-weighted allocation) ----------------------------

    def allocate_vaccines(
        self,
        snapshot: EpidemicSnapshot,
        available_per_city: np.ndarray,
        max_daily_per_city: np.ndarray,
    ) -> VaccineAllocation:
        """Allocate vaccines proportionally to a composite priority score.

        Priority = 0.30 * transmission_pressure
                 + 0.25 * centrality
                 + 0.25 * growth_rate
                 + 0.20 * bed_strain
        """
        n = snapshot.n_cities
        pop = snapshot.populations.astype(float)

        # Transmission pressure: (active / pop) * susceptible_fraction
        transmission_pressure = np.where(
            pop > 0,
            (snapshot.active_cases / pop) * snapshot.susceptible_fraction,
            0.0,
        )

        # Growth rate: new_cases / (cumulative / day + 1)
        safe_day = max(snapshot.day, 1)
        growth_rate = snapshot.new_cases_today / (
            snapshot.cumulative_cases / safe_day + 1.0
        )

        # Bed strain: occupied / (total + 1)
        bed_strain = snapshot.beds_occupied / (snapshot.beds_total + 1.0)

        # Composite priority score
        priority = (
            self.W_TRANSMISSION * _normalize(transmission_pressure)
            + self.W_CENTRALITY * _normalize(snapshot.city_centrality)
            + self.W_GROWTH * _normalize(np.clip(growth_rate, 0, None))
            + self.W_BED_STRAIN * _normalize(bed_strain)
        )

        total_priority = float(np.sum(priority))
        if total_priority <= 0:
            # Fallback to uniform when no signal
            doses = np.minimum(available_per_city, max_daily_per_city).astype(int)
            return VaccineAllocation(doses_per_city=doses)

        # Total available vaccines across all cities
        total_available = int(np.sum(available_per_city))

        # Allocate proportionally to priority, respecting per-city caps
        raw_alloc = (priority / total_priority) * total_available
        doses = np.minimum(raw_alloc, max_daily_per_city)
        doses = np.minimum(doses, available_per_city).astype(int)

        return VaccineAllocation(doses_per_city=doses)

    # -- Redistribution (burn-rate based, days-of-stock) --------------------

    def plan_redistribution(
        self,
        snapshot: EpidemicSnapshot,
        country_city_indices: list[int],
    ) -> RedistributionPlan:
        """Transfer resources from surplus cities (>21 days of stock) to
        critical cities (<7 days of stock), keeping a 14-day buffer for
        donors."""
        transfers: list[tuple[int, int, str, int]] = []

        for resource in CONSUMABLE_RESOURCES:
            stock = snapshot.stock_levels[resource]
            burn = snapshot.burn_rates[resource]

            # Compute days of stock for each city in this country
            idx = np.array(country_city_indices)
            city_stock = stock[idx].astype(float)
            city_burn = burn[idx].astype(float)

            # Days of stock (inf when burn rate is zero)
            safe_burn = np.where(city_burn > 0, city_burn, 1.0)
            days_of_stock = np.where(
                city_burn > 0,
                city_stock / safe_burn,
                np.inf,
            )

            # Critical cities: < 7 days
            critical_mask = days_of_stock < self.CRITICAL_DAYS
            # Surplus cities: > 21 days
            surplus_mask = days_of_stock > self.SURPLUS_DAYS

            if not np.any(critical_mask) or not np.any(surplus_mask):
                continue

            # Sort critical cities by urgency (fewest days first)
            critical_local = np.where(critical_mask)[0]
            critical_local = critical_local[np.argsort(days_of_stock[critical_local])]

            surplus_local = np.where(surplus_mask)[0]
            surplus_local = surplus_local[np.argsort(-days_of_stock[surplus_local])]

            # Track remaining donatable amounts
            donatable = np.zeros(len(idx), dtype=float)
            for s in surplus_local:
                # Keep 14 days of buffer
                keep = city_burn[s] * self.BUFFER_DAYS
                donatable[s] = max(0.0, city_stock[s] - keep)

            for c in critical_local:
                # Need enough to reach 7 days
                need = city_burn[c] * self.CRITICAL_DAYS - city_stock[c]
                if need <= 0:
                    continue
                for s in surplus_local:
                    if donatable[s] <= 0:
                        continue
                    transfer = int(min(need, donatable[s]))
                    if transfer > 0:
                        transfers.append((
                            int(idx[s]),    # from global index
                            int(idx[c]),    # to global index
                            resource,
                            transfer,
                        ))
                        donatable[s] -= transfer
                        need -= transfer
                    if need <= 0:
                        break

        return RedistributionPlan(transfers=transfers)

    # -- Continental deployment (acceleration or low stock days) -------------

    def should_deploy_reserves(
        self,
        snapshot: EpidemicSnapshot,
        reserves: dict[str, int],
    ) -> DeploymentDecision:
        """Deploy when epidemic is accelerating (positive 2nd derivative of
        active case trajectory) or when any resource has fewer than 14 days
        of aggregate stock remaining.

        Allocation is proportional to predicted need (burn_rate * lead_time),
        not current deficit.
        """
        # Check condition (a): epidemic acceleration
        traj = snapshot.recent_active_trajectory
        acceleration_detected = False
        if len(traj) >= 3:
            # 2nd derivative (discrete): traj[-1] - 2*traj[-2] + traj[-3]
            second_deriv = float(traj[-1] - 2.0 * traj[-2] + traj[-3])
            acceleration_detected = second_deriv > 0

        # Check condition (b): any resource with < 14 days aggregate stock
        low_stock_detected = False
        for resource in CONSUMABLE_RESOURCES:
            total_stock = float(np.sum(snapshot.stock_levels[resource]))
            total_burn = float(np.sum(snapshot.burn_rates[resource]))
            if total_burn > 0:
                agg_days = total_stock / total_burn
                if agg_days < self.deploy_stock_days_threshold:
                    low_stock_detected = True
                    break

        if not acceleration_detected and not low_stock_detected:
            return DeploymentDecision(deploy=False, allocations={})

        # Allocate proportionally to predicted need = burn_rate * lead_time
        # For "push" resources with no local burn rate (vaccines, pills),
        # use epidemic pressure (active cases) as proxy for need.
        allocations: dict[str, dict[str, int]] = {}
        for resource in CONSUMABLE_RESOURCES:
            available = reserves.get(resource, 0)
            if available <= 0:
                continue

            burn = snapshot.burn_rates[resource]
            predicted_need = burn * self.lead_time_days  # per-city

            total_need = float(np.sum(predicted_need))
            if total_need <= 0:
                # No burn rate → use active cases as proxy (push resources)
                total_active = float(np.sum(snapshot.active_cases))
                if total_active <= 0:
                    continue
                # Deploy 1/7 of available per week (called weekly)
                deploy_total = min(available, available // 4)
                if deploy_total <= 0:
                    continue
                city_allocs: dict[str, int] = {}
                for i in range(snapshot.n_cities):
                    if snapshot.active_cases[i] <= 0:
                        continue
                    share = int(deploy_total * snapshot.active_cases[i] / total_active)
                    if share > 0:
                        city_allocs[snapshot.city_names[i]] = share
                if city_allocs:
                    allocations[resource] = city_allocs
                continue

            deploy_total = min(available, int(total_need))
            city_allocs2: dict[str, int] = {}
            for i in range(snapshot.n_cities):
                if predicted_need[i] <= 0:
                    continue
                share = int(deploy_total * predicted_need[i] / total_need)
                if share > 0:
                    city_allocs2[snapshot.city_names[i]] = share

            if city_allocs2:
                allocations[resource] = city_allocs2

        should_deploy = bool(allocations)
        return DeploymentDecision(deploy=should_deploy, allocations=allocations)

    # -- Reorder (burn-rate projection with surge safety factor) -------------

    def compute_reorder(
        self,
        snapshot: EpidemicSnapshot,
        resource: str,
        total_current: int,
        total_initial: int,
    ) -> ReorderDecision:
        """Order = burn_rate * lead_time * safety_factor.

        safety_factor = 1.5 + max(0, growth_rate)
        Capped at 2x initial to prevent absurd orders.
        """
        if total_initial <= 0:
            return ReorderDecision(orders={})

        total_burn = float(np.sum(snapshot.burn_rates.get(resource, np.array([0.0]))))
        if total_burn <= 0:
            return ReorderDecision(orders={})

        # Continent-wide growth rate proxy
        traj = snapshot.recent_active_trajectory
        if len(traj) >= 2 and traj[-2] > 0:
            growth_rate = float((traj[-1] - traj[-2]) / traj[-2])
        else:
            growth_rate = 0.0

        safety_factor = 1.5 + max(0.0, growth_rate)

        order_amount = int(total_burn * self.lead_time_days * safety_factor)
        # Cap at 2x initial
        order_amount = min(order_amount, 2 * total_initial)

        if order_amount > 0:
            return ReorderDecision(orders={resource: order_amount})

        return ReorderDecision(orders={})
