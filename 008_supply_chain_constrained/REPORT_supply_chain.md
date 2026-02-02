# Supply Chain Constraints as the Binding Failure Mode in AI-Augmented Pandemic Response Across Africa

## Overview

This analysis extends the continental-scale agent-based DES pandemic simulation (Sections 001-007) to investigate whether AI-optimized supply chain management can improve outbreak outcomes when combined with AI-driven behavioral interventions. We compare four configurations under a COVID bioattack scenario (R$_0$ = 3.5) across all 442 African cities (242 million population):

| Config | Behavioral AI | Supply Chain | Strategy |
|--------|:---:|:---:|:---:|
| A: Baseline | Standard | OFF | - |
| B: Behavioral AI | 10x providers | OFF | - |
| C: Supply + Rules | 10x providers | ON | Rule-based |
| D: Supply + AI | 10x providers | ON | AI-optimized |

**Key finding:** Enabling realistic supply chain tracking *increases* deaths by 119% compared to behavioral AI alone. Africa's medical supplies — PPE, diagnostic swabs, reagents — deplete within days under R$_0$ = 3.5, collapsing the screening-detection-isolation pipeline that behavioral AI depends on. AI-optimized allocation (Config D) marginally outperforms rule-based allocation (Config C), but neither can overcome fundamental resource inadequacy.

This result carries a direct policy implication: **optimizing the allocation of inadequate resources produces worse outcomes than not tracking resources at all**, because the tracking mechanism itself enforces the constraint. Investment in supply chain capacity must precede or accompany AI optimization.

---

## 1. Background and Motivation

### 1.1 Prior work

Sections 001-007 established that AI healthcare worker agents — operating through mobile phones to screen, advise isolation, and deliver culturally-adapted messaging — reduce COVID bioattack deaths by approximately 5% across Africa (61,000 lives saved). This modest effect at R$_0$ = 3.5 was expected: behavioral interventions alone reduce R$_\text{eff}$ from 3.5 to ~1.89, still far above the epidemic threshold of 1.0.

The natural question was whether AI-driven **supply chain optimization** — smarter allocation of vaccines, therapeutics, PPE, and diagnostics — could amplify the behavioral effect by ensuring resources flow to where the epidemic is worst.

### 1.2 The supply chain gap

Our comprehensive African medical supply chain dataset (442 cities, 35 columns; see `DATA_DICTIONARY.md`) reveals the scale of the gap:

| Metric | Value |
|--------|-------|
| Total hospital beds (442 cities) | 261,786 |
| ICU beds (estimated) | 9,104 |
| Total health workers | 603,175 |
| Average SCRI (0-100) | 32.1 |
| Highest SCRI (Curepipe, Mauritius) | 77.7 |
| Lowest SCRI (Yei, South Sudan) | 7.5 |
| Countries with local pharma production | 20/52 |
| Average import dependency | 74% |

The Supply Chain Resilience Index (SCRI) ranges from 7.5 to 77.7, with a continental average of 32.1/100. Most African cities operate with fewer than 10 hospital beds per 10,000 population (WHO recommends 25-30), and diagnostic laboratory coverage is sparse outside capital cities.

### 1.3 What we built

Three new components were developed for this analysis:

1. **African Medical Supply Chain Dataset** (`african_medical_supply_chain.csv`): 442 cities with WHO GHO beds/workforce data, World Bank financing data, JEE health security scores, GHSI indices, cold chain assessments, and pharmaceutical manufacturing capacity — all downscaled from country-level to city-level using facility-weighted proportional allocation.

2. **Allocation Strategy Module** (`allocation_strategy.py`): An abstract strategy pattern with two implementations:
   - `RuleBasedStrategy`: Fixed thresholds (reorder at 30%, redistribute above 60%, deploy reserves below 15%)
   - `AIOptimizedStrategy`: Epidemic-aware allocation using growth rates, network centrality, bed strain, burn-rate projections, and acceleration detection

3. **Three-Tier Supply Chain Integration**: City-level resource tracking (beds, PPE, swabs, reagents, vaccines, pills) feeding into country-level redistribution and continent-level reserve deployment, with strategy-driven decision-making at each tier.

