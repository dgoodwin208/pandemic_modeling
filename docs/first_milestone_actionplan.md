# First Milestone: DES ↔ SEIR Convergence Validation

**Goal**: Show that the mid-scale DES simulation produces epidemic curves that converge to the SEIR differential equation solution when run at sufficient N with multiple Monte Carlo iterations.

**Validation artifact**: A plot with smooth SEIR ODE curves overlaid on a scatter cloud of DES Monte Carlo runs, showing convergence.

---

## The Three Scales

| Scale | Population | Method | Fidelity |
|-------|-----------|--------|----------|
| **Large** | >100,000 | SEIR differential equations | Smooth deterministic curves |
| **Mid** | 1,000 - 100,000 | DES + social network, probability-based agents | Stochastic, converges to SEIR at large N |
| **Small** | <1,000 | Agent-based with intelligent actors | High interpretability, theory-of-mind |

**This milestone validates the Mid ↔ Large bridge.** Once we can trust the DES produces SEIR-consistent dynamics, we can use either as a reference frame for small-scale intelligent simulations.

---

## What Exists Today

| Component | Status | Location |
|-----------|--------|----------|
| SEIR ODE solver | Working | `notebooks/seir_ai_interventions.ipynb` - `SEIRModel` class using scipy `odeint` |
| DES engine | Working | `des_system/des_core.py` - `Environment`, `Resource`, event scheduling |
| Social network | Working | `des_system/social_network.py` - Watts-Strogatz small-world graph |
| Disease state machine | Working | `des_system/disease_model.py` - S→E→I→Sy→H/R/D progression |
| Simulation runner | Working | `des_system/simulation.py` - `run_simulation()` with daily snapshots |
| Daily time-series | Working | `SimulationResult.daily_snapshots` - state counts per day |
| Supply chain | Working but **not needed** for this milestone |

---

## The Parameter Mapping Problem

This is the core intellectual challenge. The two models use different parameterizations:

### SEIR ODE (from notebook)

```
dS/dt = -β × S × I / N
dE/dt =  β × S × I / N - σ × E
dI/dt =  σ × E - γ × I
dR/dt =  γ × I

β = R₀ × γ          (transmission rate, derived)
σ = 1 / incubation   (E→I rate)
γ = 1 / infectious    (I→R rate)
```

Three free parameters: **R₀**, **incubation_days**, **infectious_days**

### DES (from config.py)

```
transmission_prob:   0.15    # Per-contact probability
daily_contact_rate:  0.5     # Fraction of contacts interacted with daily
avg_contacts:        6       # Network degree (k in Watts-Strogatz)
exposure_period:     3.0     # Days in EXPOSED
infectious_period:   2.0     # Days INFECTIOUS (pre-symptomatic)
symptomatic_period:  7.0     # Days SYMPTOMATIC
```

Five+ free parameters, plus network topology effects.

### The Bridge

In a well-mixed population (which a Watts-Strogatz network approximates at large N with sufficient rewiring), the DES effective transmission rate should be:

```
β_DES ≈ transmission_prob × daily_contact_rate × avg_contacts
```

And the SEIR "infectious period" maps to the **total contagious time** in the DES:

```
SEIR infectious_days ≈ DES infectious_period + symptomatic_period
                     = 2.0 + 7.0 = 9.0 days
```

So the mapping is:

| SEIR Parameter | Formula | DES Source |
|---------------|---------|------------|
| σ (E→I rate) | 1 / exposure_period | `config.disease.exposure_period` |
| γ (I→R rate) | 1 / (infectious_period + symptomatic_period) | Sum of contagious durations |
| β (transmission) | transmission_prob × daily_contact_rate × avg_contacts | Product of three config values |
| R₀ (derived) | β / γ | Emergent from above |

**But**: Network topology breaks the well-mixed assumption. The Watts-Strogatz network has clustering and short path lengths, so the effective β will differ from the naive product. This is exactly what the validation will measure.

---

## Action Plan

### Step 1: Extract the SEIR Solver into a Standalone Module

