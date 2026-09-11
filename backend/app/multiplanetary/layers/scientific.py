"""Scientific Intelligence Layer: hypothesis-driven observation planning.

Turns mission science goals into concrete survey/observation actions that
the robotics and navigation layers execute.  Guarded by mission control:
any action here that involves moving sensors is a *proposal*, never an
autonomous land-use decision.

The layer maintains a small hypothesis registry and ranks candidate
sensor targets by expected scientific value, cost (energy, time), and
risk.  The MVP is a priority queue with scoring -- deliberately no
fictional "autonomous scientists".
"""


from app.multiplanetary.layers.core import Action, ActionType, Layer, MissionContext


class ScientificIntelligenceLayer(Layer):
    name = "scientific_intelligence"

    def __init__(self, hypotheses: list[dict] | None = None):
        super().__init__()
        self._hypotheses = hypotheses or [
            {"id": "water_psr_1", "resource": "water_ice", "priority": 1.0,
             "target": {"x": 10, "y": 20}, "expected_value": 0.95},
            {"id": "mineral_basin", "resource": "metals", "priority": 0.7,
             "target": {"x": 40, "y": 5}, "expected_value": 0.6},
        ]

    def evaluate(self, ctx: MissionContext) -> list[Action]:
        actions: list[Action] = []
        candidates = sorted(
            self._hypotheses,
            key=lambda h: (h["expected_value"], -h["priority"]),
            reverse=True,
        )
        if not ctx.science_hypotheses:
            actions.append(Action(
                layer=self.name,
                action_type=ActionType.ALERT,
                target="context",
                description=(
                    "No science hypotheses registered; requesting survey plan "
                    "for highest-value candidate."
                ),
            ))
        top = candidates[0]
        latency_tolerance = ctx.one_way_delay_s > 60.0
        actions.append(Action(
            layer=self.name,
            action_type=ActionType.PLAN,
            target="rover-1",
            description=(
                f"Survey plan for hypothesis {top['id']} "
                f"(resource {top['resource']}, value {top['expected_value']})."
            ),
            payload={
                "hypothesis_id": top["id"],
                "target": top["target"],
                "expected_value": top["expected_value"],
                "latency_tolerant": latency_tolerance,
            },
            requires_authorization=not latency_tolerance,
            reversible=True,
        ))
        return actions
