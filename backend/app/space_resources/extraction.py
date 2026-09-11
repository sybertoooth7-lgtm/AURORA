"""Extraction process models for water, oxygen, metals, and construction materials.

Each extractor is a simplified physics-based model of the real process:
power in → resource out, with efficiency, yield, and waste tracking.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ExtractionStatus(Enum):
    OFFLINE = "offline"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


@dataclass
class ExtractionResult:
    resource_type: str
    mass_produced_kg: float
    mass_waste_kg: float
    energy_used_wh: float
    status: ExtractionStatus
    duration_hours: float = 0.0

    @property
    def yield_fraction(self) -> float:
        total = self.mass_produced_kg + self.mass_waste_kg
        return self.mass_produced_kg / total if total > 0 else 0.0

    @property
    def specific_energy_kwh_per_kg(self) -> float:
        if self.mass_produced_kg <= 0:
            return float("inf")
        return self.energy_used_wh / 1000.0 / self.mass_produced_kg


class ExtractionProcess:
    name: str = "base_extraction"
    resource_type: str = "unknown"

    def __init__(self, efficiency: float = 0.5, power_w: float = 100.0):
        self._efficiency = max(0.0, min(1.0, efficiency))
        self._power_w = power_w
        self._status = ExtractionStatus.OFFLINE
        self._total_extracted_kg = 0.0

    def start(self) -> None:
        self._status = ExtractionStatus.RUNNING

    def stop(self) -> None:
        self._status = ExtractionStatus.OFFLINE

    def extract(self, hours: float, feedstock_kg: float = 0.0) -> ExtractionResult:
        if self._status != ExtractionStatus.RUNNING:
            return ExtractionResult(
                resource_type=self.resource_type,
                mass_produced_kg=0.0,
                mass_waste_kg=0.0,
                energy_used_wh=0.0,
                status=self._status,
                duration_hours=hours,
            )
        energy_wh = self._power_w * hours
        theoretical_max_kg = energy_wh / 3600.0 * 0.5  # simplified energy-to-mass
        produced_kg = theoretical_max_kg * self._efficiency
        waste_kg = theoretical_max_kg * (1.0 - self._efficiency)
        if feedstock_kg > 0:
            produced_kg = min(produced_kg, feedstock_kg * self._efficiency)
            waste_kg = feedstock_kg - produced_kg
        self._total_extracted_kg += produced_kg
        return ExtractionResult(
            resource_type=self.resource_type,
            mass_produced_kg=round(produced_kg, 6),
            mass_waste_kg=round(waste_kg, 6),
            energy_used_wh=round(energy_wh, 2),
            status=self._status,
            duration_hours=hours,
        )

    @property
    def status(self) -> ExtractionStatus:
        return self._status

    @property
    def total_extracted_kg(self) -> float:
        return self._total_extracted_kg


class WaterIceExtractor(ExtractionProcess):
    name = "water_ice_extractor"
    resource_type = "water"

    def __init__(
        self,
        efficiency: float = 0.45,
        power_w: float = 80.0,
        regolith_moisture_fraction: float = 0.03,
    ):
        super().__init__(efficiency=efficiency, power_w=power_w)
        self._moisture_fraction = regolith_moisture_fraction

    def extract(self, hours: float, feedstock_kg: float = 0.0) -> ExtractionResult:
        if feedstock_kg > 0:
            available_water_kg = feedstock_kg * self._moisture_fraction
            return super().extract(hours, feedstock_kg=available_water_kg)
        return super().extract(hours, feedstock_kg=0.0)


class OxygenFromRegolith(ExtractionProcess):
    name = "oxygen_from_regolith"
    resource_type = "oxygen"

    def __init__(
        self,
        efficiency: float = 0.35,
        power_w: float = 150.0,
        regolith_oxygen_fraction: float = 0.43,
    ):
        super().__init__(efficiency=efficiency, power_w=power_w)
        self._oxygen_fraction = regolith_oxygen_fraction

    def extract(self, hours: float, feedstock_kg: float = 0.0) -> ExtractionResult:
        if feedstock_kg > 0:
            available_oxygen_kg = feedstock_kg * self._oxygen_fraction
            result = super().extract(hours, feedstock_kg=available_oxygen_kg)
            return result
        return super().extract(hours, feedstock_kg=0.0)


class MetalExtractor(ExtractionProcess):
    name = "metal_extractor"
    resource_type = "metals"

    def __init__(
        self,
        efficiency: float = 0.3,
        power_w: float = 200.0,
        regolith_metal_fraction: float = 0.15,
    ):
        super().__init__(efficiency=efficiency, power_w=power_w)
        self._metal_fraction = regolith_metal_fraction

    def extract(self, hours: float, feedstock_kg: float = 0.0) -> ExtractionResult:
        if feedstock_kg > 0:
            available_metal_kg = feedstock_kg * self._metal_fraction
            return super().extract(hours, feedstock_kg=available_metal_kg)
        return super().extract(hours, feedstock_kg=feedstock_kg)


class ConstructionMaterialSinterer(ExtractionProcess):
    name = "construction_sinterer"
    resource_type = "construction_material"

    def __init__(
        self,
        efficiency: float = 0.85,
        power_w: float = 300.0,
    ):
        super().__init__(efficiency=efficiency, power_w=power_w)

    def extract(self, hours: float, feedstock_kg: float = 0.0) -> ExtractionResult:
        if self._status != ExtractionStatus.RUNNING:
            return ExtractionResult(
                resource_type=self.resource_type,
                mass_produced_kg=0.0,
                mass_waste_kg=0.0,
                energy_used_wh=0.0,
                status=self._status,
                duration_hours=hours,
            )
        if feedstock_kg > 0:
            sintered_kg = feedstock_kg * self._efficiency
            waste_kg = feedstock_kg - sintered_kg
            energy_wh = self._power_w * hours
            self._total_extracted_kg += sintered_kg
            return ExtractionResult(
                resource_type=self.resource_type,
                mass_produced_kg=round(sintered_kg, 4),
                mass_waste_kg=round(waste_kg, 4),
                energy_used_wh=round(energy_wh, 2),
                status=self._status,
                duration_hours=hours,
            )
        return ExtractionResult(
            resource_type=self.resource_type,
            mass_produced_kg=0.0,
            mass_waste_kg=0.0,
            energy_used_wh=0.0,
            status=ExtractionStatus.OFFLINE,
            duration_hours=hours,
        )