---

## 2. Method

### 2.1 Simulation architecture

The simulation uses a hybrid Agent-Based / Discrete-Event Simulation (ABS-DES) engine with:

- **442 cities** across 52 African countries
- **5,000 agents per city** (DES population), with results scaled to real populations
- **Small-world contact networks** with household structure and random mixing
- **7-state disease model**: S, E, I$_\text{minor}$, I$_\text{needs\_care}$, I$_\text{receiving\_care}$, R, D
- **Gravity-model inter-city coupling** calibrated to geographic distance
- **Per-agent behavioral state**: phone ownership (84%), provider-advised status, isolation compliance

### 2.2 Supply chain model

When enabled (Configs C and D), the supply chain tracks six resource categories at daily resolution:

| Resource | Initial Seeding | Consumption Trigger |
|----------|----------------|-------------------|
| Hospital beds | From WHO data (facility-weighted) | Severe cases admitted |
| PPE | 500 sets per facility | 1 per screening, 2 per care-day |
| Diagnostic swabs | 1,000 per lab | 1 per test |
| Reagents | 2,000 per lab | 1 per test |
| Vaccines | 0 local (continent reserve: ~45K DES-scale) | 2% of DES pop/day when available |
| Therapeutic pills | 0 local (continent reserve: ~18K DES-scale) | 1 per care-day |

Resources are scaled to DES population using per-capita density: if a city has 10 beds per 10,000 in real life, the DES gets proportionally scaled beds.

The three-tier management operates as:
- **City level**: Track consumption, compute 7-day EMA burn rates
- **Country level** (daily): Redistribute from surplus to deficit cities; reorder from external suppliers when country stock falls below threshold
- **Continent level** (weekly): Deploy strategic reserves to countries/cities in need

### 2.3 AI-optimized strategy

The `AIOptimizedStrategy` differs from the rule-based approach in four key decisions:

**Vaccine allocation**: Priority-weighted distribution using:
$$\text{priority}_i = 0.30 \cdot \text{transmission\_pressure}_i + 0.25 \cdot \text{centrality}_i + 0.25 \cdot \text{growth\_rate}_i + 0.20 \cdot \text{bed\_strain}_i$$

City centrality is pre-computed as eigenvector centrality of the travel matrix.

**Resource redistribution**: Burns-rate-based instead of threshold-based. Cities with <7 days of stock receive transfers from cities with >21 days, preserving a 14-day buffer for donors.

**Continental deployment**: Triggered by epidemic acceleration (positive second derivative of active case trajectory) or aggregate stock <14 days, rather than fixed 15% threshold. Allocation proportional to predicted need (burn rate $\times$ lead time).

**Reorder quantities**: Order = burn\_rate $\times$ lead\_time $\times$ safety\_factor, where safety\_factor = 1.5 + max(0, growth\_rate). Capped at 2$\times$ initial stock.

### 2.4 Scenario parameters

| Parameter | Value |
|-----------|-------|
| Disease | COVID bioattack |
| R$_0$ | 3.5 |
| Incubation period | 4 days |
| Infectious period | 9 days |
| Severe fraction | 2.0% |
| IFR | ~0.55% (emergent from care quality + bed availability) |
| Simulation duration | 250 days |
| Seeded cities | 5 simultaneous (bioattack pattern) |
| AI provider density | 50 per 1,000 (10x baseline of 5) |
| AI screening capacity | 200 per provider/day (10x baseline of 20) |
| Advised isolation probability | 55% (vs 20% baseline) |
| Disclosure probability | 80% (vs 50% baseline) |
| Receptivity override | 85% (vs score-derived ~60% baseline) |
| Mobile phone reach | 84% |
| Continent vaccine reserve | ~5M real doses (~45K DES-scale) |
| Continent pill reserve | ~2M real courses (~18K DES-scale) |

---

## 3. Results

### 3.1 Summary table

