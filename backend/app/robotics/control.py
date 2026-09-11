"""Robot control: PID controllers, waypoint following, servo management.

Provides a PID controller that works for both simulation and hardware
backends (ROS 2 / direct PWM).
"""

from dataclasses import dataclass


@dataclass
class PIDGains:
    kp: float = 1.0
    ki: float = 0.0
    kd: float = 0.0
    output_min: float = -1.0
    output_max: float = 1.0
    integral_max: float = 10.0


class PIDController:
    """Discrete PID controller.

    Works identically in simulation and hardware.  Call ``compute()``
    once per control loop iteration with the current error and dt.
    """

    def __init__(self, gains: PIDGains, name: str = "pid"):
        self.gains = gains
        self.name = name
        self._integral = 0.0
        self._prev_error: float | None = None
        self._last_time: float | None = None

    def reset(self) -> None:
        self._integral = 0.0
        self._prev_error = None
        self._last_time = None

    def compute(self, error: float, dt: float) -> float:
        if dt <= 0.0:
            return 0.0
        self._integral += error * dt
        self._integral = max(-self.gains.integral_max,
                             min(self.gains.integral_max, self._integral))
        derivative = 0.0
        if self._prev_error is not None and self._last_time is not None:
            actual_dt = dt if self._last_time == 0 else dt
            derivative = (error - self._prev_error) / actual_dt
        self._prev_error = error
        self._last_time = dt
        output = (self.gains.kp * error
                  + self.gains.ki * self._integral
                  + self.gains.kd * derivative)
        return max(self.gains.output_min, min(self.gains.output_max, output))


class VelocityPIDController:
    """Wraps a PID to track a velocity setpoint."""

    def __init__(self, gains: PIDGains, name: str = "vel_pid"):
        self._pid = PIDController(gains, name=name)
        self.name = name

    def compute(self, current_velocity: float, target_velocity: float, dt: float) -> float:
        error = target_velocity - current_velocity
        return self._pid.compute(error, dt)

    def reset(self) -> None:
        self._pid.reset()


class PositionPIDController:
    """Wraps a PID to track a position setpoint."""

    def __init__(self, gains: PIDGains, name: str = "pos_pid"):
        self._pid = PIDController(gains, name=name)
        self.name = name

    def compute(self, current_position: float, target_position: float, dt: float) -> float:
        error = target_position - current_position
        return self._pid.compute(error, dt)

    def reset(self) -> None:
        self._pid.reset()