**What**: Pull `SEIRModel`, `DiseaseParams` out of the notebook into `des_system/seir_ode.py`.

**Why**: We need to run the ODE solver programmatically alongside DES runs, not in a notebook.

**Simplification**: Use basic SEIR (S, E, I, R) without the I_u/I_d detection split for this milestone. The detection split is an intervention feature - the baseline epidemic dynamics must match first.

**Deliverable**: `des_system/seir_ode.py` with:
- `SEIRParams` dataclass (R0, incubation_days, infectious_days, population)
- `solve_seir(params, days, initial_infected)` → dict of time-series arrays
- Standalone `if __name__ == "__main__"` that plots a basic SEIR curve

### Step 2: Create a Shared Parameter Set

**What**: A single configuration that can drive both the SEIR ODE and the DES, ensuring they use equivalent parameters.

**Why**: If we tune parameters independently, we're not validating convergence - we're fitting curves. The parameters must be **derived** from the same source of truth.

**Deliverable**: `des_system/validation_config.py` with:
- `ValidationScenario` dataclass holding the shared truth (R0, incubation_days, infectious_days, population, initial_infected)
- `to_seir_params()` → parameters for the ODE solver
- `to_des_config()` → `SimulationConfig` for the DES runner, with transmission_prob, daily_contact_rate, and avg_contacts chosen to produce the target β
- A few preset scenarios (e.g., `COVID_LIKE`, `MEASLES_LIKE`, `FLU_LIKE`)

**Key decision**: Given a target β and avg_contacts, we derive:
```python
transmission_prob = β / (daily_contact_rate × avg_contacts)
```
This lets us hold the network structure (avg_contacts, rewire_prob) fixed and adjust transmission_prob to hit the target R₀.

### Step 3: Build the Monte Carlo DES Runner

**What**: A function that runs the DES N times with different random seeds and collects the time-series from each run.

**Why**: A single DES run is noisy. We need many runs to see that the **mean** converges to the SEIR curve and the **variance** shrinks with population size.

**Deliverable**: `des_system/monte_carlo.py` with:
- `run_monte_carlo(scenario, n_runs, seeds)` → list of per-run daily state counts
- Extracts S, E, I (infectious + symptomatic), R counts per day per run
- Returns structured data ready for plotting
- Progress output (e.g., "Run 5/20 complete")

**Note**: The existing DES tracks daily_snapshots with state counts - we just need to run it repeatedly and collect the results. The DES disease states map to SEIR as:
- S = `susceptible`
- E = `exposed`
- I = `infectious` + `symptomatic` + `hospitalized` (all still "infected" in SEIR terms)
- R = `recovered` + `deceased`

### Step 4: Build the Comparison Plotter

**What**: A script that generates the milestone validation plot.

**Why**: This is the deliverable - the visual proof that the DES converges to SEIR.

**Deliverable**: `des_system/validation_plot.py` that produces:

**Plot 1 - The Money Shot** (SEIR curves + DES scatter):
- Smooth SEIR ODE lines for S(t), E(t), I(t), R(t) as fraction of population
- Scatter points from each DES Monte Carlo run (semi-transparent)
- Mean DES trajectory as a dashed line
- Title showing N, number of runs, R₀

**Plot 2 - Convergence by N** (optional but powerful):
- Run at N = 500, 1000, 5000, 10000
- Show DES variance shrinking toward SEIR curves as N increases
- This visually proves: "DES → SEIR as N → ∞"

**Plot 3 - Key Metrics Comparison** (table or bar chart):
- Peak infection day: SEIR vs DES mean ± std
- Peak infection count: SEIR vs DES mean ± std
- Final attack rate: SEIR vs DES mean ± std
- R₀ effective: SEIR (analytic) vs DES (estimated from early exponential growth)

### Step 5: Run and Iterate

**What**: Actually run the validation and debug the parameter mapping.

