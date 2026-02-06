"""
FastAPI backend for ABS-DES Pandemic Simulation Web App.

Endpoints:
  POST /simulate/absdes          -- Start a simulation (returns session_id)
  GET  /simulate/absdes/{id}/progress -- SSE stream of simulation progress
  GET  /simulate/absdes/{id}/frame/{view}/{day} -- Serve a rendered PNG frame
  GET  /simulate/absdes/{id}/metadata  -- Return session metadata
  GET  /countries                 -- List available countries with city counts
  GET  /scenarios                 -- List disease scenarios with parameters
"""

import asyncio
import csv
import json
import pickle
import shutil
import time
import threading
import uuid
from pathlib import Path
from typing import Optional

import io
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
import numpy as np
from pydantic import BaseModel, Field
from enum import Enum

from simulation import run_absdes_simulation, SimulationParams, load_cities
from renderer import render_all_frames, load_africa_boundaries, generate_video, generate_combined_video
from progress import ProgressManager
from schemas import SimulationRequest, ResourceConfig
from sim_config import load_disease_params
from supply_config import ResourceDefaults

# =============================================================================
# App initialization
# =============================================================================

app = FastAPI(
    title="Pandemic Simulation API",
    description="ABS-DES pandemic simulation with ACTUAL vs OBSERVED views",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# Global state
# =============================================================================

progress_manager = ProgressManager()
OUTPUTS_BASE = Path(__file__).parent / "outputs"
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # pandemic_modeling/

# Session cleanup: track session creation times
_session_timestamps: dict[str, float] = {}
_session_results: dict[str, object] = {}  # Store DualViewResult for CSV export
_session_params: dict[str, dict] = {}  # Store request params for restoration
_SESSION_TTL_SECONDS = 3600  # 1 hour

# Persistent session storage
_SESSIONS_DIR = Path(__file__).parent / "sessions"
_SESSIONS_DIR.mkdir(exist_ok=True)


def _save_session(session_id: str):
    """Persist a completed session (result + params + timestamp) to disk."""
    try:
        data = {
            "result": _session_results[session_id],
            "params": _session_params.get(session_id, {}),
            "timestamp": _session_timestamps.get(session_id, time.time()),
        }
        path = _SESSIONS_DIR / f"{session_id}.pkl"
        with open(path, "wb") as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception as e:
        print(f"[sessions] Failed to save {session_id}: {e}")


def _load_persisted_sessions():
    """Load all persisted sessions from disk into memory on startup."""
    count = 0
    for path in _SESSIONS_DIR.glob("*.pkl"):
        sid = path.stem
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            _session_results[sid] = data["result"]
            _session_params[sid] = data.get("params", {})
            _session_timestamps[sid] = data.get("timestamp", path.stat().st_mtime)
            count += 1
        except Exception as e:
            print(f"[sessions] Failed to load {sid}: {e}")
    if count:
        print(f"[sessions] Restored {count} persisted session(s)")


# Restore sessions on import
_load_persisted_sessions()

# =============================================================================
# Disease scenarios
# =============================================================================

DISEASE_SCENARIOS = {
    "covid_natural": {
        "name": "COVID-19 — Natural Outbreak",
        "R0": 2.5,
        "incubation_days": 5.0,
        "infectious_days": 9.0,
        "description": "SARS-CoV-2-like respiratory pathogen, single-city origin",
    },
    "covid_bioattack": {
        "name": "COVID-19 — Bioattack",
        "R0": 3.5,
        "incubation_days": 4.0,
        "infectious_days": 9.0,
        "description": "Engineered SARS-CoV-2 variant, multi-city simultaneous seeding",
    },
    "ebola_natural": {
        "name": "Ebola — Natural Outbreak",
        "R0": 2.0,
        "incubation_days": 10.0,
        "infectious_days": 10.0,
        "description": "Ebola-like hemorrhagic fever, single-city origin",
    },
    "ebola_bioattack": {
        "name": "Ebola — Bioattack",
        "R0": 2.5,
        "incubation_days": 8.0,
        "infectious_days": 10.0,
        "description": "Engineered Ebola variant, multi-city simultaneous seeding",
    },
}

# =============================================================================
# Vaccine supply model
# =============================================================================

def _compute_vaccine_supply_curve(n_days: int, total_population: int, lead_time: int = 120) -> list[float]:
    """Model vaccine supply as cumulative doses available per day.

    Assumes:
    - Configurable lead time before first doses arrive (manufacturing setup)
    - Logistic (S-curve) manufacturing ramp-up after lead time
    - Max daily production capacity reaches ~0.5% of total population per day
      at peak (roughly matching real-world pandemic vaccine rollout rates)
    - Cumulative supply is capped at total population (one dose per person)
    """
    lead_time_days = lead_time
    # Logistic growth rate (steepness of ramp-up)
    k = 0.04  # moderate ramp — reaches ~50% of max capacity ~40 days after lead time
    # Max daily production at peak (doses/day across entire region)
    max_daily = total_population * 0.005

    cumulative = 0.0
    supply = []
    for day in range(n_days):
        if day < lead_time_days:
            daily = 0.0
        else:
            t = day - lead_time_days
            # Logistic function: daily production ramps from 0 toward max_daily
            daily = max_daily / (1.0 + np.exp(-k * (t - 60)))
        cumulative = min(cumulative + daily, total_population)
        supply.append(round(cumulative))
    return supply


# =============================================================================
# Session cleanup
# =============================================================================

def _cleanup_stale_sessions():
    """Remove output directories for sessions older than TTL."""
    now = time.time()
    stale_ids = [
        sid for sid, created_at in _session_timestamps.items()
        if now - created_at > _SESSION_TTL_SECONDS
    ]
    for sid in stale_ids:
        output_dir = OUTPUTS_BASE / sid
        if output_dir.exists():
            try:
                shutil.rmtree(output_dir)
            except OSError:
                pass
        _session_timestamps.pop(sid, None)
        _session_results.pop(sid, None)
        _session_params.pop(sid, None)
        pkl_path = _SESSIONS_DIR / f"{sid}.pkl"
        pkl_path.unlink(missing_ok=True)
        progress_manager.cleanup(sid)


# =============================================================================
# Background simulation thread
# =============================================================================

def _run_simulation_thread(session_id: str, request: SimulationRequest):
    """Execute the full simulation + rendering pipeline in a background thread."""
    try:
        progress_manager.update(session_id, "initializing", 0, 0,
                                "Loading city data and computing travel matrix...")

        # Build supply chain params from resource_config
        rc = request.resource_config or ResourceConfig()

        params = SimulationParams(
            country=request.country,
            scenario=request.scenario.value,
            n_people=request.n_people,
            avg_contacts=request.avg_contacts,
            rewire_prob=request.rewire_prob,
            daily_contact_rate=request.daily_contact_rate,
            days=request.days,
            provider_density=request.provider_density,
            screening_capacity=request.screening_capacity,
            disclosure_prob=request.disclosure_prob,
            base_isolation_prob=request.base_isolation_prob,
            advised_isolation_prob=request.advised_isolation_prob,
            advice_decay_prob=request.advice_decay_prob,
            gravity_scale=request.gravity_scale,
            gravity_alpha=request.gravity_alpha,
            transmission_factor=request.transmission_factor,
            seed_fraction=request.seed_fraction,
            random_seed=request.random_seed,
            receptivity_override=request.receptivity_override,
            detection_memory_days=request.detection_memory_days,
            incubation_days=request.incubation_days,
            infectious_days=request.infectious_days,
            r0_override=request.r0_override,
            # Supply chain
            enable_supply_chain=rc.enable_supply_chain,
            beds_per_hospital=rc.beds_per_hospital,
            beds_per_clinic=rc.beds_per_clinic,
            ppe_sets_per_facility=rc.ppe_sets_per_facility,
            swabs_per_lab=rc.swabs_per_lab,
            reagents_per_lab=rc.reagents_per_lab,
            lead_time_mean_days=rc.lead_time_mean_days,
            continent_vaccine_stockpile=rc.continent_vaccine_stockpile,
            continent_pill_stockpile=rc.continent_pill_stockpile,
        )

        def sim_progress(phase, current, total, message=""):
            progress_manager.update(session_id, phase, current, total, message)

        result = run_absdes_simulation(params, sim_progress)
        _session_results[session_id] = result
        _save_session(session_id)

        output_dir = OUTPUTS_BASE / session_id
        output_dir.mkdir(parents=True, exist_ok=True)

        africa_gdf = load_africa_boundaries()
        # Convert params dataclass to dict for metadata storage
        from dataclasses import asdict
        params_dict = asdict(params)
        render_all_frames(result, africa_gdf, output_dir, sim_progress,
                          country=request.country, params=params_dict)

        progress_manager.update(session_id, "complete", 0, 0,
                                "Simulation complete")
    except Exception as e:
        import traceback
        traceback.print_exc()
        progress_manager.update(session_id, "error", 0, 0, str(e))


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/")
async def root():
    return {
        "name": "Pandemic Simulation API",
        "version": "1.0.0",
        "endpoints": [
            "POST /simulate/absdes",
            "GET  /simulate/absdes/{session_id}/progress",
            "GET  /simulate/absdes/{session_id}/frame/{view}/{day}",
            "GET  /simulate/absdes/{session_id}/metadata",
            "GET  /countries",
            "GET  /scenarios",
        ],
    }


# -- Simulation lifecycle ------------------------------------------------------

@app.get("/simulate/absdes/latest")
async def get_latest_session():
    """Return the most recent completed simulation session ID and its params."""
    if not _session_timestamps:
        raise HTTPException(status_code=404, detail="No sessions available")

    completed = [
        (sid, ts) for sid, ts in _session_timestamps.items()
        if sid in _session_results
    ]
    if not completed:
        raise HTTPException(status_code=404, detail="No completed sessions")

    latest_sid = max(completed, key=lambda x: x[1])[0]
    result = _session_results[latest_sid]

    return {
        "session_id": latest_sid,
        "total_days": int(result.t[-1]),
        "params": _session_params.get(latest_sid),
    }


@app.get("/simulate/absdes/sessions")
async def list_sessions():
    """Return all completed sessions with top-line summary stats."""
    completed = [
        (sid, ts) for sid, ts in _session_timestamps.items()
        if sid in _session_results
    ]
    if not completed:
        return {"sessions": []}

    # Sort by timestamp descending (most recent first)
    completed.sort(key=lambda x: -x[1])

    sessions = []
    for sid, ts in completed:
        result = _session_results[sid]
        n_cities = len(result.city_names)
        n_people = result.n_people_per_city
        last_day = result.actual_S.shape[1] - 1
        real_pops = np.array(result.city_populations, dtype=float)
        total_real_pop = int(np.sum(real_pops))
        scale = real_pops / n_people

        # Scaled aggregates
        total_infected = int(np.sum(
            result.actual_R[:, last_day] * scale +
            result.actual_D[:, last_day] * scale +
            result.actual_I[:, last_day] * scale +
            result.actual_E[:, last_day] * scale
        ))
        total_dead = int(np.sum(result.actual_D[:, last_day] * scale))
        peak_I_per_city = result.actual_I.max(axis=1)
        peak_infectious = int(np.sum(peak_I_per_city * scale))
        total_detected = int(np.sum(result.observed_I.max(axis=1) * scale))

        params = _session_params.get(sid, {})

        sessions.append({
            "session_id": sid,
            "timestamp": ts,
            "scenario": getattr(result, 'scenario_name', params.get('scenario', '?')),
            "country": params.get('country', '?'),
            "n_cities": n_cities,
            "total_population": total_real_pop,
            "total_days": last_day,
            "total_infected": total_infected,
            "total_deaths": total_dead,
            "peak_infectious": peak_infectious,
            "total_detected": total_detected,
            "supply_chain_enabled": getattr(result, 'supply_chain_enabled', False),
            "params": params,
        })

    return {"sessions": sessions}


@app.delete("/simulate/absdes/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and its persisted data."""
    if session_id not in _session_timestamps and session_id not in _session_results:
        raise HTTPException(status_code=404, detail="Session not found")
    _session_timestamps.pop(session_id, None)
    _session_results.pop(session_id, None)
    _session_params.pop(session_id, None)
    pkl_path = _SESSIONS_DIR / f"{session_id}.pkl"
    pkl_path.unlink(missing_ok=True)
    output_dir = OUTPUTS_BASE / session_id
    if output_dir.exists():
        try:
            shutil.rmtree(output_dir)
        except OSError:
            pass
    progress_manager.cleanup(session_id)
    return {"status": "deleted"}


@app.post("/simulate/absdes")
async def start_simulation(request: SimulationRequest):
    """
    Start an ABS-DES pandemic simulation in a background thread.
    Returns a session_id to poll for progress and retrieve frames.
    """
    # Cleanup stale sessions on new simulation start
    _cleanup_stale_sessions()

    session_id = str(uuid.uuid4())
    _session_timestamps[session_id] = time.time()
    _session_params[session_id] = request.model_dump()

    progress_manager.create_session(session_id)

    thread = threading.Thread(
        target=_run_simulation_thread,
        args=(session_id, request),
        daemon=True,
    )
    thread.start()

    return {"session_id": session_id}


@app.get("/simulate/absdes/{session_id}/progress")
async def simulation_progress(session_id: str):
    """
    Server-Sent Events endpoint that streams simulation progress.
    Polls the ProgressManager every 0.5 seconds and yields JSON events.
    Includes ETA calculation based on elapsed time and completion rate.
    """
    async def event_stream():
        while True:
            state = progress_manager.get_state(session_id)
            if not state:
                yield f"data: {json.dumps({'phase': 'error', 'message': 'Session not found'})}\n\n"
                break

            elapsed = time.time() - state.started_at
            eta = 0
            if state.current > 0 and state.total > 0:
                rate = elapsed / state.current
                eta = int((state.total - state.current) * rate)

            data = json.dumps({
                "phase": state.phase,
                "current": state.current,
                "total": state.total,
                "message": state.message,
                "eta_seconds": eta,
                "elapsed_seconds": round(elapsed, 1),
            })
            yield f"data: {data}\n\n"

            if state.phase in ("complete", "error"):
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/simulate/absdes/{session_id}/frame/{view}/{day}")
async def get_frame(session_id: str, view: str, day: int):
    """
    Serve a rendered PNG frame for the given session, view, and day.

    Parameters
    ----------
    session_id : str
        UUID of the simulation session.
    view : str
        Either "actual" or "observed".
    day : int
        Day number (0-indexed).
    """
    if view not in ("actual", "observed"):
        raise HTTPException(status_code=400,
                            detail=f"Invalid view '{view}'. Must be 'actual' or 'observed'.")

    output_dir = OUTPUTS_BASE / session_id
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    filename = f"{view}_day{day:03d}.png"
    filepath = output_dir / filename

    if not filepath.exists():
        raise HTTPException(status_code=404,
                            detail=f"Frame not found: {filename}")

    return FileResponse(
        str(filepath),
        media_type="image/png",
        filename=filename,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/simulate/absdes/{session_id}/metadata")
async def get_metadata(session_id: str):
    """Return the metadata.json contents for a completed simulation session."""
    output_dir = OUTPUTS_BASE / session_id
    metadata_path = output_dir / "metadata.json"

    if not metadata_path.exists():
        # Check if session exists but is still running
        state = progress_manager.get_state(session_id)
        if state and state.phase not in ("complete", "error"):
            raise HTTPException(status_code=202,
                                detail="Simulation still in progress")
        raise HTTPException(status_code=404,
                            detail="Session not found or metadata not yet generated")

    with open(metadata_path) as f:
        return json.load(f)


@app.get("/simulate/absdes/{session_id}/summary")
async def get_summary(session_id: str):
    """
    Return simulation summary statistics scaled to real city populations.

    The DES runs n_people agents per city (e.g. 5,000), but each city
    represents a real population (e.g. Cairo = 11.9M). All absolute counts
    are scaled by (real_population / n_people) per city so the summary
    reflects real-world scale.
    """
    result = _session_results.get(session_id)
    if result is None:
        raise HTTPException(status_code=404,
                            detail="Session not found or result not available")

    n_cities = len(result.city_names)
    n_people = result.n_people_per_city
    last_day = result.actual_S.shape[1] - 1

    # Real population total
    real_pops = np.array(result.city_populations, dtype=float)
    total_real_pop = int(np.sum(real_pops))

    # Per-city scale factors: real_pop / n_people
    scale = real_pops / n_people  # shape (n_cities,)

    # --- Aggregate totals (scaled to real populations) ---

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

    # Infection rate as fraction of total real population
    infection_rate = agg_infected / max(1, total_real_pop)
    detection_rate = agg_detected / max(1, agg_infected)
    fatality_rate = agg_dead / max(1, agg_infected)

    # Peak infectious (scaled): for each day, sum scaled I across cities
    scaled_I_per_day = np.zeros(last_day + 1)
    for i in range(n_cities):
        scaled_I_per_day += result.actual_I[i, :] * scale[i]
    peak_infectious = int(round(np.max(scaled_I_per_day)))
    peak_day = int(np.argmax(scaled_I_per_day))

    # --- Per-city summary (scaled) ---
    city_summaries = []
    for i in range(n_cities):
        s = scale[i]
        city_infected_des = (result.actual_R[i, last_day] +
                             result.actual_I[i, last_day] +
                             result.actual_E[i, last_day] +
                             result.actual_D[i, last_day])
        city_infected = int(round(city_infected_des * s))
        city_inf_rate = city_infected_des / n_people
        city_peak_I = int(round(float(np.max(result.actual_I[i, :])) * s))
        city_peak_day = int(np.argmax(result.actual_I[i, :]))
        city_detected = int(round((result.observed_I[i, last_day] +
                                   result.observed_R[i, last_day] +
                                   result.observed_D[i, last_day]) * s))
        city_deaths = int(round(result.actual_D[i, last_day] * s))
        city_summaries.append({
            "name": result.city_names[i],
            "population": result.city_populations[i],
            "total_infected": city_infected,
            "infection_rate": round(city_inf_rate, 4),
            "peak_infectious": city_peak_I,
            "peak_day": city_peak_day,
            "total_detected": city_detected,
            "deaths": city_deaths,
        })

    # Sort by total infected descending
    city_summaries.sort(key=lambda c: -c["total_infected"])

    # Resource summary (when supply chain enabled)
    resource_summary = None
    if result.supply_chain_enabled and result.resource_beds_occupied is not None:
        # Compute aggregate resource stats
        agg_beds_occupied = result.resource_beds_occupied.sum(axis=0)
        agg_beds_total = result.resource_beds_total.sum(axis=0)
        agg_ppe = result.resource_ppe.sum(axis=0)
        agg_swabs = result.resource_swabs.sum(axis=0)
        agg_reagents = result.resource_reagents.sum(axis=0)

        beds_at_capacity_days = int(np.sum(agg_beds_occupied >= agg_beds_total))
        ppe_stockout_days = int(np.sum(agg_ppe == 0))
        swab_stockout_days = int(np.sum(agg_swabs == 0))
        reagent_stockout_days = int(np.sum(agg_reagents == 0))

        resource_summary = {
            "beds_at_capacity_days": beds_at_capacity_days,
            "ppe_stockout_days": ppe_stockout_days,
            "swab_stockout_days": swab_stockout_days,
            "reagent_stockout_days": reagent_stockout_days,
            "final_beds_occupied": int(agg_beds_occupied[-1]),
            "final_beds_total": int(agg_beds_total[-1]),
            "final_ppe": int(agg_ppe[-1]),
            "final_swabs": int(agg_swabs[-1]),
            "final_reagents": int(agg_reagents[-1]),
        }

    response = {
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
        response["resource_summary"] = resource_summary
    return response


@app.get("/simulate/absdes/{session_id}/resources")
async def get_resource_timeseries(session_id: str):
    """Return daily resource supply and demand time series for charts.

    Returns aggregated (across all cities) daily values for:
    - Actual supply levels (when supply chain enabled)
    - Shadow demand (always available — what resources WOULD be consumed)
    """
    result = _session_results.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")

    days = int(result.t[-1]) + 1

    response: dict = {
        "days": days,
        "supply_chain_enabled": result.supply_chain_enabled,
        "supply": None,
        "demand": None,
    }

    # Actual supply levels (only when supply chain was enabled)
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

    # Shadow demand (always populated)
    if result.shadow_demand_ppe is not None:
        # Vaccine supply: use manufacturing lead time from simulation result
        mfg_lead = getattr(result, 'vaccine_manufacturing_lead_days', 120)
        total_pop = int(np.sum(np.array(result.city_populations, dtype=float)))
        vaccine_supply = _compute_vaccine_supply_curve(days, total_pop, lead_time=mfg_lead)

        response["demand"] = {
            "ppe": result.shadow_demand_ppe.sum(axis=0).tolist(),
            "swabs": result.shadow_demand_swabs.sum(axis=0).tolist(),
            "reagents": result.shadow_demand_reagents.sum(axis=0).tolist(),
            "pills": result.shadow_demand_pills.sum(axis=0).tolist(),
            "beds": result.shadow_demand_beds.sum(axis=0).tolist(),
            "vaccines": vaccine_supply,
        }

        # Include manufacturing metadata
        mfg_sites = getattr(result, 'vaccine_manufacturing_sites', None)
        if mfg_sites:
            response["vaccine_manufacturing"] = {
                "sites": mfg_sites,
                "lead_days": mfg_lead,
                "cumulative_produced": getattr(result, 'vaccine_cumulative_production', 0),
            }

    return response


@app.get("/simulate/absdes/{session_id}/events")
async def get_events(
    session_id: str,
    day: Optional[int] = None,
    city: Optional[str] = None,
    category: Optional[str] = None,
):
    """Return filtered event log as JSON.

    Query parameters:
        day: Filter to events on a specific day.
        city: Filter to events for a specific city.
        category: Filter by event category (screening, stockout, redistribution, etc.)
    """
    result = _session_results.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")

    elog = getattr(result, "event_log", None)
    if elog is None:
        return {"events": [], "summary": {"total_events": 0}}

    if day is not None:
        events = elog.events_on_day(day, city=city, category=category)
    elif category is not None:
        events = elog.events_by_category(category)
        if city is not None:
            events = [e for e in events if e.city == city]
    elif city is not None:
        events = [e for e in elog.events if e.city == city]
    else:
        events = elog.events

    return {
        "events": [
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
            for e in events[:1000]  # cap at 1000 events per response
        ],
        "total_matching": len(events),
        "summary": elog.summary(),
        "notable": [
            {
                "day": e.day,
                "city": e.city,
                "category": e.category,
                "action": e.action,
                "resource": e.resource,
                "quantity": e.quantity,
                "reason": e.reason,
            }
            for e in elog.notable_events()
        ],
    }


@app.get("/simulate/absdes/{session_id}/export/csv")
async def export_csv(session_id: str):
    """
    Export simulation SEIR data as CSV.

    Columns: day, then for each city: actual_S, actual_E, actual_I, actual_R,
    observed_S, observed_E, observed_I, observed_R.
    If multiple cities, aggregates across all cities.
    """
    result = _session_results.get(session_id)
    if result is None:
        raise HTTPException(status_code=404,
                            detail="Session not found or result not available")

    output = io.StringIO()
    writer = csv.writer(output)

    n_cities = len(result.city_names)
    days = result.actual_S.shape[1]

    # Header
    header = ["day",
              "actual_S", "actual_E", "actual_I", "actual_I_minor",
              "actual_I_needs", "actual_I_care", "actual_R", "actual_D",
              "observed_S", "observed_E", "observed_I", "observed_R", "observed_D"]
    # Add per-city columns if more than 1 city
    if n_cities > 1:
        for i, name in enumerate(result.city_names):
            safe = name.replace(",", "")
            header.extend([
                f"{safe}_actual_S", f"{safe}_actual_E",
                f"{safe}_actual_I", f"{safe}_actual_I_minor",
                f"{safe}_actual_I_needs", f"{safe}_actual_I_care",
                f"{safe}_actual_R", f"{safe}_actual_D",
                f"{safe}_observed_S", f"{safe}_observed_E",
                f"{safe}_observed_I", f"{safe}_observed_R",
                f"{safe}_observed_D",
            ])
    writer.writerow(header)

    # Data rows
    for d in range(days):
        row = [d]
        # Aggregated totals
        row.append(int(np.sum(result.actual_S[:, d])))
        row.append(int(np.sum(result.actual_E[:, d])))
        row.append(int(np.sum(result.actual_I[:, d])))
        row.append(int(np.sum(result.actual_I_minor[:, d])))
        row.append(int(np.sum(result.actual_I_needs[:, d])))
        row.append(int(np.sum(result.actual_I_care[:, d])))
        row.append(int(np.sum(result.actual_R[:, d])))
        row.append(int(np.sum(result.actual_D[:, d])))
        row.append(int(np.sum(result.observed_S[:, d])))
        row.append(int(np.sum(result.observed_E[:, d])))
        row.append(int(np.sum(result.observed_I[:, d])))
        row.append(int(np.sum(result.observed_R[:, d])))
        row.append(int(np.sum(result.observed_D[:, d])))

        if n_cities > 1:
            for i in range(n_cities):
                row.extend([
                    int(result.actual_S[i, d]), int(result.actual_E[i, d]),
                    int(result.actual_I[i, d]), int(result.actual_I_minor[i, d]),
                    int(result.actual_I_needs[i, d]), int(result.actual_I_care[i, d]),
                    int(result.actual_R[i, d]), int(result.actual_D[i, d]),
                    int(result.observed_S[i, d]), int(result.observed_E[i, d]),
                    int(result.observed_I[i, d]), int(result.observed_R[i, d]),
                    int(result.observed_D[i, d]),
                ])
        writer.writerow(row)

    csv_content = output.getvalue()
    output.close()

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=simulation_{session_id[:8]}.csv",
        },
    )


@app.get("/simulate/absdes/{session_id}/export/video")
async def export_video(
    session_id: str,
    view: str = "actual",
    fps: int = 10,
    format: str = "mp4",
):
    """
    Export simulation frames as a video file.

    Args:
        session_id: The simulation session ID.
        view: Which view to export - "actual", "observed", or "combined".
        fps: Frames per second (default 10).
        format: Output format - "mp4" (recommended for Google Slides) or "webm".

    Returns:
        The video file as a download.
    """
    result = _session_results.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")

    output_dir = OUTPUTS_BASE / session_id

    if not output_dir.exists():
        raise HTTPException(
            status_code=400,
            detail="No frames available. Run simulation with render_maps=True first.",
        )

    # Check if frames exist
    actual_frames = list(output_dir.glob("actual_day*.png"))
    if not actual_frames:
        raise HTTPException(
            status_code=400,
            detail="No frame images found in output directory.",
        )

    try:
        if view == "combined":
            video_path = generate_combined_video(output_dir, fps=fps, output_format=format)
        elif view in ("actual", "observed"):
            video_path = generate_video(output_dir, view=view, fps=fps, output_format=format)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid view: {view}. Use 'actual', 'observed', or 'combined'.",
            )
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"Video generation failed: {e}")

    # Return video file
    media_type = "video/mp4" if format == "mp4" else "video/webm"
    filename = f"simulation_{session_id[:8]}_{view}.{format}"

    return FileResponse(
        path=video_path,
        media_type=media_type,
        filename=filename,
    )


