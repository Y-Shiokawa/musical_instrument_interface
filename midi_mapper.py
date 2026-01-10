"""
MIDI mapping module.

- MIDIDriver: handles opening MIDI output (virtual if available)
- MidiMapper: maps FSR channels to MIDI notes and IMU axes to pitchbend & modulation (CC1)
"""

import mido
from typing import List, Callable, Optional

# Mapping defaults
DEFAULT_BASE_NOTE = 60  # Middle C (C4)
DEFAULT_NOTES = [DEFAULT_BASE_NOTE + i for i in range(5)]  # chromatic for 5 FSRs
DEFAULT_THRESHOLD = 0.05  # when to trigger note on/off

class MIDIDriver:
    def __init__(self, port_name: str = "fsr-sim", virtual: bool = True, logger: Optional[Callable] = None):
        self.port_name = port_name
        self.virtual = virtual
        self.outport = None
        self.logger = logger or (lambda s: None)

    def open(self):
        try:
            # Try to create (or open) a MIDI output.
            # Note: virtual=True requires rtmidi backend to be installed.
            self.outport = mido.open_output(self.port_name, virtual=self.virtual)
            self.logger(f"MIDI output opened: '{self.port_name}' (virtual={self.virtual})")
        except Exception as e:
            # Fallback to the default output if virtual not supported
            try:
                self.outport = mido.open_output()
                self.logger(f"Virtual MIDI not available; opened default MIDI output: {self.outport.name}")
            except Exception as ex:
                self.outport = None
                self.logger(f"Failed to open MIDI output: {e}; fallback also failed: {ex}")

    def send(self, msg):
        try:
            if self.outport:
                self.outport.send(msg)
            self.logger(str(msg))
        except Exception as e:
            self.logger(f"Failed to send MIDI message: {e}")

class MidiMapper:
    def __init__(self, midi_driver: MIDIDriver, notes: List[int] = None, channel: int = 0, logger: Optional[Callable] = None):
        self.driver = midi_driver
        self.notes = notes or DEFAULT_NOTES
        self.channel = channel
        self.logger = logger or (lambda s: None)
        self.threshold = DEFAULT_THRESHOLD
        # track note state to send note_off when pressure released
        self._note_on = [False] * len(self.notes)

    def _velocity_from_level(self, level: float) -> int:
        # level is 0.0..1.0 -> velocity 1..127 (0 reserved)
        return max(1, min(127, int(level * 127)))

    def process(self, fsr_levels: List[float], imu_snapshot: dict):
        # fsr_levels: list of smoothed, amplified levels 0..1
        for i, level in enumerate(fsr_levels):
            note = self.notes[i] if i < len(self.notes) else (DEFAULT_BASE_NOTE + i)
            if level >= self.threshold and not self._note_on[i]:
                vel = self._velocity_from_level(level)
                msg = mido.Message('note_on', note=note, velocity=vel, channel=self.channel)
                self.driver.send(msg)
                self._note_on[i] = True
            elif level < self.threshold and self._note_on[i]:
                msg = mido.Message('note_off', note=note, velocity=0, channel=self.channel)
                self.driver.send(msg)
                self._note_on[i] = False
            else:
                # Optionally, send aftertouch or continuous velocity updates (not implemented)
                pass

        # IMU -> pitch bend and modulation CC
        # Use gyro X (gx) mapped to pitch bend, range -8192..8191
        gx = imu_snapshot.get("gx", 0.0)
        pitch = int(max(-1.0, min(1.0, gx)) * 8191)
        msg_pb = mido.Message('pitchwheel', pitch=pitch, channel=self.channel)
        self.driver.send(msg_pb)

        # Use gyro Y (gy) mapped to CC1 (modulation) 0..127
        gy = imu_snapshot.get("gy", 0.0)
        cc_val = max(0, min(127, int((gy + 1.0) / 2.0 * 127)))
        msg_cc = mido.Message('control_change', control=1, value=cc_val, channel=self.channel)
        self.driver.send(msg_cc)
