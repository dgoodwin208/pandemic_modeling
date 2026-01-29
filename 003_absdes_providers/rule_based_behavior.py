"""
Level 1: Rule-Based Behavior for Agent-Based DES.

Extends BehaviorStrategy with provider-interaction capabilities.
Unlike StatisticalBehavior (Level 0, memoryless), RuleBasedBehavior has
internal state: once a provider successfully advises a person, their
isolation and care-seeking probabilities permanently increase.

Two new methods beyond the protocol:
    would_disclose() -> bool
        Whether this person reveals symptoms when asked by a provider.
    receive_advice() -> bool
        Whether this person accepts and follows provider guidance.
"""

import random
from typing import Optional


class RuleBasedBehavior:
    """
    Level 1 person behavior with provider responsiveness.

    Satisfies BehaviorStrategy protocol (is_isolating, seeks_care)
    and adds provider interaction methods (would_disclose, receive_advice).

    Parameters:
        disclosure_prob: P(reveal symptoms when asked by provider)
        receptivity: P(accept and follow provider advice)
        base_isolation_prob: isolation probability without advice
        advised_isolation_prob: isolation probability after accepting advice
        base_care_prob: care-seeking probability without advice
        advised_care_prob: care-seeking probability after accepting advice
    """

    def __init__(
        self,
        disclosure_prob: float = 0.5,
        receptivity: float = 0.6,
        base_isolation_prob: float = 0.05,
        advised_isolation_prob: float = 0.4,
        base_care_prob: float = 0.0,
        advised_care_prob: float = 0.5,
    ):
        if not (0.0 <= disclosure_prob <= 1.0):
            raise ValueError(f"disclosure_prob must be in [0, 1], got {disclosure_prob}")
        if not (0.0 <= receptivity <= 1.0):
            raise ValueError(f"receptivity must be in [0, 1], got {receptivity}")

        self.disclosure_prob = disclosure_prob
        self.receptivity = receptivity
        self.base_isolation_prob = base_isolation_prob
        self.advised_isolation_prob = advised_isolation_prob
        self.base_care_prob = base_care_prob
        self.advised_care_prob = advised_care_prob
        self._provider_advised = False

    # ── BehaviorStrategy protocol ─────────────────────────────────

    def is_isolating(self) -> bool:
        """Whether this person isolates this tick."""
        prob = self.advised_isolation_prob if self._provider_advised else self.base_isolation_prob
        return random.random() < prob

    def seeks_care(self) -> Optional[bool]:
        """Whether this person seeks medical care."""
        prob = self.advised_care_prob if self._provider_advised else self.base_care_prob
        if prob <= 0.0:
            return None  # Defer to default disease model logic
        return random.random() < prob

    # ── Provider interaction ──────────────────────────────────────

    def would_disclose(self) -> bool:
        """Whether this person reveals symptoms when screened by a provider."""
        return random.random() < self.disclosure_prob

    def receive_advice(self) -> bool:
        """
        Provider gives advice. Returns True if person accepts.

        Once accepted, the person's isolation and care-seeking
        probabilities permanently shift to their advised levels.
        """
        if random.random() < self.receptivity:
            self._provider_advised = True
            return True
        return False

    @property
    def is_advised(self) -> bool:
        """Whether this person has been successfully advised by a provider."""
        return self._provider_advised

    def __repr__(self) -> str:
        advised_str = " [advised]" if self._provider_advised else ""
        return (
            f"RuleBasedBehavior("
            f"disclosure={self.disclosure_prob:.2f}, "
            f"receptivity={self.receptivity:.2f}, "
            f"iso={self.base_isolation_prob:.2f}/{self.advised_isolation_prob:.2f}"
            f"){advised_str}"
        )
