"""Communication delay model and autonomy budget calculation.

Models the real one-way light time (OWLT) from Earth to the target
body and derives the autonomy budget: how much independent decision-
making the spacecraft/rover must do, and when to fall back to
fully-scripted mission sequences.
"""

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TargetBody(Enum):
    EARTH_LEO = "earth_leo"
    MOON = "moon"
    MARS = "mars"
    JUPITER = "jupiter"
    SATURN = "saturn"
    ASTEROID = "asteroid"
    DEEP_SPACE = "deep_space"


@dataclass
class CommsDelayModel:
    target_body: TargetBody = TargetBody.MOON
    owlt_seconds: float = 1.3

    @staticmethod
    def for_target(target: TargetBody) -> "CommsDelayModel":
        owlt = {
            TargetBody.EARTH_LEO: 0.003,
            TargetBody.MOON: 1.3,
            TargetBody.MARS: 780.0,       # ~13 min average
            TargetBody.JUPITER: 2700.0,   # ~45 min average
            TargetBody.SATURN: 5400.0,    # ~90 min average
            TargetBody.ASTEROID: 1200.0,  # varies
            TargetBody.DEEP_SPACE: 10800.0,  # ~3 hours
        }
        return CommsDelayModel(target_body=target, owlt_seconds=owlt.get(target, 1.3))

    @property
    def round_trip_delay_s(self) -> float:
        return self.owlt_seconds * 2.0

    @property
    def autonomy_level(self) -> int:
        rtt = self.round_trip_delay_s
        if rtt < 5:
            return 1
        elif rtt < 60:
            return 2
        elif rtt < 600:
            return 3
        elif rtt < 7200:
            return 4
        else:
            return 5

    @property
    def recommended_contact_interval_s(self) -> float:
        return max(300.0, self.round_trip_delay_s * 5)

    def is_real_time_controllable(self) -> bool:
        return self.round_trip_delay_s < 2.0

    @property
    def max_autonomous_operations_s(self) -> float:
        if self.autonomy_level <= 2:
            return 60.0
        elif self.autonomy_level == 3:
            return 3600.0
        elif self.autonomy_level == 4:
            return 86400.0 * 7
        else:
            return float("inf")

    def to_dict(self) -> dict:
        return {
            "target_body": self.target_body.value,
            "owlt_s": self.owlt_seconds,
            "rtt_s": self.round_trip_delay_s,
            "autonomy_level": self.autonomy_level,
            "real_time": self.is_real_time_controllable(),
        }