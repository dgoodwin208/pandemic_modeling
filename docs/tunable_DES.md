# Tunable Intelligence in Discrete Event Simulation

**Exploration of agent intelligence levels for pandemic modeling**

---

## The Core Insight

Currently, `Person` is a pure data container - all behavior lives in `DiseaseModel`. For intelligent agents, we need to invert this: **the Person (or their behavior strategy) makes decisions, not the simulation**.

---

## Intelligence Spectrum

I see five distinct levels:

| Level | Name | Decision Method | Cost | Suitable N |
|-------|------|-----------------|------|------------|
| 0 | Statistical | Probability draws | O(1) | 10,000+ |
| 1 | Rule-Based | If-then on attributes | O(1) | 1,000+ |
| 2 | Utility-Based | Optimize utility function | O(factors) | 100+ |
| 3 | Memory-Based | Learn from past events | O(memory) | 50+ |
| 4 | LLM-Driven | Natural language reasoning | O(API call) | <50 |

---

## Key Decision Points in Pandemic Simulation

Looking at where intelligence matters:

### 1. Contact Selection
Who to interact with today?
- **Statistical**: Random sample from contacts
- **Intelligent**: "I'm avoiding Bob - he was coughing yesterday"

### 2. Quarantine Compliance
Self-isolate when symptomatic?
- **Statistical**: Fixed probability (c_q = 0.3)
- **Intelligent**: "I have a job interview, I'll risk it" vs "Grandma is visiting, I'll stay home"

### 3. Care-Seeking
When to see a doctor?
- **Statistical**: Fixed delay (tau_care = 5 days)
- **Intelligent**: "Just a cold" vs "This feels serious"

### 4. Contact Notification
Warn others about infection?
- **Statistical**: Fixed notification rate
- **Intelligent**: "I should call my elderly mother first"

---

## Proposed Architecture

### Core Simplification: Two Decisions + Observability

A Person really only makes two behavioral decisions:
1. **Am I isolating?** (staying home, quarantining, reducing contacts)
2. **Do I need acute care?** (seeking hospitalization)

Everything else (contact selection, notification) flows from isolation status.

The **Healthcare System** can only act on **observed cases** - this is the critical link
to the SEIR model's detected (I_d) vs undetected (I_u) split.

---

### 1. Simplified BehaviorStrategy Protocol

```python
from typing import Protocol
from dataclasses import dataclass

@dataclass
class MacroContext:
    """Global simulation state visible to agents."""
    day: float
    policy_level: int          # 0=normal, 1=guidelines, 2=lockdown
    observed_infection_rate: float  # What public sees (not true rate)
    news_severity: str         # "calm", "concerned", "panic"

class BehaviorStrategy(Protocol):
    """Simplified protocol - just two decisions."""

    def is_isolating(self, person: 'Person', ctx: MacroContext) -> bool:
        """Is this person currently isolating (reducing contacts to ~0)?"""
        ...

    def seeks_care(self, person: 'Person', ctx: MacroContext) -> bool:
        """Does this person seek acute care (hospitalization)?"""
        ...
```

**Key insight**: If `is_isolating()` returns True, transmission from/to this person drops to near zero.
The disease model handles the rest.

---

### 2. Observation Model (What Healthcare Can See)

```python
@dataclass
class ObservationModel:
    """Tracks what fraction of cases are observable to the healthcare system."""

    # Base detection rates
    symptomatic_detection_rate: float = 0.3  # 30% of symptomatic cases get detected
    asymptomatic_detection_rate: float = 0.05  # 5% of asymptomatic found via testing

    # Tracking
    true_cases: int = 0
    observed_cases: int = 0
    observation_history: list[dict] = field(default_factory=list)

    def observe_case(self, person: 'Person', detected: bool):
        """Record whether a case was observed."""
        self.true_cases += 1
        if detected:
            self.observed_cases += 1

        self.observation_history.append({
            "person_id": person.id,
            "true_state": person.state.value,
            "detected": detected,
            "day": person.infected_at
        })

    @property
    def detection_rate(self) -> float:
        """Current fraction of cases observed."""
        if self.true_cases == 0:
            return 0.0
        return self.observed_cases / self.true_cases

    @property
    def dark_figure(self) -> float:
        """Unobserved cases as multiple of observed (the 'iceberg')."""
        if self.observed_cases == 0:
            return float('inf')
        return self.true_cases / self.observed_cases

    def is_detected(self, person: 'Person') -> bool:
        """Determine if this person's case gets detected."""
        if person.state == DiseaseState.SYMPTOMATIC:
            return random.random() < self.symptomatic_detection_rate
        elif person.state in (DiseaseState.EXPOSED, DiseaseState.INFECTIOUS):
            return random.random() < self.asymptomatic_detection_rate
        return False
```

