# ABS-DES Pandemic Simulation: Technical Audit & White Paper

**Prepared:** January 2026
**Scope:** Full code-path audit of `simulation_app/backend/` and its upstream modules (003-006)

---

## 1. System Architecture

The simulation is a **multi-city Agent-Based / Discrete-Event hybrid** (ABS-DES) model that produces dual views of a pandemic: the **ACTUAL** ground truth (true SEIR compartment counts) and the **OBSERVED** view (what the healthcare surveillance system detects).

### Request lifecycle

```
Browser POST /simulate/absdes (JSON parameters)
  -> FastAPI main.py: validate via Pydantic SimulationRequest schema
  -> Spawn background thread (_run_simulation_thread)
    -> simulation.py: run_absdes_simulation()
      -> Load cities from african_cities.csv, filter by country
      -> Build EpidemicScenario from validation_config presets
      -> Compute DES-scale gravity travel matrix
      -> Instantiate N CityDES engines (one per city)
      -> Daily stepping loop (days 1..D):
          for each city: city.step(until=day)          # advance DES
          for each city: city.run_provider_screening()  # healthcare
          apply_travel_coupling_des(...)                # inter-city
          record ACTUAL S/E/I/R from city.{S,E,I,R}
          record OBSERVED from city.{observed_I, observed_R, new_detections_today}
      -> Return DualViewResult
    -> renderer.py: render_all_frames() -> PNGs to disk
  -> SSE progress stream to browser during execution
  -> Browser fetches PNGs by day via GET /frame/{view}/{day}
```

### File inventory

| File | Lines | Role |
|------|-------|------|
| `main.py` | 568 | FastAPI endpoints, session management, background threading |
| `simulation.py` | 449 | Multi-city orchestrator, travel coupling, OBSERVED tracking |
| `city_des_extended.py` | 359 | Per-city DES engine (SimPy + Watts-Strogatz) |
| `renderer.py` | ~280 | Matplotlib PNG frame generation |
| `progress.py` | 142 | Thread-safe SSE progress state |
| `schemas.py` | 70 | Pydantic request/response models |

Upstream dependencies (imported via `sys.path`):

| Module | File | What's used |
|--------|------|-------------|
| `des_system/` | `validation_config.py` | `EpidemicScenario` dataclass, 4 scenario presets |
| `004_multicity/` | `gravity_model.py` | `compute_distance_matrix()` (Haversine) |
| `005_multicity_des/` | `city_des.py` | Origin of `city_des_extended.py` (forked + extended) |

---

## 2. The Person Model

There are no `Person` objects in the current simulator. A person exists as an **integer index** (0 to N-1) into several parallel arrays. This is a deliberate performance trade from module 003, where each person was a full Python object with its own `RuleBasedBehavior` instance. The current representation is ~100x faster at the cost of extensibility.

### 2.1 What constitutes a "person"

A person with index `pid` is fully described by three pieces of state:

| Array | Type | What it stores | Initialized to |
|-------|------|----------------|----------------|
| `_states[pid]` | `int8` | Disease compartment: 0=S, 1=E, 2=I, 3=R | 0 (susceptible) |
| `_provider_advised[pid]` | `bool` | Has this person accepted provider advice? | False |
| `_neighbors[pid]` | `list[int]` | Adjacency list in the social network | From Watts-Strogatz generation |

Plus membership in a set:

| Set | What it tracks |
|-----|----------------|
| `_detected_ever` | PIDs that have been detected by a provider at any point |

There is no age, no sex, no location within the city, no risk group, no occupation, no household membership. Every person is identical except for their network position (who their neighbors are) and their accumulated state (disease stage, advice status, detection history).

### 2.2 Person lifecycle

A person's trajectory through one simulation:

