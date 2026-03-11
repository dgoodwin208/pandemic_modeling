"""
Intelligent Disease Model — Behavioral Extension of DiseaseModel.

Subclasses DiseaseModel to consult person-level BehaviorStrategy objects
at two decision points:

1. _transmission_process: checks is_isolating() before each transmission tick
2. _determine_outcome: checks seeks_care() before hospitalization decision

The DES event engine (des_core.py), social network, and supply chain are
unchanged. Only the decision logic is extended.
"""

import random
import sys
from pathlib import Path
from typing import Generator, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "des_system"))

from des_core import Environment
from social_network import SocialNetwork, Person, DiseaseState
from supply_chain import SupplyChain
from disease_model import DiseaseModel
from config import DiseaseConfig, SupplyChainConfig

from behavior import BehaviorStrategy


class IntelligentDiseaseModel(DiseaseModel):
    """
    Disease model with person-level behavioral strategies.

    Each person can have an associated BehaviorStrategy that modifies:
    - Whether they isolate (reducing transmission)
    - Whether they seek care (affecting hospitalization)

    Persons without a registered behavior use default DiseaseModel logic,
    making this fully backward-compatible.
    """

    def __init__(
        self,
        env: Environment,
        network: SocialNetwork,
        supply_chain: SupplyChain,
        behaviors: dict[int, BehaviorStrategy],
        disease_config: Optional[DiseaseConfig] = None,
        supply_config: Optional[SupplyChainConfig] = None,
    ):
        super().__init__(env, network, supply_chain, disease_config, supply_config)
        self.behaviors = behaviors

        self.isolation_events: list[dict] = []
        self.care_decisions: list[dict] = []

    def _get_behavior(self, person: Person) -> Optional[BehaviorStrategy]:
        return self.behaviors.get(person.id)

    def _transmission_process(self, person: Person) -> Generator:
        """
        Attempt to spread disease to contacts while contagious.

        Override: checks is_isolating() before each daily transmission tick.
        If isolating, the person makes no contacts that day.
        """
        behavior = self._get_behavior(person)

        while person.is_contagious():
            # Wait one day between transmission attempts
            yield self.env.timeout(1.0)

            if not person.is_contagious():
                break

            if behavior and behavior.is_isolating():
                self.isolation_events.append({
                    "time": self.env.now,
                    "person_id": person.id,
                })
                continue

            susceptible = self.network.get_susceptible_contacts(person.id)
            if not susceptible:
                continue

            n_interactions = max(
                1,
                int(len(susceptible) * self.config.daily_contact_rate)
            )
            contacts_today = random.sample(
                susceptible,
                min(n_interactions, len(susceptible))
            )

            for contact in contacts_today:
                if random.random() < self.config.transmission_prob:
                    self.infect_person(contact, source=person)

    def _determine_outcome(self, person: Person) -> Generator:
        """
        Determine final outcome: recovery, hospitalization, or death.

        Override: checks seeks_care() before hospitalization decision.
        - True  → person enters hospitalization path
        - False → person recovers at home (skips hospital entirely)
        - None  → use default probabilistic logic from parent
        """
        behavior = self._get_behavior(person)

        if behavior:
            care_decision = behavior.seeks_care()

            if care_decision is not None:
                self.care_decisions.append({
                    "time": self.env.now,
                    "person_id": person.id,
                    "seeks_care": care_decision,
                })

                if not care_decision:
                    # Person avoids care → direct recovery
                    person.state = DiseaseState.RECOVERED
                    person.recovered_at = self.env.now
                    self.total_recoveries += 1
                    return

                # Person actively seeks care → fall through to parent
                # (which handles hospitalization, resource consumption, mortality)

        # Default behavior from parent
        yield from super()._determine_outcome(person)

    def get_behavioral_statistics(self) -> dict:
        total_care = len(self.care_decisions)
        sought_care = sum(1 for d in self.care_decisions if d["seeks_care"])

        return {
            "total_isolation_events": len(self.isolation_events),
            "total_care_decisions": total_care,
            "sought_care": sought_care,
            "avoided_care": total_care - sought_care,
        }
