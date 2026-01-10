"""
Sensor simulation module.

Provides:
- FSRChannel: simulated FSR with RC low-pass smoothing and optional gain
- IMUSimulator: simulated 3-axis accelerometer and 3-axis gyroscope
- LowPassFilter: helper to implement RC-like smoothing
"""

import time
from dataclasses import dataclass, field
from typing import List

class LowPassFilter:
    def __init__(self, tau: float = 0.05, dt: float = 1/60):
        # tau is time constant in seconds. Smaller tau -> faster -> less smoothing.
        self.tau = max(1e-6, float(tau))
        self.dt = dt
        self._y = 0.0

    def update(self, x: float, dt: float = None) -> float:
        if dt is None:
            dt = self.dt
        alpha = dt / (self.tau + dt)
        self._y = alpha * x + (1 - alpha) * self._y
        return self._y

    @property
    def value(self) -> float:
        return self._y

@dataclass
class FSRChannel:
    id: int
    raw: float = 0.0            # raw input 0.0 - 1.0 (from GUI slider)
    gain: float = 1.0           # gain stage to emulate LM358
    tau: float = 0.05           # RC time constant (seconds)
    _filter: LowPassFilter = field(init=False, repr=False)

    def __post_init__(self):
        self._filter = LowPassFilter(tau=self.tau, dt=1/60)

    def set_raw(self, value: float):
        # clamp raw to 0-1
        self.raw = max(0.0, min(1.0, float(value)))

    def update(self, dt: float = 1/60) -> float:
        self._filter.dt = dt
        self._filter.tau = self.tau
        smoothed = self._filter.update(self.raw, dt=dt)
        amplified = smoothed * self.gain
        # clamp again to 0-1 for mapping
        return max(0.0, min(1.0, amplified))

    @property
    def smoothed(self) -> float:
        return self._filter.value * self.gain

class IMUSimulator:
    """
    Simple IMU simulator storing 3 accel axes (Ax,Ay,Az) and 3 gyro axes (Gx,Gy,Gz).
    Ax/Ay/Az values are in -2..+2 (g) nominally; we normalize to -1..+1 for mapping convenience.
    Gyro values are in degrees/sec (we normalize to -1..+1 across a chosen range).
    """

    def __init__(self, gyro_range_dps: float = 250.0):
        # values stored normalized to -1..1
        self.ax = 0.0
        self.ay = 0.0
        self.az = 0.0
        self.gx = 0.0
        self.gy = 0.0
        self.gz = 0.0
        self.gyro_range = gyro_range_dps

    def set_accel_raw(self, ax: float, ay: float, az: float):
        # Accepts -2..+2 g typical; normalize to -1..1 by dividing by 2
        self.ax = max(-1.0, min(1.0, ax / 2.0))
        self.ay = max(-1.0, min(1.0, ay / 2.0))
        self.az = max(-1.0, min(1.0, az / 2.0))

    def set_gyro_raw(self, gx_dps: float, gy_dps: float, gz_dps: float):
        # Normalize by gyro_range
        self.gx = max(-1.0, min(1.0, gx_dps / self.gyro_range))
        self.gy = max(-1.0, min(1.0, gy_dps / self.gyro_range))
        self.gz = max(-1.0, min(1.0, gz_dps / self.gyro_range))

    def snapshot(self):
        return {
            "ax": self.ax,
            "ay": self.ay,
            "az": self.az,
            "gx": self.gx,
            "gy": self.gy,
            "gz": self.gz,
        }
