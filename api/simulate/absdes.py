"""Vercel serverless function: POST /api/simulate/absdes

Runs the ABS-DES pandemic simulation synchronously and returns all results
in a single response. No sessions, no SSE, no frame rendering.

This is a demo-mode endpoint — suitable for short simulations that complete
within the 60-second Vercel Pro timeout.
"""

import json
import sys
import uuid
from http.server import BaseHTTPRequestHandler
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Set up sys.path so we can import the simulation engine
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_BACKEND_DIR = str(_PROJECT_ROOT / "simulation_app" / "backend")
_DES_DIR = str(_PROJECT_ROOT / "des_system")
_MULTI_DIR = str(_PROJECT_ROOT / "004_multicity")
_MULTI_DES_DIR = str(_PROJECT_ROOT / "005_multicity_des")

for p in [_BACKEND_DIR, _DES_DIR, _MULTI_DIR, _MULTI_DES_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from simulation import run_absdes_simulation, SimulationParams  # noqa: E402


def _compute_summary(result) -> dict:
    """Compute summary statistics from a DualViewResult, scaled to real populations."""
    n_cities = len(result.city_names)
    n_people = result.n_people_per_city
    last_day = result.actual_S.shape[1] - 1

    real_pops = np.array(result.city_populations, dtype=float)
    total_real_pop = int(np.sum(real_pops))
    scale = real_pops / n_people

    agg_infected = 0.0
    agg_susceptible = 0.0
    agg_recovered = 0.0
    agg_dead = 0.0
    agg_detected = 0.0

    for i in range(n_cities):
        s = scale[i]
        city_infected = (result.actual_R[i, last_day] +
                         result.actual_I[i, last_day] +
                         result.actual_E[i, last_day] +
                         result.actual_D[i, last_day])
        agg_infected += city_infected * s
        agg_susceptible += result.actual_S[i, last_day] * s
        agg_recovered += result.actual_R[i, last_day] * s
        agg_dead += result.actual_D[i, last_day] * s
        agg_detected += (result.observed_I[i, last_day] +
                         result.observed_R[i, last_day] +
                         result.observed_D[i, last_day]) * s

    total_infected = int(round(agg_infected))
    total_susceptible = int(round(agg_susceptible))
    total_recovered = int(round(agg_recovered))
    total_dead = int(round(agg_dead))
    total_detected = int(round(agg_detected))

    infection_rate = agg_infected / max(1, total_real_pop)
    detection_rate = agg_detected / max(1, agg_infected)
    fatality_rate = agg_dead / max(1, agg_infected)

    scaled_I_per_day = np.zeros(last_day + 1)
    for i in range(n_cities):
        scaled_I_per_day += result.actual_I[i, :] * scale[i]
    peak_infectious = int(round(np.max(scaled_I_per_day)))
    peak_day = int(np.argmax(scaled_I_per_day))

    city_summaries = []
    for i in range(n_cities):
        s = scale[i]
        city_infected_des = (result.actual_R[i, last_day] +
                             result.actual_I[i, last_day] +
                             result.actual_E[i, last_day] +
                             result.actual_D[i, last_day])
        city_inf_rate = city_infected_des / n_people
        city_summaries.append({
            "name": result.city_names[i],
            "population": result.city_populations[i],
            "total_infected": int(round(city_infected_des * s)),
            "infection_rate": round(city_inf_rate, 4),
            "peak_infectious": int(round(float(np.max(result.actual_I[i, :])) * s)),
            "peak_day": int(np.argmax(result.actual_I[i, :])),
            "total_detected": int(round((result.observed_I[i, last_day] +
                                         result.observed_R[i, last_day] +
                                         result.observed_D[i, last_day]) * s)),
            "deaths": int(round(result.actual_D[i, last_day] * s)),
        })

    city_summaries.sort(key=lambda c: -c["total_infected"])

    resource_summary = None
    if result.supply_chain_enabled and result.resource_beds_occupied is not None:
        agg_beds_occupied = result.resource_beds_occupied.sum(axis=0)
        agg_beds_total = result.resource_beds_total.sum(axis=0)
        resource_summary = {
            "beds_at_capacity_days": int(np.sum(agg_beds_occupied >= agg_beds_total)),
            "ppe_stockout_days": int(np.sum(result.resource_ppe.sum(axis=0) == 0)),
            "swab_stockout_days": int(np.sum(result.resource_swabs.sum(axis=0) == 0)),
            "reagent_stockout_days": int(np.sum(result.resource_reagents.sum(axis=0) == 0)),
        }

    summary = {
        "total_population": total_real_pop,
        "simulation_days": last_day,
        "scenario": result.scenario_name,
        "provider_density": result.provider_density,
        "n_cities": n_cities,
        "n_people_per_city": n_people,
        "supply_chain_enabled": result.supply_chain_enabled,
        "aggregate": {
            "total_infected": total_infected,
            "infection_rate": round(infection_rate, 4),
            "peak_infectious": peak_infectious,
            "peak_day": peak_day,
            "total_deaths": total_dead,
            "fatality_rate": round(fatality_rate, 4),
            "final_susceptible": total_susceptible,
            "final_recovered": total_recovered,
            "total_detected": total_detected,
            "detection_rate": round(detection_rate, 4),
        },
        "cities": city_summaries[:20],
    }
    if resource_summary is not None:
        summary["resource_summary"] = resource_summary
    return summary


def _compute_resources(result) -> dict:
    """Compute resource timeseries from a DualViewResult."""
    days = int(result.t[-1]) + 1
    response = {
        "days": days,
        "supply_chain_enabled": result.supply_chain_enabled,
        "supply": None,
        "demand": None,
    }

    if result.supply_chain_enabled and result.resource_beds_occupied is not None:
        response["supply"] = {
            "beds_occupied": result.resource_beds_occupied.sum(axis=0).tolist(),
            "beds_total": result.resource_beds_total.sum(axis=0).tolist(),
            "ppe": result.resource_ppe.sum(axis=0).tolist(),
            "swabs": result.resource_swabs.sum(axis=0).tolist(),
            "reagents": result.resource_reagents.sum(axis=0).tolist(),
            "vaccines": result.resource_vaccines.sum(axis=0).tolist() if result.resource_vaccines is not None else None,
            "pills": result.resource_pills.sum(axis=0).tolist() if result.resource_pills is not None else None,
        }

    if result.shadow_demand_ppe is not None:
        response["demand"] = {
            "ppe": result.shadow_demand_ppe.sum(axis=0).tolist(),
            "swabs": result.shadow_demand_swabs.sum(axis=0).tolist(),
            "reagents": result.shadow_demand_reagents.sum(axis=0).tolist(),
            "pills": result.shadow_demand_pills.sum(axis=0).tolist(),
            "beds": result.shadow_demand_beds.sum(axis=0).tolist(),
        }

    return response


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            request = json.loads(body) if body else {}

            # Build SimulationParams from request (matching schemas.SimulationRequest)
            rc = request.get("resource_config", {})
            params = SimulationParams(
                country=request.get("country", "Nigeria"),
                scenario=request.get("scenario", "covid_natural"),
                n_people=request.get("n_people", 5000),
                avg_contacts=request.get("avg_contacts"),
                rewire_prob=request.get("rewire_prob", 0.4),
                daily_contact_rate=request.get("daily_contact_rate", 0.5),
                transmission_factor=request.get("transmission_factor", 0.3),
                gravity_scale=request.get("gravity_scale", 0.01),
                gravity_alpha=request.get("gravity_alpha", 2.0),
                days=request.get("days", 150),
                provider_density=request.get("provider_density", 5.0),
                screening_capacity=request.get("screening_capacity", 20),
                disclosure_prob=request.get("disclosure_prob", 0.5),
                base_isolation_prob=request.get("base_isolation_prob", 0.0),
                advised_isolation_prob=request.get("advised_isolation_prob", 0.40),
                advice_decay_prob=request.get("advice_decay_prob", 0.05),
                seed_fraction=request.get("seed_fraction", 0.005),
                random_seed=request.get("random_seed", 42),
                receptivity_override=request.get("receptivity_override"),
                detection_memory_days=request.get("detection_memory_days", 7),
                incubation_days=request.get("incubation_days"),
                infectious_days=request.get("infectious_days"),
                r0_override=request.get("r0_override"),
                enable_supply_chain=rc.get("enable_supply_chain", False),
                beds_per_hospital=rc.get("beds_per_hospital", 120),
                beds_per_clinic=rc.get("beds_per_clinic", 8),
                ppe_sets_per_facility=rc.get("ppe_sets_per_facility", 500),
                swabs_per_lab=rc.get("swabs_per_lab", 1000),
                reagents_per_lab=rc.get("reagents_per_lab", 2000),
                lead_time_mean_days=rc.get("lead_time_mean_days", 7.0),
                continent_vaccine_stockpile=rc.get("continent_vaccine_stockpile", 0),
                continent_pill_stockpile=rc.get("continent_pill_stockpile", 0),
            )

            # Run simulation synchronously (no rendering)
            def noop_progress(phase, current, total, message=""):
                pass

            result = run_absdes_simulation(params, noop_progress)

            session_id = str(uuid.uuid4())
            summary = _compute_summary(result)
            resources = _compute_resources(result)

            response_data = {
                "session_id": session_id,
                "total_days": int(result.t[-1]),
                "summary": summary,
                "resources": resources,
                "sync_mode": True,
            }

            response_body = json.dumps(response_data)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(response_body.encode())

        except Exception as e:
            import traceback
            traceback.print_exc()
            error_body = json.dumps({"detail": str(e)})
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(error_body.encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