# -- Reference data endpoints --------------------------------------------------

@app.get("/countries")
async def list_countries():
    """
    Parse african_cities.csv and return unique countries with their city counts.
    """
    csv_path = _PROJECT_ROOT / "backend" / "data" / "african_cities.csv"

    if not csv_path.exists():
        raise HTTPException(status_code=500,
                            detail=f"City data file not found at {csv_path}")

    countries: dict[str, int] = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            country_name = row.get("country", "Unknown")
            countries[country_name] = countries.get(country_name, 0) + 1

    # Sort by city count descending
    sorted_countries = sorted(countries.items(), key=lambda x: -x[1])

    return {
        "countries": [
            {"name": name, "city_count": count}
            for name, count in sorted_countries
        ],
        "total_countries": len(sorted_countries),
        "total_cities": sum(countries.values()),
    }


@app.get("/scenarios")
async def list_scenarios():
    """Return the 4 disease scenarios with their parameters."""
    return {
        "scenarios": {
            scenario_id: {
                "id": scenario_id,
                **params,
            }
            for scenario_id, params in DISEASE_SCENARIOS.items()
        }
    }


@app.get("/resources/defaults")
async def get_resource_defaults():
    """Return default resource configuration for the frontend form."""
    d = ResourceDefaults()
    return {
        "beds_per_hospital": d.beds_per_hospital,
        "beds_per_clinic": d.beds_per_clinic,
        "ppe_sets_per_facility": d.ppe_sets_per_facility,
        "swabs_per_lab": d.swabs_per_lab,
        "reagents_per_lab": d.reagents_per_lab,
        "lead_time_mean_days": d.lead_time_mean_days,
        "continent_lead_time_mean": d.continent_lead_time_mean,
        "country_reorder_threshold": d.country_reorder_threshold,
        "continent_deploy_threshold": d.continent_deploy_threshold,
    }


