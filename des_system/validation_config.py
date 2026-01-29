"""
Shared Parameter Bridge for DES ↔ SEIR Validation.

Defines epidemic scenarios as scale-agnostic disease parameters,
then derives both SEIR ODE parameters and DES SimulationConfig
from the same source of truth.
"""

from dataclasses import dataclass

from seir_ode import SEIRParams
from config import SimulationConfig, DiseaseConfig, NetworkConfig


@dataclass
class EpidemicScenario:
    """
    Scale-agnostic disease parameters.

    This is the single source of truth. Both the SEIR ODE solver
    and the DES simulation derive their parameters from here.
    """
    name: str
    R0: float                # Basic reproduction number
    incubation_days: float   # Mean days in Exposed state
    infectious_days: float   # Mean total days infectious (maps to SEIR I→R)

    def to_seir_params(self, population: int) -> SEIRParams:
        """Generate SEIR ODE parameters."""
        return SEIRParams(
            R0=self.R0,
            incubation_days=self.incubation_days,
            infectious_days=self.infectious_days,
            population=population,
        )

    def to_des_config(
        self,
        population: int,
        initial_infections: int = 3,
        duration_days: float = 180.0,
        avg_contacts: int = 10,
        rewire_prob: float = 0.4,
        daily_contact_rate: float = 0.5,
        random_seed: int | None = None,
    ) -> SimulationConfig:
        """
        Generate DES SimulationConfig with parameters derived from the scenario.

        The key derivation:
            β = R0 × γ = R0 / infectious_days
            β ≈ transmission_prob × daily_contact_rate × avg_contacts  (in well-mixed network)
            ∴ transmission_prob = β / (daily_contact_rate × avg_contacts)

        The DES splits infectious_days into two phases:
            infectious_period (pre-symptomatic, contagious) + symptomatic_period (contagious)
        We split roughly 20/80 to match the original DES structure.
        """
        # Derive β from R0
        gamma = 1.0 / self.infectious_days
        beta = self.R0 * gamma

        # Derive transmission_prob to hit target β
        transmission_prob = beta / (daily_contact_rate * avg_contacts)

        # Clamp to valid probability range
        if transmission_prob > 1.0:
            raise ValueError(
                f"Cannot achieve R0={self.R0} with avg_contacts={avg_contacts}, "
                f"daily_contact_rate={daily_contact_rate}. "
                f"Derived transmission_prob={transmission_prob:.3f} > 1.0. "
                f"Increase avg_contacts or daily_contact_rate."
            )

        # Split infectious time into pre-symptomatic + symptomatic
        # Keep ratio roughly matching original DES defaults (2/7 ≈ 22% pre-symptomatic)
        pre_symptomatic_fraction = 0.22
        infectious_period = self.infectious_days * pre_symptomatic_fraction
        symptomatic_period = self.infectious_days * (1 - pre_symptomatic_fraction)

        config = SimulationConfig(
            initial_infections=initial_infections,
            duration_days=duration_days,
            random_seed=random_seed,
        )

        # Network
        config.network = NetworkConfig(
            n_people=population,
            avg_contacts=avg_contacts,
            rewire_prob=rewire_prob,
        )

        # Disease - derived from scenario
        config.disease = DiseaseConfig(
            transmission_prob=transmission_prob,
            daily_contact_rate=daily_contact_rate,
            exposure_period=self.incubation_days,
            infectious_period=infectious_period,
            symptomatic_period=symptomatic_period,
            # Disable hospitalization/mortality for pure SEIR validation
            # (hospitalized patients are removed from transmission, distorting I→R)
            hospitalization_prob=0.0,
            mortality_prob=0.0,
        )

        return config

    def describe(self) -> str:
        """Human-readable summary of the scenario and derived parameters."""
        gamma = 1.0 / self.infectious_days
        beta = self.R0 * gamma
        return (
            f"Scenario: {self.name}\n"
            f"  R₀ = {self.R0}\n"
            f"  Incubation = {self.incubation_days} days (σ = {1/self.incubation_days:.4f})\n"
            f"  Infectious = {self.infectious_days} days (γ = {gamma:.4f})\n"
            f"  β = R₀ × γ = {beta:.4f}\n"
        )


# ── Preset Scenarios ──────────────────────────────────────────────

COVID_LIKE = EpidemicScenario(
    name="COVID-like",
    R0=2.5,
    incubation_days=5.0,
    infectious_days=9.0,
)

FLU_LIKE = EpidemicScenario(
    name="Influenza-like",
    R0=1.5,
    incubation_days=2.0,
    infectious_days=5.0,
)

MEASLES_LIKE = EpidemicScenario(
    name="Measles-like",
    R0=12.0,
    incubation_days=10.0,
    infectious_days=8.0,
)


if __name__ == "__main__":
    for scenario in [COVID_LIKE, FLU_LIKE, MEASLES_LIKE]:
        print(scenario.describe())

        # Show DES derivation for N=5000
        try:
            des_config = scenario.to_des_config(population=5000, avg_contacts=10)
            print(f"  DES config (N=5000, k=10):")
            print(f"    transmission_prob = {des_config.disease.transmission_prob:.4f}")
            print(f"    daily_contact_rate = {des_config.disease.daily_contact_rate:.4f}")
            print(f"    exposure_period = {des_config.disease.exposure_period:.1f}")
            print(f"    infectious_period = {des_config.disease.infectious_period:.1f}")
            print(f"    symptomatic_period = {des_config.disease.symptomatic_period:.1f}")
            print()
        except ValueError as e:
            print(f"  ⚠ {e}")
            print()