**This connects to SEIR**: The `symptomatic_detection_rate` maps to ρ_sx in the notebook.
Higher detection = more cases flow to I_d instead of I_u.

---

### 3. Person with Observable Status

```python
@dataclass
class Person:
    """Person with simplified behavior and observable status."""
    id: int
    name: str
    age: int
    state: DiseaseState = DiseaseState.SUSCEPTIBLE
    contacts: list[int] = field(default_factory=list)

    # Behavior strategy
    behavior: BehaviorStrategy = field(default_factory=lambda: StatisticalBehavior())

    # Observable status (what healthcare system knows)
    is_observed: bool = False  # Has this case been detected?
    observed_at: Optional[float] = None

    # Isolation status (affects transmission)
    isolating: bool = False
    isolation_start: Optional[float] = None

    # Care status
    seeking_care: bool = False
    care_start: Optional[float] = None

    # Timing
    infected_at: Optional[float] = None
    recovered_at: Optional[float] = None

    def effective_contacts(self) -> list[int]:
        """Contacts available for transmission (zero if isolating)."""
        if self.isolating:
            return []  # No transmission while isolating
        return self.contacts
```

---

### 4. Level 0: StatisticalBehavior (Simplified)

```python
@dataclass
class StatisticalBehavior:
    """Pure probabilistic - two simple probabilities."""
    isolation_probability: float = 0.3  # P(isolate | symptomatic)
    care_seeking_probability: float = 0.15  # P(seek care | symptomatic)

    def is_isolating(self, person, ctx):
        # Only isolate if symptomatic and roll succeeds
        if person.state != DiseaseState.SYMPTOMATIC:
            return False
        return random.random() < self.isolation_probability

    def seeks_care(self, person, ctx):
        if person.state != DiseaseState.SYMPTOMATIC:
            return False
        return random.random() < self.care_seeking_probability
```

---

### 5. Level 1: RuleBasedBehavior (Simplified)

```python
@dataclass
class RuleBasedBehavior:
    """If-then rules based on attributes."""

    def is_isolating(self, person, ctx):
        if person.state != DiseaseState.SYMPTOMATIC:
            return False

        prob = 0.3

        # Age increases compliance
        if person.age > 60:
            prob += 0.2
        # Policy increases compliance
        if ctx.policy_level >= 2:
            prob += 0.3
        # Essential workers less able to isolate
        if getattr(person, 'is_essential_worker', False):
            prob -= 0.2

        return random.random() < min(0.95, max(0.05, prob))

    def seeks_care(self, person, ctx):
        if person.state != DiseaseState.SYMPTOMATIC:
            return False

        prob = 0.15

        # Elderly more likely to seek care
        if person.age > 65:
            prob += 0.2
        if person.age > 75:
            prob += 0.2

        return random.random() < prob
```

---

### 6. Level 2: UtilityBehavior (Simplified)

```python
@dataclass
class UtilityBehavior:
    """Utility-based decisions."""
    health_weight: float = 1.0
    economic_weight: float = 0.8

    def is_isolating(self, person, ctx):
        if person.state != DiseaseState.SYMPTOMATIC:
            return False

        # Utility of isolating
        u_isolate = self.health_weight * 0.8  # Health benefit

        # Utility of not isolating
        daily_cost = getattr(person, 'daily_income', 100) / 1000
        u_not_isolate = self.economic_weight * daily_cost

        # Softmax
        prob = 1 / (1 + math.exp(-(u_isolate - u_not_isolate)))
        return random.random() < prob

    def seeks_care(self, person, ctx):
        if person.state != DiseaseState.SYMPTOMATIC:
            return False

        # Simple: seek care if perceived severity is high
        severity = 0.15
        if person.age > 65:
            severity += 0.2
        return random.random() < severity
```

---

### 7. Level 3: MemoryBehavior (Simplified)

```python
class MemoryBehavior:
    """Learns from observed outcomes."""

    def __init__(self):
        self.known_deaths: int = 0
        self.known_recoveries: int = 0
        self.perceived_severity: float = 0.15  # Updates based on observations

    def is_isolating(self, person, ctx):
        if person.state != DiseaseState.SYMPTOMATIC:
            return False

        # Higher perceived severity = more likely to isolate
        return random.random() < (0.3 + self.perceived_severity)

    def seeks_care(self, person, ctx):
        if person.state != DiseaseState.SYMPTOMATIC:
            return False
        return random.random() < self.perceived_severity

    def observe_outcome(self, outcome: str):
        """Update beliefs based on observed outcomes."""
        if outcome == "death":
            self.known_deaths += 1
        elif outcome == "recovery":
            self.known_recoveries += 1

        total = self.known_deaths + self.known_recoveries
        if total > 0:
            self.perceived_severity = self.known_deaths / total
```

