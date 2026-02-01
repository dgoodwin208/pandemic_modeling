"""
Centralized configuration for the ABS-DES pandemic simulation.

Consolidates magic numbers, formulas, and data loading that were
previously scattered across simulation.py and city_des_extended.py.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

_DATA_DIR = Path(__file__).parent / "data"


# -- Formulas ------------------------------------------------------------------

def score_to_receptivity(medical_services_score: float) -> float:
    """Convert medical_services_score (0-100) to receptivity (0.2-0.8).

    Higher medical scores mean the population is more receptive to
    provider advice (e.g., better health literacy, trust in institutions).
    """
    return 0.2 + 0.6 * (medical_services_score / 100.0)


def score_to_care_quality(medical_services_score: float) -> float:
    """Convert medical_services_score (0-100) to care quality multiplier (0.7-1.0).

    Multiplied against care_survival_prob: cities with higher medical scores
    have better outcomes for patients receiving care.
    """
    return 0.7 + 0.3 * (medical_services_score / 100.0)


# -- Constants -----------------------------------------------------------------

BIOATTACK_SEED_CITIES = ["Cairo", "Lagos", "Nairobi", "Kinshasa", "Johannesburg"]


# -- Disease parameters --------------------------------------------------------

@dataclass
class DiseaseParams:
    """Per-scenario disease parameters loaded from disease_params.csv."""
    scenario: str
    R0: float
    incubation_days: float
    infectious_days: float
    severe_fraction: float        # P(I_minor -> I_needs_care)
    care_survival_prob: float     # P(I_receiving_care -> R), modulated by care_quality
    ifr: float                    # Infection fatality rate (reference)
    gamma_shape: float            # Gamma distribution shape (6.25 -> CV=0.4)
    base_daily_death_prob: float  # Daily death prob for I_needs_care on day 1
    death_prob_increase_per_day: float  # Additive increase per day untreated


def load_household_sizes() -> dict[str, float]:
    """Load household_size.csv into a dict: country name -> household size."""
    path = _DATA_DIR / "household_size.csv"
    sizes: dict[str, float] = {}
    with open(path, newline="", encoding="utf-8") as f:
        # Skip comment lines starting with #
        lines = [line for line in f if not line.startswith("#")]
    import io
    reader = csv.DictReader(io.StringIO("".join(lines)))
    for row in reader:
        sizes[row["country"]] = float(row["household_size"])
    return sizes


def household_size_to_avg_contacts(household_size: float) -> int:
    """Convert household size to avg_contacts for the Watts-Strogatz network.

    Total daily close contacts ≈ 2× household size (household members +
    similar number of out-of-household contacts). Clamped to [4, 20] and
    rounded to nearest even integer (WS requirement: k must be even).
    """
    raw = household_size * 2.0
    clamped = max(4.0, min(20.0, raw))
    # Round to nearest even integer (Watts-Strogatz k must be even)
    return int(round(clamped / 2.0) * 2)


def load_disease_params() -> dict[str, DiseaseParams]:
    """Load disease_params.csv into a dict keyed by scenario name."""
    path = _DATA_DIR / "disease_params.csv"
    params: dict[str, DiseaseParams] = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dp = DiseaseParams(
                scenario=row["scenario"],
                R0=float(row["R0"]),
                incubation_days=float(row["incubation_days"]),
                infectious_days=float(row["infectious_days"]),
                severe_fraction=float(row["severe_fraction"]),
                care_survival_prob=float(row["care_survival_prob"]),
                ifr=float(row["ifr"]),
                gamma_shape=float(row["gamma_shape"]),
                base_daily_death_prob=float(row["base_daily_death_prob"]),
                death_prob_increase_per_day=float(row["death_prob_increase_per_day"]),
            )
            params[dp.scenario] = dp
    return params