@app.get("/disease-params")
async def get_disease_params():
    """Return disease parameters from disease_params.csv for frontend display.

    Includes severity model parameters: severe_fraction, care_survival_prob,
    death probabilities, gamma distribution shape, etc.
    """
    params = load_disease_params()
    return {
        scenario: {
            "scenario": dp.scenario,
            "R0": dp.R0,
            "incubation_days": dp.incubation_days,
            "infectious_days": dp.infectious_days,
            "severe_fraction": dp.severe_fraction,
            "care_survival_prob": dp.care_survival_prob,
            "ifr": dp.ifr,
            "gamma_shape": dp.gamma_shape,
            "base_daily_death_prob": dp.base_daily_death_prob,
            "death_prob_increase_per_day": dp.death_prob_increase_per_day,
        }
        for scenario, dp in params.items()
    }


# =============================================================================
# ABS-DES Visualization API (Multi-Level Zoom)
# =============================================================================

@app.get("/api/absdes/{session_id}/schema")
async def get_schema(session_id: str):
    """Return simulation schema for frontend visualization.

    The schema defines entity types, state machines, aggregation levels,
    and current parameter values - enabling the frontend to render
    schema-driven visualizations without hardcoding model specifics.
    """
    result = _session_results.get(session_id)
    params = _session_params.get(session_id, {})

    # Load disease params for current scenario
    disease_params = load_disease_params()
    scenario_key = params.get("scenario", "covid_natural")
    dp = disease_params.get(scenario_key)

    # Build schema with current parameter values
    schema = {
        "name": "ABS-DES Pandemic Model",
        "sessionId": session_id,
        "entityTypes": [
            {
                "id": "person",
                "name": "Person Agent",
                "stateVariable": "compartment",
                "attributes": [
                    {"name": "compartment", "type": "enum",
                     "enumValues": ["S", "E", "I_mild", "I_needs", "I_care", "R", "D"]},
                    {"name": "has_phone", "type": "boolean", "description": "Can receive health messages"},
                    {"name": "is_advised", "type": "boolean", "description": "Has received health advice"},
                    {"name": "is_vaccinated", "type": "boolean", "description": "Has been vaccinated"},
                ]
            },
            {
                "id": "city",
                "name": "City Environment",
                "stateVariable": None,
                "attributes": [
                    {"name": "name", "type": "string"},
                    {"name": "population", "type": "number"},
                    {"name": "latitude", "type": "number"},
                    {"name": "longitude", "type": "number"},
                ]
            },
            {
                "id": "resource",
                "name": "Supply Resource",
                "stateVariable": "type",
                "attributes": [
                    {"name": "type", "type": "enum",
                     "enumValues": ["beds", "ppe", "swabs", "reagents", "vaccines", "pills"]},
                    {"name": "quantity", "type": "number"},
                    {"name": "burn_rate", "type": "number"},
                ]
            }
        ],
        "stateMachines": [
            {
                "entityType": "person",
                "states": [
                    {"id": "S", "name": "Susceptible", "color": "#4ade80"},
                    {"id": "E", "name": "Exposed", "color": "#fbbf24"},
                    {"id": "I_mild", "name": "Infectious (Mild)", "color": "#f97316"},
                    {"id": "I_needs", "name": "Needs Care", "color": "#ef4444"},
                    {"id": "I_care", "name": "Receiving Care", "color": "#ec4899"},
                    {"id": "R", "name": "Recovered", "color": "#3b82f6"},
                    {"id": "D", "name": "Dead", "color": "#1f2937"},
                ],
                "transitions": [
                    {"from": "S", "to": "E", "trigger": "event",
                     "description": "Contact with infectious agent"},
                    {"from": "E", "to": "I_mild", "trigger": "time",
                     "meanDuration": dp.incubation_days if dp else 5.5,
                     "distribution": "gamma", "description": "Incubation period"},
                    {"from": "I_mild", "to": "R", "trigger": "time",
                     "probability": 1 - (dp.severe_fraction if dp else 0.15),
                     "description": "Mild case recovers"},
                    {"from": "I_mild", "to": "I_needs", "trigger": "time",
                     "probability": dp.severe_fraction if dp else 0.15,
                     "description": "Case becomes severe"},
                    {"from": "I_needs", "to": "I_care", "trigger": "event",
                     "description": "Admitted to hospital bed"},
                    {"from": "I_needs", "to": "D", "trigger": "time",
                     "probability": 0.6, "description": "Death without care"},
                    {"from": "I_care", "to": "R", "trigger": "time",
                     "probability": dp.care_survival_prob if dp else 0.9,
                     "description": "Recovers with care"},
                    {"from": "I_care", "to": "D", "trigger": "time",
                     "probability": 1 - (dp.care_survival_prob if dp else 0.9),
                     "description": "Death despite care"},
                ]
            }
        ],
        "aggregationLevels": [
            {"id": "agent", "name": "Individual Agent", "parent": "city"},
            {"id": "city", "name": "City", "parent": "country", "groupBy": "city_id"},
            {"id": "country", "name": "Country", "parent": "system", "groupBy": "country"},
            {"id": "system", "name": "System", "parent": None},
        ],
        "parameters": [
            {"id": "R0", "name": "Basic Reproduction Number", "type": "number",
             "value": dp.R0 if dp else 2.5, "description": "Expected secondary infections"},
            {"id": "incubation_days", "name": "Incubation Period", "type": "number",
             "value": dp.incubation_days if dp else 5.5, "unit": "days"},
            {"id": "infectious_days", "name": "Infectious Period", "type": "number",
             "value": dp.infectious_days if dp else 9.0, "unit": "days"},
            {"id": "severe_fraction", "name": "Severe Fraction", "type": "number",
             "value": dp.severe_fraction if dp else 0.15},
            {"id": "provider_density", "name": "Provider Density", "type": "number",
             "value": params.get("provider_density", 5.0), "unit": "per 1000"},
            {"id": "disclosure_prob", "name": "Disclosure Probability", "type": "number",
             "value": params.get("disclosure_prob", 0.5)},
            {"id": "transmission_factor", "name": "Transmission Factor", "type": "number",
             "value": params.get("transmission_factor", 0.3)},
        ]
    }

    # Add simulation metadata if result exists
    if result:
        schema["simulationInfo"] = {
            "cities": result.city_names,
            "totalDays": int(result.t[-1]),
            "nPeoplePerCity": result.n_people_per_city,
            "supplyChainEnabled": result.supply_chain_enabled,
        }

    return schema


