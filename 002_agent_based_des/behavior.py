"""
Behavior Strategies for Agent-Based DES.

Defines the BehaviorStrategy protocol and Level 0 implementations.
These strategies modify disease transmission and care-seeking decisions
without changing the underlying DES event engine.

Protocol:
    is_isolating() -> bool
        True if the person reduces/eliminates transmission this tick.

    seeks_care() -> Optional[bool]
        True  = actively seeks hospitalization
        False = avoids care (recovers at home regardless of severity)
        None  = defer to default disease model logic (no behavioral override)
"""

import random
from typing import Optional, Protocol


class BehaviorStrategy(Protocol):
    """Protocol for person-level behavioral decisions."""

    def is_isolating(self) -> bool:
        """Whether this person is currently isolating (skips transmission)."""
        ...

    def seeks_care(self) -> Optional[bool]:
        """
        Whether this person seeks medical care.

        Returns:
            True  - person seeks care (enters hospitalization path)
            False - person avoids care (direct recovery)
            None  - use default disease model probability
        """
        ...


class NullBehavior:
    """
    Level 0 null behavior — no behavioral modification.

    Produces bit-for-bit identical results to the vanilla DES because
    it makes no random draws and always defers to default logic.

    Use this to validate that IntelligentDiseaseModel with NullBehavior
    exactly reproduces the original DiseaseModel.
    """

    def is_isolating(self) -> bool:
        return False

    def seeks_care(self) -> Optional[bool]:
        return None


class StatisticalBehavior:
    """
    Level 0 statistical behavior — probabilistic isolation and care-seeking.

    Each decision is an independent coin flip with fixed probability.
    No memory, no adaptation, no context awareness.

    Note: Unlike NullBehavior, this consumes random numbers even when
    probabilities are 0.0. This means StatisticalBehavior(0.0, 0.0)
    will NOT produce identical results to vanilla DES due to random
    state desynchronization. Use NullBehavior for exact equivalence.
    """

    def __init__(
        self,
        isolation_prob: float = 0.0,
        care_seeking_prob: float = 0.0,
    ):
        if not (0.0 <= isolation_prob <= 1.0):
            raise ValueError(f"isolation_prob must be in [0, 1], got {isolation_prob}")
        if not (0.0 <= care_seeking_prob <= 1.0):
            raise ValueError(f"care_seeking_prob must be in [0, 1], got {care_seeking_prob}")

        self.isolation_prob = isolation_prob
        self.care_seeking_prob = care_seeking_prob

    def is_isolating(self) -> bool:
        return random.random() < self.isolation_prob

    def seeks_care(self) -> Optional[bool]:
        if self.care_seeking_prob <= 0.0:
            return None  # Defer to default — no random draw
        return random.random() < self.care_seeking_prob

    def __repr__(self) -> str:
        return (
            f"StatisticalBehavior("
            f"isolation={self.isolation_prob:.2f}, "
            f"care={self.care_seeking_prob:.2f})"
        )
