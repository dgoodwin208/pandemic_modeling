"""
Gravity Model — Inter-City Transportation Graph.

Computes pairwise travel rates between cities using the gravity model:
    travel_rate(i, j) = scale * (pop_i * pop_j) / distance_ij^alpha

Uses Haversine formula for great-circle distances from lat/lon coordinates.
"""

import math

import numpy as np


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Great-circle distance between two points in kilometers.

    Uses the Haversine formula with Earth radius = 6371 km.
    """
    R = 6371.0  # Earth radius in km

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def compute_distance_matrix(cities: list) -> np.ndarray:
    """
    Compute pairwise Haversine distances between cities.

    Args:
        cities: List of objects with .latitude and .longitude attributes.

    Returns:
        n x n distance matrix in kilometers.
    """
    n = len(cities)
    dist = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            d = haversine_km(
                cities[i].latitude, cities[i].longitude,
                cities[j].latitude, cities[j].longitude,
            )
            dist[i, j] = d
            dist[j, i] = d
    return dist


def compute_travel_matrix(
    cities: list,
    alpha: float = 2.0,
    scale: float = 1e-6,
) -> np.ndarray:
    """
    Gravity model travel matrix.

    travel_rate[i][j] = scale * (pop_i * pop_j) / distance_ij^alpha

    Args:
        cities: List of objects with .population, .latitude, .longitude.
        alpha: Distance decay exponent (typically 1-3).
        scale: Scaling constant to produce reasonable daily traveler counts.

    Returns:
        n x n matrix of daily travelers between each city pair.
        Diagonal is zero. Symmetric.
    """
    n = len(cities)
    dist = compute_distance_matrix(cities)
    travel = np.zeros((n, n))

    for i in range(n):
        for j in range(i + 1, n):
            if dist[i, j] > 0:
                rate = scale * (cities[i].population * cities[j].population) / (dist[i, j] ** alpha)
                travel[i, j] = rate
                travel[j, i] = rate

    return travel