---

### 8. Level 4: LLMBehavior (Simplified)

```python
@dataclass
class PersonaProfile:
    """Rich personality for LLM agents."""
    name: str
    age: int
    occupation: str
    personality: list[str]  # ["cautious", "social", "skeptical"]
    values: list[str]       # ["family", "career", "health"]
    backstory: str

class LLMBehavior:
    """LLM reasoning for two key decisions - with narrative output."""

    def __init__(self, persona: PersonaProfile, llm_client, budget: 'LLMBudget'):
        self.persona = persona
        self.llm = llm_client
        self.budget = budget
        self.memory: list[str] = []
        self.decision_log: list[dict] = []

    async def is_isolating(self, person, ctx) -> tuple[bool, str]:
        """Decide whether to isolate, with reasoning."""
        if person.state != DiseaseState.SYMPTOMATIC:
            return False, "Not symptomatic"

        if not self.budget.can_make_call():
            return random.random() < 0.5, "Budget fallback"

        prompt = f"""You are {self.persona.name}, {self.persona.age}yo {self.persona.occupation}.
Personality: {', '.join(self.persona.personality)}
Values: {', '.join(self.persona.values)}

You're feeling sick with flu-like symptoms. Day {int(ctx.day)} of outbreak.
Policy: {['normal', 'guidelines', 'lockdown'][ctx.policy_level]}

Stay home and isolate, or continue normal activities?

ISOLATE: [YES/NO]
WHY: [1 sentence, first person]"""

        response = await self.llm.complete(prompt, max_tokens=80)
        self.budget.record_call(80)

        decision = "YES" in response.split("ISOLATE:")[1].split("\n")[0].upper()
        reasoning = response.split("WHY:")[1].strip() if "WHY:" in response else ""

        self.memory.append(f"Day {int(ctx.day)}: {'Isolated' if decision else 'Kept working'}. {reasoning}")
        return decision, reasoning

    async def seeks_care(self, person, ctx) -> tuple[bool, str]:
        """Decide whether to seek hospital care."""
        if person.state != DiseaseState.SYMPTOMATIC:
            return False, "Not symptomatic"

        if not self.budget.can_make_call():
            return random.random() < 0.2, "Budget fallback"

        prompt = f"""You are {self.persona.name}, {self.persona.age}yo.
Sick for a few days: fever, fatigue, cough.

Go to hospital, or manage at home?

HOSPITAL: [YES/NO]
WHY: [1 sentence]"""

        response = await self.llm.complete(prompt, max_tokens=50)
        self.budget.record_call(50)

        decision = "YES" in response.split("HOSPITAL:")[1].split("\n")[0].upper()
        reasoning = response.split("WHY:")[1].strip() if "WHY:" in response else ""
        return decision, reasoning
```

---

### 9. PersonFactory for Mixed Networks

```python
class PersonFactory:
    """Creates persons with appropriate intelligence levels."""

    def __init__(self,
                 population_size: int,
                 llm_client=None,
                 llm_budget: int = 50,
                 focal_agent_ids: list[int] = None):
        self.n = population_size
        self.llm_client = llm_client
        self.budget = LLMBudget(max_calls=llm_budget * 100)  # ~100 decisions per agent
        self.focal_ids = set(focal_agent_ids or [])
        self.llm_count = 0

    def create_person(self, id: int, name: str, age: int) -> Person:
        """Create person with intelligence level based on network size and role."""

        # Focal agents (patient zero, super-spreaders) always get LLM
        if id in self.focal_ids and self.llm_client:
            behavior = self._create_llm_behavior(name, age)
            return Person(id=id, name=name, age=age, behavior=behavior)

        # Select level based on population size
        if self.n <= 30 and self.llm_client:
            # Tiny network: all LLM
            behavior = self._create_llm_behavior(name, age)
        elif self.n <= 100:
            # Small: memory-based
            behavior = MemoryBasedBehavior()
        elif self.n <= 500:
            # Medium: utility-based
            behavior = UtilityBasedBehavior()
        elif self.n <= 2000:
            # Large: rule-based
            behavior = RuleBasedBehavior()
        else:
            # Very large: statistical
            behavior = StatisticalBehavior()

        return Person(id=id, name=name, age=age, behavior=behavior)

    def _create_llm_behavior(self, name: str, age: int) -> LLMBehavior:
        """Generate a rich persona for LLM agent."""
        self.llm_count += 1

        persona = PersonaProfile(
            name=name,
            age=age,
            occupation=random.choice(["teacher", "nurse", "engineer", "retail worker", "retired"]),
            personality=random.sample(["cautious", "social", "skeptical", "trusting", "anxious", "carefree"], 2),
            values=random.sample(["family", "career", "health", "freedom", "community"], 2),
            backstory=f"{name} is a {age}-year-old who values their independence."
        )

        return LLMBehavior(persona, self.llm_client, self.budget)
```

