"""
Structured event logging for simulation interpretability.

Captures every decision the simulation makes — resource allocation,
screening outcomes, supply chain transfers, travel coupling — so that
the simulation is auditable and queryable by AI agents.

Events are lightweight dataclass instances accumulated in an EventLog.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SimulationEvent:
    day: int
    city: str
    category: str   # shipment, screening, vaccination, travel, redistribution, deployment, admission, stockout
    action: str     # receive, consume, detect, inject, transfer, deploy, admit, deny
    resource: str = ""       # beds, ppe, swabs, reagents, vaccines, pills, or ""
    quantity: int = 0
    reason: str = ""         # capacity_full, deficit_critical, contact_traced, etc.
    metadata: dict[str, Any] = field(default_factory=dict)


class EventLog:
    """Accumulates SimulationEvents during a simulation run.

    Provides filtering and summary methods for interpretability.
    """

    def __init__(self) -> None:
        self._events: list[SimulationEvent] = []

    def log(
        self,
        day: int,
        city: str,
        category: str,
        action: str,
        resource: str = "",
        quantity: int = 0,
        reason: str = "",
        **metadata: Any,
    ) -> None:
        self._events.append(SimulationEvent(
            day=day,
            city=city,
            category=category,
            action=action,
            resource=resource,
            quantity=quantity,
            reason=reason,
            metadata=metadata,
        ))

    @property
    def events(self) -> list[SimulationEvent]:
        return self._events

    def events_on_day(
        self,
        day: int,
        city: str | None = None,
        category: str | None = None,
    ) -> list[SimulationEvent]:
        result = [e for e in self._events if e.day == day]
        if city is not None:
            result = [e for e in result if e.city == city]
        if category is not None:
            result = [e for e in result if e.category == category]
        return result

    def events_by_category(
        self,
        category: str,
        day_range: tuple[int, int] | None = None,
    ) -> list[SimulationEvent]:
        result = [e for e in self._events if e.category == category]
        if day_range is not None:
            lo, hi = day_range
            result = [e for e in result if lo <= e.day <= hi]
        return result

    def first_event(self, category: str, resource: str = "") -> SimulationEvent | None:
        for e in self._events:
            if e.category == category:
                if resource and e.resource != resource:
                    continue
                return e
        return None

    def summary(self) -> dict[str, Any]:
        if not self._events:
            return {"total_events": 0, "by_category": {}}

        by_cat: dict[str, int] = {}
        for e in self._events:
            by_cat[e.category] = by_cat.get(e.category, 0) + 1

        return {
            "total_events": len(self._events),
            "by_category": by_cat,
            "first_day": self._events[0].day,
            "last_day": self._events[-1].day,
        }

    def notable_events(self, max_events: int = 20) -> list[SimulationEvent]:
        """Return a curated list of notable/milestone events for display.

        Prioritizes: first stockouts, large transfers, capacity events.
        """
        notable: list[SimulationEvent] = []
        seen_firsts: set[str] = set()

        for e in self._events:
            key = f"{e.category}:{e.resource}:{e.city}"

            # First stockout per resource per city
            if e.category == "stockout" and key not in seen_firsts:
                notable.append(e)
                seen_firsts.add(key)

            # First admission denial per city
            elif e.category == "admission" and e.action == "deny" and key not in seen_firsts:
                notable.append(e)
                seen_firsts.add(key)

            # Continent deployments (rare, always notable)
            elif e.category == "deployment":
                notable.append(e)

            # Large redistributions
            elif e.category == "redistribution" and e.quantity >= 50:
                notable.append(e)

            if len(notable) >= max_events:
                break

        return notable

    def to_dicts(self) -> list[dict[str, Any]]:
        return [
            {
                "day": e.day,
                "city": e.city,
                "category": e.category,
                "action": e.action,
                "resource": e.resource,
                "quantity": e.quantity,
                "reason": e.reason,
                "metadata": e.metadata,
            }
            for e in self._events
        ]
