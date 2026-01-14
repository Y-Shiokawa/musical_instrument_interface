# FSR + IMU MIDI Simulator

This project is a Python simulator of a musical interface that maps pressure sensors (FSRs) and an IMU to MIDI output.
No hardware is required; everything is simulated in software using sliders and controls.

## Features

- Simulates 10 FSR pressure inputs with RC low-pass smoothing and an optional gain stage.
- Simulates IMU (Ax, Ay, Az, Gx, Gy, Gz).
- Maps:
  - Each FSR -> MIDI note (chromatic by default, starting at MIDI note 60).
  - FSR pressure -> MIDI velocity.
  - IMU Gx -> pitch bend.
  - IMU Gy -> modulation (MIDI CC 1).
- Real-time Tkinter GUI with sliders for sensors and a log panel showing sent MIDI messages.
- Uses `mido` + `python-rtmidi` for real MIDI I/O (creates a virtual port when backend supports it), with console/log echo.

## Files

- `src/main.py` - program entry point
- `src/gui.py` - Tkinter GUI and main loop
- `src/sensors.py` - simulated FSR and IMU classes (smoothing and gain)
- `src/midi_mapper.py` - MIDI driver and mapping logic
- `requirements.txt` - Python dependencies

## Quick start

1. Create and activate a virtual environment (recommended):

   python3 -m venv venv
   source venv/bin/activate   # macOS / Linux
   venv\Scripts\activate      # Windows

2. Install dependencies:

   pip install -r requirements.txt

   Note: `python-rtmidi` is required to create virtual MIDI ports and to connect to system MIDI. If installation fails, `mido` will still work with available ports.

3. Run the simulator:

   python src/main.py

4. In the GUI:
   - Use the vertical sliders to change simulated FSR pressures (0..1023).
   - Use the IMU sliders to provide accelerometer and gyro values.
   - Click "Open MIDI Output" to create a virtual MIDI port (or open the default output).
   - Watch the MIDI log for messages being sent. You can route the virtual port in your DAW or MIDI monitor.

## MIDI mapping defaults

- FSR 0..9 -> MIDI notes [60, 61, 62, 63, 64, 65, 66, 67, 68, 69] (chromatic)
- Velocity = pressure (0..1) mapped to 1..127
- IMU Gx (gyro X) -> pitch bend (-8191..+8191)
- IMU Gy (gyro Y) -> CC1 (modulation) 0..127

## Customization

- Adjust per-FSR tau/gain and MIDI channel in the code (`src/sensors.py`, `src/midi_mapper.py`).
- To use a different scale (e.g., pentatonic), modify the `notes` list passed to `MidiMapper`.

## Notes

- The simulation updates at ~60 Hz by default. Change `UPDATE_HZ` in `src/gui.py` to alter responsiveness.
- This project is intended as a starting simulator for algorithm development and UI prototyping before connecting physical sensors and a microcontroller (Teensy).

## License

MIT
