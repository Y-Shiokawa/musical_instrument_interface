# FSR + IMU MIDI Simulator

This project is a Python simulator of a musical interface that maps pressure sensors (FSRs) and an IMU to MIDI output.
No hardware is required; everything is simulated in software using sliders and controls.

## Features

- Simulates 10 FSR pressure inputs with RC low-pass smoothing and an optional gain stage.
- Simulates IMU (Ax, Ay, Az, Gx, Gy, Gz).
- Maps:
  - 10 FSRs -> single pitch from a 2-octave scale (genre-dependent).
  - Average FSR pressure -> volume (0.0..1.0).
  - IMU periodic motion (2..10 Hz) -> vibrato strength boost.
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
   - Use the vertical sliders to change simulated FSR pressures (0..100).
   - Use the IMU sliders to provide accelerometer and gyro values.
   - Click "Open MIDI Output" to create a virtual MIDI port (or open the default output).
   - Watch the MIDI log for messages being sent. You can route the virtual port in your DAW or MIDI monitor.

## MIDI mapping defaults

- Pitch is derived from sensors 2, 5, 7, 10 using a 2-octave scale.
- Volume is derived from the average of all 10 sensors.
- IMU periodic motion (2..10 Hz) boosts vibrato strength.

## Customization

- Adjust per-FSR tau/gain and MIDI channel in the code (`src/sensors.py`, `src/midi_mapper.py`).
- To use a different scale (e.g., pentatonic), change the genre preset scale in `src/audio_synth.py`.

## Notes

- The simulation updates at ~60 Hz by default. Change `UPDATE_HZ` in `src/gui.py` to alter responsiveness.
- This project is intended as a starting simulator for algorithm development and UI prototyping before connecting physical sensors and a microcontroller (Teensy).

## License

MIT
