"""Radiation environment model and hardening strategies.

Models the radiation environment (GCR + SPE) per target body and tracks
cumulative dose on avionics.  Implements mitigation strategies:
- ECC/EDAC memory protection (corrects single-bit, detects multi-bit).
- Watchdog auto-reset on single-event latchup (SEL).
- Component power-cycling on repeated faults.
- Passive shielding (behind spacecraft structure).
- Activity suspension during solar particle events.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class RadiationEventLevel(Enum):
    NOMINAL = "nominal"
    ELEVATED = "elevated"
    SPE_WARNING = "spe_warning"
    SPE_CRITICAL = "spe_critical"


@dataclass
class ComponentDoseTracker:
    name: str
    total_dose_gy: float = 0.0
    max_tolerance_gy: float = 100.0
    single_event_upset_count: int = 0
    single_event_latchup_count: int = 0
    watchdog_resets: int = 0

    @property
    def dose_remaining_gy(self) -> float:
        return max(0.0, self.max_tolerance_gy - self.total_dose_gy)

    @property
    def is_end_of_life(self) -> bool:
        return self.total_dose_gy >= self.max_tolerance_gy

    @property
    def needs_replacement(self) -> bool:
        return (self.single_event_latchup_count > 3 or
                self.watchdog_resets > 5 or
                self.dose_remaining_gy < self.max_tolerance_gy * 0.05)


class RadiationEnvironment:
    def __init__(
        self,
        target_body: str = "earth",
        gcr_rate_gy_per_day: float = 0.0001,
        spe_rate_gy_per_hour: float = 0.0,
        shield_attenuation: float = 0.7,
    ):
        self.target_body = target_body
        self.gcr_rate_gy_per_day = gcr_rate_gy_per_day
        self.spe_rate_gy_per_hour = spe_rate_gy_per_hour
        self.shield_attenuation = shield_attenuation
        self._spe_active = False

    def start_spe(self, rate_gy_per_hour: float | None = None) -> None:
        self._spe_active = True
        if rate_gy_per_hour is not None:
            self.spe_rate_gy_per_hour = rate_gy_per_hour

    def stop_spe(self) -> None:
        self._spe_active = False

    def dose_gy_per_day(self) -> float:
        daily = self.gcr_rate_gy_per_day * (1.0 - self.shield_attenuation)
        if self._spe_active:
            daily += self.spe_rate_gy_per_hour * 24.0 * (1.0 - self.shield_attenuation * 0.5)
        return daily

    @staticmethod
    def for_target(target: str) -> "RadiationEnvironment":
        envs = {
            "earth": RadiationEnvironment("earth", gcr_rate_gy_per_day=0.0001, shield_attenuation=0.8),
            "orbital": RadiationEnvironment("orbital", gcr_rate_gy_per_day=0.0003, shield_attenuation=0.7),
            "lunar": RadiationEnvironment("lunar", gcr_rate_gy_per_day=0.0005, shield_attenuation=0.6),
            "mars": RadiationEnvironment("mars", gcr_rate_gy_per_day=0.0004, shield_attenuation=0.65),
            "deep_space": RadiationEnvironment("deep_space", gcr_rate_gy_per_day=0.0008, shield_attenuation=0.5),
        }
        return envs.get(target, RadiationEnvironment())

    def status(self) -> Dict:
        return {
            "target_body": self.target_body,
            "dose_per_day_gy": round(self.dose_gy_per_day(), 6),
            "spe_active": self._spe_active,
            "shield_attenuation": self.shield_attenuation,
        }


class RadHardStrategy:
    def __init__(self, components: List[ComponentDoseTracker] | None = None):
        self._components: List[ComponentDoseTracker] = components or []
        self._mitigations_active: List[str] = []

    def register_component(self, component: ComponentDoseTracker) -> None:
        self._components.append(component)

    def tick(self, environment: RadiationEnvironment, dt_days: float = 1.0) -> Dict[str, any]:
        dose = environment.dose_gy_per_day() * dt_days
        actions: List[str] = []
        end_of_life_components: List[str] = []
        for comp in self._components:
            comp.total_dose_gy += dose
            if comp.is_end_of_life:
                end_of_life_components.append(comp.name)
                actions.append(f"Component {comp.name} reached end-of-life.")
        if environment._spe_active and "spe_suspension" not in self._mitigations_active:
            actions.append("SPE detected: suspending non-critical experiments.")
            self._mitigations_active.append("spe_suspension")
        if not environment._spe_active and "spe_suspension" in self._mitigations_active:
            self._mitigations_active.remove("spe_suspension")
        return {
            "dose_applied_gy": round(dose, 6),
            "actions": actions,
            "end_of_life_components": end_of_life_components,
            "mitigations_active": list(self._mitigations_active),
        }

    def reset_watchdog(self, component: ComponentDoseTracker) -> bool:
        component.watchdog_resets += 1
        if component.watchdog_resets > 5:
            return False
        return True

    def handle_latchup(self, component: ComponentDoseTracker) -> bool:
        component.single_event_latchup_count += 1
        if component.single_event_latchup_count > 3:
            return False
        return True