@app.get("/api/absdes/{session_id}/aggregates/{level}")
async def get_aggregates(
    session_id: str,
    level: str,
    day: Optional[int] = None,
):
    """Return aggregated metrics at specified hierarchy level.

    Levels:
      - system: Continent-wide totals
      - country: Per-country aggregates (currently single-country)
      - city: Per-city breakdowns
    """
    result = _session_results.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")

    n_cities = len(result.city_names)
    total_days = result.actual_S.shape[1]
    target_day = day if day is not None else total_days - 1
    target_day = min(max(0, target_day), total_days - 1)

    real_pops = np.array(result.city_populations, dtype=float)
    n_people = result.n_people_per_city
    scale = real_pops / n_people

    if level == "system":
        # Aggregate across all cities
        return {
            "level": "system",
            "day": target_day,
            "metrics": {
                "S": int(np.sum(result.actual_S[:, target_day] * scale)),
                "E": int(np.sum(result.actual_E[:, target_day] * scale)),
                "I": int(np.sum(result.actual_I[:, target_day] * scale)),
                "I_mild": int(np.sum(result.actual_I_minor[:, target_day] * scale)),
                "I_needs": int(np.sum(result.actual_I_needs[:, target_day] * scale)),
                "I_care": int(np.sum(result.actual_I_care[:, target_day] * scale)),
                "R": int(np.sum(result.actual_R[:, target_day] * scale)),
                "D": int(np.sum(result.actual_D[:, target_day] * scale)),
                "observed_I": int(np.sum(result.observed_I[:, target_day] * scale)),
                "observed_R": int(np.sum(result.observed_R[:, target_day] * scale)),
                "observed_D": int(np.sum(result.observed_D[:, target_day] * scale)),
            },
            "totalPopulation": int(np.sum(real_pops)),
            "nCities": n_cities,
        }

    elif level == "city":
        # Per-city metrics
        cities = []
        for i in range(n_cities):
            s = scale[i]
            cities.append({
                "name": result.city_names[i],
                "population": result.city_populations[i],
                "metrics": {
                    "S": int(result.actual_S[i, target_day] * s),
                    "E": int(result.actual_E[i, target_day] * s),
                    "I": int(result.actual_I[i, target_day] * s),
                    "I_mild": int(result.actual_I_minor[i, target_day] * s),
                    "I_needs": int(result.actual_I_needs[i, target_day] * s),
                    "I_care": int(result.actual_I_care[i, target_day] * s),
                    "R": int(result.actual_R[i, target_day] * s),
                    "D": int(result.actual_D[i, target_day] * s),
                    "observed_I": int(result.observed_I[i, target_day] * s),
                    "observed_R": int(result.observed_R[i, target_day] * s),
                    "observed_D": int(result.observed_D[i, target_day] * s),
                }
            })
        return {
            "level": "city",
            "day": target_day,
            "cities": cities,
        }

    else:
        raise HTTPException(status_code=400, detail=f"Unknown level: {level}")