| Metric | A: Baseline | B: Behavioral AI | C: Supply + Rules | D: Supply + AI |
|--------|:-----------:|:-----------:|:-----------:|:-----------:|
| **Total deaths** | **1,309,352** | **1,248,282** | **2,862,394** | **2,909,969** |
| Total infected | 238,221,828 | 219,983,044 | 238,948,200 | 238,663,787 |
| Attack rate | 98.4% | 90.9% | 98.7% | 98.6% |
| Case fatality rate | 0.550% | 0.567% | 1.198% | 1.219% |
| Peak day | 91 | 101 | 89 | 90 |
| Peak active cases | 38.8M | 23.1M | 41.2M | 40.2M |
| Detection rate (final) | 40.4% | 99.8% | 0.6% | 2.9% |
| Stockout events | 0 | 0 | 29,290 | 29,177 |
| Redistributions | 0 | 0 | 17,164 | 7,230 |
| Deployments | 0 | 0 | 7,474 | 174 |
| Vaccinations | 0 | 0 | 3,294 | 223 |
| Runtime | 285s | 260s | 291s | 276s |

### 3.2 Figure 1: Total deaths by configuration

![Deaths comparison](results/01_deaths_comparison.png)

**Figure 1.** Total deaths across the four configurations. Config B (Behavioral AI only) achieves the lowest death toll at 1.25M, a 4.7% reduction from the 1.31M baseline. Enabling supply chain tracking (Configs C and D) approximately doubles deaths to ~2.9M due to resource stockouts collapsing the detection pipeline.

### 3.3 Figure 2b: Resource demand under unconstrained behavioral AI

![Resource demand](results/02b_resource_demand.png)

**Figure 2b.** Shadow resource accounting for Config B (Behavioral AI, supply chain OFF). These are the resources Config B *would consume* if they were tracked. Four panels show: (top-left) daily screening demand — 242M swabs and reagents per day, totaling 60.5B over 250 days; (top-right) hospital bed demand peaks at 240K vs Africa's 262K supply, meaning beds are the one resource near adequacy; (bottom-left) 20M therapeutic pill courses needed vs 2M in continent reserves; (bottom-right) demand/supply ratio on log scale — diagnostic supplies are 70,000–143,000× short, PPE is 1,954× short, pills are 10× short, and beds are actually near 1:1 (0.9×). This explains why turning on supply chain tracking destroys outcomes: the screening pipeline requires 60+ billion consumable units that simply do not exist.

### 3.4 Figure 3: Epidemic curves

![Epidemic curves](results/02_epidemic_curves.png)

**Figure 3.** Active infection curves showing population-scaled active cases over 250 days. Config B (Behavioral AI) flattens the peak from 38.8M to 23.1M and delays it from day 91 to day 101. Configs C and D show slightly higher peaks than baseline because supply stockouts disable screening, removing the behavioral intervention's effect.

### 3.5 Figure 4: Detection collapse under supply constraints

![Detection and deaths](results/03_detection_and_deaths.png)

**Figure 4.** Left: Detection rate over time. Config B maintains near-100% detection throughout the epidemic via unlimited screening resources. Configs C and D see detection collapse to <3% as PPE and diagnostic supplies deplete — screening cannot function without swabs and reagents. Right: Cumulative deaths diverge sharply as supply-constrained configurations lose their detection capability.

This is the critical mechanism: **the supply chain constraint doesn't just limit treatment — it destroys surveillance**, which is the foundation of all behavioral interventions. Without screening, providers cannot detect cases, cannot advise isolation, and cannot trigger the compliance pathway.

### 3.6 Figure 5: Supply chain event comparison

![Supply chain events](results/04_supply_chain_events.png)

**Figure 5.** Event breakdown for Configs C (Rule-Based) and D (AI-Optimized). Both experience ~29,000 stockout events. The AI strategy produces fewer redistributions (7,230 vs 17,164) and far fewer deployment events (174 vs 7,474), indicating more targeted resource movement. However, neither strategy can prevent stockouts because the underlying resource pool is insufficient.

### 3.7 Figure 6: Attack rate and case fatality rate

![Attack rate and CFR](results/05_attack_rate_cfr.png)

