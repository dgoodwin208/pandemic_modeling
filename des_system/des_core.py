"""
Minimal Discrete Event Simulation Engine.

Extracted and simplified from GeoForce DES backend.
Supports:
- Event scheduling with priority queue
- Generator-based processes
- Resources with blocking requests
"""

from __future__ import annotations

import heapq
from collections import deque
from dataclasses import dataclass, field
from typing import Generator, Any, Optional

Process = Generator[Any, Any, Any]


# =============================================================================
# Core Events
# =============================================================================

@dataclass(order=True)
class Event:
    """A scheduled event in the simulation."""
    time: float
    sequence: int = field(compare=True)
    process: Process = field(compare=False)
    value: Any = field(compare=False, default=None)


class Timeout:
    """A timeout event - process resumes after delay."""
    def __init__(self, env: Environment, delay: float):
        self.env = env
        self.delay = delay
        self._value = None

    def __iter__(self):
        return self

    def __next__(self):
        raise StopIteration(self._value)


class ResourceRequest:
    """A request for a resource."""
    def __init__(self, resource: Resource):
        self.resource = resource
        self.granted = False
        self._process: Optional[Process] = None


# =============================================================================
# Environment (Scheduler)
# =============================================================================

class Environment:
    """
    Discrete event simulation environment.

    Manages simulation clock and event scheduling.
    Processes are Python generators that yield events.
    """

    def __init__(self, initial_time: float = 0.0):
        self.now = initial_time
        self._queue: list[Event] = []
        self._sequence = 0
        self._active_process: Optional[Process] = None

    def timeout(self, delay: float) -> Timeout:
        """Create a timeout event - process resumes after delay."""
        if delay < 0:
            raise ValueError(f"Timeout delay must be >= 0, got {delay}")
        return Timeout(self, delay)

    def process(self, generator: Process) -> None:
        """Register a generator as a simulation process."""
        self._schedule(generator, self.now)

    def _schedule(self, process: Process, time: float, value: Any = None) -> None:
        """Schedule a process to resume at a given time."""
        self._sequence += 1
        heapq.heappush(self._queue, Event(time, self._sequence, process, value))

    def run(self, until: Optional[float] = None) -> None:
        """
        Run simulation until specified time or queue exhaustion.

        Args:
            until: Stop time (None = run until no more events)
        """
        until = until if until is not None else float('inf')

        while self._queue:
            if self._queue[0].time > until:
                self.now = until
                break

            event = heapq.heappop(self._queue)
            self.now = event.time
            self._active_process = event.process

            try:
                yielded = event.process.send(event.value)

                if isinstance(yielded, Timeout):
                    self._schedule(event.process, self.now + yielded.delay)
                elif isinstance(yielded, ResourceRequest):
                    yielded._process = event.process
                    yielded.resource._enqueue_request(yielded)
                else:
                    raise TypeError(f"Process yielded unknown type: {type(yielded)}")

            except StopIteration:
                pass

            self._active_process = None

    def peek(self) -> float:
        """Return time of next scheduled event, or inf if none."""
        return self._queue[0].time if self._queue else float('inf')


# =============================================================================
# Resource (Basic Pool)
# =============================================================================

class Resource:
    """
    A limited-capacity resource pool.

    Processes request resources and block until available.
    """

    def __init__(self, env: Environment, capacity: int = 1):
        self.env = env
        self.capacity = capacity
        self._count = 0
        self._waiters: deque[ResourceRequest] = deque()

    @property
    def count(self) -> int:
        """Number of resources currently in use."""
        return self._count

    @property
    def available(self) -> int:
        """Number of resources currently available."""
        return self.capacity - self._count

    def request(self) -> ResourceRequest:
        """Request a resource (yield this to wait for availability)."""
        return ResourceRequest(self)

    def _enqueue_request(self, request: ResourceRequest) -> None:
        """Internal: handle a resource request."""
        if self._count < self.capacity:
            self._count += 1
            request.granted = True
            self.env._schedule(request._process, self.env.now, request)
        else:
            self._waiters.append(request)

    def release(self, request: ResourceRequest) -> None:
        """Release a resource back to the pool."""
        if not request.granted:
            raise ValueError("Cannot release a request that was never granted")

        self._count -= 1
        request.granted = False

        if self._waiters:
            next_request = self._waiters.popleft()
            self._count += 1
            next_request.granted = True
            self.env._schedule(next_request._process, self.env.now, next_request)


# =============================================================================
# Inventory (Non-blocking tracking)
# =============================================================================

@dataclass
class InventoryRecord:
    """Record of inventory allocation."""
    name: str
    quantity: int
    allocated_at: float


class Inventory:
    """
    Non-blocking inventory for tracking supply levels.

    Unlike Resource, this doesn't block processes.
    It's for accounting - tracking production and consumption.
    """

    def __init__(self, env: Environment, name: str, initial: int = 0):
        self.env = env
        self.name = name
        self._level = initial
        self._history: list[dict] = []

    @property
    def level(self) -> int:
        """Current inventory level."""
        return self._level

    def add(self, quantity: int, source: str = "") -> None:
        """Add inventory (production)."""
        self._level += quantity
        self._history.append({
            "time": self.env.now,
            "action": "add",
            "quantity": quantity,
            "source": source,
            "level": self._level,
        })

    def consume(self, quantity: int, consumer: str = "") -> bool:
        """
        Consume inventory if available.

        Returns True if successful, False if insufficient.
        """
        if self._level >= quantity:
            self._level -= quantity
            self._history.append({
                "time": self.env.now,
                "action": "consume",
                "quantity": quantity,
                "consumer": consumer,
                "level": self._level,
            })
            return True
        return False

    def get_history(self) -> list[dict]:
        """Get inventory transaction history."""
        return self._history.copy()
