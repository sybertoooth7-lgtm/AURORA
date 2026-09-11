"""Pure pricing/trigger math for parametric agriculture insurance (AURORA-2).

Kept free of FastAPI/DB imports so the payout model is unit-testable and
deliberately simple: proportional liability = sum-insured x severity, with
a coverage-ratio haircut. This is a planning estimate, never a settlement.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TriggerEvaluation:
    """Result of applying a parametric trigger to a pipeline severity."""

    trigger_breached: bool
    estimated_liability_usd: float
    payout_usd: float


def evaluate_trigger(
    severity: float,
    sum_insured_usd: float,
    trigger_threshold: float,
    coverage_ratio: float = 1.0,
) -> TriggerEvaluation:
    """Apply a parametric trigger to a pipeline severity.

    ``estimated_liability_usd`` is sum-insured x severity (always reported);
    ``payout_usd`` is the liability x coverage-ratio hair-cut, zero unless
    the trigger is breached. A planning estimate, never a settlement.
    """
    breached = severity >= trigger_threshold
    liability = round(sum_insured_usd * severity, 2)
    payout = round(sum_insured_usd * severity * coverage_ratio, 2)
    return TriggerEvaluation(
        trigger_breached=breached,
        estimated_liability_usd=liability,
        payout_usd=payout if breached else 0.0,
    )
