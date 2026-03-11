# Peer Review: APR Pandemic Simulation Platform

> **This is an AI-generated peer review**, produced by Claude Code (Opus 4) against the `main` branch at commit [`0ca4131`](https://github.com/danielgoodwin/pandemic_modeling/commit/0ca4131620406fdc2d72a911a7e5f14c440c29da) on March 11, 2026. It is a technical review of the simulation platform included in the HSPA report, intended as a starting point for future builders and technical collaborators. It identifies known limitations, modeling assumptions, and areas for improvement in what is presented here. It is not a substitute for formal domain-expert peer review.

**Reviewer:** Claude (Opus 4), acting as domain expert in computational epidemiology, agent-based modeling, and discrete-event simulation.

**Date:** 2026-03-11

**Scope:** Full codebase review covering the DES engine, disease model, social network, gravity coupling, supply chain, allocation strategies, provider/intervention system, validation modules (001--009), and unit tests.

---

## Executive Summary

This is an ambitious and architecturally well-structured simulation platform that models AI-augmented pandemic response across continental Africa. The dual-view concept (actual vs. observed epidemic) is a genuinely novel contribution. The progressive validation ladder (001--009) demonstrates good scientific intent. The code is clean, well-organized, and the conservation law enforcement is rigorous.

However, the system has significant methodological weaknesses that would be flagged in peer review. The most serious are: (1) systematic under-replication in validation modules, with half the suite running single stochastic realizations; (2) linear population scaling from small DES populations to real cities, which is mathematically incorrect for nonlinear epidemic dynamics; (3) absence of formal statistical tests anywhere in the validation suite; and (4) a gravity model that eliminates population-size effects between cities.

The findings below are organized by severity: critical issues that undermine key claims, major concerns that limit generalizability, and minor issues that should be documented or addressed.

---

## 1. Critical Issues

### 1.1 Systematic Under-Replication in Validation (Modules 004--009)

The most pervasive weakness in the validation suite. Stochastic simulations require multiple replications to characterize output distributions. Six of nine modules run 1--3 Monte Carlo replications:

| Module | Runs | Adequate? |
|--------|------|-----------|
| 001 DES-SEIR convergence | 10--15 | Marginal |
| 002 Behavioral isolation | 15--20 | Adequate |
| 003 Provider screening | 20--30 | Good |
| 004 Multi-city gravity | **1** | Unacceptable |
| 005 Nigeria country-scale | **3** | Insufficient |
| 006 Continental Africa | **1** | Unacceptable |
| 007 Coverage dose-response | **2** | Unacceptable |
| 008 Supply chain | **1** | Unacceptable |
| 009 7-1-7 assessment | **1** | Unacceptable |

With n=1, any single realization can be atypical. No confidence intervals, error bars, or variability assessment is possible. Claims like "AI providers save X lives" (Module 008) or "100% detection compliance" (Module 009) are from single runs and have unknown uncertainty. Standard practice in computational epidemiology requires 30--100 replications for publication-quality results, or at minimum 10 with formal power justification.

**Recommendation:** Increase all modules to minimum 20 replications. Report mean, median, and 95% confidence intervals for all key metrics.

### 1.2 Linear Population Scaling

Modules 005--009 scale DES results to real populations via:

```python
real_deaths = des_deaths * (real_population / des_population)
```

This assumes epidemic dynamics scale linearly with population size. They do not. Epidemic models exhibit threshold effects (herd immunity), network saturation, and nonlinear force-of-infection. For Lagos (real population ~15M, DES population 5,000), the scale factor is 3,000x. A single extra stochastic death in the DES becomes 3,000 deaths in the "real" estimate. This makes absolute death counts unreliable.

The correct approach would be either: (a) run DES at larger N and demonstrate convergence of per-capita metrics, or (b) use the DES to estimate per-capita rates and apply them through a separate scaling model that accounts for nonlinearity, or (c) clearly caveat all scaled absolute numbers as order-of-magnitude estimates only.

**Recommendation:** Add convergence-by-N validation showing that per-capita attack rate and CFR stabilize as N increases from 500 to 50,000. Document the scaling methodology's limitations prominently.

### 1.3 Gravity Model Eliminates Population Heterogeneity

The inter-city travel coupling uses uniform DES population for both cities in the gravity product:

```python
rate = scale * (n_people * n_people) / (distance ** alpha)
```

Since `n_people` is identical for all cities (default 5,000), the population product is constant and coupling depends only on distance. In reality, Lagos (23M) generates orders of magnitude more travel to any given city than a small town. The model treats all cities as equally-sized nodes differing only in geographic position.

This is documented in a code comment ("Uses uniform DES population for all cities") but its implications are not discussed. It means the simulation cannot capture hub-and-spoke epidemic dynamics where megacities act as amplifiers and redistributors.

**Recommendation:** Use `real_population_i * real_population_j` in the gravity numerator (scaled to DES rates), or document this as a known simplification with discussion of its impact on wave propagation patterns.

### 1.4 No Formal Statistical Tests in Validation Suite

Not a single module performs a formal hypothesis test (KS test, chi-squared, permutation test, bootstrap CI, or even a t-test). All validation is visual (overlay plots) or based on printed delta-percentages. Module 001 claims DES-SEIR convergence but provides no quantitative convergence criterion. Module 002 claims monotonic dose-response but performs no monotonicity test.

For a peer-reviewed computational study, the minimum standard would be: (a) a formal convergence criterion for Module 001 (e.g., "DES mean within 5% of ODE at all time points, p < 0.05"); (b) correlation tests for Module 004 (distance vs. wave arrival time); and (c) dose-response model fitting for Module 007.

**Recommendation:** Add quantitative pass/fail criteria to each validation module. Encode the DES-ODE convergence test as an automated pytest.

---

## 2. Major Concerns

### 2.1 COVID Severity Parameters Are Unusually Low

The COVID-natural scenario uses `severe_fraction = 0.005` (0.5% of infections become severe). Published WHO estimates place COVID-19 hospitalization rates at 5--20% depending on age distribution and variant. The model's 0.5% is 10--40x lower than empirical estimates.

The effective IFR emerges from the interaction of `severe_fraction`, `base_daily_death_prob` (0.006), `death_prob_increase_per_day` (0.002), and `care_survival_prob` (0.93), so the final IFR may still be reasonable. But the mechanistic pathway is unrealistic: very few people become severe, and those who do face escalating daily death risk. In reality, many people are hospitalized but most survive. The model approximates this with few hospitalizations and high per-hospitalization mortality risk.

The `calibrate.py` script shows explicit tuning of `severe_fraction` to match Africa-wide COVID death targets (257K reported, 500K--1.2M excess). This is legitimate calibration, but it should be transparent that the mechanistic parameters were chosen to match aggregate outcomes, not derived from clinical data.

**Recommendation:** Document that severity parameters were calibrated to continent-level mortality targets rather than derived from clinical studies. Discuss the trade-off: mechanistically unrealistic severity fraction vs. aggregate-realistic mortality.

### 2.2 Ebola Model Validity

Modules 006 and 007 apply the same small-world-network DES to Ebola. Real Ebola transmission is predominantly through direct contact with bodily fluids, healthcare settings, and funeral practices -- not general community social networks. The Watts-Strogatz topology with daily random contacts is a respiratory-disease transmission model applied to a contact-fluid disease.

Key differences not captured:
- Ebola is not airborne; transmission requires close physical contact with infected fluids
- Nosocomial (hospital-acquired) transmission is a major Ebola driver, not modeled here
- Funeral practices are a documented super-spreading mechanism for Ebola
- Ebola patients are most infectious when severely ill (not during mild phase)

Using COVID-calibrated network transmission for Ebola is a significant model misspecification that should be explicitly caveated.

**Recommendation:** Either add Ebola-specific transmission mechanics (nosocomial, funeral) or clearly state that Ebola scenarios use a generic respiratory-pathogen network model and results should be interpreted as qualitative only.

### 2.3 No Age Stratification in Production Engine

The production DES (`city_des_extended.py`) assigns identical `severe_fraction` to all agents regardless of age. The standalone DES in `des_system/disease_model.py` does implement age-stratified risk (2x multiplier above age 60), but this capability was not carried forward to the production engine.

For COVID-19, age is the strongest predictor of severity and death (100x difference in IFR between ages 10 and 80). Modeling all agents with the same 0.5% severity rate means the model cannot capture age-dependent intervention targeting, which is precisely the kind of strategy AI health agents would implement.

**Recommendation:** Acknowledge this limitation. For COVID scenarios, age stratification would significantly improve the realism of provider triage and vaccine prioritization results.

### 2.4 Parameter Default Inconsistencies

Several parameters have different defaults in `SimulationParams` (Python class) vs. `SimulationRequest` (API schema):

| Parameter | SimulationParams | API Schema | Impact |
|-----------|-----------------|------------|--------|
| `gravity_scale` | 0.04 | 0.01 | 4x difference in inter-city coupling |
| `base_isolation_prob` | 0.05 | 0.0 | API users get zero spontaneous isolation |
| `advised_isolation_prob` | 0.20 | 0.40 | API users get 2x advised isolation effect |

This means validation scripts (which use `SimulationParams` directly) and dashboard users (who go through the API) operate under different default assumptions. Results from the validation modules cannot be reproduced through the API without manually overriding defaults.

**Recommendation:** Unify defaults. The API schema should be the single source of truth, and `SimulationParams` should inherit from it.

### 2.5 Dimensional Inconsistency in AI Strategy

The `EpidemicSnapshot` provides `populations` as real city populations (millions) but `active_cases` at DES scale (max ~5,000). The AI strategy computes:

```python
transmission_pressure = (active_cases / population) * susceptible_fraction
```

This mixes DES-scale numerators with real-population denominators, producing tiny values. The `_normalize()` step rescues relative ordering, but the strategy's design intent (measuring transmission pressure) is obscured by the scale mismatch. If all cities have similar per-capita infection rates at DES scale, normalization amplifies noise rather than signal.

**Recommendation:** Either pass DES populations in the snapshot (for consistent per-capita rates) or scale active_cases to real populations before computing transmission pressure.

### 2.6 Validation Modules 002--003 Are Verification, Not Validation

Module 002 tests whether increasing isolation probability suppresses epidemics. Module 003 tests whether more providers detect more cases. Both are testing that the model does what it was programmed to do -- this is **verification** (does the code implement the specification correctly?) not **validation** (does the model represent reality?).

True validation requires comparison against external data: empirical studies of isolation effectiveness, real-world provider detection rates, or published meta-analyses. The modules demonstrate internal consistency but cannot establish external validity.

**Recommendation:** Relabel these as "verification" in documentation. Add at least one external validation point (e.g., published COVID contact-tracing effectiveness data, WHO surveillance sensitivity benchmarks).

---

## 3. Minor Issues

### 3.1 Hardcoded Constants Without Justification

Several epidemiologically significant values are hardcoded without cited sources:

| Constant | Value | Location | Concern |
|----------|-------|----------|---------|
| Vaccine efficacy | 70% (0.3x susceptibility) | city_des_extended.py:689 | Not configurable; real vaccine efficacy varies by pathogen |
| Care duration | 0.5 * infectious_days | city_des_extended.py:770 | No cited source for this ratio |
| Screening split | 70% random / 30% contact-traced | city_des_extended.py:453 | No evidence for this specific ratio |
| No-phone receptivity | 0.6 | city_des_extended.py:502 | Hardcoded fallback |
| Death probability cap | 0.95 | city_des_extended.py:733 | Prevents certainty of death; arbitrary ceiling |
| PPE per care-day | 2 units | city_des_extended.py:777 | No cited source |

**Recommendation:** Document the source or rationale for each hardcoded constant, or make them configurable.

### 3.2 Two Divergent DES Implementations

The repository contains two DES engines that differ significantly:

| Feature | `des_system/disease_model.py` | `city_des_extended.py` |
|---------|------------------------------|----------------------|
| Duration distributions | Gaussian | Gamma |
| Age stratification | Yes | No |
| Agent representation | Objects (Person class) | NumPy arrays |
| Supply chain | SimPy Resources | CitySupply class |
| State model | S-E-I-Symptomatic-H-R-D | S-E-I_minor-I_needs-I_care-R-D |

These are effectively different models sharing a name. The `des_system/` version appears to be an earlier prototype. If it is no longer used in production or validation, it should be clearly marked as archival to avoid confusion.

**Recommendation:** Document which DES engine is canonical. Consider moving the prototype to an `archive/` directory or adding a deprecation notice.

### 3.3 Supply Chain Simplifications

The supply chain model makes several simplifying assumptions that should be documented:

- No resource spoilage or expiry (vaccines, reagents)
- No transportation loss (100% of shipped goods arrive)
- No cost model (resources constrained only by availability and lead time)
- No warehouse capacity limits (stockpiles grow without bound)
- Intra-country redistribution is instantaneous (zero transfer time)
- All-or-nothing resource consumption (no partial fulfillment)
- Equal per-city vaccine deployment regardless of population size (rule-based strategy)

These are reasonable for a first-order model but should be discussed as limitations, especially the equal-per-city vaccine deployment which gives small towns the same allocation as megacities.

### 3.4 Module 005 Filename Mismatch

`005_multicity_des/validation_des_vs_ode.py` contains no ODE comparison despite the filename. The module compares DES results to empirical Nigeria COVID death counts. This is misleading.

**Recommendation:** Rename to `validation_nigeria_scale.py` or similar.

### 3.5 Legacy NumPy RNG

The engine uses `np.random.RandomState` (legacy API) with the same seed as Python's `random.Random`. Modern NumPy recommends `np.random.Generator` with `np.random.PCG64`. The identical seeding of both streams creates potential statistical correlation between scalar and vectorized random draws.

**Recommendation:** Migrate to `np.random.Generator` and use independent seed streams (e.g., `SeedSequence.spawn()`).

### 3.6 Self-Contact Replacement Is Deterministic

When a random mass-action contact lands on the infecting agent itself, it is replaced with `(idx + 1) % n_people` -- a deterministic, non-random replacement. This creates a slight bias toward infecting agent `idx+1`. At N=5,000 the effect is negligible, but it is a minor implementation blemish.

### 3.7 Burn Rate EMA Cold Start

The supply chain's exponential moving average for resource burn rates starts at 0.0. During the first ~7 days, the EMA underestimates actual consumption. The AI allocation strategy's days-of-stock calculations (`stock / burn_rate_ema`) produce infinity during this period, causing the strategy to take no redistribution action when it may be most needed (early outbreak phase).

### 3.8 Coverage Sweep Pools City and Run Variability

Module 007 accumulates per-city peak values across runs: `peak_I_vals` contains values from all cities across all runs, conflating inter-city variability with inter-run (stochastic) variability. The error bars therefore overstate the precision of the per-run estimate while masking the true inter-run uncertainty.

**Recommendation:** Compute per-run aggregates first, then report inter-run statistics.

### 3.9 Module 009 Hardcodes Notification Time

The 7-1-7 assessment sets `T2 = T1 + 1` for AI providers (1-day notification) and `T1 + 3` for paper-based. These are assumptions, not simulation outputs. The apparent advantage of AI providers in the notification metric is predetermined by the input, not demonstrated by the model.

### 3.10 No Negative Controls

No validation module tests that the model produces correct behavior at boundary conditions: R0 < 1 should produce no sustained epidemic; isolation probability = 1.0 should halt all transmission; zero seed infections should produce no epidemic. These are trivial to implement and would catch a class of bugs that the current test suite misses.

---

## 4. Strengths Worth Highlighting

Despite the issues above, the platform has genuine strengths that should be preserved and built upon:

1. **Dual-view architecture** (actual vs. observed epidemic) is a conceptually powerful innovation for modeling surveillance gaps. This is the platform's most distinctive contribution.

2. **Conservation law enforcement** is rigorous -- the atomic `_transition()` method and debug-mode assertions ensure population accounting is always exact.

3. **Progressive validation ladder** (001--009) demonstrates good scientific methodology in structure, even where individual modules are underpowered. The concept of building trust incrementally from first principles (ODE convergence) to policy outputs (7-1-7 compliance) is sound.

4. **Gamma-distributed waiting times** (CV=0.4) are a meaningful improvement over the exponential (Markov) assumption common in simpler models.

5. **Hybrid network/mass-action transmission** (85% network, 15% random) is epidemiologically well-motivated and provides a middle ground between purely structured and purely random mixing.

6. **Household-size-derived contact networks** with cited UN data and Prem et al. justification is a careful, data-grounded approach.

7. **Event logging system** provides full audit trail of every simulation decision, enabling post-hoc interpretability.

8. **7-1-7 framework application** (Module 009) is conceptually novel -- applying a published outbreak response framework to evaluate simulation outputs is a creative connection between modeling and policy.

9. **Behavioral diagnosis fallback** (detecting cases through symptoms when diagnostic supplies run out) models an operationally important resilience mechanism.

10. **Structured allocation strategy pattern** with pluggable rule-based and AI-optimized strategies enables controlled comparison of intervention approaches.

---

## 5. Recommendations Summary

### For Publication Readiness

1. Increase MC replications to 20+ for all validation modules
2. Add formal statistical tests (convergence criteria, correlation tests, dose-response model fitting)
3. Replace or caveat linear population scaling
4. Add at least one external validation against published epidemic data
5. Unify parameter defaults between SimulationParams and API schema
6. Fix dimensional inconsistency in AI strategy snapshot

### For Scientific Rigor

7. Add negative controls (R0 < 1, isolation = 1.0, zero seeds)
8. Add convergence-by-N validation for per-capita metrics
9. Perform sensitivity analyses on key parameters (screening split, behavioral parameters, gravity scale)
10. Caveat Ebola scenarios as using generic respiratory-pathogen transmission model
11. Document calibration methodology for severity parameters

### For Code Quality

12. Migrate to modern NumPy RNG (`np.random.Generator`)
13. Document or make configurable all hardcoded epidemiological constants
14. Mark the `des_system/disease_model.py` prototype as archival
15. Rename Module 005 file to match its actual content
16. Fix self-contact replacement to use random selection

---

*This review was conducted by reading the complete source code of all simulation engines, configuration files, validation modules, unit tests, and supporting infrastructure. All findings are based on the code as committed, not on external documentation or claims.*