---

### 10. Adaptive Resolution (Dynamic Upgrades)

```python
class AdaptiveResolutionManager:
    """Dynamically upgrade agents when they become interesting."""

    def __init__(self, network: SocialNetwork, llm_client, upgrade_budget: int = 10):
        self.network = network
        self.llm_client = llm_client
        self.budget = LLMBudget(max_calls=upgrade_budget * 100)
        self.upgraded: set[int] = set()

    def check_for_upgrades(self, ctx: MacroContext):
        """Check if any statistical agents should become LLM agents."""

        for pid, person in self.network.people.items():
            if pid in self.upgraded:
                continue
            if person.is_intelligent():
                continue
            if not self.budget.can_make_call():
                return  # Budget exhausted

            # Upgrade conditions
            reason = self._should_upgrade(person, ctx)
            if reason:
                self._upgrade_to_llm(person, reason)
                self.upgraded.add(pid)

    def _should_upgrade(self, person: Person, ctx: MacroContext) -> Optional[str]:
        """Determine if person should be upgraded."""

        # Super-spreader: high contacts + infected
        if len(person.contacts) > 15 and person.is_contagious():
            return "potential super-spreader"

        # Critical decision point: symptomatic during peak
        if person.state == DiseaseState.SYMPTOMATIC and ctx.observed_infection_rate > 0.1:
            return "critical decision during peak"

        return None

    def _upgrade_to_llm(self, person: Person, reason: str):
        """Convert statistical agent to LLM agent."""
        print(f"⬆️ Upgrading {person.name} to LLM agent: {reason}")

        persona = PersonaProfile(
            name=person.name,
            age=person.age,
            occupation=getattr(person, 'occupation', 'worker'),
            personality=["cautious"] if person.age > 60 else ["social"],
            values=["health"] if person.age > 60 else ["career"],
            backstory=f"{person.name} became a focus of the simulation."
        )

        person.behavior = LLMBehavior(persona, self.llm_client, self.budget)
```

---

### 11. Modified DiseaseModel for Intelligent Agents

```python
class IntelligentDiseaseModel(DiseaseModel):
    """Disease model using simplified behavior protocol."""

    def __init__(self, *args, observation_model: ObservationModel = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.observation_model = observation_model or ObservationModel()
        self.decision_log: list[dict] = []

    def _transmission_process(self, person: Person) -> Generator:
        """Transmission respecting isolation decisions."""

        while person.is_contagious():
            yield self.env.timeout(1.0)

            if not person.is_contagious():
                break

            ctx = MacroContext(
                day=self.env.now,
                policy_level=self.current_policy_level,
                observed_infection_rate=self.observation_model.detection_rate,
                news_severity="concerned" if self.observation_model.observed_cases > 10 else "calm"
            )

            # Check if person is isolating (reduces transmission to ~0)
            person.isolating = person.behavior.is_isolating(person, ctx)

            if person.isolating:
                continue  # No transmission while isolating

            # Get susceptible contacts
            available = self.network.get_susceptible_contacts(person.id)

            for contact in available:
                if random.random() < self.config.transmission_prob:
                    self.infect_person(contact, source=person)

    def _determine_outcome(self, person: Person) -> Generator:
        """Outcome determination with care-seeking decisions."""

        ctx = MacroContext(
            day=self.env.now,
            policy_level=self.current_policy_level,
            observed_infection_rate=self.observation_model.detection_rate,
            news_severity="concerned"
        )

        # Record case for observation model
        detected = self.observation_model.is_detected(person)
        self.observation_model.observe_case(person, detected)
        person.is_observed = detected

        # Check if person seeks care
        person.seeking_care = person.behavior.seeks_care(person, ctx)

        if person.seeking_care:
            # Enter hospital pathway
            yield from self._hospitalization_pathway(person)
        else:
            # Home recovery pathway
            yield from self._home_recovery(person)
```

**Key insight**: The DiseaseModel now just checks `is_isolating()` and `seeks_care()` -
the behavior strategy handles all the intelligence.

---

## LLM Budget Management

```python
class LLMBudget:
    """Manages LLM API costs."""

    def __init__(self, max_calls: int = 1000, max_tokens: int = 100000):
        self.max_calls = max_calls
        self.max_tokens = max_tokens
        self.calls_made = 0
        self.tokens_used = 0

    def can_make_call(self, estimated_tokens: int = 500) -> bool:
        return (self.calls_made < self.max_calls and
                self.tokens_used + estimated_tokens < self.max_tokens)

    def record_call(self, tokens: int):
        self.calls_made += 1
        self.tokens_used += tokens

    def usage_report(self) -> dict:
        return {
            "calls_made": self.calls_made,
            "calls_remaining": self.max_calls - self.calls_made,
            "tokens_used": self.tokens_used,
            "tokens_remaining": self.max_tokens - self.tokens_used,
            "utilization": self.tokens_used / self.max_tokens
        }
```

