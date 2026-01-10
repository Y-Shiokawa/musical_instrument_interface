"""
Tkinter GUI for the simulator.

- Provides sliders for 5 FSR sensors
- Sliders for IMU axes (Ax, Ay, Az, Gx, Gy, Gz)
- Controls for smoothing (tau) and gain per FSR (simple global control provided)
- Connect button for MIDI
- Live log panel for MIDI messages
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import time
from sensors import FSRChannel, IMUSimulator
from midi_mapper import MIDIDriver, MidiMapper
from threading import Lock

UPDATE_HZ = 60.0

class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("FSR+IMU MIDI Simulator")
        self.lock = Lock()

        # sensors
        self.fsrs = [FSRChannel(i, tau=0.05, gain=1.0) for i in range(5)]
        self.imu = IMUSimulator(gyro_range_dps=250.0)

        # midi
        self.log_widget = None
        self.midi_driver = MIDIDriver(port_name="FSR-IMU-Sim", virtual=True, logger=self._log)
        self.mapper = MidiMapper(self.midi_driver, notes=None, logger=self._log)

        # GUI elements
        self._build_ui()

        # time
        self._last_time = time.time()
        self.running = True

    def _build_ui(self):
        frm = ttk.Frame(self.root, padding=8)
        frm.grid(row=0, column=0, sticky="nsew")

        # FSR sliders (0..1023 to mimic ADC)
        fsr_frame = ttk.LabelFrame(frm, text="FSR Sensors (0..1023)", padding=6)
        fsr_frame.grid(row=0, column=0, sticky="nw", padx=4, pady=4)
        self.fsr_sliders = []
        for i in range(5):
            s = ttk.Scale(fsr_frame, from_=0, to=1023, orient=tk.VERTICAL)
            s.set(0)
            s.grid(row=0, column=i, padx=6, pady=6)
            lbl = ttk.Label(fsr_frame, text=f"FSR {i}")
            lbl.grid(row=1, column=i)
            self.fsr_sliders.append(s)

        # IMU controls
        imu_frame = ttk.LabelFrame(frm, text="IMU (Accel g, Gyro dps)", padding=6)
        imu_frame.grid(row=0, column=1, sticky="ne", padx=4, pady=4)
        self.imu_scales = {}
        # accel axes - range -2..2 g
        for idx, ax in enumerate(("Ax","Ay","Az")):
            s = ttk.Scale(imu_frame, from_=2.0, to=-2.0, orient=tk.VERTICAL)
            s.set(0.0)
            s.grid(row=0, column=idx, padx=6)
            ttk.Label(imu_frame, text=ax).grid(row=1, column=idx)
            self.imu_scales[ax] = s
        # gyro axes - range -250..250 dps
        for idx, gx in enumerate(("Gx","Gy","Gz")):
            s = ttk.Scale(imu_frame, from_=250.0, to=-250.0, orient=tk.VERTICAL)
            s.set(0.0)
            s.grid(row=0, column=3+idx, padx=6)
            ttk.Label(imu_frame, text=gx).grid(row=1, column=3+idx)
            self.imu_scales[gx] = s

        # Controls: smoothing (tau) and gain
        ctrl_frame = ttk.LabelFrame(frm, text="Controls", padding=6)
        ctrl_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        ttk.Label(ctrl_frame, text="FSR tau (s)").grid(row=0, column=0, padx=8)
        self.tau_var = tk.DoubleVar(value=0.05)
        tau_entry = ttk.Entry(ctrl_frame, textvariable=self.tau_var, width=8)
        tau_entry.grid(row=0, column=1)
        ttk.Label(ctrl_frame, text="FSR gain").grid(row=0, column=2, padx=8)
        self.gain_var = tk.DoubleVar(value=1.0)
        gain_entry = ttk.Entry(ctrl_frame, textvariable=self.gain_var, width=8)
        gain_entry.grid(row=0, column=3)

        # MIDI controls
        midi_frame = ttk.Frame(ctrl_frame)
        midi_frame.grid(row=0, column=4, padx=8)
        self.connect_btn = ttk.Button(midi_frame, text="Open MIDI Output", command=self._open_midi)
        self.connect_btn.grid(row=0, column=0, padx=4)
        self.virtual_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(midi_frame, text="Virtual Port", variable=self.virtual_var).grid(row=0, column=1, padx=4)

        # Log panel
        log_frame = ttk.LabelFrame(frm, text="MIDI Log", padding=6)
        log_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)
        self.log_widget = scrolledtext.ScrolledText(log_frame, width=80, height=10, state=tk.DISABLED)
        self.log_widget.pack(fill=tk.BOTH, expand=True)

        # Make window resizable
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

    def _open_midi(self):
        self.midi_driver.virtual = bool(self.virtual_var.get())
        self.midi_driver.open()
        self._log("MIDI connect initiated.")

    def _log(self, text: str):
        with self.lock:
            if self.log_widget:
                self.log_widget.configure(state=tk.NORMAL)
                self.log_widget.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {text}\n")
                self.log_widget.see(tk.END)
                self.log_widget.configure(state=tk.DISABLED)
            else:
                print(text)

    def _update_sensors_from_ui(self, dt):
        # Update FSRs from sliders (0..1023 -> 0..1)
        for i, s in enumerate(self.fsr_sliders):
            raw_adc = s.get()
            level = float(raw_adc) / 1023.0
            self.fsrs[i].set_raw(level)
            # apply global tau and gain
            try:
                self.fsrs[i].tau = float(self.tau_var.get())
            except Exception:
                pass
            try:
                self.fsrs[i].gain = float(self.gain_var.get())
            except Exception:
                pass

        # Update IMU from sliders
        ax = self.imu_scales["Ax"].get()
        ay = self.imu_scales["Ay"].get()
        az = self.imu_scales["Az"].get()
        gx = self.imu_scales["Gx"].get()
        gy = self.imu_scales["Gy"].get()
        gz = self.imu_scales["Gz"].get()
        self.imu.set_accel_raw(ax, ay, az)
        self.imu.set_gyro_raw(gx, gy, gz)

        # Step the filters and collect smoothed values
        smoothed = []
        for ch in self.fsrs:
            sm = ch.update(dt=dt)
            smoothed.append(sm)
        return smoothed

    def _main_loop(self):
        now = time.time()
        dt = now - self._last_time if self._last_time else (1/UPDATE_HZ)
        self._last_time = now

        # read UI values into simulators, update filters
        smoothed = self._update_sensors_from_ui(dt)

        imu_snap = self.imu.snapshot()
        # send through mapper
        self.mapper.process(smoothed, imu_snap)

        # schedule next update
        if self.running:
            self.root.after(int(1000 / UPDATE_HZ), self._main_loop)

    def run(self):
        # start periodic loop
        self._last_time = time.time()
        self.root.after(0, self._main_loop)
        self.root.mainloop()
        self.running = False
