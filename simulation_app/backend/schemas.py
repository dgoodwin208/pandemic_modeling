"""
Pydantic request/response models for the FastAPI pandemic simulation endpoints.
"""

from enum import Enum

from pydantic import BaseModel, Field


class DiseaseScenario(str, Enum):
    COVID_NATURAL = "covid_natural"
    COVID_BIOATTACK = "covid_bioattack"
    COVID_RING3 = "covid_ring3"
    EBOLA_NATURAL = "ebola_natural"
    EBOLA_BIOATTACK = "ebola_bioattack"
    EBOLA_RING3 = "ebola_ring3"


class AllocationStrategyType(str, Enum):
    RULE_BASED = "rule_based"
    AI_OPTIMIZED = "ai_optimized"


class ResourceConfig(BaseModel):
    """Supply chain resource configuration."""
    enable_supply_chain: bool = False
    allocation_strategy: AllocationStrategyType = AllocationStrategyType.RULE_BASED
    beds_per_hospital: int = Field(120, ge=1, le=1000)
    beds_per_clinic: int = Field(8, ge=0, le=100)
    ppe_sets_per_facility: int = Field(500, ge=0, le=10000)
    swabs_per_lab: int = Field(1000, ge=0, le=50000)
    reagents_per_lab: int = Field(2000, ge=0, le=100000)
    lead_time_mean_days: float = Field(7.0, ge=1.0, le=60.0)
    continent_vaccine_stockpile: int = Field(0, ge=0, le=10000000)
    continent_pill_stockpile: int = Field(0, ge=0, le=10000000)


class SimulationRequest(BaseModel):
    """Request body for starting a new simulation run."""
    country: str = "Nigeria"
    scenario: DiseaseScenario = DiseaseScenario.COVID_NATURAL
    n_people: int = Field(5000, ge=500, le=50000)
    avg_contacts: int | None = Field(None, ge=2, le=50)
    rewire_prob: float = Field(0.4, ge=0.0, le=1.0)
    daily_contact_rate: float = Field(0.5, ge=0.1, le=1.0)
    transmission_factor: float = Field(0.3, ge=0.01, le=1.0)
    gravity_scale: float = Field(0.01, ge=0.001, le=1.0)
    gravity_alpha: float = Field(2.0, ge=0.5, le=4.0)
    incubation_days: float | None = None
    infectious_days: float | None = None
    r0_override: float | None = None
    seed_fraction: float = Field(0.005, ge=0.0001, le=0.1)
    provider_density: float = Field(5.0, ge=0.0, le=200.0)
    screening_capacity: int = Field(20, ge=1, le=100)
    disclosure_prob: float = Field(0.5, ge=0.0, le=1.0)
    base_isolation_prob: float = Field(0.0, ge=0.0, le=1.0)
    advised_isolation_prob: float = Field(0.40, ge=0.0, le=1.0)
    advice_decay_prob: float = Field(0.05, ge=0.0, le=1.0)
    receptivity_override: float | None = None  # Override per-city medical-score-derived receptivity
    days: int = Field(200, ge=10, le=1000)
    random_seed: int = Field(42)
    detection_memory_days: int = Field(7, ge=0, le=30)
    # Supply chain
    resource_config: ResourceConfig | None = None


class ProgressResponse(BaseModel):
    """SSE progress update sent to the client."""
    phase: str
    current: int
    total: int
    message: str
    eta_seconds: int


class SimulationStartResponse(BaseModel):
    """Response returned when a simulation is started."""
    session_id: str


class ScenarioInfo(BaseModel):
    """Information about a disease scenario preset."""
    id: str
    name: str
    R0: float
    incubation_days: float
    infectious_days: float


class CountryInfo(BaseModel):
    """Information about an available country."""
    name: str
    city_count: int
