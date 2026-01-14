"""
MIDI mapping module.

- MIDIDriver: handles opening MIDI output (virtual if available)
- MidiMapper: maps 10 FSR sensors to pitch and volume based on the spec
"""

from typing import Callable, List, Optional
from collections import deque
import time
import mido

DEFAULT_BASE_NOTE = 60  # C4
DEFAULT_SCALE = [0, 2, 4, 5, 7, 9, 11]  # Major scale fallback
FSR_COUNT = 10

T_MIN = -200
T_MAX = 200
V_THRESHOLD = 10
V_MAX = 100
IMU_WINDOW_SEC = 1.5
IMU_MIN_FREQ = 2.0
IMU_MAX_FREQ = 10.0
IMU_MIN_AMPLITUDE = 0.05
VIBRATO_SCALE_MAX = 1.3


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
    def __init__(
        self,
        midi_driver: MIDIDriver,
        base_note: int = DEFAULT_BASE_NOTE,
        channel: int = 0,
        logger: Optional[Callable] = None,
        audio_synth=None,
    ):
        self.driver = midi_driver
        self.base_note = base_note
        self.channel = channel
        self.logger = logger or (lambda s: None)
        self.audio_synth = audio_synth

        self._note_on = False
        self._current_note = None
        self._imu_samples = deque()
        self._last_vibrato_scale = 1.0

    def _clip01(self, value: float) -> float:
        return max(0.0, min(1.0, value))

    def _get_scale(self) -> List[int]:
        if self.audio_synth and hasattr(self.audio_synth, "get_scale"):
            scale = self.audio_synth.get_scale()
            if scale:
                return scale
        return DEFAULT_SCALE

    def _build_scale_notes(self) -> List[int]:
        scale = self._get_scale()
        notes = []
        for octave in range(2):
            for step in scale:
                notes.append(self.base_note + step + 12 * octave)
        return notes

    def _compute_pitch_note(self, sensor_values: List[float]) -> int:
        # sensor_values are S_i in 0..100, index 0..9 corresponds to sensor 1..10
        s2 = sensor_values[1]
        s5 = sensor_values[4]
        s7 = sensor_values[6]
        s10 = sensor_values[9]

        t_pitch = (s5 - s2) + (s7 - s10)
        p = self._clip01((t_pitch - T_MIN) / (T_MAX - T_MIN))

        scale_notes = self._build_scale_notes()
        n = len(scale_notes)
        if n == 0:
            return self.base_note

        k = int(round(p * (n - 1)))
        return scale_notes[k]

    def _compute_volume(self, sensor_values: List[float]) -> float:
        v_avg = sum(sensor_values) / FSR_COUNT
        if v_avg <= V_THRESHOLD:
            return 0.0
        return self._clip01((v_avg - V_THRESHOLD) / (V_MAX - V_THRESHOLD))

    def _velocity_from_volume(self, volume: float) -> int:
        return max(1, min(127, int(volume * 127)))

    def _update_vibrato_from_imu(self, imu_snapshot: dict):
        if not (self.audio_synth and hasattr(self.audio_synth, "set_vibrato_scale")):
            return

        gx = float(imu_snapshot.get("gx", 0.0))
        gy = float(imu_snapshot.get("gy", 0.0))
        gz = float(imu_snapshot.get("gz", 0.0))
        magnitude = (abs(gx) + abs(gy) + abs(gz)) / 3.0

        now = time.time()
        self._imu_samples.append((now, magnitude))
        cutoff = now - IMU_WINDOW_SEC
        while self._imu_samples and self._imu_samples[0][0] < cutoff:
            self._imu_samples.popleft()

        if len(self._imu_samples) < 6:
            return

        times = [t for t, _ in self._imu_samples]
        values = [v for _, v in self._imu_samples]
        duration = times[-1] - times[0]
        if duration <= 0.0:
            return

        mean_val = sum(values) / len(values)
        centered = [v - mean_val for v in values]
        amplitude = max(centered) - min(centered)
        if amplitude < IMU_MIN_AMPLITUDE:
            scale = 1.0
        else:
            crossings = 0
            for i in range(1, len(centered)):
                prev = centered[i - 1]
                curr = centered[i]
                if (prev <= 0.0 < curr) or (prev >= 0.0 > curr):
                    crossings += 1
            freq = crossings / (2.0 * duration) if duration > 0 else 0.0
            if IMU_MIN_FREQ <= freq <= IMU_MAX_FREQ:
                t = (freq - IMU_MIN_FREQ) / (IMU_MAX_FREQ - IMU_MIN_FREQ)
                scale = 1.0 + t * (VIBRATO_SCALE_MAX - 1.0)
            else:
                scale = 1.0

        if abs(scale - self._last_vibrato_scale) >= 0.02:
            self.audio_synth.set_vibrato_scale(scale)
            self._last_vibrato_scale = scale

    def process(self, fsr_levels: List[float], imu_snapshot: dict):
        if imu_snapshot is None:
            imu_snapshot = {}
        self._update_vibrato_from_imu(imu_snapshot)

        # fsr_levels are 0..1; convert to 0..100
        values = [max(0.0, min(1.0, v)) * 100.0 for v in fsr_levels]
        if len(values) < FSR_COUNT:
            values.extend([0.0] * (FSR_COUNT - len(values)))
        elif len(values) > FSR_COUNT:
            values = values[:FSR_COUNT]

        volume = self._compute_volume(values)
        if volume <= 0.0:
            if self._note_on and self._current_note is not None:
                self.driver.send(mido.Message('note_off', note=self._current_note, velocity=0, channel=self.channel))
                if self.audio_synth:
                    self.audio_synth.note_off(self._current_note, 'fsr_pitch')
            self._note_on = False
            self._current_note = None
            return

        note = self._compute_pitch_note(values)
        velocity = self._velocity_from_volume(volume)

        # Update channel volume for external MIDI devices
        self.driver.send(mido.Message('control_change', control=7, value=velocity, channel=self.channel))
        if self.audio_synth and hasattr(self.audio_synth, "set_expression"):
            self.audio_synth.set_expression(volume)

        if not self._note_on:
            self.driver.send(mido.Message('note_on', note=note, velocity=velocity, channel=self.channel))
            if self.audio_synth:
                self.audio_synth.note_on(note, velocity, 'fsr_pitch')
            self._note_on = True
            self._current_note = note
            return

        if note != self._current_note:
            self.driver.send(mido.Message('note_off', note=self._current_note, velocity=0, channel=self.channel))
            if self.audio_synth:
                self.audio_synth.note_off(self._current_note, 'fsr_pitch')
            self.driver.send(mido.Message('note_on', note=note, velocity=velocity, channel=self.channel))
            if self.audio_synth:
                self.audio_synth.note_on(note, velocity, 'fsr_pitch')
            self._current_note = note
