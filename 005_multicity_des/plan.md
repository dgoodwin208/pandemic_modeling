# 005: Multi-City DES — Plan

## What

Replace the ODE-per-city approach (module 004) with ABS-DES per city for the
multi-city metapopulation simulation. The inter-city gravity coupling remains
identical — only the within-city model changes from a continuous ODE to a
discrete-event network simulation.

## Why

Module 004 used a heuristic (`R_eff = R0 * (1 - isolation_effect * score/100)`)
to map health system capacity into SEIR parameters. This works for a single
intervention dimension, but becomes increasingly fragile as interventions
compound:

- Adding providers requires a new heuristic mapping
- Adding behavioral dynamics requires another mapping
- Adding supply chain effects requires yet another
- These heuristics interact in hard-to-predict ways

The ABS-DES approach avoids this entirely. Interventions (providers, behavioral
nudges, supply constraints) are modeled as agent behaviors. Their effect on
transmission **emerges from simulation**, not from parameter formulas. Module 003
already demonstrated this for providers in a single city.

### Computational feasibility (benchmarked)

| N per city | Time/city | 51 cities (Nigeria) | 443 cities (Africa) |
|-----------|-----------|--------------------|--------------------|
| 1,000     | 0.11s     | 5s                 | 47s                |
| 5,000     | 0.50s     | 25s                | 3.7 min            |
| 10,000    | 1.02s     | 52s                | 7.5 min            |

Even the full 443-city Africa simulation at N=5,000 takes under 4 minutes
sequential. The ODE speed advantage no longer justifies the heuristic
complexity cost.

## Architecture

### Stepping DES for one city (`city_des.py`)

A new, minimal DES class designed for day-by-day stepping:

- **CityDES(n_people, scenario, ...)**: Creates SimPy environment,
  Watts-Strogatz social network, SEIR agent states
- **step(until)**: Advances SimPy env to a given day (supports pause/resume)
- **inject_exposed(n)**: External seeding from inter-city travel — picks
  random susceptible agents and starts their E->I->R disease progression.
  This is how the inter-city coupling feeds into the DES.
- **S, E, I, R, infection_fraction**: State readouts

Disease parameters are derived from `EpidemicScenario` using the same
`beta = transmission_prob * daily_contact_rate * avg_contacts` mapping
validated in modules 001-003.

**Why a new class instead of wrapping the existing AgentSimulation**: The
existing simulation is designed to run-to-completion with monitoring, supply
chains, and behavior strategies. Refactoring it for day-by-day stepping risks
breaking validated behavior. A minimal DES that captures only epidemic network
dynamics is cleaner, self-contained, and independently validatable. Following
the "regenerate the brick" philosophy.

### Multi-city coupling loop (`multicity_des_sim.py`)

Same daily loop as module 004, but with DES cities:

```
for each day:
    1. Advance each city's DES by 1 day (env.run(until=day))
    2. Read infection fractions from each city
    3. Compute inter-city coupling (gravity model, same formula)
    4. Inject new exposures into each city (stochastic rounding)
    5. Record state snapshot
```

The coupling layer is model-agnostic — it only needs `infection_fraction` from
each city and `inject_exposed(n)` to feed in new exposures. This means we could
mix ODE and DES cities in the same simulation (hybrid multi-scale) if needed.

### Reused from module 004

- `gravity_model.py` — Haversine distance + gravity travel matrix
- `city.py` — CityState data loading from african_cities.csv (for
  populations, coordinates; DES creates its own agent population)
- `validation_config.py` — `COVID_LIKE` epidemic scenario

### Key design decisions

1. **Stochastic rounding for fractional exposures**: The gravity coupling
   produces continuous values (e.g., 2.7 new exposures). DES needs discrete
   agents. We use stochastic rounding: `floor(n) + Bernoulli(n - floor(n))`,
   preserving the expected value.

2. **Uniform R0 for validation**: The first figure uses `isolation_effect=0`
   (uniform R0 across all cities) so we get an apples-to-apples ODE-vs-DES
   comparison. Health system modulation comes later via provider agents.

3. **N=5,000 per city**: Validated in modules 001-003 as sufficient to capture
   epidemic dynamics. Curves converge to ODE at large N.

4. **10 Monte Carlo runs**: At ~2.5s per full 5-city run, 10 runs take ~25s
   and produce a meaningful stochastic envelope.

## Phased implementation

### Phase 1 (this step): Validate DES coupling matches ODE

- Build `city_des.py` with stepping interface
- Build `multicity_des_sim.py` with coupling loop
- Produce comparison figure: ODE vs DES for 5 demo cities
- Confirm wave propagation timing and peak heights match within noise

### Phase 2 (next): Nigeria at scale

- Run all 51 Nigerian cities with DES
- Add provider agents (from module 003) per city
- Provider density proportional to `medical_services_score`
- Heterogeneous outcomes emerge from agent behavior, not heuristics

### Phase 3 (future): All of Africa

- 443 cities, parallelized with multiprocessing
- Monte Carlo ensembles with confidence intervals
- Travel restriction and intervention scenarios

## Validation figure (Phase 1)

One figure with 5 demo cities (Cairo, Lagos, Nairobi, Johannesburg, Kinshasa):

- ODE multi-city infection curves as **solid lines** (from module 004 code)
- DES multi-city mean infection curves as **dashed lines** (mean of 10 MC runs)
- DES stochastic envelope as **shaded bands** (+/- 1 standard deviation)
- Same colors per city, same configuration (uniform R0, gravity coupling)

If the dashed lines track the solid lines, we've validated that the DES
coupling produces equivalent multi-city dynamics — and we're ready to add
interventions that emerge from agent behavior rather than ODE heuristics.
