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
    def __init__(self, midi_driver: MIDIDriver, notes: List[int] = None, channel: int = 0, logger: Optional[Callable] = None, audio_synth=None):
        self.driver = midi_driver
        self.notes = notes or DEFAULT_NOTES
        self.channel = channel
        self.logger = logger or (lambda s: None)
        self.threshold = DEFAULT_THRESHOLD
        self.audio_synth = audio_synth  # Optional audio synthesizer
        # track note state to send note_off when pressure released
        self._note_on = [False] * len(self.notes)
        
        # IMU audio control
        self.imu_audio_enabled = True  # ENABLED by default
        
        # IMU smoothing buffers
        self._imu_velocities = {}  # Store last velocity for each IMU axis
        self._imu_notes = {}  # Store current note for each IMU axis

    def _velocity_from_level(self, level: float) -> int:
        # level is 0.0..1.0 -> velocity 1..127 (0 reserved)
        return max(1, min(127, int(level * 127)))

    def process(self, fsr_levels: List[float], imu_snapshot: dict):
        # fsr_levels: list of smoothed, amplified levels 0..1
        for i, level in enumerate(fsr_levels):
            note = self.notes[i] if i < len(self.notes) else (DEFAULT_BASE_NOTE + i)
            instrument = f'fsr{i}'
            
            if level >= self.threshold and not self._note_on[i]:
                vel = self._velocity_from_level(level)
                msg = mido.Message('note_on', note=note, velocity=vel, channel=self.channel)
                self.driver.send(msg)
                # Play audio feedback with specific instrument
                if self.audio_synth:
                    self.audio_synth.note_on(note, vel, instrument)
                self._note_on[i] = True
            elif level < self.threshold and self._note_on[i]:
                msg = mido.Message('note_off', note=note, velocity=0, channel=self.channel)
                self.driver.send(msg)
                # Stop audio feedback
                if self.audio_synth:
                    self.audio_synth.note_off(note, instrument)
                self._note_on[i] = False
            else:
                # Optionally, send aftertouch or continuous velocity updates (not implemented)
                pass

        # IMU -> pitch bend and modulation CC + audio feedback
        # Use gyro X (gx) mapped to pitch bend, range -8192..8191
        gx = imu_snapshot.get("gx", 0.0)
        pitch = int(max(-1.0, min(1.0, gx)) * 8191)
        msg_pb = mido.Message('pitchwheel', pitch=pitch, channel=self.channel)
        self.driver.send(msg_pb)
        
        # Audio feedback for gyro X - SIMPLIFIED
        if self.audio_synth and self.imu_audio_enabled:
            if abs(gx) > 0.4:  # Higher threshold to reduce noise
                vel = max(20, int(abs(gx) * 30))  # Quieter - max 30
                self.audio_synth.note_on(72, vel, 'imu_gx')
            else:
                self.audio_synth.note_off(72, 'imu_gx')

        # Use gyro Y (gy) mapped to CC1 (modulation) 0..127
        gy = imu_snapshot.get("gy", 0.0)
        cc_val = max(0, min(127, int((gy + 1.0) / 2.0 * 127)))
        msg_cc = mido.Message('control_change', control=1, value=cc_val, channel=self.channel)
        self.driver.send(msg_cc)
        
        # Audio feedback for gyro Y - SIMPLIFIED
        if self.audio_synth and self.imu_audio_enabled:
            if abs(gy) > 0.4:
                vel = max(20, int(abs(gy) * 30))
                self.audio_synth.note_on(84, vel, 'imu_gy')
            else:
                self.audio_synth.note_off(84, 'imu_gy')
        
        # Audio feedback for gyro Z - SIMPLIFIED
        if self.audio_synth and self.imu_audio_enabled:
            gz = imu_snapshot.get("gz", 0.0)
            if abs(gz) > 0.4:
                vel = max(20, int(abs(gz) * 30))
                self.audio_synth.note_on(96, vel, 'imu_gz')
            else:
                self.audio_synth.note_off(96, 'imu_gz')
        
        # Audio feedback for accelerometer axes - SIMPLIFIED
        ax = imu_snapshot.get("ax", 0.0)
        ay = imu_snapshot.get("ay", 0.0)
        az = imu_snapshot.get("az", 0.0)
        
        if self.audio_synth and self.imu_audio_enabled:
            # Ax
            if abs(ax) > 0.4:
                vel = max(15, int(abs(ax) * 25))
                self.audio_synth.note_on(48, vel, 'imu_ax')
            else:
                self.audio_synth.note_off(48, 'imu_ax')
            
            # Ay
            if abs(ay) > 0.4:
                vel = max(15, int(abs(ay) * 25))
                self.audio_synth.note_on(36, vel, 'imu_ay')
            else:
                self.audio_synth.note_off(36, 'imu_ay')
            
            # Az
            if abs(az) > 0.4:
                vel = max(15, int(abs(az) * 25))
                self.audio_synth.note_on(24, vel, 'imu_az')
            else:
                self.audio_synth.note_off(24, 'imu_az')