"""Thermal management system for CubeSat.

Lumped-capacitance thermal model.  The spacecraft is modelled as a
single thermal node with configurable heater/radiator parameters.
In LEO the environment oscillates between direct sunlight (~+50 C) and
eclipse (~-150 C) depending on orbit.  The thermal model runs a simple
energy balance each tick.
"""

import math
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ThermalState:
    temperature_c: float = 25.0
    heater_on: bool = False
    heater_power_w: float = 0.0
    radiator_power_w: float = 0.0
    solar_heating_w: float = 0.0
    albedo_heating_w: float = 0.0
    earth_ir_w: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "temperature_c": round(self.temperature_c, 2),
            "heater_on": self.heater_on,
            "heater_power_w": round(self.heater_power_w, 3),
            "radiator_power_w": round(self.radiator_power_w, 3),
        }


class ThermalModel:
    """Lumped-capacitance thermal model.

    Parameters based on a 3U CubeSat with body-mounted solar panels
    and minimal internal heat dissipation.
    """

    def __init__(
        self,
        thermal_mass_j_per_k: float = 80.0,
        min_operating_c: float = -10.0,
        max_operating_c: float = 50.0,
        heater_power_w: float = 3.0,
        radiator_area_m2: float = 0.01,
        radiator_emissivity: float = 0.85,
        solar_absorptivity: float = 0.8,
        spacecraft_area_m2: float = 0.06,
        boltzmann: float = 5.67e-8,
        initial_temp_c: float = 25.0,
    ):
        self.thermal_mass_j_per_k = thermal_mass_j_per_k
        self.min_operating_c = min_operating_c
        self.max_operating_c = max_operating_c
        self.heater_power_w = heater_power_w
        self.radiator_area_m2 = radiator_area_m2
        self.radiator_emissivity = radiator_emissivity
        self.solar_absorptivity = solar_absorptivity
        self.spacecraft_area_m2 = spacecraft_area_m2
        self.boltzmann = boltzmann
        self._temp_k = initial_temp_c + 273.15
        self._heater_on = False

    @property
    def temperature_c(self) -> float:
        return self._temp_k - 273.15

    @property
    def state(self) -> ThermalState:
        return ThermalState(
            temperature_c=self.temperature_c,
            heater_on=self._heater_on,
            heater_power_w=self.heater_power_w if self._heater_on else 0.0,
        )

    def tick(
        self,
        dt: float,
        eclipse: bool = False,
        sun_angle_cos: float = 0.0,
        internal_heat_w: float = 0.5,
    ) -> ThermalState:
        solar_flux = 1361.0
        solar_in = 0.0 if eclipse else solar_flux * self.spacecraft_area_m2 * self.solar_absorptivity * max(0.0, sun_angle_cos)
        t_env_k = 3.0 if eclipse else 288.0
        radiated = self.radiator_emissivity * self.boltzmann * self.radiator_area_m2 * (self._temp_k**4 - t_env_k**4)
        heater = self.heater_power_w if self._heater_on else 0.0
        net_power = solar_in + internal_heat_w + heater - radiated
        delta_t = net_power * dt / self.thermal_mass_j_per_k
        self._temp_k += delta_t
        self._temp_k = max(200.0, min(400.0, self._temp_k))
        if self.temperature_c < self.min_operating_c:
            self._heater_on = True
        elif self.temperature_c > self.min_operating_c + 5.0:
            self._heater_on = False
        return ThermalState(
            temperature_c=self.temperature_c,
            heater_on=self._heater_on,
            heater_power_w=heater,
            radiator_power_w=radiated,
            solar_heating_w=solar_in,
        )

    def reset(self, temp_c: float = 25.0) -> None:
        self._temp_k = temp_c + 273.15
        self._heater_on = False