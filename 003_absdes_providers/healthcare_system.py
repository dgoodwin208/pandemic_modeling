"""
Healthcare System — Surveillance Tracker.

Passive tracking class that records detected cases and computes
surveillance accuracy by comparing detected vs true active cases.

Not a DES entity — updated by providers, queried by monitoring.
"""

from typing import Optional


class HealthcareSystem:
    """
    Tracks detected cases and surveillance accuracy over time.

    Providers call detect_case() when they find a sick person.
    The daily monitor calls record_daily() to snapshot surveillance state.
    """

    def __init__(self, population_size: int):
        self.population_size = population_size
        self.detected_ids: set[int] = set()
        self.detection_times: dict[int, float] = {}  # person_id → first detection time
        self.daily_surveillance: list[dict] = []

    def detect_case(self, person_id: int, time: float) -> bool:
        """
        Record that person_id has been detected as sick.

        Returns True if this is a new detection, False if already known.
        """
        if person_id in self.detected_ids:
            return False
        self.detected_ids.add(person_id)
        self.detection_times[person_id] = time
        return True

    def record_daily(
        self,
        time: float,
        true_active_count: int,
        contagious_ids: set[int],
    ) -> dict:
        """
        Record daily surveillance snapshot.

        Args:
            time: Current simulation time (day).
            true_active_count: Actual number of active (contagious) cases.
            contagious_ids: Set of person IDs currently contagious.

        Returns:
            The snapshot dict (also appended to daily_surveillance).
        """
        detected_active = len(self.detected_ids & contagious_ids)

        snapshot = {
            "day": time,
            "true_active": true_active_count,
            "detected_active": detected_active,
            "total_detected_ever": len(self.detected_ids),
            "estimation_error": abs(detected_active - true_active_count) / self.population_size,
        }
        self.daily_surveillance.append(snapshot)
        return snapshot

    def get_summary(self, total_infections: int) -> dict:
        """
        Compute summary surveillance statistics.

        Args:
            total_infections: Total cumulative infections in the simulation.
        """
        cumulative_rate = (
            len(self.detected_ids) / total_infections * 100
            if total_infections > 0 else 0.0
        )

        errors = [s["estimation_error"] for s in self.daily_surveillance]
        mean_error = sum(errors) / len(errors) if errors else 0.0

        return {
            "total_detected": len(self.detected_ids),
            "total_infections": total_infections,
            "cumulative_detection_rate": cumulative_rate,
            "mean_estimation_error": mean_error,
        }
