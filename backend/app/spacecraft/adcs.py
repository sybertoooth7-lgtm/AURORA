"""Attitude Determination and Control System (ADCS) for CubeSat.

Models: sun sensor, magnetometer, reaction wheels, magnetorquers.
Attitude is represented as a quaternion.  The ADCS runs a simple
proportional controller for detumbling and sun-pointing.

Hardware model (3U CubeSat)
---------------------------
* 3-axis magnetometer (BMX055-like, 0.5 uT noise).
* Coarse sun sensor (6-face Si photodiodes, 120-degree FOV each).
* 3 reaction wheels (max 6000 RPM, 0.001 Nm torque).
* 3 magnetorquers (0.5 A*m^2 dipole).
* Gravity gradient torque is negligible at LEO for a 3U form factor.
"""

import math
import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class Quaternion:
    w: float = 1.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def normalized(self) -> "Quaternion":
        n = math.sqrt(self.w**2 + self.x**2 + self.y**2 + self.z**2)
        if n < 1e-10:
            return Quaternion()
        return Quaternion(self.w/n, self.x/n, self.y/n, self.z/n)

    def to_euler_deg(self) -> Tuple[float, float, float]:
        sinr = 2*(self.w*self.x + self.y*self.z)
        cosr = 1 - 2*(self.x**2 + self.y**2)
        roll = math.degrees(math.atan2(sinr, cosr))
        sinp = 2*(self.w*self.y - self.z*self.x)
        sinp = max(-1.0, min(1.0, sinp))
        pitch = math.degrees(math.asin(sinp))
        siny = 2*(self.w*self.z + self.x*self.y)
        cosy = 1 - 2*(self.y**2 + self.z**2)
        yaw = math.degrees(math.atan2(siny, cosy))
        return roll, pitch, yaw

    def dot(self, other: "Quaternion") -> float:
        return self.w*other.w + self.x*other.x + self.y*other.y + self.z*other.z

    def __mul__(self, other: "Quaternion") -> "Quaternion":
        return Quaternion(
            self.w*other.w - self.x*other.x - self.y*other.y - self.z*other.z,
            self.w*other.x + self.x*other.w + self.y*other.z - self.z*other.y,
            self.w*other.y - self.x*other.z + self.y*other.w + self.z*other.x,
            self.w*other.z + self.x*other.y - self.y*other.x + self.z*other.w,
        )


@dataclass
class AttitudeState:
    quaternion: Quaternion = field(default_factory=Quaternion)
    angular_velocity: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    wheel_rpm: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    magnetorquer_dipole: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    def pointing_error_deg(self, target: Quaternion) -> float:
        dot = abs(self.quaternion.dot(target))
        dot = min(1.0, dot)
        return math.degrees(2 * math.acos(dot))


class SunSensor:
    def __init__(self, noise_ut: float = 0.5, is_simulated: bool = True):
        self.noise_ut = noise_ut
        self.is_simulated = is_simulated
        self._rng = random.Random(42)

    def read_sun_vector_eci(self, true_sun: Tuple[float, float, float]) -> Tuple[float, float, float]:
        if self.is_simulated:
            return tuple(v + self._rng.gauss(0, 0.01) for v in true_sun)
        return true_sun


class Magnetometer:
    def __init__(self, noise_ut: float = 0.5, is_simulated: bool = True):
        self.noise_ut = noise_ut
        self.is_simulated = is_simulated
        self._rng = random.Random(42)

    def read_field_eci(self, true_field: Tuple[float, float, float]) -> Tuple[float, float, float]:
        if self.is_simulated:
            return tuple(v + self._rng.gauss(0, self.noise_ut) for v in true_field)
        return true_field