**Why**: The naive β mapping will likely not produce perfect convergence due to network topology effects. We may need to:
1. Increase rewire probability (makes network more random / well-mixed)
2. Adjust the effective β by a correction factor
3. Use a larger avg_contacts (more connections ≈ more mixing)

**Deliverable**:
- Run validation at multiple N values
- Document any correction factors needed
- Produce the final validation plots
- Write a brief summary of results in the notebook or docs

---

## State Mapping Reference

| SEIR Compartment | DES DiseaseState(s) | Notes |
|-----------------|---------------------|-------|
| S (Susceptible) | `SUSCEPTIBLE` | Direct 1:1 |
| E (Exposed) | `EXPOSED` | Direct 1:1 |
| I (Infectious) | `INFECTIOUS` + `SYMPTOMATIC` + `HOSPITALIZED` | All three are "infected and not yet resolved" |
| R (Recovered) | `RECOVERED` + `DECEASED` | Both are "removed from transmission" |

### Why Hospitalized maps to I, not R

In the basic SEIR, "I" means "infected and participating in disease dynamics." Hospitalized people are still infected (consuming resources, potentially dying). They're removed from **transmission** but not from **disease burden**. For the transmission-matching validation, we can either:
- Count hospitalized as I (they're still sick)
- Count hospitalized as R (they're isolated from transmission)

The choice depends on whether our DES hospitalized patients can still transmit. Looking at the code: hospitalized patients are removed from the contact network (they're in hospital, not interacting), so they're effectively **removed from transmission** = maps to R for transmission dynamics. But for "active cases" curve matching, they should be counted as I.

**Decision**: For this validation, use two views:
- **Transmission view**: I_DES = INFECTIOUS + SYMPTOMATIC (only those actively transmitting)
- **Burden view**: I_DES = INFECTIOUS + SYMPTOMATIC + HOSPITALIZED (all active cases)

---

## What We're NOT Doing (Yet)

- No supply chain modeling (irrelevant to epidemic curve matching)
- No I_u/I_d detection split (that's an intervention feature, not baseline dynamics)
- No intelligent agents (that's the small-scale milestone)
- No frontend changes
- No multi-city modeling
- No intervention parameters

**This milestone is purely**: Does the stochastic DES produce the same epidemic shape as the deterministic SEIR when parameters match?

---

## Success Criteria

The milestone is achieved when we can show a plot where:

1. **SEIR smooth curves** for S(t), I(t), R(t) are clearly visible
2. **DES scatter cloud** from 10-20 Monte Carlo runs clusters around the SEIR curves
3. **DES mean trajectory** tracks the SEIR curves within reasonable tolerance
4. **Peak timing** (DES mean) is within ~10% of SEIR peak day
5. **Final attack rate** (DES mean) is within ~5% of SEIR final attack rate
6. **Variance decreases** visibly when comparing N=1000 vs N=10000

If the DES consistently overshoots or undershoots the SEIR (systematic bias), that's interesting and we document why (network effects). If it's noisy but centered on the SEIR, we've validated convergence.

---

## File Plan

```
des_system/
├── seir_ode.py           # Step 1: Standalone SEIR ODE solver
├── validation_config.py  # Step 2: Shared parameter mapping
├── monte_carlo.py        # Step 3: Multi-run DES executor
├── validation_plot.py    # Step 4: Comparison plotting
├── (existing files unchanged)
```

All new files. No modifications to existing DES code needed unless we find bugs during validation.

---

## Estimated Complexity

| Step | New Code | Depends On | Risk |
|------|----------|------------|------|
| 1. SEIR solver module | ~80 lines | Nothing (port from notebook) | Low |
| 2. Shared config | ~60 lines | Step 1 | Low |
| 3. Monte Carlo runner | ~60 lines | Step 2 + existing DES | Low |
| 4. Validation plotter | ~120 lines | Steps 1-3 | Low |
| 5. Run and iterate | 0 new code | Steps 1-4 | **Medium** - parameter tuning |

The code is straightforward. The intellectual risk is in Step 5: will the naive parameter mapping produce convergence, or will network topology effects require correction? That's the interesting question this milestone answers.
