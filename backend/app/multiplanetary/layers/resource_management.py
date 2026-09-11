"""Resource Management Layer: inventory tracking, allocation, energy budget.

Maintains a live view of all consumables (water, oxygen, hydrogen, fuel,
battery charge, propellant reserves, metals, construction materials) and
proposes allocation and rationing actions when levels fall below
operational thresholds.
"""


from app.multiplanetary.layers.core import Action, ActionType, Layer, MissionContext

DEFAULT_INVENTORY = {
    "water_kg": 0.0,
    "oxygen_kg": 0.0,
    "hydrogen_kg": 0.0,
    "fuel_kg": 0.0,
    "metals_kg": 0.0,
    "construction_material_kg": 0.0,
    "regolith_kg": 0.0,
    "battery_wh": 100.0,
}


class ResourceManagementLayer(Layer):
    name = "resource_management"

    def __init__(self, thresholds: dict | None = None):
        super().__init__()
        self._thresholds = thresholds or {
            "water_kg": 5.0,
            "oxygen_kg": 3.0,
            "fuel_kg": 2.0,
            "battery_wh": 20.0,
        }

    def evaluate(self, ctx: MissionContext) -> list[Action]:
        actions: list[Action] = []
        inv = dict(DEFAULT_INVENTORY)
        inv.update(ctx.inventory)
        for key, min_val in self._thresholds.items():
            current = inv.get(key, 0.0)
            if current < min_val:
                severity = "critical" if current < min_val * 0.5 else "warning"
                actions.append(Action(
                    layer=self.name,
                    action_type=ActionType.ALERT,
                    target="mission_control",
                    description=(
                        f"{key} low ({current:.1f} < {min_val:.1f} threshold). "
                        f"Initiating rationing plan."
                    ),
                    severity=severity,
                    payload={"resource": key, "current": current, "threshold": min_val},
                ))
                actions.append(Action(
                    layer=self.name,
                    action_type=ActionType.PLAN,
                    target="infrastructure",
                    description=f"Request ISRU ramp-up to restore {key}.",
                    payload={"resource": key, "deficit": min_val - current},
                    requires_authorization=severity == "critical",
                ))
        power_margin = ctx.power_available_w - ctx.power_demand_w
        if power_margin < 10.0:
            actions.append(Action(
                layer=self.name,
                action_type=ActionType.PLAN,
                target="infrastructure",
                description=(
                    f"Power margin low ({power_margin:.1f}W). "
                    f"Shedding non-critical loads."
                ),
                payload={"action": "shed_loads", "margin_w": power_margin},
            ))
        return actions
