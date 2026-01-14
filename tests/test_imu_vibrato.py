import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import midi_mapper
from midi_mapper import MidiMapper


class DummyDriver:
    def send(self, msg):
        pass


class FakeSynth:
    def __init__(self):
        self.scales = []

    def set_vibrato_scale(self, scale):
        self.scales.append(scale)


def run_test():
    driver = DummyDriver()
    synth = FakeSynth()
    mapper = MidiMapper(driver, audio_synth=synth)

    original_time = midi_mapper.time.time
    current_time = [0.0]

    def fake_time():
        return current_time[0]

    midi_mapper.time.time = fake_time
    try:
        freq = 5.0  # Hz within 2..10
        amplitude = 0.2  # above IMU_MIN_AMPLITUDE
        dt = 0.02  # 50 Hz sampling
        total = 2.5  # seconds
        steps = int(total / dt)
        for i in range(steps):
            t = i * dt
            current_time[0] = t
            gx = amplitude * math.sin(2.0 * math.pi * freq * t)
            imu = {"gx": gx, "gy": 0.0, "gz": 0.0}
            mapper.process([0.0] * 10, imu)

        boosted = any(scale > 1.0 for scale in synth.scales)
        if not boosted:
            print("FAIL: vibrato scale was not boosted")
            return 1
        print("PASS: vibrato scale boosted by periodic IMU input")
        return 0
    finally:
        midi_mapper.time.time = original_time


if __name__ == "__main__":
    sys.exit(run_test())
