"""
City State — Data model and CSV loading for multi-city simulation.

Each city is an SEIR compartment (S, E, I, R) with geographic metadata.
Loads city data from the project's african_cities.csv.
"""

import csv
from dataclasses import dataclass
from pathlib import Path


# Default path to city data
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = _PROJECT_ROOT / "backend" / "data" / "african_cities.csv"


@dataclass
class CityState:
    """SEIR compartment state for one city."""

    name: str
    country: str
    latitude: float
    longitude: float
    population: int
    medical_services_score: float  # 0-100, from african_cities.csv
    S: float  # susceptible
    E: float  # exposed
    I: float  # infected (infectious)
    R: float  # recovered

    @property
    def N(self) -> float:
        """Total population (should be conserved)."""
        return self.S + self.E + self.I + self.R

    @property
    def infection_fraction(self) -> float:
        """Fraction of population currently infectious."""
        return self.I / self.N if self.N > 0 else 0.0


def load_cities(
    city_names: list[str],
    csv_path: Path = DEFAULT_CSV,
) -> list[CityState]:
    """
    Load selected cities from african_cities.csv.

    Initializes all compartments: S = population, E = I = R = 0.

    Args:
        city_names: List of city names to load (case-sensitive match).
        csv_path: Path to the CSV file.

    Returns:
        List of CityState objects in the same order as city_names.

    Raises:
        ValueError: If any requested city is not found in the CSV.
    """
    city_data: dict[str, dict] = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            city_data[row["city"]] = row

    cities = []
    missing = []
    for name in city_names:
        if name not in city_data:
            missing.append(name)
            continue
        row = city_data[name]
        pop = int(row["population"])
        score = float(row.get("medical_services_score", 0))
        cities.append(CityState(
            name=name,
            country=row["country"],
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            population=pop,
            medical_services_score=score,
            S=float(pop),
            E=0.0,
            I=0.0,
            R=0.0,
        ))

    if missing:
        raise ValueError(f"Cities not found in {csv_path.name}: {missing}")

    return cities


def seed_infection(city: CityState, n_infected: int) -> None:
    """
    Seed initial infections in a city.

    Moves n_infected individuals from S to I.
    """
    actual = min(n_infected, city.S)
    city.S -= actual
    city.I += actual