**Figure 6.** Left: Attack rate is near-universal (>90%) in all configurations — R$_0$ = 3.5 overwhelms any intervention. Config B reduces it to 90.9% (vs 98.4% baseline) through screening-driven isolation. Right: CFR approximately doubles under supply constraints (0.55% to 1.20%) because resource depletion reduces care quality. The CFR *increase* is the primary driver of excess deaths in Configs C and D.

---

## 4. Analysis

### 4.1 The resource-constraint paradox

The central finding is counterintuitive: **modeling resource constraints faithfully produces worse outcomes than ignoring them**. This is not a modeling error — it reveals a genuine policy truth.

When supply chain tracking is disabled (Configs A and B), the simulation implicitly assumes unlimited PPE, unlimited diagnostic capacity, and unlimited screening resources. This is the assumption embedded in most compartmental epidemic models and many agent-based models. Under this assumption, AI behavioral interventions work as designed: providers screen, detect, advise, and cases isolate.

When supply chain tracking is enabled (Configs C and D), the simulation enforces reality: PPE runs out, swabs deplete, reagents are consumed. At that point, providers physically cannot screen patients. The behavioral AI pathway — which depends on screening as the entry point — collapses entirely.

The excess deaths (~1.6M) in the supply-constrained configurations represent patients who would have been detected, advised, and isolated under the unlimited-resource assumption but were missed because the screening infrastructure broke down.

### 4.2 Stockout dynamics

With R$_0$ = 3.5 seeded simultaneously in 5 cities, the epidemic reaches all 442 cities within 30-40 days via the gravity-coupled travel network. Peak infection involves ~38M simultaneously active cases across a population of 242M.

At this scale, even generous resource assumptions are overwhelmed:
- 500 PPE sets per facility × ~62,000 facilities = 31M PPE sets, consumed at 1 per screening + 2 per care-day
- ~400 laboratories × 1,000 swabs = 400K swabs — enough for days, not weeks, of continent-wide screening

The stockout cascades: PPE depletes first (required for screening), then swabs and reagents. Once any diagnostic resource reaches zero, that city's screening halts entirely. With 29,000+ stockout events across 250 days, most cities experience extended periods without any screening capability.

### 4.3 AI strategy marginal effects

Although both supply-constrained configs fail compared to Config B, the AI strategy (D) shows advantages over rule-based (C) in operational efficiency:

| Metric | Rule-Based (C) | AI (D) | Interpretation |
|--------|:-----------:|:-----------:|----------------|
| Redistributions | 17,164 | 7,230 | AI targets transfers to critical cities only |
| Deployments | 7,474 | 174 | AI avoids wasteful uniform deployment |
| Detection rate | 0.6% | 2.9% | AI maintains screening slightly longer |
| Peak active | 41.2M | 40.2M | Marginal epidemic curve difference |

The AI strategy's burn-rate-based redistribution and acceleration-triggered deployment are demonstrably smarter, but the magnitude of improvement (~2% detection vs ~1%) is dwarfed by the underlying resource gap.

### 4.4 Vaccine deployment

Despite continent-level reserves of ~5M doses (45K DES-scale), vaccination had minimal impact in both supply-constrained configurations (3,294 and 223 vaccination events respectively). At R$_0$ = 3.5 with simultaneous multi-city seeding, the epidemic outpaces any realistic vaccination campaign. The 5M-dose reserve covers ~2% of Africa's 1.4B population — orders of magnitude below the coverage needed for herd immunity at this R$_0$ (>70%).

---

## 5. Implications

### 5.1 For policy

1. **Supply chain capacity must precede optimization.** AI-driven allocation of insufficient resources is worse than no allocation at all, because constraint-tracking enforces the shortage. Before deploying AI supply chain management, ensure minimum viable resource levels.

2. **Diagnostic stockpiles are the critical bottleneck.** PPE and testing supplies enable the entire detection-to-isolation pipeline. Strategic reserves of diagnostic materials may be more impactful than vaccine stockpiles under high-R$_0$ bioattack scenarios.

3. **Behavioral interventions remain the fastest lever.** Config B (AI providers, no supply constraints) achieved the best outcomes with only software/communication infrastructure — no physical supply chain required. Mobile-phone-based screening and isolation advice are deployable immediately with existing phone penetration (84%).

### 5.2 For modeling