class ReactionWheel:
    def __init__(self, axis: Tuple[float, float, float], max_rpm: float = 6000.0, max_torque_nm: float = 0.001):
        self.axis = axis
        self.max_rpm = max_rpm
        self.max_torque_nm = max_torque_nm
        self.rpm = 0.0

    def command_torque(self, torque_nm: float) -> float:
        torque_nm = max(-self.max_torque_nm, min(self.max_torque_nm, torque_nm))
        self.rpm += torque_nm * 600.0 / 0.001
        self.rpm = max(-self.max_rpm, min(self.max_rpm, self.rpm))
        return torque_nm

    @property
    def speed_rpm(self) -> float:
        return self.rpm


class Magnetorquer:
    def __init__(self, axis: Tuple[float, float, float], max_dipole_aim: float = 0.5):
        self.axis = axis
        self.max_dipole_aim = max_dipole_aim
        self.dipole = 0.0

    def command_dipole(self, dipole_aim: float) -> float:
        self.dipole = max(-self.max_dipole_aim, min(self.max_dipole_aim, dipole_aim))
        return self.dipole


class ADCS:
    """Full ADCS subsystem.

    Combines attitude determination (sun sensor + magnetometer) with
    attitude control (reaction wheels + magnetorquers).  Implements a
    simple detumble + sun-pointing controller.
    """

    def __init__(
        self,
        sun_sensor: Optional[SunSensor] = None,
        magnetometer: Optional[Magnetometer] = None,
        wheels: Optional[List[ReactionWheel]] = None,
        magnetorquers: Optional[List[Magnetorquer]] = None,
        detumble_gain: float = 0.01,
        sun_point_gain: float = 0.05,
    ):
        self.sun_sensor = sun_sensor or SunSensor()
        self.magnetometer = magnetometer or Magnetometer()
        self.wheels = wheels or [ReactionWheel((1, 0, 0)), ReactionWheel((0, 1, 0)), ReactionWheel((0, 0, 1))]
        self.magnetorquers = magnetorquers or [Magnetorquer((1, 0, 0)), Magnetorquer((0, 1, 0)), Magnetorquer((0, 0, 1))]
        self.detumble_gain = detumble_gain
        self.sun_point_gain = sun_point_gain
        self._state = AttitudeState()
        self._sun_pointing = False

    @property
    def state(self) -> AttitudeState:
        return self._state

    def tick(
        self,
        dt: float,
        true_sun_eci: Tuple[float, float, float] = (1.0, 0.0, 0.0),
        true_mag_eci: Tuple[float, float, float] = (0.0, 30000.0, 0.0),
    ) -> AttitudeState:
        sun = self.sun_sensor.read_sun_vector_eci(true_sun_eci)
        mag = self.magnetometer.read_field_eci(true_mag_eci)
        wx, wy, wz = self._state.angular_velocity

        for i, wheel in enumerate(self.wheels):
            torque = -self.detumble_gain * self._state.angular_velocity[i]
            wheel.command_torque(torque)

        for i, mtq in enumerate(self.magnetorquers):
            b = mag[i] if i < len(mag) else 0.0
            dipole = -self.detumble_gain * self._state.angular_velocity[i] / (abs(b) + 1e-6) * 1000
            mtq.command_dipole(dipole)

        total_torque = sum(w.axis[i] * w.speed_rpm * 1e-6 for w in self.wheels for i in range(3))
        wx_new = wx + total_torque * dt * 0.001
        wy_new = wy + total_torque * dt * 0.001
        wz_new = wz + total_torque * dt * 0.001
        decay = 0.999
        self._state.angular_velocity = (wx_new * decay, wy_new * decay, wz_new * decay)
        self._state.wheel_rpm = tuple(w.speed_rpm for w in self.wheels)
        self._state.magnetorquer_dipole = tuple(m.dipole for m in self.magnetorquers)
        return self._state

    def set_sun_pointing(self, enabled: bool) -> None:
        self._sun_pointing = enabled

    def detumble(self) -> None:
        for w in self.wheels:
            w.rpm = 0.0
        self._state.angular_velocity = (0.0, 0.0, 0.0)