```
t=0:  Created as susceptible (state 0)
      Network neighbors assigned (fixed for entire simulation)

...some day later...

      Contacted by infectious neighbor -> Bernoulli(transmission_prob) succeeds
      state 0 -> 1 (exposed)
      SimPy coroutine _exposed_process(pid) spawned

      Wait Exponential(mean = incubation_days)
      state 1 -> 2 (infectious)
      Coroutine chains into _infectious_process(pid)

      Each day while infectious:
        Isolation check: Bernoulli(base_isolation_prob or advised_isolation_prob)
          If isolating: zero contacts this day, skip to next day
          If not: generate Poisson contacts, attempt transmission to neighbors

      Wait Exponential(mean = infectious_days)
      state 2 -> 3 (recovered, permanent)
      Coroutine terminates. Person is inert for rest of simulation.
```

A person can also be:
- **Screened** by a provider on any day (uniform random from whole population)
- **Detected** if screened while infectious AND discloses (Bernoulli(disclosure_prob))
- **Advised** if screened AND accepts advice (Bernoulli(receptivity))
- **Injected as exposed** from inter-city travel coupling (skips the contact event, enters directly at state 1)

Seed-infected persons at t=0 skip the exposed state entirely -- they start at state 2 (infectious) with an `_infectious_process` coroutine but no preceding `_exposed_process`.

### 2.3 Behavioral dimensions

Each person has exactly two behavioral properties, both Bernoulli probabilities evaluated each day:

**Isolation** (`_is_isolating`, line 298 of `city_des_extended.py`):

```python
prob = advised_isolation_prob if _provider_advised[pid] else base_isolation_prob
isolating_today = random() < prob
```

