"""Electrical Power System (EPS) for CubeSat.

Models: battery (SOC, voltage, capacity fade), solar panels (eclipse-aware),
power bus, and load distribution.  The same interface works for larger
spacecraft by adjusting area and battery parameters.

Hardware reference (3U CubeSat)
-------------------------------
* 6 body-mounted solar panels, ~80 cm^2 total, ~22% efficiency, triple-junction.
* 2S1P LiFePO4 battery, ~6.6 V nominal, 10 Wh.
* Maximum steady load: ~2 W (radio + ADCS + OBC).
* Peak load: ~5 W (transmit burst + imaging).
"""

from dataclasses import dataclass


@dataclass
class PowerBudget:
    timestamp: float = 0.0
    solar_generation_w: float = 0.0
    battery_discharge_w: float = 0.0
    load_w: float = 0.0
    battery_soc_percent: float = 100.0
    battery_voltage: float = 6.6
    eclipse: bool = False

    def to_dict(self) -> dict[str, float]:
        return {
            "solar_generation_w": round(self.solar_generation_w, 4),
            "battery_discharge_w": round(self.battery_discharge_w, 4),
            "load_w": round(self.load_w, 4),
            "battery_soc_percent": round(self.battery_soc_percent, 2),
            "battery_voltage": round(self.battery_voltage, 3),
            "eclipse": self.eclipse,
        }


class SolarPanelModel:
    def __init__(
        self,
        area_m2: float = 0.008,
        efficiency: float = 0.22,
        sun_efficiency: float = 1361.0,
        degradation_per_year: float = 0.02,
    ):
        self.area_m2 = area_m2
        self.efficiency = efficiency
        self.sun_efficiency = sun_efficiency
        self.degradation_per_year = degradation_per_year

    def power_w(self, sun_angle_cos: float, eclipse: bool = False) -> float:
        if eclipse or sun_angle_cos <= 0:
            return 0.0
        return self.area_m2 * self.efficiency * self.sun_efficiency * sun_angle_cos

    def aged_power_w(self, mission_days: float, sun_angle_cos: float, eclipse: bool = False) -> float:
        degradation = (1.0 - self.degradation_per_year) ** (mission_days / 365.25)
        return self.power_w(sun_angle_cos, eclipse) * degradation


class BatteryModel:
    def __init__(
        self,
        capacity_wh: float = 10.0,
        nominal_voltage: float = 6.6,
        min_voltage: float = 5.5,
        max_charge_rate_c: float = 0.5,
        coulomb_efficiency: float = 0.95,
        capacity_fade_per_cycle: float = 0.00001,
    ):
        self.capacity_wh = capacity_wh
        self.nominal_voltage = nominal_voltage
        self.min_voltage = min_voltage
        self.max_charge_rate_c = max_charge_rate_c
        self.coulomb_efficiency = coulomb_efficiency
        self.capacity_fade_per_cycle = capacity_fade_per_cycle
        self._soc_wh = capacity_wh
        self._cycle_count = 0.0

    @property
    def soc_percent(self) -> float:
        return (self._soc_wh / self.capacity_wh) * 100.0

    @property
    def voltage(self) -> float:
        soc_frac = self._soc_wh / self.capacity_wh
        return self.min_voltage + (self.nominal_voltage - self.min_voltage) * soc_frac

    @property
    def is_depleted(self) -> bool:
        return self._soc_wh <= 0.0

    def discharge(self, energy_wh: float) -> float:
        actual = min(self._soc_wh, energy_wh)
        self._soc_wh -= actual
        return actual

    def charge(self, energy_wh: float) -> float:
        max_charge = self.capacity_wh - self._soc_wh
        actual = min(energy_wh * self.coulomb_efficiency, max_charge)
        self._soc_wh += actual
        if actual > 0:
            self._cycle_count += 0.01
        return actual

    def reset_cycles(self) -> None:
        self._cycle_count = 0.0


class PowerSystem:
    def __init__(
        self,
        solar: SolarPanelModel | None = None,
        battery: BatteryModel | None = None,
        base_load_w: float = 1.5,
        peak_load_w: float = 5.0,
    ):
        self.solar = solar or SolarPanelModel()
        self.battery = battery or BatteryModel()
        self.base_load_w = base_load_w
        self.peak_load_w = peak_load_w
        self._load_fraction = 0.3
        self._budget = PowerBudget()

    @property
    def budget(self) -> PowerBudget:
        return self._budget

    def set_load_fraction(self, frac: float) -> None:
        self._load_fraction = max(0.0, min(1.0, frac))

    def tick(self, dt: float, sun_angle_cos: float, eclipse: bool, mission_days: float = 0.0) -> PowerBudget:
        solar_w = self.solar.aged_power_w(mission_days, sun_angle_cos, eclipse)
        load_w = self.base_load_w + (self.peak_load_w - self.base_load_w) * self._load_fraction
        net_w = solar_w - load_w
        if net_w >= 0:
            self.battery.charge(net_w * dt / 3600.0)
        else:
            self.battery.discharge(-net_w * dt / 3600.0)
        self._budget = PowerBudget(
            solar_generation_w=solar_w,
            battery_discharge_w=max(0.0, -net_w),
            load_w=load_w,
            battery_soc_percent=self.battery.soc_percent,
            battery_voltage=self.battery.voltage,
            eclipse=eclipse,
        )
        return self._budget
