"""Human Assistance Layer: advisories, plain-language reporting, verification.

The only layer that speaks to the human.  It translates technical stack
state into plain-language advisories, recommends verification checklists
before irreversible actions, and presents decision prompts when the
mission control layer has elevated a ``request_authorization`` action.
"""


from app.multiplanetary.layers.core import Action, ActionType, Layer, MissionContext


class HumanAssistanceLayer(Layer):
    name = "human_assistance"

    def __init__(self) -> None:
        super().__init__()
        self._pending_verifications: list[str] = []
        self._advisories: list[str] = []

    def generate_advisory(self, ctx: MissionContext) -> str:
        parts = [
            f"Environment: {ctx.environment}, body: {ctx.target_body}.",
            f"Autonomy level: {ctx.autonomy_level} "
            f"(one-way delay {ctx.one_way_delay_s:.1f}s).",
            f"Battery: {ctx.battery_percent:.0f}%, "
            f"power: {ctx.power_available_w:.0f}W available / "
            f"{ctx.power_demand_w:.0f}W demand.",
            f"Contact: {'yes' if ctx.in_contact else 'NO (disconnected mode)'}.",
            f"Temperature: {ctx.temperature_c:.1f}C.",
            f"Current plan: {ctx.current_plan or 'none'}.",
            f"Inventory: {ctx.inventory if ctx.inventory else 'not loaded'}.",
            f"Warnings: {', '.join(ctx.warnings) if ctx.warnings else 'none'}.",
        ]
        return " ".join(parts)

    def evaluate(self, ctx: MissionContext) -> list[Action]:
        actions: list[Action] = []
        advisory = self.generate_advisory(ctx)
        actions.append(Action(
            layer=self.name,
            action_type=ActionType.ALERT,
            target="human",
            description=advisory,
            payload={"advisory": advisory, "inventory": ctx.inventory},
        ))
        if ctx.autonomy_level < 3 and ctx.battery_percent < 40.0:
            actions.append(Action(
                layer=self.name,
                action_type=ActionType.ALERT,
                target="human",
                description=(
                    "Low battery at reduced autonomy: recommend pausing "
                    "non-critical operations and planning return-to-base."
                ),
                severity="warning",
            ))
        if ctx.one_way_delay_s > 120.0:
            actions.append(Action(
                layer=self.name,
                action_type=ActionType.ALERT,
                target="human",
                description=(
                    f"Round-trip delay ~{ctx.one_way_delay_s * 2:.0f}s: "
                    f"recommended autonomy level is {min(5, int(ctx.one_way_delay_s / 30))}. "
                    f"Verify ground commands are needed at all -- suggest autonomous execution."
                ),
                severity="info",
            ))
        return actions

    def verification_checklist(self, action: Action) -> list[str]:
        return [
            f"Action: {action.description} ({action.layer} → {action.target})",
            f"Severity: {action.severity}",
            f"Reversible: {action.reversible}",
            "Battery sufficient: review resource-management alert output.",
            "Navigation confidence: check NavigationLayer path quality.",
            "Confirm no other irreversible action is queued.",
        ]