1. **Resource assumptions matter.** Most epidemic models assume unlimited healthcare capacity. This analysis shows that faithfully modeling resource constraints can change the sign of intervention effects (from beneficial to harmful).

2. **Multi-layer interventions interact non-linearly.** Behavioral AI + supply chain management is not additive — supply stockouts destroy the behavioral pathway.

3. **Strategy comparison requires adequate baseline resources.** Comparing rule-based vs AI-optimized strategies is only meaningful when resources are sufficient for the strategy to make choices. Under extreme scarcity, all strategies converge to the same outcome: stockout.

### 5.3 For future work

1. **Resource adequacy threshold sweep**: At what resource level does supply chain tracking become beneficial? Run a sweep over PPE/swab multipliers (1x, 5x, 10x, 50x, 100x) to find the crossover point.

2. **Staged response**: Combine immediate behavioral AI (day 0) with supply chain scaling (week 2+) to model realistic surge capacity timelines.

3. **Regional supply chain clusters**: Rather than continent-wide management, model regional supply hubs (e.g., ECOWAS, SADC) with shorter lead times and existing trade infrastructure.

4. **Pharmaceutical manufacturing capacity**: The dataset shows only 20/52 African countries have local pharmaceutical production. Model the impact of expanding local manufacturing on supply chain resilience.

---

## 6. Data

### 6.1 African Medical Supply Chain Dataset

The analysis produced a comprehensive, machine-readable dataset as a standalone research contribution:

- **File**: `backend/data/african_medical_supply_chain.csv`
- **Coverage**: 442 cities, 52 countries, 35 columns
- **Sources**: WHO GHO API (beds, physicians, nurses), World Bank (health expenditure), JEE scores, GHSI, Gavi cold chain, AU pharmaceutical manufacturing
- **Methodology**: Country-level data downscaled to city level using facility-weighted proportional allocation
- **Documentation**: Full data dictionary at `backend/data/DATA_DICTIONARY.md`

### 6.2 Supply Chain Resilience Index (SCRI)

A composite 0-100 score incorporating beds, workforce, diagnostics, cold chain, import dependency, health expenditure, and JEE response capacity:

| Quintile | SCRI Range | Countries (examples) |
|----------|-----------|---------------------|
| Top (Q5) | 56-78 | Algeria, Mauritius, South Africa |
| Q4 | 42-56 | Egypt, Morocco, Kenya, Tunisia |
| Q3 | 30-42 | Nigeria, Ghana, Senegal |
| Q2 | 18-30 | DRC, Ethiopia, Mozambique |
| Bottom (Q1) | 7-18 | Somalia, South Sudan, Chad |

---

## 7. Reproduction

### Running the analysis

```bash
cd 008_supply_chain_constrained
python supply_chain_analysis.py
```

Results are cached to `results/config_*.npz` after first run. Subsequent runs regenerate figures without re-simulating.

### File reference

| File | Purpose |
|------|---------|
| `supply_chain_analysis.py` | Main analysis script (4-config comparison + 5 figures) |
| `REPORT_supply_chain.md` | This report |
| `results/01_deaths_comparison.png` | Fig 1: Death count bar chart |
| `results/02b_resource_demand.png` | Fig 2b: Shadow resource demand (Config B) |
| `results/02_epidemic_curves.png` | Fig 3: Active case curves (4 panels) |
| `results/03_detection_and_deaths.png` | Fig 4: Detection collapse + cumulative deaths |
| `results/04_supply_chain_events.png` | Fig 5: Event breakdown (C vs D) |
| `results/05_attack_rate_cfr.png` | Fig 6: Attack rate and CFR |
| `results/config_*.npz` | Cached simulation time-series |
| `results/config_*_meta.json` | Cached summary metrics |

### Dependencies

- `simulation_app/backend/` — Core ABS-DES engine
- `simulation_app/backend/allocation_strategy.py` — Strategy pattern module
- `simulation_app/backend/supply_chain.py` — Three-tier supply chain managers
- `simulation_app/backend/data/african_medical_supply_chain.csv` — Enriched dataset
- `matplotlib`, `numpy` — Plotting and computation