@app.get("/api/absdes/{session_id}/timeseries/{level}")
async def get_timeseries(
    session_id: str,
    level: str,
    entity_id: Optional[str] = None,
):
    """Return time series data at specified aggregation level.

    Levels:
      - system: Aggregate time series across all cities
      - city: Time series for a specific city (requires entity_id)
    """
    result = _session_results.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")

    n_cities = len(result.city_names)
    total_days = result.actual_S.shape[1]
    real_pops = np.array(result.city_populations, dtype=float)
    n_people = result.n_people_per_city
    scale = real_pops / n_people

    if level == "system":
        # Aggregate time series
        return {
            "level": "system",
            "days": list(range(total_days)),
            "actual": {
                "S": [int(np.sum(result.actual_S[:, d] * scale)) for d in range(total_days)],
                "E": [int(np.sum(result.actual_E[:, d] * scale)) for d in range(total_days)],
                "I": [int(np.sum(result.actual_I[:, d] * scale)) for d in range(total_days)],
                "R": [int(np.sum(result.actual_R[:, d] * scale)) for d in range(total_days)],
                "D": [int(np.sum(result.actual_D[:, d] * scale)) for d in range(total_days)],
            },
            "observed": {
                "I": [int(np.sum(result.observed_I[:, d] * scale)) for d in range(total_days)],
                "R": [int(np.sum(result.observed_R[:, d] * scale)) for d in range(total_days)],
                "D": [int(np.sum(result.observed_D[:, d] * scale)) for d in range(total_days)],
            }
        }

    elif level == "city":
        if not entity_id:
            raise HTTPException(status_code=400, detail="entity_id required for city level")

        # Find city index
        try:
            city_idx = result.city_names.index(entity_id)
        except ValueError:
            raise HTTPException(status_code=404, detail=f"City not found: {entity_id}")

        s = scale[city_idx]
        return {
            "level": "city",
            "cityName": entity_id,
            "population": result.city_populations[city_idx],
            "days": list(range(total_days)),
            "actual": {
                "S": [int(result.actual_S[city_idx, d] * s) for d in range(total_days)],
                "E": [int(result.actual_E[city_idx, d] * s) for d in range(total_days)],
                "I": [int(result.actual_I[city_idx, d] * s) for d in range(total_days)],
                "R": [int(result.actual_R[city_idx, d] * s) for d in range(total_days)],
                "D": [int(result.actual_D[city_idx, d] * s) for d in range(total_days)],
            },
            "observed": {
                "I": [int(result.observed_I[city_idx, d] * s) for d in range(total_days)],
                "R": [int(result.observed_R[city_idx, d] * s) for d in range(total_days)],
                "D": [int(result.observed_D[city_idx, d] * s) for d in range(total_days)],
            }
        }

    else:
        raise HTTPException(status_code=400, detail=f"Unknown level: {level}")


# =============================================================================
# Run Server
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
