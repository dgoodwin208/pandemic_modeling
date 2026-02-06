"""
Stepping DES for one city — 7-state epidemic on a social network.

Extended version with:
  - 7 disease states: S, E, I_minor, I_needs_care, I_receiving_care, R, D
  - Gamma-distributed waiting times (CV=0.4 with shape=6.25)
  - Targeted screening (70% random + 30% contact-based)
  - OBSERVED tracking via detected PIDs
  - Increasing daily death probability for untreated patients

Designed for day-by-day stepping in the multi-city coupling loop.
Each city maintains a SimPy environment that can be advanced to any
time point, paused, have external exposures injected, then resumed.

Disease parameters are derived from EpidemicScenario using the same
beta = transmission_prob * daily_contact_rate * avg_contacts mapping
validated in modules 001-003.

Provider mechanics (from module 003, with decay extension):
    Healthcare providers screen the population daily, detect infectious
    cases (if disclosed), and give advice that shifts isolation behavior.
    Advised persons isolate with P=advised_isolation_prob vs baseline.
    Advice decays: each day, advised persons revert with P=advice_decay_prob.

    Detection tracking has two layers:
    1. Permanent (_detected_ever): Once detected, an agent's state transitions
       are always tracked in observed counts (I -> R -> D).
    2. Active (_detected_day): Expires after detection_memory_days (default 7).
       After expiry, neighbors leave the contact-candidate pool (contact tracing
       stops), but outcome tracking continues.

State machine:
    S(0) -> E(1) -> I_minor(2) -> R(5)          [mild case]
                  -> I_needs_care(3) -> D(6)     [untreated, dies]
                                     -> I_receiving_care(4) -> R(5)  [treated, survives]
                                                             -> D(6)  [treated, dies]
"""

import random

import networkx as nx
import numpy as np
import simpy


# Default network parameters (same as to_des_config defaults)
DEFAULT_AVG_CONTACTS = 10
DEFAULT_REWIRE_PROB = 0.4
DEFAULT_DAILY_CONTACT_RATE = 0.5


