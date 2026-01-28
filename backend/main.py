"""
AI-Augmented Pandemic Response Model - Backend API
FastAPI server with SEIR epidemic modeling and intervention simulations
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import numpy as np
from enum import Enum

app = FastAPI(
    title="Pandemic Response Model API",
    description="SEIR epidemic modeling with AI intervention parameters for African Union countries",
    version="0.1.0"
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Data Models
# =============================================================================

class DiseaseScenario(str, Enum):
    COVID_LIKE = "covid-like"
    INFLUENZA = "influenza"
    SARS_LIKE = "sars-like"
    NOVEL = "novel"


class InterventionParams(BaseModel):
    """Parameters for AI-powered interventions"""
    contact_trace_efficacy: float = Field(0.3, ge=0, le=1, description="Probability of successful contact trace")
    time_to_contact: float = Field(48, ge=1, le=168, description="Hours from positive test to first contact")
    quarantine_compliance: float = Field(0.5, ge=0, le=1, description="Proportion complying with quarantine")
    symptom_reporting: float = Field(0.3, ge=0, le=1, description="Proportion reporting symptoms promptly")
    mobile_testing_coverage: float = Field(0.1, ge=0, le=1, description="Population coverage of mobile testing")


class SimulationRequest(BaseModel):
    """Request parameters for epidemic simulation"""
    population: int = Field(100_000_000, gt=0)
    scenario: DiseaseScenario = DiseaseScenario.COVID_LIKE
    days: int = Field(180, ge=1, le=730)
    initial_infected: int = Field(1000, ge=1)
    baseline_params: InterventionParams = InterventionParams()
    ai_params: Optional[InterventionParams] = None


class CountryData(BaseModel):
    """Country information with supply chain data"""
    id: str
    name: str
    lat: float
    lng: float
    population: int
    supply_hubs: int
    testing_facilities: int
    hospital_beds: Optional[int] = None
    icu_beds: Optional[int] = None


class SimulationResult(BaseModel):
    """Single day simulation result"""
    day: int
    susceptible: float
    exposed: float
    infected: float
    recovered: float
    deaths: float
    cumulative_cases: float
    cumulative_deaths: float
    daily_cases: float
    daily_deaths: float
    r_eff: float


# =============================================================================
# Disease Parameters
# =============================================================================

DISEASE_PARAMS = {
    DiseaseScenario.COVID_LIKE: {
        "name": "COVID-like (Respiratory)",
        "R0": 2.5,
        "incubation_days": 5,
        "infectious_days": 10,
        "ifr": 0.01,
    },
    DiseaseScenario.INFLUENZA: {
        "name": "Pandemic Influenza",
        "R0": 1.8,
        "incubation_days": 2,
        "infectious_days": 5,
        "ifr": 0.002,
    },
    DiseaseScenario.SARS_LIKE: {
        "name": "SARS-like (High Severity)",
        "R0": 2.0,
        "incubation_days": 4,
        "infectious_days": 14,
        "ifr": 0.1,
    },
    DiseaseScenario.NOVEL: {
        "name": "Novel Pathogen X",
        "R0": 3.5,
        "incubation_days": 7,
        "infectious_days": 12,
        "ifr": 0.05,
    },
}


# =============================================================================
# African Union Country Data (placeholder - replace with your database)
# =============================================================================

AFRICAN_COUNTRIES: List[CountryData] = [
    CountryData(id="DZA", name="Algeria", lat=28.0, lng=3.0, population=44_600_000, supply_hubs=3, testing_facilities=12),
    CountryData(id="EGY", name="Egypt", lat=26.8, lng=30.8, population=102_300_000, supply_hubs=5, testing_facilities=18),
    CountryData(id="NGA", name="Nigeria", lat=9.1, lng=8.7, population=206_100_000, supply_hubs=4, testing_facilities=15),
    CountryData(id="ETH", name="Ethiopia", lat=9.1, lng=40.5, population=114_900_000, supply_hubs=2, testing_facilities=8),
    CountryData(id="ZAF", name="South Africa", lat=-30.6, lng=22.9, population=59_300_000, supply_hubs=6, testing_facilities=22),
    CountryData(id="KEN", name="Kenya", lat=-0.0, lng=38.0, population=53_800_000, supply_hubs=3, testing_facilities=10),
    CountryData(id="TZA", name="Tanzania", lat=-6.4, lng=34.9, population=59_700_000, supply_hubs=2, testing_facilities=7),
    CountryData(id="UGA", name="Uganda", lat=1.4, lng=32.3, population=45_700_000, supply_hubs=2, testing_facilities=6),
    CountryData(id="GHA", name="Ghana", lat=7.9, lng=-1.0, population=31_100_000, supply_hubs=2, testing_facilities=8),
    CountryData(id="MOZ", name="Mozambique", lat=-18.7, lng=35.5, population=31_300_000, supply_hubs=1, testing_facilities=5),
    CountryData(id="AGO", name="Angola", lat=-11.2, lng=17.9, population=32_900_000, supply_hubs=2, testing_facilities=6),
    CountryData(id="MAR", name="Morocco", lat=31.8, lng=-7.1, population=36_900_000, supply_hubs=3, testing_facilities=14),
    CountryData(id="SDN", name="Sudan", lat=12.9, lng=30.2, population=43_800_000, supply_hubs=1, testing_facilities=4),
    CountryData(id="COD", name="DR Congo", lat=-4.0, lng=21.8, population=89_600_000, supply_hubs=2, testing_facilities=6),
    CountryData(id="SEN", name="Senegal", lat=14.5, lng=-14.5, population=16_700_000, supply_hubs=2, testing_facilities=7),
    CountryData(id="RWA", name="Rwanda", lat=-1.9, lng=29.9, population=13_000_000, supply_hubs=1, testing_facilities=5),
    CountryData(id="TUN", name="Tunisia", lat=34.0, lng=9.5, population=11_800_000, supply_hubs=2, testing_facilities=9),
    CountryData(id="ZMB", name="Zambia", lat=-13.1, lng=27.8, population=18_400_000, supply_hubs=1, testing_facilities=4),
    CountryData(id="ZWE", name="Zimbabwe", lat=-19.0, lng=29.2, population=14_900_000, supply_hubs=1, testing_facilities=4),
    CountryData(id="CMR", name="Cameroon", lat=7.4, lng=12.4, population=26_500_000, supply_hubs=2, testing_facilities=6),
]


# =============================================================================
# SEIR Model Implementation
# =============================================================================

def calculate_intervention_effect(params: InterventionParams) -> float:
    """
    Calculate the intervention multiplier that reduces transmission.
    
    The effect is modeled as a weighted combination of intervention parameters,
    each contributing to reducing the effective reproduction number.
    
    Weights are based on literature estimates:
    - Contact tracing: ~30% reduction potential (Ferretti et al., 2020)
    - Time to contact: ~20% reduction potential (faster = better)
    - Quarantine compliance: ~25% reduction potential (Peak et al., 2020)
    - Symptom reporting: ~15% reduction potential
    - Mobile testing: ~10% additional reduction
    """
    effect = (
        params.contact_trace_efficacy * 0.30 +
        (1 - params.time_to_contact / 72) * 0.20 +
        params.quarantine_compliance * 0.25 +
        params.symptom_reporting * 0.15 +
        params.mobile_testing_coverage * 0.10
    )
    return max(0.2, 1 - effect)  # Floor at 80% reduction


def run_seir_simulation(
    population: int,
    R0: float,
    incubation_days: float,
    infectious_days: float,
    ifr: float,
    days: int,
    initial_infected: int,
    intervention_params: InterventionParams,
) -> List[SimulationResult]:
    """
    Run SEIR epidemic simulation with intervention effects.
    
    Compartments:
    - S: Susceptible
    - E: Exposed (infected but not yet infectious)
    - I: Infectious
    - R: Recovered
    - D: Dead
    
    Parameters are modified by intervention efficacy.
    """
    # Calculate rates
    beta = R0 / infectious_days  # Transmission rate
    sigma = 1 / incubation_days   # Rate E -> I
    gamma = 1 / infectious_days   # Rate I -> R/D
    
    # Apply intervention effect
    intervention_multiplier = calculate_intervention_effect(intervention_params)
    effective_beta = beta * intervention_multiplier
    
    # Initialize compartments
    S = float(population - initial_infected)
    E = 0.0
    I = float(initial_infected)
    R = 0.0
    D = 0.0
    cum_cases = float(initial_infected)
    cum_deaths = 0.0
    
    results = []
    
    for day in range(days + 1):
        # Calculate transitions (Euler method - could upgrade to RK4)
        new_exposed = (effective_beta * S * I) / population
        new_infected = sigma * E
        new_recovered = gamma * I * (1 - ifr)
        new_deaths = gamma * I * ifr
        
        # Update compartments
        S -= new_exposed
        E += new_exposed - new_infected
        I += new_infected - new_recovered - new_deaths
        R += new_recovered
        D += new_deaths
        cum_cases += new_infected
        cum_deaths += new_deaths
        
        # Calculate effective R
        r_eff = (effective_beta / gamma) * (S / population) if population > 0 else 0
        
        results.append(SimulationResult(
            day=day,
            susceptible=max(0, S),
            exposed=max(0, E),
            infected=max(0, I),
            recovered=max(0, R),
            deaths=max(0, D),
            cumulative_cases=cum_cases,
            cumulative_deaths=cum_deaths,
            daily_cases=max(0, new_infected),
            daily_deaths=max(0, new_deaths),
            r_eff=max(0, r_eff),
        ))
    
    return results


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/")
async def root():
    return {
        "name": "Pandemic Response Model API",
        "version": "0.1.0",
        "endpoints": ["/simulate", "/countries", "/scenarios"]
    }


@app.get("/scenarios")
async def get_scenarios() -> Dict[str, Any]:
    """Get available disease scenarios and their parameters"""
    return {
        scenario.value: {
            **params,
            "id": scenario.value
        }
        for scenario, params in DISEASE_PARAMS.items()
    }


@app.get("/countries")
async def get_countries() -> List[CountryData]:
    """Get all African Union countries with supply chain data"""
    return AFRICAN_COUNTRIES


@app.get("/countries/{country_id}")
async def get_country(country_id: str) -> CountryData:
    """Get a specific country by ID"""
    for country in AFRICAN_COUNTRIES:
        if country.id == country_id:
            return country
    raise HTTPException(status_code=404, detail=f"Country {country_id} not found")


@app.post("/simulate")
async def run_simulation(request: SimulationRequest) -> Dict[str, Any]:
    """
    Run epidemic simulation comparing baseline vs AI-augmented response.
    
    Returns both simulation trajectories and summary statistics.
    """
    disease = DISEASE_PARAMS[request.scenario]
    
    # Run baseline simulation
    baseline_results = run_seir_simulation(
        population=request.population,
        R0=disease["R0"],
        incubation_days=disease["incubation_days"],
        infectious_days=disease["infectious_days"],
        ifr=disease["ifr"],
        days=request.days,
        initial_infected=request.initial_infected,
        intervention_params=request.baseline_params,
    )
    
    # Run AI-augmented simulation if params provided
    ai_results = None
    if request.ai_params:
        ai_results = run_seir_simulation(
            population=request.population,
            R0=disease["R0"],
            incubation_days=disease["incubation_days"],
            infectious_days=disease["infectious_days"],
            ifr=disease["ifr"],
            days=request.days,
            initial_infected=request.initial_infected,
            intervention_params=request.ai_params,
        )
    
    # Calculate summary statistics
    baseline_peak = max(r.infected for r in baseline_results)
    baseline_total_deaths = baseline_results[-1].cumulative_deaths
    
    summary = {
        "baseline": {
            "peak_infected": baseline_peak,
            "peak_day": next(i for i, r in enumerate(baseline_results) if r.infected == baseline_peak),
            "total_cases": baseline_results[-1].cumulative_cases,
            "total_deaths": baseline_total_deaths,
        }
    }
    
    if ai_results:
        ai_peak = max(r.infected for r in ai_results)
        ai_total_deaths = ai_results[-1].cumulative_deaths
        
        summary["ai_augmented"] = {
            "peak_infected": ai_peak,
            "peak_day": next(i for i, r in enumerate(ai_results) if r.infected == ai_peak),
            "total_cases": ai_results[-1].cumulative_cases,
            "total_deaths": ai_total_deaths,
        }
        summary["comparison"] = {
            "peak_reduction_pct": (1 - ai_peak / baseline_peak) * 100 if baseline_peak > 0 else 0,
            "mortality_reduction_pct": (1 - ai_total_deaths / baseline_total_deaths) * 100 if baseline_total_deaths > 0 else 0,
            "lives_averted": baseline_total_deaths - ai_total_deaths,
        }
    
    return {
        "scenario": {
            "id": request.scenario.value,
            **disease
        },
        "population": request.population,
        "days": request.days,
        "baseline": [r.model_dump() for r in baseline_results],
        "ai_augmented": [r.model_dump() for r in ai_results] if ai_results else None,
        "summary": summary,
    }


@app.post("/simulate/sensitivity")
async def run_sensitivity_analysis(
    request: SimulationRequest,
    parameter: str = "contact_trace_efficacy",
    values: List[float] = [0.2, 0.4, 0.6, 0.8, 1.0]
) -> Dict[str, Any]:
    """
    Run sensitivity analysis varying a single intervention parameter.
    
    Useful for understanding which interventions have the most impact.
    """
    if not hasattr(InterventionParams, parameter.replace("_", "")):
        # Check with underscores
        test_params = InterventionParams()
        if not hasattr(test_params, parameter):
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid parameter: {parameter}"
            )
    
    disease = DISEASE_PARAMS[request.scenario]
    results = []
    
    for value in values:
        # Create params with varied parameter
        params_dict = request.baseline_params.model_dump()
        params_dict[parameter] = value
        params = InterventionParams(**params_dict)
        
        sim_results = run_seir_simulation(
            population=request.population,
            R0=disease["R0"],
            incubation_days=disease["incubation_days"],
            infectious_days=disease["infectious_days"],
            ifr=disease["ifr"],
            days=request.days,
            initial_infected=request.initial_infected,
            intervention_params=params,
        )
        
        peak = max(r.infected for r in sim_results)
        total_deaths = sim_results[-1].cumulative_deaths
        
        results.append({
            "parameter_value": value,
            "peak_infected": peak,
            "total_deaths": total_deaths,
            "total_cases": sim_results[-1].cumulative_cases,
        })
    
    return {
        "parameter": parameter,
        "values": values,
        "results": results,
    }


# =============================================================================
# Run Server
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
