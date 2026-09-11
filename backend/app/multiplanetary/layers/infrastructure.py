"""Infrastructure Layer: ISRU plants, power grid, comms, habitats.

Maintains the live status of all physical infrastructure and proposes
maintenance, expansion, or load-shedding actions.
"""

from typing import List

from app.multiplanetary.layers.core import Action, ActionType, Layer, MissionContext


DEFAULT_INFRA = {
    "isru": {
        "status": "off",
        "plants": ["water_extractor", "oxygen_electrolyzer"],
        "power_demand_w": 0.0,
    },
    "power": {
        "solar_output_w": 120.0,
        "battery_wh": 100.0,
        "battery_percent": 100.0,
    },
    "comms": {
        "status": "connected",
        "data_rate_bps": 9600,
        "ground_station_visible": True,
    },
    "habitat": {
        "temperature_c": 22.0,
        "pressure_kpa": 101.3,
        "status": "nominal",
    },
}


class InfrastructureLayer(Layer):
    name = "infrastructure"

    def __init__(self, infra: dict | None = None):
        super().__init__()
        self._infra = dict(DEFAULT_INFRA)
        if infra:
            self._infra.update(infra)

    def update(self, patch: dict) -> None:
        for k, v in patch.items():
            if isinstance(v, dict) and k in self._infra and isinstance(self._infra[k], dict):
                self._infra[k].update(v)
            else:
                self._infra[k] = v

    @property
    def status(self) -> dict:
        return dict(self._infra)

    def evaluate(self, ctx: MissionContext) -> List[Action]:
        actions: List[Action] = []
        infra = ctx.infrastructure if ctx.infrastructure else self._infra
        isru = infra.get("isru", {})
        if isru.get("status") == "off" and ctx.power_available_w > 80.0:
            actions.append(Action(
                layer=self.name,
                action_type=ActionType.COMMAND,
                target="isru-plant",
                description="Activate ISRU plant (power budget sufficient).",
                payload={"plant": "isru", "power_w": isru.get("power_demand_w", 50.0)},
                reversible=True,
            ))
        power = infra.get("power", {})
        bat_pct = power.get("battery_percent", ctx.battery_percent)
        if bat_pct is not None and bat_pct < 25.0:
            actions.append(Action(
                layer=self.name,
                action_type=ActionType.ALERT,
                target="mission_control",
                description=f"Battery at {bat_pct:.0f}%; initiating safe-power mode.",
                severity="warning",
                payload={"action": "safe_power", "battery_percent": bat_pct},
            ))
        hab = infra.get("habitat", {})
        if hab.get("status") != "nominal":
            actions.append(Action(
                layer=self.name,
                action_type=ActionType.ALERT,
                target="human_assistance",
                description=(
                    f"Habitat status: {hab.get('status')}; "
                    f"temp={hab.get('temperature_c')}C, "
                    f"pressure={hab.get('pressure_kpa')}kPa."
                ),
                severity="warning",
            ))
        return actions