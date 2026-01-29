"""
Level 0: Statistical Provider Strategy.

Each provider screens a fixed number of people per day.
No memory, no adaptation, no prioritization — pure random sampling.

Two actions per screened person:
1. Detection: if person is contagious AND discloses → report to HealthcareSystem
2. Advice: attempt to advise → if person is receptive, their behavior shifts
"""

import random

from healthcare_system import HealthcareSystem
from rule_based_behavior import RuleBasedBehavior


class StatisticalProvider:
    """
    Level 0 statistical provider.

    Screens a random sample of the population each day.
    Detection requires the person to be contagious AND willing to disclose.
    Advice is given to everyone screened; acceptance depends on person's receptivity.
    """

    def __init__(self, screening_capacity: int = 20):
        """
        Args:
            screening_capacity: Number of people this provider screens per day.
        """
        self.screening_capacity = screening_capacity

    def screen_daily(
        self,
        people: dict,
        behaviors: dict,
        healthcare_system: HealthcareSystem,
        current_time: float,
    ) -> dict:
        """
        Screen a random sample of the population.

        Args:
            people: dict[int, Person] — the social network's people.
            behaviors: dict[int, RuleBasedBehavior] — behavior map.
            healthcare_system: HealthcareSystem to report detections to.
            current_time: Current simulation time (day).

        Returns:
            Stats dict: {screened, detected, advice_given, advice_accepted}
        """
        all_ids = list(people.keys())
        sample_size = min(self.screening_capacity, len(all_ids))
        sample_ids = random.sample(all_ids, sample_size)

        detected = 0
        advice_accepted = 0

        for pid in sample_ids:
            person = people[pid]
            behavior = behaviors.get(pid)
            if behavior is None:
                continue

            # Detection: sick person who discloses
            if person.is_contagious() and behavior.would_disclose():
                new = healthcare_system.detect_case(pid, current_time)
                if new:
                    detected += 1

            # Advice: provider advises, person may or may not accept
            if behavior.receive_advice():
                advice_accepted += 1

        return {
            "screened": sample_size,
            "detected": detected,
            "advice_given": sample_size,
            "advice_accepted": advice_accepted,
        }