class CityDES:
    """
    Stepping SEIR-D simulation on a Watts-Strogatz social network.

    7-state disease model with severity branching and provider screening.

    Usage:
        city = CityDES(n_people=5000, scenario=COVID_LIKE, seed_infected=10)
        for day in range(1, 301):
            city.step(until=day)
            # read city.S, city.E, city.I, city.I_minor, etc.
            city.run_provider_screening()
            city.inject_exposed(n)
    """

    def __init__(
        self,
        n_people: int,
        scenario,
        seed_infected: int = 1,
        random_seed: int | None = None,
        avg_contacts: int = DEFAULT_AVG_CONTACTS,
        rewire_prob: float = DEFAULT_REWIRE_PROB,
        daily_contact_rate: float = DEFAULT_DAILY_CONTACT_RATE,
        r0_override: float | None = None,
        # Provider parameters (0 providers = no behavioral intervention)
        n_providers: int = 0,
        screening_capacity: int = 20,
        # Behavioral parameters (defaults from module 003)
        disclosure_prob: float = 0.5,
        receptivity: float = 0.6,
        base_isolation_prob: float = 0.0,
        advised_isolation_prob: float = 0.20,
        advice_decay_prob: float = 0.0,
        # Severity parameters (from disease_params.csv via sim_config)
        severe_fraction: float = 0.15,
        care_survival_prob: float = 0.85,
        base_daily_death_prob: float = 0.02,
        death_prob_increase_per_day: float = 0.015,
        gamma_shape: float = 6.25,
        care_quality: float = 1.0,
        # Random mixing: fraction of contacts with random agents (vs network neighbors)
        p_random: float = 0.15,
        # Mobile phone reach: fraction of population reachable by AI providers.
        # Gates effective disclosure, receptivity, and isolation compliance.
        # Agents without phones fall back to baseline behavioral parameters.
        mobile_phone_reach: float = 1.0,
        # Detection memory window (days). 0 = infinite (legacy).
        detection_memory_days: int = 7,
        # Behavioral diagnosis accuracy when lab supplies are depleted.
        # 0.0 = disabled, 0.5 = 50% (default), 1.0 = perfect clinical dx.
        behavioral_diagnosis_accuracy: float = 0.5,
        # Supply chain (None = disabled, backward compatible)
        city_supply=None,
    ):
        # Seed RNGs
        self._rng = random.Random(random_seed)
        self._np_rng = np.random.RandomState(random_seed)

        self.n_people = n_people
        self._p_random = p_random
        self.env = simpy.Environment()

        # Disease parameters (same derivation as validation_config.to_des_config)
        r0 = r0_override if r0_override is not None else scenario.R0
        self.incubation_days = scenario.incubation_days
        self.infectious_days = scenario.infectious_days
        gamma = 1.0 / scenario.infectious_days
        beta = r0 * gamma
        self.transmission_prob = beta / (daily_contact_rate * avg_contacts)
        self.daily_contact_rate = daily_contact_rate

        if self.transmission_prob > 1.0:
            raise ValueError(
                f"Cannot achieve R0={r0} with avg_contacts={avg_contacts}, "
                f"daily_contact_rate={daily_contact_rate}. "
                f"Derived transmission_prob={self.transmission_prob:.3f} > 1.0."
            )

        # Severity parameters
        self._severe_fraction = severe_fraction
        self._care_survival_prob = care_survival_prob
        self._base_daily_death_prob = base_daily_death_prob
        self._death_prob_increase_per_day = death_prob_increase_per_day
        self._gamma_shape = gamma_shape
        self._care_quality = care_quality

        # Provider parameters
        self._n_providers = n_providers
        self._screening_capacity = screening_capacity
        self._disclosure_prob = disclosure_prob
        self._receptivity = receptivity
        self._base_isolation_prob = base_isolation_prob
        self._advised_isolation_prob = advised_isolation_prob
        self._advice_decay_prob = advice_decay_prob

        # Per-agent mobile phone ownership (gates AI provider reach)
        self._has_phone = self._np_rng.random(n_people) < mobile_phone_reach

        # Per-agent behavioral state: has this person accepted provider advice?
        self._provider_advised = np.zeros(n_people, dtype=np.bool_)

        # Build social network (Watts-Strogatz small-world)
        G = nx.watts_strogatz_graph(
            n_people, k=avg_contacts, p=rewire_prob,
            seed=random_seed,
        )
        self._neighbors = [list(G.neighbors(i)) for i in range(n_people)]

        # Agent states: 0=S, 1=E, 2=I_minor, 3=I_needs_care, 4=I_receiving_care, 5=R, 6=D
        self._states = np.zeros(n_people, dtype=np.int8)

        # Compartment counts: [S, E, I_minor, I_needs, I_care, R, D]
        self._counts = [n_people, 0, 0, 0, 0, 0, 0]

        # --- OBSERVED tracking (incremental counters) ---
        # Permanent set of all agents ever detected (for outcome tracking).
        # Once detected, an agent's state transitions are always tracked.
        self._detected_ever: set[int] = set()
        # Maps PID -> day of detection. Detections expire after
        # detection_memory_days (for contact tracing only).
        self._detected_day: dict[int, int] = {}
        self._new_detections_today: int = 0
        # Observed compartment counts: [S, E, I_minor, I_needs, I_care, R, D]
        # Updated incrementally on state transitions for detected-ever agents.
        self._obs_counts = [0, 0, 0, 0, 0, 0, 0]
        # Contact candidates for targeted screening, rebuilt from active
        # detections' neighbors after each expiry pass.
        self._contact_candidates: set[int] = set()

        # Detection memory: how many days a detection remains "active".
        # After this window, the agent's state is no longer tracked in
        # _obs_counts and their neighbors leave the contact-candidate pool.
        # 0 = infinite memory (legacy behavior).
        self._detection_memory_days = detection_memory_days
        self._behavioral_dx_accuracy = behavioral_diagnosis_accuracy

        # Supply chain integration (None = no resource constraints)
        self._supply = city_supply
        # Vaccination tracking: set of vaccinated agent PIDs
        self._vaccinated: set[int] = set()

        # Seed initial infections (directly to I_minor, matching ODE seeding)
        indices = self._rng.sample(range(n_people), min(seed_infected, n_people))
        for idx in indices:
            self._transition(idx, 0, 2)  # S -> I_minor
            self.env.process(self._infectious_minor_process(idx))

    # -- Gamma-distributed waiting times ---------------------------------------

    def _gamma_wait(self, mean_days: float) -> float:
        """Sample from Gamma(shape, scale=mean/shape) distribution.

        With shape=6.25 and CV=1/sqrt(shape)=0.4, this gives more
        realistic peaked waiting times than exponential (CV=1.0).
        """
        scale = mean_days / self._gamma_shape
        return max(0.01, self._np_rng.gamma(self._gamma_shape, scale))

    def _transition(self, idx: int, from_state: int, to_state: int) -> None:
        """Move agent idx from from_state to to_state, updating all counters."""
        self._states[idx] = to_state
        self._counts[from_state] -= 1
        self._counts[to_state] += 1
        # Track observed state for ALL ever-detected agents (permanent)
        if idx in self._detected_ever:
            self._obs_counts[from_state] -= 1
            self._obs_counts[to_state] += 1

    # -- State readouts --------------------------------------------------------

    @property
    def S(self) -> int:
        return self._counts[0]

    @property
    def E(self) -> int:
        return self._counts[1]

    @property
    def I(self) -> int:  # noqa: E743
        """Total infectious (all I sub-states) — backward compatible."""
        return self._counts[2] + self._counts[3] + self._counts[4]

    @property
    def I_minor(self) -> int:
        return self._counts[2]

    @property
    def I_needs_care(self) -> int:
        return self._counts[3]

    @property
    def I_receiving_care(self) -> int:
        return self._counts[4]

    @property
    def R(self) -> int:
        return self._counts[5]

    @property
    def D(self) -> int:
        return self._counts[6]

    @property
    def infection_fraction(self) -> float:
        return self.I / self.n_people if self.n_people > 0 else 0.0

    @property
    def traveling_infection_fraction(self) -> float:
        """Fraction of population that is infectious AND not isolating.

        Isolating individuals don't travel, so inter-city coupling should
        use this instead of raw infection_fraction.

        For each infectious person:
        - If not advised: they travel normally (count as 1)
        - If advised with phone: isolate with P=advised_isolation_prob (count as 1-P)
        - If advised without phone: use base_isolation_prob
        """
        if self.n_people == 0:
            return 0.0

        # Find infectious agents (states 2, 3, 4)
        infectious_mask = (self._states >= 2) & (self._states <= 4)
        n_infectious = infectious_mask.sum()

        if n_infectious == 0:
            return 0.0

        # Calculate expected travelers among infectious
        # Advised with phone: travel with P = (1 - advised_isolation_prob)
        # Advised without phone: travel with P = (1 - base_isolation_prob)
        # Not advised: travel with P = 1
        advised_with_phone = infectious_mask & self._provider_advised & self._has_phone
        advised_no_phone = infectious_mask & self._provider_advised & ~self._has_phone
        not_advised = infectious_mask & ~self._provider_advised

        expected_travelers = (
            not_advised.sum() * 1.0 +
            advised_no_phone.sum() * (1.0 - self._base_isolation_prob) +
            advised_with_phone.sum() * (1.0 - self._advised_isolation_prob)
        )

        return expected_travelers / self.n_people

    @property
    def advised_fraction(self) -> float:
        """Fraction of population that has accepted provider advice."""
        return self._provider_advised.sum() / self.n_people if self.n_people > 0 else 0.0

    # -- OBSERVED state readouts -----------------------------------------------

    @property
    def observed_I(self) -> int:
        """Count of detected-ever agents currently infectious (states 2, 3, or 4)."""
        return self._obs_counts[2] + self._obs_counts[3] + self._obs_counts[4]

    @property
    def observed_R(self) -> int:
        """Count of detected-ever agents currently recovered (state 5)."""
        return self._obs_counts[5]

    @property
    def observed_D(self) -> int:
        """Count of detected-ever agents currently dead (state 6)."""
        return self._obs_counts[6]

    @property
    def total_detected(self) -> int:
        """Total agents ever detected (permanent)."""
        return len(self._detected_ever)

    @property
    def active_detections(self) -> int:
        """Agents with active detection (for contact tracing)."""
        return len(self._detected_day)

    @property
    def new_detections_today(self) -> int:
        return self._new_detections_today

    # -- Stepping interface ----------------------------------------------------

    def step(self, until: float) -> None:
        """Advance the SimPy environment to the given time."""
        self.env.run(until=until)

    def inject_exposed(self, n_exposed: float) -> None:
        """
        Inject external exposures from inter-city travel coupling.

        Uses stochastic rounding to preserve expected value.
        """
        n_int = int(n_exposed)
        if self._rng.random() < (n_exposed - n_int):
            n_int += 1
        if n_int <= 0:
            return

        susceptible = np.where(self._states == 0)[0]
        if len(susceptible) == 0:
            return
        n_int = min(n_int, len(susceptible))

        chosen = self._np_rng.choice(susceptible, size=n_int, replace=False)
        for idx in chosen:
            self._transition(idx, 0, 1)  # S -> E
            self.env.process(self._exposed_process(idx))

    # -- Detection memory expiry ------------------------------------------------

    def _expire_detections(self, current_day: int) -> int:
        """Remove active detections older than detection_memory_days.

        Detection expiry ONLY affects contact tracing, not outcome tracking.
        When a detection expires:
        1. Agent is removed from _detected_day (contact tracing stops)
        2. _contact_candidates is rebuilt from remaining active detections
        3. Agent remains in _detected_ever (outcome tracking continues)

        Returns number of expired detections.
        """
        if self._detection_memory_days <= 0:
            return 0  # infinite memory

        expired_pids = [
            pid for pid, day in self._detected_day.items()
            if current_day - day >= self._detection_memory_days
        ]

        if not expired_pids:
            return 0

        for pid in expired_pids:
            # Remove from active tracking (contact tracing only)
            # NOTE: Do NOT touch _obs_counts - agent stays in _detected_ever
            del self._detected_day[pid]

        # Rebuild contact candidates from remaining active detections
        self._contact_candidates = set()
        for pid in self._detected_day:
            for nb in self._neighbors[pid]:
                if nb not in self._detected_day:
                    self._contact_candidates.add(nb)

        return len(expired_pids)

    # -- Provider screening (targeted 70/30 split) -----------------------------

    def run_provider_screening(self) -> dict:
        """
        Run one day of provider screening with targeted contact tracing.

        Three phases each day:

        0. **Expiry**: Detections older than detection_memory_days are removed.
           Their state is no longer tracked in _obs_counts and their neighbors
           leave the contact-candidate pool.

        1. **Decay**: Each currently-advised person reverts to baseline with
           P=advice_decay_prob.

        2. **Screening**: 70% random population sample + 30% contact-based
           (neighbors of recently detected agents). Detection requires
           infectious state + disclosure. Advice accepted with P=receptivity.

        Returns dict with screening stats.
        """
        self._new_detections_today = 0
        current_day = int(self.env.now)

        # Phase 0: Expire old detections
        expired = self._expire_detections(current_day)

        # Phase 1: Advice decay (vectorized)
        decayed = 0
        if self._advice_decay_prob > 0:
            advised_indices = np.where(self._provider_advised)[0]
            if len(advised_indices) > 0:
                decay_rolls = self._np_rng.random(len(advised_indices))
                revert_mask = decay_rolls < self._advice_decay_prob
                self._provider_advised[advised_indices[revert_mask]] = False
                decayed = int(revert_mask.sum())

        # Phase 2: Targeted screening
        if self._n_providers <= 0:
            return {"screened": 0, "detected": 0, "advice_accepted": 0,
                    "decayed": decayed}

        # Clinical visit capacity: determined by providers (no supply dependency).
        # Providers can visit, observe symptoms, and give isolation advice
        # without consuming test supplies.
        visit_capacity = self._n_providers * self._screening_capacity

        # Diagnostic test capacity: limited by available supplies.
        # Confirmatory testing requires swabs + reagents + PPE.
        test_capacity = visit_capacity  # unlimited when supply chain disabled
        if self._supply is not None:
            max_by_ppe = self._supply.ppe
            max_by_swabs = self._supply.swabs
            max_by_reagents = self._supply.reagents
            test_capacity = min(visit_capacity, max_by_ppe, max_by_swabs,
                                max_by_reagents)
            test_capacity = max(0, test_capacity)

        sample_size = min(visit_capacity, self.n_people)

        # 70% random, 30% contact-based
        random_count = int(sample_size * 0.7)
        contact_count = sample_size - random_count

        # Random sample (numpy C-level sampling)
        random_sample = self._np_rng.choice(
            self.n_people, size=random_count, replace=False,
        )

        # Contact-based: use cached contact candidates (grown incrementally)
        if self._contact_candidates and contact_count > 0:
            random_set = set(random_sample)
            eligible = self._contact_candidates - random_set
            if len(eligible) >= contact_count:
                eligible_arr = np.array(list(eligible), dtype=np.intp)
                contact_sample = self._np_rng.choice(
                    eligible_arr, size=contact_count, replace=False,
                )
            else:
                contact_sample_list = list(eligible)
                extra_needed = contact_count - len(contact_sample_list)
                if extra_needed > 0:
                    already = random_set | eligible
                    # Build pool via numpy set-difference
                    all_ids = np.arange(self.n_people, dtype=np.intp)
                    already_arr = np.array(list(already), dtype=np.intp)
                    pool = np.setdiff1d(all_ids, already_arr, assume_unique=True)
                    take = min(extra_needed, len(pool))
                    if take > 0:
                        extra = self._np_rng.choice(pool, size=take, replace=False)
                        contact_sample_list.extend(extra)
                contact_sample = np.array(contact_sample_list, dtype=np.intp)
        else:
            # No detections yet: fill contact slots with random from remainder
            already_arr = random_sample
            all_ids = np.arange(self.n_people, dtype=np.intp)
            pool = np.setdiff1d(all_ids, already_arr, assume_unique=False)
            take = min(contact_count, len(pool))
            contact_sample = self._np_rng.choice(pool, size=take, replace=False) if take > 0 else np.array([], dtype=np.intp)

        sample_arr = np.concatenate([random_sample, np.asarray(contact_sample, dtype=np.intp)])
        screened_count = len(sample_arr)

        # -- Advice (given to ALL visited, no supplies needed) ---------------------
        # Providers advise everyone they visit to reduce contacts/isolate.
        has_phone_mask = self._has_phone[sample_arr]

        # Per-agent receptivity: agents with phones use the configured
        # receptivity (elevated for AI); agents without fall back to baseline (0.6).
        receptivity_probs = np.where(
            has_phone_mask, self._receptivity, 0.6
        )

        not_advised = ~self._provider_advised[sample_arr]
        advice_rolls = self._np_rng.random(len(sample_arr))
        accept_mask = not_advised & (advice_rolls < receptivity_probs)
        self._provider_advised[sample_arr[accept_mask]] = True
        advice_accepted = int(accept_mask.sum())

        # -- Diagnostic testing (requires supplies) --------------------------------
        # Only test up to test_capacity agents. Tests confirm infection
        # and feed the surveillance/contact-tracing system.
        detected = 0
        if test_capacity > 0:
            testable_count = min(screened_count, test_capacity)
            testable_arr = sample_arr[:testable_count]

            states = self._states[testable_arr]
            det_rolls = self._np_rng.random(len(testable_arr))

            # Per-agent disclosure probability
            has_phone_test = self._has_phone[testable_arr]
            disclosure_probs = np.where(
                has_phone_test, self._disclosure_prob, 0.5
            )

            # Bulk detection: infectious (state 2,3,4) AND disclosed
            infectious_mask = (states >= 2) & (states <= 4)
            detected_mask = infectious_mask & (det_rolls < disclosure_probs)
            detected_pids = testable_arr[detected_mask]
            detected = len(detected_pids)
            self._new_detections_today = detected

            # Only loop over genuinely NEW detections (small subset)
            for pid in detected_pids:
                pid = int(pid)
                if pid not in self._detected_ever:
                    self._detected_ever.add(pid)
                    self._obs_counts[self._states[pid]] += 1
                if pid not in self._detected_day:
                    self._detected_day[pid] = current_day
                    for nb in self._neighbors[pid]:
                        if nb not in self._detected_day:
                            self._contact_candidates.add(nb)
                    self._contact_candidates.discard(pid)

            # Consume test supplies only for tested agents
            if self._supply is not None and testable_count > 0:
                self._supply.try_consume("ppe", testable_count)
                self._supply.try_consume("swabs", testable_count)
                self._supply.try_consume("reagents", testable_count)
        else:
            self._new_detections_today = 0

        # -- Behavioral diagnosis (no supplies needed) ----------------------------
        # Agents visited but not lab-tested can still be clinically assessed.
        # Lower accuracy than lab testing, but provides non-zero detection
        # when diagnostic supplies are depleted.
        behavioral_detected = 0
        untested_start = min(screened_count, max(0, test_capacity))
        if untested_start < screened_count and self._behavioral_dx_accuracy > 0:
            untested_arr = sample_arr[untested_start:]
            states_u = self._states[untested_arr]
            beh_rolls = self._np_rng.random(len(untested_arr))
            infectious_mask_u = (states_u >= 2) & (states_u <= 4)
            detected_mask_u = infectious_mask_u & (beh_rolls < self._behavioral_dx_accuracy)
            beh_detected_pids = untested_arr[detected_mask_u]
            behavioral_detected = len(beh_detected_pids)

            for pid in beh_detected_pids:
                pid = int(pid)
                if pid not in self._detected_ever:
                    self._detected_ever.add(pid)
                    self._obs_counts[self._states[pid]] += 1
                if pid not in self._detected_day:
                    self._detected_day[pid] = current_day
                    for nb in self._neighbors[pid]:
                        if nb not in self._detected_day:
                            self._contact_candidates.add(nb)
                    self._contact_candidates.discard(pid)

            self._new_detections_today += behavioral_detected

        return {
            "screened": screened_count,
            "tested": min(screened_count, max(0, test_capacity)),
            "detected": detected + behavioral_detected,
            "lab_detected": detected,
            "behavioral_detected": behavioral_detected,
            "advice_accepted": advice_accepted,
            "decayed": decayed,
            "expired": expired,
            "limited_by_supplies": (test_capacity < visit_capacity),
        }

    # -- Disease processes -----------------------------------------------------

    def _exposed_process(self, idx: int):
        """E -> I_minor progression."""
        # Incubation period (Gamma-distributed)
        duration = self._gamma_wait(self.incubation_days)
        yield self.env.timeout(duration)

        # E -> I_minor
        if self._states[idx] != 1:
            return  # state changed externally
        self._transition(idx, 1, 2)

        # Run infectious minor phase
        yield from self._infectious_minor_process(idx)

    def _is_isolating(self, idx: int) -> bool:
        """Daily stochastic isolation check (module 003 semantics).

        Advised agents with phones use advised_isolation_prob.
        Advised agents WITHOUT phones fall back to base_isolation_prob
        (they can't receive AI monitoring/reminders).
        """
        if self._provider_advised[idx] and self._has_phone[idx]:
            prob = self._advised_isolation_prob
        else:
            prob = self._base_isolation_prob
        return self._rng.random() < prob

    def _infectious_minor_process(self, idx: int):
        """I_minor: make contacts during infectious period, then branch to R or I_needs_care.

        OPTIMIZED: Batches all contacts per day using numpy vectorization.
        Yields once per day instead of per-contact (reduces SimPy overhead).
        """
        neighbors = self._neighbors[idx]
        if not neighbors:
            # Isolated node: just wait
            duration = self._gamma_wait(self.infectious_days)
            yield self.env.timeout(duration)
        else:
            contact_rate = self.daily_contact_rate * len(neighbors)
            recovery_time = self.env.now + self._gamma_wait(self.infectious_days)
            neighbors_arr = np.array(neighbors)  # Pre-convert for numpy

            while self.env.now < recovery_time:
                current_day = int(self.env.now)
                day_end = min(float(current_day + 1), recovery_time)
                time_in_day = day_end - self.env.now

                # Daily isolation check
                if self._is_isolating(idx):
                    if time_in_day > 0:
                        yield self.env.timeout(time_in_day)
                    continue

                # BATCH: Sample number of contacts for this day (Poisson)
                expected_contacts = contact_rate * time_in_day
                n_contacts = self._np_rng.poisson(expected_contacts)

                if n_contacts > 0:
                    # BATCH: Sample all targets at once
                    if self._p_random > 0:
                        # Mix of random and neighbor contacts
                        random_mask = self._np_rng.random(n_contacts) < self._p_random
                        n_random = int(random_mask.sum())
                        n_neighbor = n_contacts - n_random

                        targets = np.empty(n_contacts, dtype=np.int64)
                        if n_random > 0:
                            rand_targets = self._np_rng.randint(0, self.n_people, size=n_random)
                            # Exclude self-contacts
                            rand_targets[rand_targets == idx] = (idx + 1) % self.n_people
                            targets[random_mask] = rand_targets
                        if n_neighbor > 0:
                            targets[~random_mask] = self._np_rng.choice(neighbors_arr, size=n_neighbor)
                    else:
                        # All neighbor contacts
                        targets = self._np_rng.choice(neighbors_arr, size=n_contacts)

                    # BATCH: Filter to susceptible targets
                    target_states = self._states[targets]
                    susceptible_mask = target_states == 0

                    if susceptible_mask.any():
                        susceptible_targets = targets[susceptible_mask]

                        # BATCH: Transmission rolls with vaccination adjustment
                        tp = self.transmission_prob
                        trans_rolls = self._np_rng.random(len(susceptible_targets))

                        # Vectorized vaccination check
                        if self._vaccinated:
                            vaccinated_mask = np.isin(susceptible_targets, list(self._vaccinated))
                            effective_tp = np.where(vaccinated_mask, tp * 0.3, tp)
                        else:
                            effective_tp = tp

                        infected_mask = trans_rolls < effective_tp
                        new_infections = susceptible_targets[infected_mask]

                        # Transition each new infection (must be sequential for state consistency)
                        for target in new_infections:
                            if self._states[target] == 0:  # Double-check still susceptible
                                self._transition(target, 0, 1)  # S -> E
                                self.env.process(self._exposed_process(target))

                # Yield once per day (not per contact)
                if time_in_day > 0:
                    yield self.env.timeout(time_in_day)

        # End of infectious period: severity branching
        if self._states[idx] != 2:
            return  # state changed externally

        if self._rng.random() < self._severe_fraction:
            # I_minor -> I_needs_care
            self._transition(idx, 2, 3)
            self.env.process(self._needs_care_process(idx))
        else:
            # I_minor -> R (mild case)
            self._transition(idx, 2, 5)

    def _needs_care_process(self, idx: int):
        """I_needs_care: daily increasing death probability until care is received.

        If supply chain is enabled, admission to care is gated by bed
        availability (city_supply.try_admit()). If no beds are available,
        the patient waits with escalating death probability each day.

        If supply chain is disabled (self._supply is None), automatically
        transitions to I_receiving_care after 1 day (legacy behavior).
        """
        days_waiting = 0

        while self._states[idx] == 3:
            # Daily death check with increasing probability
            death_prob = min(
                0.95,
                self._base_daily_death_prob
                + days_waiting * self._death_prob_increase_per_day,
            )
            if self._rng.random() < death_prob:
                # Dies without care
                self._transition(idx, 3, 6)
                return

            days_waiting += 1

            # Check if patient can be admitted to care
            if self._supply is not None:
                admitted = self._supply.try_admit()
            else:
                # Legacy behavior: auto-admit after 1 day
                admitted = (days_waiting >= 1)

            if admitted:
                self._transition(idx, 3, 4)
                yield from self._receiving_care_process(idx)
                return

            yield self.env.timeout(1.0)

    def _receiving_care_process(self, idx: int):
        """I_receiving_care: wait for care resolution, then R or D.

        Care duration is Gamma-distributed (half of infectious_days).
        Survival probability is care_survival_prob * care_quality,
        where care_quality is derived from the city's medical_services_score.

        If supply chain is enabled:
        - Consumes 1 pill per day during care
        - Releases bed on exit (R or D)
        - Consumes PPE per care-day
        """
        care_duration = self._gamma_wait(self.infectious_days * 0.5)

        # Consume resources daily during care
        if self._supply is not None:
            days_in_care = max(1, int(care_duration))
            for _ in range(days_in_care):
                self._supply.try_consume("pills", 1)
                self._supply.try_consume("ppe", 2)  # PPE per care-day
                yield self.env.timeout(1.0)
            # Wait for any fractional remainder
            remainder = care_duration - days_in_care
            if remainder > 0:
                yield self.env.timeout(remainder)
        else:
            yield self.env.timeout(care_duration)

        if self._states[idx] != 4:
            # Release bed even if state changed externally
            if self._supply is not None:
                self._supply.release_bed()
            return

        effective_survival = self._care_survival_prob * self._care_quality
        if self._rng.random() < effective_survival:
            self._transition(idx, 4, 5)  # Survives -> R
        else:
            self._transition(idx, 4, 6)  # Dies despite care -> D

        # Release bed on exit
        if self._supply is not None:
            self._supply.release_bed()

    # -- Vaccination -----------------------------------------------------------

    def apply_vaccinations(self, count: int, priority_pids: list[int] | None = None) -> int:
        """Vaccinate up to `count` susceptible, unvaccinated people.

        Vaccinated people have 0.3x susceptibility to transmission.

        Args:
            count: Maximum number of vaccinations to administer.
            priority_pids: Optional list of agent IDs to vaccinate first
                (e.g., contact-traced or high-degree nodes). Only susceptible,
                unvaccinated agents from this list are chosen; remaining doses
                go to random susceptible agents.

        Returns the actual number vaccinated.
        """
        susceptible_set = {
            i for i in range(self.n_people)
            if self._states[i] == 0 and i not in self._vaccinated
        }
        if not susceptible_set:
            return 0

        chosen: list[int] = []
        remaining = count

        # Phase 1: Priority PIDs (if provided)
        if priority_pids and remaining > 0:
            priority_eligible = [p for p in priority_pids if p in susceptible_set]
            n_priority = min(remaining, len(priority_eligible))
            if n_priority > 0:
                chosen.extend(priority_eligible[:n_priority])
                remaining -= n_priority

        # Phase 2: Random from remaining susceptible
        if remaining > 0:
            random_pool = list(susceptible_set - set(chosen))
            n_random = min(remaining, len(random_pool))
            if n_random > 0:
                chosen.extend(self._rng.sample(random_pool, n_random))

        for pid in chosen:
            self._vaccinated.add(pid)
        return len(chosen)

    @property
    def vaccinated_count(self) -> int:
        """Number of people who have been vaccinated."""
        return len(self._vaccinated)

    @property
    def vaccine_priority_targets(self) -> list[int]:
        """Contact-traced susceptible agents who should be vaccinated first.

        Returns agent IDs that are:
        - Contacts of detected infectious agents (high exposure risk)
        - Currently susceptible (state 0)
        - Not yet vaccinated

        This enables provider-driven vaccine prioritization: more providers
        → more detections → more contacts identified → better targeting.
        """
        if not self._contact_candidates:
            return []
        targets = [
            pid for pid in self._contact_candidates
            if self._states[pid] == 0 and pid not in self._vaccinated
        ]
        return targets