This is binary: if isolating, the person makes zero contacts that calendar day. If not, they make full contacts at their normal Poisson rate. There is no partial reduction (e.g., wearing a mask reduces transmission probability but doesn't eliminate contacts).

**Disclosure** (checked during screening, line 262):

```python
detected = (_states[pid] == 2) and (random() < disclosure_prob)
```

This is the person's willingness (or ability) to reveal symptoms when a provider asks. It combines symptom awareness, trust in the healthcare system, and test sensitivity into a single probability.

### 2.4 What module 003 had that was lost

Module 003 modeled each person as a `RuleBasedBehavior` object with six behavioral parameters:

| Parameter | Module 003 | Current simulator | Status |
|-----------|-----------|-------------------|--------|
| `disclosure_prob` | Per-person, on the behavior object | Global, same for all people | **Flattened** |
| `receptivity` | Per-person | Global per-city (from medical_services_score) | **Flattened** |
| `base_isolation_prob` | Per-person, default 0.05 | Global, default 0.0 | **Flattened + default changed** |
| `advised_isolation_prob` | Per-person, default 0.40 | Global, default 0.40 | **Flattened** |
| `base_care_prob` | Per-person, default 0.0 | Not modeled | **Dropped** |
| `advised_care_prob` | Per-person, default 0.5 | Not modeled | **Dropped** |

Key differences:

1. **No care-seeking.** In module 003, `seeks_care()` was a behavioral method -- advised persons had a 50% daily probability of actively seeking medical care. This created a pull-based detection pathway (person goes to provider) alongside the push-based pathway (provider screens person). The current simulator only has push-based detection via uniform random screening.

2. **No per-person parameter variation.** In module 003, each `Person` owned its own `RuleBasedBehavior` instance, so in principle each person could have different disclosure/receptivity/isolation probabilities. The current simulator uses a single value per city. This eliminates individual heterogeneity in behavioral response.

3. **Advice was permanent in 003, decays in current.** Module 003's `receive_advice()` set `_provider_advised = True` with no mechanism to revert. The current simulator added `advice_decay_prob` (default 0.05/day, ~20-day half-life), which is more realistic -- people stop complying over time.

4. **No Python object per person.** Module 003 had `Person` objects (from the `social_network` module) with methods like `is_contagious()`, individual disease state tracking, and a behavior strategy pattern. The current simulator replaced all of this with numpy arrays indexed by integer PID, which is necessary for scaling to 5,000+ agents per city across 50+ cities.

### 2.5 Implications for extending the person model

Adding new person-level features requires adding new parallel arrays or modifying the SimPy coroutines:

- **Age/risk groups:** Add `_age_group[pid]` array, use it to modulate `transmission_prob`, `infectious_days`, or IFR per person. Straightforward but requires parameterizing the age distribution.
- **Superspreaders:** Replace uniform `daily_contact_rate` with a per-person rate drawn from a heavy-tailed distribution (e.g., lognormal). Requires `_contact_rate[pid]` array and modifying `_infectious_process`.
- **Care-seeking:** Restore `base_care_prob`/`advised_care_prob` as a daily Bernoulli check during the infectious process. When a person seeks care, they self-report to a provider (detection without waiting for random screening). Requires adding a care-seeking check inside `_infectious_process`'s daily loop.
- **Resource-dependent behavior:** If PPE or test kits run out, a person's `disclosure_prob` could drop (no test available) or `advised_isolation_prob` could decrease (no PPE to safely isolate). This couples person behavior to city-level resource state.

The key architectural constraint is that all person-level state must be representable as arrays indexed by PID. Any feature requiring complex per-person objects (e.g., contact tracing history, household graph, employment status) would need either a separate data structure or a return to the module 003 object-oriented approach at some performance cost.

---

## 3. The CityDES Engine

Each city runs an independent `CityDES` instance -- the core computational unit of the simulation.

### 3.1 State Machine

Four states encoded as `int8` in a numpy array `_states[n_people]`:

```
S (0) -> E (1) -> I (2) -> R (3)
         ^
         |
    transmission    exponential     exponential
    Bernoulli       wait            wait
    p = β/(c·k)    mean = σ        mean = γ⁻¹
```

| Transition | Trigger | Distribution |
|------------|---------|--------------|
| S -> E | Contact with I neighbor, Bernoulli(transmission_prob) | Instantaneous on contact event |
| E -> I | Incubation complete | Exponential(mean = incubation_days) |
| I -> R | Recovery complete | Exponential(mean = infectious_days) |

**No death state.** Mortality is estimated post-hoc via a flat IFR multiplier. No hospitalization compartment exists.

### 3.2 Network

**Watts-Strogatz small-world graph** via NetworkX:

```python
G = nx.watts_strogatz_graph(n_people, k=avg_contacts, p=rewire_prob, seed=random_seed)
```

- Default: n=5000 nodes, k=10 neighbors, p=0.4 rewiring
- Mean degree is exactly k (preserved by construction)
- High clustering + short path lengths (small-world property)
- Degree distribution is narrow (NOT scale-free or power-law)
- Graph is built once and never modified (static network)
- The NetworkX object is discarded; only adjacency lists are retained

### 3.3 Transmission

Each infectious agent runs a SimPy coroutine (`_infectious_process`) that generates contacts as a **Poisson process**:

```
contact_rate = daily_contact_rate * degree(agent)
inter_contact_time ~ Exponential(rate = contact_rate)
```

Per contact:
1. Select a random neighbor uniformly from adjacency list
2. If neighbor is in state S: infect with probability `transmission_prob`
3. Newly exposed agent gets a new `_exposed_process` coroutine

### 3.4 R0 Calibration

The per-contact transmission probability is derived from R0 using the mean-field SIR relationship:

```
γ = 1 / infectious_days
β = R0 × γ
transmission_prob = β / (daily_contact_rate × avg_contacts)
```

| Scenario | R0 | γ | β | transmission_prob |
|----------|-----|-----|-------|-------------------|
| COVID natural | 2.5 | 0.111 | 0.278 | 0.0556 |
| COVID bioattack | 3.5 | 0.111 | 0.389 | 0.0778 |
| Ebola natural | 2.0 | 0.100 | 0.200 | 0.0400 |
| Ebola bioattack | 2.5 | 0.125 | 0.313 | 0.0625 |

**Assumption:** This calibration assumes a well-mixed population. On a clustered Watts-Strogatz network, the effective R0 is typically lower than the mean-field value due to local depletion of susceptibles among clustered contacts. The DES was validated against ODE trajectories in module 005.

### 3.5 Isolation (Behavioral Model)

Each day of the infectious period, agents check whether to isolate:

```python
prob = advised_isolation_prob if provider_advised[agent] else base_isolation_prob
if random() < prob:
    skip all contacts for this calendar day  # binary: full isolation or no isolation
```

- Default `base_isolation_prob = 0.0` (no voluntary isolation)
- Default `advised_isolation_prob = 0.40` (40% daily compliance when advised)
- Isolation is re-rolled each day (not a permanent decision)
- An advised agent transmits at `(1 - 0.40) = 60%` of their uninhibited rate

### 3.6 Provider Screening

`run_provider_screening()` executes two phases per day:

**Phase 1 -- Advice decay:**
Each currently-advised agent loses advice with probability `advice_decay_prob` (default 0.05, meaning ~20-day average compliance).

**Phase 2 -- Random screening:**
```
total_screens = n_providers × screening_capacity
sample = random.sample(population, total_screens)  # without replacement
```

For each screened person:
- **Detection:** If state == I AND Bernoulli(disclosure_prob) succeeds -> detected. PID added to `_detected_ever` set.
- **Advice:** Independently, if not already advised, advice accepted with probability `receptivity`.

Key design choices:
- Screening is **uniform random** from the whole population, not targeted at symptomatic individuals
- Only **infectious** agents (state 2) can be detected; exposed agents are invisible
- Advice is offered to **everyone** screened, regardless of disease state
- Susceptible agents who receive advice will isolate IF they later become infectious (but advice may decay before that happens)

### 3.7 OBSERVED View Construction

The "observed" SEIR is constructed each day from the healthcare system's limited knowledge:

| Compartment | Formula | Source |
|-------------|---------|--------|
| observed_I | Count of `_detected_ever` agents currently in state I | Exact within detected set |
| observed_R | Count of `_detected_ever` agents currently in state R | Exact within detected set |
| observed_E | `new_detections_today × incubation_days` (clamped) | **Heuristic estimate** |
| observed_S | `n_people - obs_I - obs_R - obs_E` | Residual |

The observed_E estimate is deliberately crude -- it approximates "if we found X new cases today, there are probably X × σ exposed people upstream." This reflects the real-world challenge of estimating latent infections from detected cases.

---

## 4. Multi-City Coupling

### 4.1 Gravity Travel Model

Inter-city travel rates follow a gravity model with **DES-scaled populations**:

```
rate[i][j] = scale × (n_people²) / distance[i][j]^α
```

| Parameter | Default | Role |
|-----------|---------|------|
| `gravity_scale` | 0.01 | Absolute coupling magnitude |
| `gravity_alpha` | 2.0 | Distance decay exponent |
| `n_people` | 5000 | Uniform DES population (NOT real city population) |

Distance is Haversine great-circle (Earth radius = 6371 km). The matrix is symmetric with zero diagonal.

**Critical design choice:** All cities use the same DES population (`n_people`) in the gravity formula, erasing real population-size effects on travel volume. A city of 15M and a city of 50K generate identical coupling rates at equal distances. This was intentional to make coupling work at DES scale without producing unrealistically large or small travel flows.

### 4.2 Exposure Injection

Each day, for each city _i_:

```
daily_exposure_i = Σⱼ travelers[j→i] × infection_fraction_j × transmission_factor
exposure_debt_i += daily_exposure_i
if exposure_debt_i >= 1.0:
    inject floor(exposure_debt_i) exposed agents into city_i
    exposure_debt_i -= floor(exposure_debt_i)
```

The exposure debt accumulator handles fractional exposures -- sub-integer daily flows accumulate until they reach a whole person. `transmission_factor` (default 0.3) scales the coupling strength.

### 4.3 Seed Cities

| Scenario type | Seed cities |
|---------------|-------------|
| Natural | Largest city by population in selected country |
| Bioattack | Cairo, Lagos, Nairobi, Kinshasa, Johannesburg (filtered to selected country) |

Initial infections per seed city: `max(1, int(seed_fraction × n_people))` = 10 at defaults.

---

## 5. Catalog of Hardcoded Constants and Magic Numbers

### 5.1 Disease Parameters (Buried in `_build_scenarios`)

| Constant | Value | Location | Not user-configurable |
|----------|-------|----------|----------------------|
| COVID IFR | 0.005 (0.5%) | `simulation.py:228` | Hardcoded per scenario |
| Ebola IFR | 0.50 (50%) | `simulation.py:231` | Hardcoded per scenario |
| Bioattack seed cities | 5 specific cities | `simulation.py:218` | Hardcoded list |
| Pre-symptomatic fraction | 0.22 | `validation_config.py:77` | Applied uniformly to all pathogens |

### 5.2 Receptivity Formula (Buried)

```python
receptivity = 0.2 + 0.6 × (medical_services_score / 100)  # simulation.py:125
```

Maps score [0, 100] to receptivity [0.2, 0.8]. Not configurable.

### 5.3 Provider Count Formula

```python
n_providers = int(provider_density × n_people / 1000)  # simulation.py:322
```

The `/1000` divisor converts "per 1000 population" to absolute count. At defaults: `5.0 × 5000 / 1000 = 25` providers.

### 5.4 Renderer Visual Constants

| Constant | Value | What it controls |
|----------|-------|------------------|
| Figure size | 800×1000 px | Frame dimensions |
| Map/SEIR ratio | 60%/40% | Layout split |
| Marker size range | [8, 200] | City dot size bounds |
| Color normalization floor | 0.1% | Minimum vmax to avoid degenerate coloring |
| SEIR colors | Blue/Orange/Red/Green | S/E/I/R line colors |
| Top cities labeled | 10 | Number of city name annotations |
| Map padding | 2.0 degrees | Extent buffer beyond data bounds |

### 5.5 Unused Code

- `import math` in `city_des_extended.py` -- imported but never called
- `day % 1 == 0` check in `simulation.py:420` -- always true, vestigial reporting interval
- `FLU_LIKE` and `MEASLES_LIKE` scenarios exist in `validation_config.py` but are not importable from the web app

---

## 6. Modularity Assessment

### 6.1 Strengths

| Aspect | Assessment |
|--------|------------|
| CityDES stepping interface | Clean: `step(until)`, `inject_exposed(n)`, property readouts |
| Scenario duck-typing | Any object with `.R0`, `.incubation_days`, `.infectious_days` works |
| Screening decoupled from DES loop | Called externally, not a SimPy process |
| Dual RNG design | Python `random.Random` + NumPy `RandomState`, both seeded |
| Progress callback | Clean function signature, no coupling to SSE implementation |

### 6.2 Weaknesses

| Aspect | Assessment | Impact on extensibility |
|--------|------------|------------------------|
| No state enum | Raw integers `0,1,2,3` scattered throughout | Adding states (H, D, V) requires finding every integer comparison |
| No event hooks | No on_infection, on_recovery, on_detection callbacks | Logging, contact tracing, or custom metrics require core modification |
| Hardcoded SEIR topology | Implicit in coroutine chain | Adding hospitalization requires rewriting `_infectious_process` |
| Static network | Built once, never modified | Cannot model school closures, travel bans, or dynamic contacts |
| No per-agent heterogeneity | Uniform transmission_prob, contact_rate, recovery | No age structure, risk groups, or superspreader modeling |
| `_detected_ever` is O(n) on read | `observed_I`/`observed_R` iterate full set each call | Performance concern at large N with high detection rates |
| `_counts` is positional list | `[0]` for S, `[2]` for I, etc. | Fragile, easy to misindex |

### 6.3 Interfaces

**CityDES public API:**

| Method/Property | Purpose |
|-----------------|---------|
| `step(until)` | Advance DES to given time |
| `inject_exposed(n)` | Add exposed agents (for travel coupling) |
| `run_provider_screening()` | Execute daily screening + advice cycle |
| `S`, `E`, `I`, `R` | Current compartment counts |
| `infection_fraction` | I/N ratio |
| `advised_fraction` | Fraction of population currently advised |
| `observed_I`, `observed_R` | Detected agents by current state |
| `total_detected` | Cumulative detections |
| `new_detections_today` | Detections from most recent screening |

**Missing interfaces:**
- No dynamic network modification
- No agent-level state queries (e.g., "get state of agent 42")
- No event subscription mechanism
- No parameter modification after construction
- No simulation reset (must create new instance)

---

## 7. Key Assumptions & Limitations

### 7.1 Epidemiological

1. **Exponential waiting times**: Both incubation and infectious periods are exponentially distributed. Real diseases have gamma- or Weibull-distributed periods with lower variance. Exponential distributions overweight both very short and very long durations.

2. **No mortality during simulation**: Deaths are estimated post-hoc by multiplying total infections by a flat IFR. There is no removal of dead agents from the population, no reduced contacts from severe illness, and no healthcare capacity effects on mortality.

3. **No age structure**: All agents are identical. In reality, COVID-19 IFR varies ~1000x between age groups (0.001% for children vs. ~10% for 80+).

4. **No waning immunity**: R state is permanent. No reinfection, no vaccination, no immune escape.

5. **Pre-symptomatic fraction is universal**: The 22% pre-symptomatic split from `validation_config.py` is applied to Ebola (where pre-symptomatic transmission is negligible) and COVID equally.

### 7.2 Behavioral

6. **Binary isolation**: Agents either make full contacts or zero contacts. There is no partial contact reduction (e.g., masking, distancing while still active).

7. **Uniform screening**: Providers sample uniformly at random from the entire population. There is no targeted screening of symptomatic individuals, high-risk areas, or contacts of known cases.

8. **No voluntary care-seeking**: The `base_care_prob` and `advised_care_prob` parameters from module 003 were dropped. Agents never seek healthcare on their own -- detection is entirely provider-initiated.

9. **Advice to susceptible agents has no immediate effect**: A susceptible agent who is advised will only benefit if they later become infectious AND the advice hasn't decayed by then.

### 7.3 Structural

10. **Uniform DES population**: All cities run with the same `n_people` regardless of real population (5,000 by default). This erases population-dependent effects: a megacity of 15M and a town of 50K have identical internal epidemic dynamics.

11. **Static contact network**: The Watts-Strogatz graph is built once and never changes. School closures, workplace shutdowns, travel restrictions, and behavioral changes that alter the network structure are not representable.

12. **Narrow degree distribution**: Watts-Strogatz produces near-uniform degree. Real contact networks are heavy-tailed (some individuals have many more contacts than average), which accelerates early epidemic growth and creates superspreader dynamics.

13. **Single stochastic realization**: Each simulation run is a single sample path. No Monte Carlo averaging or confidence intervals are computed.

14. **No spatial structure within cities**: The contact network is purely topological. There is no geographic clustering of contacts within a city.

---

## 8. Lineage: What Was Lost From Upstream Modules

| Feature | Module 003 | Module 004 | Module 005 | Simulation App | Status |
|---------|-----------|-----------|-----------|---------------|--------|
| Care-seeking behavior | base_care_prob=0.0, advised_care_prob=0.5 | -- | -- | -- | **Dropped** |
| Supply chain (PPE, reagents) | Full SupplyChain model | -- | -- | -- | **Dropped** |
| Hospitalization + mortality | IntelligentDiseaseModel | -- | -- | Post-hoc IFR | **Simplified** |
| Transmission event logging | Per-contact records | -- | -- | -- | **Dropped** |
| Per-agent Python objects | Full Person class | -- | Numpy arrays | Numpy arrays | **Replaced for perf** |
| Surveillance accuracy metrics | HealthcareSystem class | -- | -- | -- | **Dropped** |
| ODE fast-mode | -- | scipy.integrate.odeint | Validation only | -- | **Not exposed** |
| R0 modulation by medical score | -- | isolation_effect param | Exists but unused | -- | **Buried** |
| Monte Carlo runs | 50 runs | -- | 5 runs | 1 run | **Reduced** |
| FLU_LIKE / MEASLES_LIKE | -- | -- | Exists | Not imported | **Orphaned** |
| Advice permanence | Permanent | -- | Decay added | Decay (0.05/day) | **Improved** |

---

## 9. Next Steps: Resource Scarcity & Operational Decision Support

The OBSERVED view already provides the healthcare system's information base -- partial, delayed, and noisy knowledge of the true epidemic. This creates a natural foundation for three operational decision-support layers.

### 9.1 Short-Term Forecasting (Next 3-7 Days)

**Problem:** Given the OBSERVED time series up to today, forecast the OBSERVED trajectory for the next few days to support resource pre-positioning.

**Approach: Bayesian nowcasting + simple projection**

The OBSERVED data gives us `obs_I(t)` and `obs_R(t)` per city. From these we can estimate:

- **Detection growth rate:** `r_obs(t) = Δobs_I(t) / obs_I(t-1)` (daily growth of detected infectious). Smooth with a 3-day moving average to reduce noise.
- **Naive projection:** `obs_I(t+k) ≈ obs_I(t) × (1 + r_obs)^k` for k = 1..7. This assumes constant growth rate, which is reasonable for short horizons.
- **Detection-adjusted forecast:** Since OBSERVED lags ACTUAL by approximately `incubation_days + detection_delay`, the true epidemic is further ahead. Multiply the naive forecast by a **detection multiplier** derived from the cumulative detection rate: `actual_forecast ≈ obs_forecast / detection_rate`.

**Implementation in the simulation:**

```python
# Per-city, per-day (computed in simulation loop or post-hoc)
class CityForecast:
    obs_growth_rate: float          # smoothed r_obs
    obs_I_forecast: list[float]     # next 7 days projected obs_I
    actual_I_estimate: list[float]  # adjusted by detection rate
    confidence_band: tuple[float, float]  # ± based on stochastic variance
```

The forecast can be computed **entirely from the OBSERVED data** -- no access to ACTUAL required. This mirrors real-world constraints where decision-makers only see surveillance data.

**Uncertainty quantification:** Run a lightweight analytical model (e.g., branching process approximation) using the observed R_eff estimate to generate confidence intervals. Alternatively, track the forecast error over previous days to calibrate empirical prediction intervals.

### 9.2 Optimal Healthcare Worker Allocation

**Problem:** Given N total healthcare workers (providers) distributed across C cities, where should they be deployed tomorrow to maximize detection impact?

**Formulation: Marginal detection value**

Each provider in city _i_ screens `screening_capacity` people per day. The expected detections per provider in city _i_ is:

```
E[detections_i] = screening_capacity × (I_i / N_i) × disclosure_prob
```

where `I_i / N_i` is the infection fraction. But we don't know `I_i` -- we only know `obs_I_i`.

**Using the forecast from 8.1:**

```
estimated_I_i = obs_I_i / detection_rate_i    # adjust for under-detection
marginal_value_i = screening_capacity × (estimated_I_i / N_i) × disclosure_prob
```

**Allocation algorithm:**

1. Compute `marginal_value_i` for each city using the detection-adjusted infection estimate
2. Sort cities by marginal value descending
3. Allocate providers greedily: assign each available provider to the city where the next provider adds the most expected detections
4. Apply a **minimum coverage constraint**: ensure every city with `obs_I > 0` retains at least 1 provider (prevents blind spots)
5. Apply a **transport constraint**: limit daily reallocation to X% of total providers (people can't teleport between cities)

**Refinement -- value of information:**

A more sophisticated version weighs not just expected detections, but the **information value** of detection. A city with high uncertainty (few detections, large gap between observed and estimated) benefits more from additional screening than a well-characterized city. This creates an explore/exploit tradeoff:

```
allocation_score_i = α × marginal_detections_i + (1-α) × uncertainty_i
```

where `uncertainty_i` could be the coefficient of variation of the forecast or the ratio of estimated-to-observed infections.

### 9.3 PPE and Test Kit Distribution

**Problem:** A finite stockpile of PPE (masks, gloves, gowns) and test kits must be distributed across cities. Supply is replenished at a known rate. Where should supplies go?

**Formulation: Consumption-weighted allocation with forecasting**

PPE consumption per city per day is proportional to:
- Number of active providers × screenings per provider (for test kits)
- Number of detected infectious × contacts per isolation visit (for PPE)
- Number of providers × provider-self-protection (for PPE)

**Model:**

```python
@dataclass
class CitySupplyState:
    ppe_stock: float              # current PPE units
    test_kit_stock: float         # current test kits
    ppe_consumption_rate: float   # units/day (from provider count + detected cases)
    test_consumption_rate: float  # kits/day (= n_providers × screening_capacity)
    days_until_stockout: float    # stock / consumption_rate
```

**Allocation algorithm:**

1. **Forecast consumption** for each city over the next 7 days using the epidemic forecast from 8.1 (more infections -> more PPE needed for isolation support)
2. **Compute days-to-stockout** per city: `days_to_stockout_i = current_stock_i / forecast_consumption_i`
3. **Priority score:** Cities with fewer days-to-stockout AND higher infection trajectories get priority
4. **Distribute incoming supply** proportional to:

```
allocation_i = replenishment_total × (priority_score_i / Σ priority_scores)
```

With constraints:
- No city receives more than `max_storage_capacity`
- Minimum allocation to any city with active cases
- Transport cost penalty for remote cities (using the existing distance matrix)

**Integration with worker allocation (8.2):**

Provider allocation and supply allocation are coupled: sending more providers to a city increases both detection AND supply consumption. The optimal joint allocation minimizes total expected undetected-infection-days subject to supply constraints:

```
minimize  Σ_i  (actual_I_i - detected_I_i) × days
subject to:
  Σ_i providers_i = total_providers
  supply_consumed_i(providers_i) ≤ supply_available_i + incoming_supply_i
  providers_i ≥ min_coverage_i  (for cities with known cases)
```

This is a constrained optimization that can be solved daily as a linear program (LP) if the relationships are linearized, or as a simple greedy heuristic for the initial implementation.

### 9.4 Implementation Roadmap

**Layer 1 -- Forecasting (extend simulation.py):**
- Add a `ForecastEngine` class that consumes the daily OBSERVED time series
- Compute per-city growth rates, detection rates, and 7-day projections
- Store forecasts in `DualViewResult` or a parallel data structure
- Display forecast cone on the SEIR chart in the frontend

**Layer 2 -- Worker allocation (new module):**
- Add `ResourceAllocator` class with `optimize_providers(city_states, total_providers) -> allocation`
- Add `n_total_providers` and `reallocation_fraction` to `SimulationParams`
- In the daily loop, call the allocator before `run_provider_screening()` and redistribute `n_providers` per city
- Track allocation decisions in the result for visualization

**Layer 3 -- Supply chain (new module):**
- Add `SupplyChainManager` class tracking per-city stocks, consumption, replenishment
- Add `initial_ppe_stock`, `initial_test_kits`, `replenishment_rate` to `SimulationParams`
- In the daily loop, consume supplies during screening, replenish at fixed rate, and reallocate
- Providers who lack supplies cannot screen (capacity drops to zero) -- this creates the scarcity feedback loop
- Track stockout events and their epidemiological impact

**The key feedback loop to model:**

```
Low supply -> fewer screenings -> fewer detections ->
  slower forecast updates -> worse allocation decisions ->
    undetected spread -> higher actual infections ->
      more supply needed (when finally detected) -> stockout
```

This vicious cycle is the core dynamic that resource-constrained healthcare systems face during pandemics. The simulation can quantify how much forecasting quality and allocation optimization reduce this cycle's severity compared to static/uniform resource distribution.