---

## Summary: Person Components

| Component | Purpose | Complexity |
|-----------|---------|------------|
| `BehaviorStrategy` protocol | Two methods: `is_isolating()`, `seeks_care()` | Low |
| `ObservationModel` | Track detected vs actual cases | Low |
| `StatisticalBehavior` | Two probabilities | Low |
| `RuleBasedBehavior` | If-then rules | Low |
| `UtilityBehavior` | Cost-benefit calculation | Medium |
| `MemoryBehavior` | Learn from observed outcomes | Medium |
| `LLMBehavior` | Natural language reasoning | High |
| `PersonFactory` | Create mixed populations | Medium |
| `AdaptiveResolutionManager` | Dynamic upgrades | Medium |
| `LLMBudget` | Cost management | Low |

---

## Key Insights

### 1. Simplicity: Two Decisions + Observability

Person behavior reduces to:
- **Is isolating?** → Stops transmission
- **Seeks care?** → Enters healthcare system

Everything else (contact selection, notification) derives from isolation status.

### 2. The Iceberg: Observed vs Actual Cases

The `ObservationModel` tracks:
- `detection_rate` = observed_cases / true_cases
- `dark_figure` = true_cases / observed_cases (the "iceberg multiplier")

This connects directly to the SEIR notebook's ρ_sx (symptomatic detection rate).
**Healthcare can only act on what it sees.**

### 3. Intelligence is Behavior, Not Data

The `Person` class stays the same - we swap `BehaviorStrategy` implementations. This allows:

- Mixing intelligence levels in the same simulation
- Dynamic switching during simulation (adaptive resolution)
- Easy testing (mock behaviors)
- Clear separation of concerns

---

## Network Size Guidelines

| Population Size | Recommended Approach |
|-----------------|---------------------|
| N > 10,000 | Pure statistical (Level 0) |
| 2,000 < N ≤ 10,000 | Statistical with rule-based focal agents |
| 500 < N ≤ 2,000 | Rule-based (Level 1) |
| 100 < N ≤ 500 | Utility-based (Level 2) |
| 50 < N ≤ 100 | Memory-based (Level 3) |
| N ≤ 50 | Full LLM (Level 4) |

For any size, **focal agents** (patient zero, super-spreaders, key decision-makers) can be upgraded to LLM for rich narrative output.

---

## Hybrid Strategies

### Representative Agents
- 10 LLM agents representing archetypes (elderly cautious, young social, essential worker, etc.)
- Their decisions inform statistical distributions for the rest

### Focal Agents
- Patient zero, super-spreaders, bridge nodes get LLM treatment
- Everyone else is statistical

### Adaptive Resolution
- Start everyone as statistical
- Upgrade to LLM when they become "interesting" (infected + high connectivity, critical decision point, etc.)

---

## Value of LLM Agents

Beyond accuracy, LLM agents provide:

1. **Narrative Output**: "Day 15: Sarah decided not to quarantine because her daughter's wedding is Saturday and she's been planning it for two years."

2. **Explainable Decisions**: Every choice has reasoning attached

3. **Emergent Behavior**: Agents might do unexpected things that reveal model blind spots

4. **Scenario Exploration**: "What if patient zero was a healthcare worker who felt obligated to keep working?"

5. **Policy Testing**: See how different personality types respond to different interventions

---

# Part 2: Provider Agents (Healthcare Workers)

