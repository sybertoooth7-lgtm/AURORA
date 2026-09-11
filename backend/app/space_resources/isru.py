"""ISRU Plant simulation.

Models an integrated In-Situ Resource Utilization plant with multiple
extraction subsystems, power management, storage tanks, and production
logging.  The plant coordinates subsystems, manages power budget, and
tracks cumulative production.
"""

from dataclasses import dataclass

from app.space_resources.extraction import (
    ExtractionProcess,
    ExtractionResult,
    ExtractionStatus,
)


@dataclass
class StorageTank:
    resource_type: str
    capacity_kg: float
    level_kg: float = 0.0
    boiloff_rate_kg_per_day: float = 0.0

    @property
    def available_capacity_kg(self) -> float:
        return self.capacity_kg - self.level_kg

    @property
    def fill_fraction(self) -> float:
        return self.level_kg / self.capacity_kg if self.capacity_kg > 0 else 0.0

    def add(self, mass_kg: float) -> float:
        accepted = min(mass_kg, self.available_capacity_kg)
        self.level_kg += accepted
        return accepted

    def remove(self, mass_kg: float) -> float:
        removed = min(mass_kg, self.level_kg)
        self.level_kg -= removed
        return removed

    def tick_boiloff(self, dt_days: float) -> float:
        loss = min(self.level_kg, self.boiloff_rate_kg_per_day * dt_days)
        self.level_kg -= loss
        return loss


@dataclass
class ISRUComponent:
    name: str
    process: ExtractionProcess
    mass_kg: float = 10.0

    @property
    def is_running(self) -> bool:
        return self.process.status == ExtractionStatus.RUNNING

    def start(self) -> None:
        self.process.start()

    def stop(self) -> None:
        self.process.stop()


@dataclass
class ProductionRecord:
    hours: float
    results: list[ExtractionResult]
    total_energy_wh: float
    total_mass_kg: float


class ISRUPlant:
    def __init__(
        self,
        name: str = "aurora_isru_01",
        max_power_w: float = 500.0,
    ):
        self.name = name
        self._max_power_w = max_power_w
        self._components: dict[str, ISRUComponent] = {}
        self._tanks: dict[str, StorageTank] = {}
        self._history: list[ProductionRecord] = []
        self._total_energy_wh = 0.0

    def add_component(self, component: ISRUComponent) -> None:
        self._components[component.name] = component

    def add_tank(self, tank: StorageTank) -> None:
        self._tanks[tank.resource_type] = tank

    def available_power_w(self) -> float:
        used = sum(
            c.process._power_w
            for c in self._components.values()
            if c.is_running
        )
        return max(0.0, self._max_power_w - used)

    def start_all(self) -> None:
        for comp in self._components.values():
            if self.available_power_w() >= comp.process._power_w:
                comp.start()

    def stop_all(self) -> None:
        for comp in self._components.values():
            comp.stop()

    def run_cycle(self, hours: float) -> list[ExtractionResult]:
        all_results: list[ExtractionResult] = []
        total_energy = 0.0
        total_mass = 0.0
        for comp in self._components.values():
            if not comp.is_running:
                continue
            result = comp.process.extract(hours)
            all_results.append(result)
            total_energy += result.energy_used_wh
            total_mass += result.mass_produced_kg
            tank = self._tanks.get(comp.process.resource_type)
            if tank and result.mass_produced_kg > 0:
                tank.add(result.mass_produced_kg)
        self._total_energy_wh += total_energy
        self._history.append(ProductionRecord(
            hours=hours,
            results=all_results,
            total_energy_wh=total_energy,
            total_mass_kg=total_mass,
        ))
        return all_results

    def tick_boiloff(self, dt_days: float) -> dict[str, float]:
        losses: dict[str, float] = {}
        for resource_type, tank in self._tanks.items():
            losses[resource_type] = round(tank.tick_boiloff(dt_days), 6)
        return losses

    def inventory(self) -> dict[str, float]:
        return {rt: round(t.level_kg, 4) for rt, t in self._tanks.items()}

    @property
    def total_energy_wh(self) -> float:
        return self._total_energy_wh

    @property
    def production_count(self) -> int:
        return len(self._history)

    @property
    def status(self) -> dict:
        return {
            "name": self.name,
            "components": {
                name: {"running": c.is_running, "mass_kg": c.mass_kg}
                for name, c in self._components.items()
            },
            "tanks": self.inventory(),
            "available_power_w": self.available_power_w(),
            "total_energy_wh": round(self._total_energy_wh, 2),
            "cycles": len(self._history),
        }