Providers are a second agent class that interact with Persons to improve outcomes. They have privileged information access (know who's infected), limited time/resources, and can influence Person behavior.

---

## Provider vs Person: Key Differences

| Aspect | Person | Provider |
|--------|--------|----------|
| **Primary Goal** | Self-interest (health, economy, social) | Patient outcomes + population health |
| **Information** | Limited (own symptoms, rumors) | Privileged (test results, case counts) |
| **Decisions** | `is_isolating()`, `seeks_care()` | `priority_score()`, `should_warn()` |
| **Risk** | Community exposure | Occupational exposure (higher) |
| **Network Position** | Peer connections | Hub (many patient connections) |

---

## Core Simplification: Two Provider Decisions

Just like Person, Provider behavior reduces to two essential decisions:

1. **Priority Score**: How urgently does this patient need attention? (Returns a number for sorting)
2. **Should Warn**: Should I warn this contact about potential exposure? (Returns boolean)

Everything else (care time, PPE usage, etc.) uses constants or simple rules.

---

## Provider Architecture

### Simplified ProviderStrategy Protocol

```python
from typing import Protocol
from enum import Enum

class ProviderType(Enum):
    """Types of healthcare providers."""
    NURSE = "nurse"
    DOCTOR = "doctor"
    CONTACT_TRACER = "contact_tracer"
    COMMUNITY_HEALTH_WORKER = "community_health_worker"

@dataclass
class ProviderContext(MacroContext):
    """Extended context for provider decisions."""
    # Inherited: day, policy_level, observed_infection_rate, news_severity

    # Provider-specific context (privileged information)
    true_case_count: int        # Actual cases (not just observed)
    beds_available: int
    current_caseload: int
    fatigue_level: float        # 0-1, affects decision quality

class ProviderStrategy(Protocol):
    """Simplified protocol - just two decisions."""

    def priority_score(self, patient: 'Person', ctx: ProviderContext) -> float:
        """How urgently does this patient need attention? Higher = more urgent."""
        ...

    def should_warn(self, contact: 'Person', source_patient: 'Person', ctx: ProviderContext) -> bool:
        """Should I warn this contact about their exposure?"""
        ...
```

**Key insight**: Sort patients by `priority_score()`, then warn contacts where `should_warn()` returns True.
Everything else (PPE, care time) uses simple constants.

---

### Provider Base Class (Simplified)

```python
@dataclass
class Provider:
    """A healthcare provider in the simulation."""
    id: int
    name: str
    provider_type: ProviderType

    # Behavior strategy (pluggable like Person)
    strategy: ProviderStrategy = field(default_factory=lambda: StatisticalProviderStrategy())

    # Provider state
    state: DiseaseState = DiseaseState.SUSCEPTIBLE  # Providers can get infected!
    fatigue: float = 0.0

    # Knowledge (privileged information)
    known_cases: set[int] = field(default_factory=set)
    warned_contacts: set[int] = field(default_factory=set)

    # Statistics
    patients_seen: int = 0
    warnings_issued: int = 0

    def is_available(self) -> bool:
        """Check if provider can work."""
        return self.state == DiseaseState.SUSCEPTIBLE and self.fatigue < 0.9
```

---

### Level 0: StatisticalProviderStrategy (Simplified)

```python
@dataclass
class StatisticalProviderStrategy:
    """Pure probabilistic - two simple decisions."""
    warning_probability: float = 0.3  # P(warn | contact of known case)

    def priority_score(self, patient, ctx):
        """Random priority (no clinical reasoning)."""
        return random.random()

    def should_warn(self, contact, source_patient, ctx):
        """Warn with fixed probability."""
        return random.random() < self.warning_probability
```

---

### Level 1: RuleBasedProviderStrategy (Simplified)

```python
@dataclass
class RuleBasedProviderStrategy:
    """If-then rules based on clinical guidelines."""

    def priority_score(self, patient, ctx):
        """Score based on severity and risk factors."""
        score = 0

        # Severity
        if patient.state == DiseaseState.HOSPITALIZED:
            score += 100
        elif patient.state == DiseaseState.SYMPTOMATIC:
            score += 50

        # Risk factors
        if patient.age > 65:
            score += 30
        if patient.age > 80:
            score += 20

        return score

    def should_warn(self, contact, source_patient, ctx):
        """Prioritize warning high-risk contacts."""
        # Always warn elderly
        if contact.age > 65:
            return True
        # Warn if outbreak is serious
        if ctx.observed_infection_rate > 0.05:
            return True
        return False
```

---

### Level 2: UtilityBasedProviderStrategy (Simplified)

```python
@dataclass
class UtilityBasedProviderStrategy:
    """Utility-based optimization."""
    life_years_weight: float = 1.0

    def priority_score(self, patient, ctx):
        """Optimize expected life-years saved."""
        # Base survival benefit from treatment
        treatment_benefit = 0.1

        # Life years remaining
        life_years = max(0, 85 - patient.age)

        # Severity multiplier
        if patient.state == DiseaseState.HOSPITALIZED:
            treatment_benefit *= 2.0

        return self.life_years_weight * treatment_benefit * life_years

    def should_warn(self, contact, source_patient, ctx):
        """Warn if expected infections prevented > threshold."""
        # Expected onward transmission if not warned
        expected_transmission = len(contact.contacts) * 0.1 * 0.3
        return expected_transmission > 0.5
```

---

### Level 3: MemoryBasedProviderStrategy (Simplified)

```python
class MemoryBasedProviderStrategy:
    """Learns from observed outcomes."""

    def __init__(self):
        self.outcomes_by_age: dict[str, list[str]] = {"young": [], "elderly": []}
        self.warning_effectiveness: list[bool] = []

    def priority_score(self, patient, ctx):
        """Score informed by past outcomes."""
        score = 0

        # Base clinical factors
        if patient.age > 65:
            score += 30
        if patient.state == DiseaseState.HOSPITALIZED:
            score += 50

        # Learn: if elderly patients have been dying, prioritize them more
        elderly_outcomes = self.outcomes_by_age["elderly"]
        if elderly_outcomes:
            mortality_rate = sum(1 for o in elderly_outcomes if o == "deceased") / len(elderly_outcomes)
            if patient.age > 65:
                score += mortality_rate * 50

        return score

    def should_warn(self, contact, source_patient, ctx):
        """Learn whether warnings are effective."""
        # If warnings have been working, be more aggressive
        if self.warning_effectiveness:
            success_rate = sum(self.warning_effectiveness) / len(self.warning_effectiveness)
            return random.random() < (0.3 + success_rate * 0.4)
        return random.random() < 0.3

    def record_outcome(self, patient_age: int, outcome: str):
        """Learn from patient outcome."""
        key = "elderly" if patient_age > 65 else "young"
        self.outcomes_by_age[key].append(outcome)

    def record_warning_result(self, warning_helped: bool):
        """Learn if warning led to isolation."""
        self.warning_effectiveness.append(warning_helped)
```

---

### Level 4: LLMProviderStrategy (Simplified)

```python
@dataclass
class ProviderPersona:
    """Rich persona for LLM provider agents."""
    name: str
    provider_type: ProviderType
    years_experience: int
    personality: list[str]  # ["thorough", "compassionate"]
    values: list[str]       # ["patient_first", "equity"]

class LLMProviderStrategy:
    """LLM reasoning for two key decisions - with narrative output."""

    def __init__(self, persona: ProviderPersona, llm_client, budget: LLMBudget):
        self.persona = persona
        self.llm = llm_client
        self.budget = budget
        self.decision_log: list[dict] = []

    async def priority_score(self, patient, ctx) -> tuple[float, str]:
        """Decide patient priority with clinical reasoning."""

        if not self.budget.can_make_call():
            return float(100 - patient.age), "Budget fallback"

        prompt = f"""You are Dr. {self.persona.name}, {self.persona.years_experience} years experience.
Values: {', '.join(self.persona.values)}

Patient: {patient.name}, {patient.age}yo, {patient.state.value}
Situation: Day {int(ctx.day)}, {ctx.current_caseload} cases, {ctx.beds_available} beds

How urgent is this patient (0-100 scale)?

SCORE: [number 0-100]
WHY: [1 sentence, first person]"""

        response = await self.llm.complete(prompt, max_tokens=60)
        self.budget.record_call(60)

        try:
            score = float(response.split("SCORE:")[1].split("\n")[0].strip())
        except:
            score = 50.0

        reasoning = response.split("WHY:")[1].strip() if "WHY:" in response else ""

        self.decision_log.append({
            "day": ctx.day,
            "patient": patient.name,
            "score": score,
            "reasoning": reasoning
        })

        return score, reasoning

    async def should_warn(self, contact, source_patient, ctx) -> tuple[bool, str]:
        """Decide whether to warn a contact."""

        if not self.budget.can_make_call():
            return True, "Budget fallback - warn by default"

        prompt = f"""You are Dr. {self.persona.name}.

{contact.name} ({contact.age}yo) was in contact with a confirmed case.
Current outbreak: {ctx.observed_infection_rate:.1%} infection rate.

Should you call to warn them?

WARN: [YES/NO]
WHY: [1 sentence]"""

        response = await self.llm.complete(prompt, max_tokens=50)
        self.budget.record_call(50)

        decision = "YES" in response.split("WARN:")[1].split("\n")[0].upper()
        reasoning = response.split("WHY:")[1].strip() if "WHY:" in response else ""

        return decision, reasoning
```

---

## Provider-Person Interactions (Simplified)

### How Provider Warnings Affect Person Behavior

```python
def provider_warns_person(provider: Provider, person: Person, ctx: MacroContext):
    """Provider warning increases person's isolation probability."""

    provider.warnings_issued += 1
    provider.warned_contacts.add(person.id)

    # Mark person as warned (affects their behavior)
    person.was_warned = True
    person.warned_at = ctx.day

    # Effect depends on person's behavior type
    if isinstance(person.behavior, MemoryBehavior):
        person.behavior.perceived_severity += 0.2

    elif isinstance(person.behavior, LLMBehavior):
        person.behavior.memory.append(
            f"Day {int(ctx.day)}: Healthcare worker called to warn me about exposure."
        )

    # For Statistical/RuleBased: the `was_warned` flag can increase isolation probability
```

**Key insight**: A warning doesn't force behavior - it shifts probabilities. The Person's `is_isolating()` method checks `was_warned` to increase compliance.

---

## Provider in the DES Loop (Simplified)

```python
class HealthcareSystem:
    """Integrates providers into the DES simulation."""

    def __init__(self, env: Environment, providers: list[Provider], network: SocialNetwork,
                 observation_model: ObservationModel):
        self.env = env
        self.providers = providers
        self.network = network
        self.observation_model = observation_model

        # Start provider process
        env.process(self._daily_provider_loop())

    def _daily_provider_loop(self) -> Generator:
        """Daily provider activities."""

        while True:
            ctx = ProviderContext(
                day=self.env.now,
                policy_level=self.current_policy_level,
                observed_infection_rate=self.observation_model.detection_rate,
                news_severity="concerned" if self.observation_model.observed_cases > 10 else "calm",
                true_case_count=self.observation_model.true_cases,
                beds_available=self.supply_chain.beds_available,
                current_caseload=self.observation_model.observed_cases,
                fatigue_level=0.0
            )

            for provider in self.providers:
                if not provider.is_available():
                    continue

                # Get observed (detected) cases for this provider
                observed_patients = [
                    p for p in self.network.people.values()
                    if p.is_observed and p.state == DiseaseState.SYMPTOMATIC
                ]

                # Sort by priority score
                scored = [(provider.strategy.priority_score(p, ctx), p) for p in observed_patients]
                scored.sort(reverse=True, key=lambda x: x[0])

                # Treat top patients, warn their contacts
                for score, patient in scored[:5]:  # Capacity limit
                    provider.patients_seen += 1

                    # Warn contacts
                    for contact_id in patient.contacts:
                        contact = self.network.people[contact_id]
                        if contact.id not in provider.warned_contacts:
                            if provider.strategy.should_warn(contact, patient, ctx):
                                provider_warns_person(provider, contact, ctx)

            # Wait until next day
            yield self.env.timeout(1.0)
```

**Key insight**: Providers can only see `is_observed` patients - connecting to the ObservationModel.
They prioritize using `priority_score()` and warn contacts using `should_warn()`.

---

## ProviderFactory (Simplified)

```python
class ProviderFactory:
    """Creates providers with appropriate intelligence levels."""

    def __init__(self, num_providers: int, llm_client=None, llm_budget: int = 20):
        self.n = num_providers
        self.llm_client = llm_client
        self.budget = LLMBudget(max_calls=llm_budget * 50)

    def create_provider(self, id: int, provider_type: ProviderType) -> Provider:
        """Create provider with appropriate intelligence level."""
        name = f"Dr_{id}"

        # Providers have higher intelligence thresholds (fewer of them, high impact)
        if self.n <= 5 and self.llm_client:
            strategy = self._create_llm_strategy(name, provider_type)
        elif self.n <= 20:
            strategy = MemoryBasedProviderStrategy()
        elif self.n <= 50:
            strategy = UtilityBasedProviderStrategy()
        else:
            strategy = StatisticalProviderStrategy()

        return Provider(id=id, name=name, provider_type=provider_type, strategy=strategy)

    def _create_llm_strategy(self, name: str, provider_type: ProviderType) -> LLMProviderStrategy:
        persona = ProviderPersona(
            name=name,
            provider_type=provider_type,
            years_experience=random.randint(3, 25),
            personality=random.sample(["thorough", "compassionate", "pragmatic"], 2),
            values=random.sample(["patient_first", "equity", "community_health"], 2),
        )
        return LLMProviderStrategy(persona, self.llm_client, self.budget)
```

---

## Summary: Provider Components

| Component | Purpose | Complexity |
|-----------|---------|------------|
| `ProviderStrategy` protocol | Two methods: `priority_score()`, `should_warn()` | Low |
| `StatisticalProviderStrategy` | Random priority, probabilistic warnings | Low |
| `RuleBasedProviderStrategy` | Clinical guidelines | Low |
| `UtilityBasedProviderStrategy` | Optimize life-years | Medium |
| `MemoryBasedProviderStrategy` | Learn from outcomes | Medium |
| `LLMProviderStrategy` | Clinical reasoning with narrative | High |
| `Provider` class | Provider state | Low |
| `HealthcareSystem` | Integrate into DES | Medium |
| `ProviderFactory` | Create mixed populations | Low |

---

## Provider-Person Interaction

| Provider Action | Person Effect |
|----------------|---------------|
| **Warning** | Sets `person.was_warned = True`, increases isolation probability |

**Key insight**: Provider's `should_warn()` → Person's `is_isolating()` probability increases.
The two agent types interact through simple state changes, not complex protocols.

---

## Value of Intelligent Providers

1. **Priority Narratives**: "I scored Mrs. Johnson higher because she's elderly and symptomatic."

2. **Warning Decisions**: "I warned the school contacts because there's a cluster emerging."

3. **Adaptive Learning**: Memory-based providers learn which warning strategies work.

4. **Policy Testing**: See how different triage approaches affect outcomes.
