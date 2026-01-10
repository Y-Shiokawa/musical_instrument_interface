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
from audio_synth import SimpleSynth
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

        # audio synth
        self.synth = SimpleSynth()
        
        # midi
        self.log_widget = None
        self.midi_driver = MIDIDriver(port_name="FSR-IMU-Sim", virtual=True, logger=self._log)
        self.mapper = MidiMapper(self.midi_driver, notes=None, logger=self._log, audio_synth=self.synth)

        # GUI elements
        self._build_ui()

        # time
        self._last_time = time.time()
        self.running = True

    def _build_ui(self):
        # Create notebook (tabbed interface)
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Main controls tab
        main_tab = ttk.Frame(notebook, padding=8)
        notebook.add(main_tab, text="Main Controls")
        
        # Settings tab
        settings_tab = ttk.Frame(notebook, padding=8)
        notebook.add(settings_tab, text="Genre Settings")
        
        self._build_main_controls(main_tab)
        self._build_genre_settings(settings_tab)
    
    def _build_main_controls(self, frm):

        # FSR sliders (0..1023 to mimic ADC)
        fsr_frame = ttk.LabelFrame(frm, text="FSR Sensors (0..1023)", padding=6)
        fsr_frame.grid(row=0, column=0, sticky="nw", padx=4, pady=4)
        self.fsr_sliders = []
        self.fsr_value_labels = []
        self.fsr_freeze_vars = []
        for i in range(5):
            col_frame = ttk.Frame(fsr_frame)
            col_frame.grid(row=0, column=i, padx=6, pady=6)
            
            # Value display
            val_lbl = ttk.Label(col_frame, text="0", width=6, anchor="center")
            val_lbl.pack()
            self.fsr_value_labels.append(val_lbl)
            
            # Slider
            s = ttk.Scale(col_frame, from_=0, to=1023, orient=tk.VERTICAL, length=200)
            s.set(0)
            s.pack()
            self.fsr_sliders.append(s)
            
            # FSR label and controls
            lbl = ttk.Label(col_frame, text=f"FSR {i}")
            lbl.pack()
            
            # Freeze checkbox
            freeze_var = tk.BooleanVar(value=False)
            freeze_cb = ttk.Checkbutton(col_frame, text="Freeze", variable=freeze_var)
            freeze_cb.pack()
            self.fsr_freeze_vars.append(freeze_var)
            
            # Reset button
            reset_btn = ttk.Button(col_frame, text="Reset", 
                                   command=lambda idx=i: self.fsr_sliders[idx].set(0))
            reset_btn.pack()

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
        
        # Audio control
        self.audio_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(midi_frame, text="Audio Feedback", variable=self.audio_enabled_var, 
                       command=self._toggle_audio).grid(row=0, column=2, padx=4)
        
        # Volume control
        volume_frame = ttk.LabelFrame(ctrl_frame, text="Master Volume", padding=6)
        volume_frame.grid(row=0, column=5, padx=8)
        
        ttk.Label(volume_frame, text="0%").grid(row=0, column=0, padx=2)
        self.volume_var = tk.DoubleVar(value=100)
        self.volume_slider = ttk.Scale(volume_frame, from_=0, to=200, orient=tk.HORIZONTAL, 
                                       variable=self.volume_var, length=150,
                                       command=self._update_volume)
        self.volume_slider.grid(row=0, column=1, padx=5)
        ttk.Label(volume_frame, text="200%").grid(row=0, column=2, padx=2)
        
        self.volume_label = ttk.Label(volume_frame, text="100%", font=('Arial', 10, 'bold'))
        self.volume_label.grid(row=1, column=0, columnspan=3, pady=2)
        self.connect_btn.grid(row=0, column=0, padx=4)
        self.virtual_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(midi_frame, text="Virtual Port", variable=self.virtual_var).grid(row=0, column=1, padx=4)

        # Log panel
        log_frame = ttk.LabelFrame(frm, text="MIDI Log", padding=6)
        log_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)
        self.log_widget = scrolledtext.ScrolledText(log_frame, width=80, height=10, state=tk.DISABLED)
        self.log_widget.pack(fill=tk.BOTH, expand=True)

        # Make main tab resizable
        frm.columnconfigure(0, weight=1)
        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(2, weight=1)
    
    def _build_genre_settings(self, frm):
        """Build genre selection and settings UI"""
        # Title
        title = ttk.Label(frm, text="Musical Genre Selection", font=('Arial', 14, 'bold'))
        title.pack(pady=10)
        
        # Description
    
    def _change_genre(self, genre_key):
        """Change the current musical genre"""
        self.synth.set_genre(genre_key)
        
        # Update status label
        genres = self.synth.get_genre_list()
        for key, name, description in genres:
            if key == genre_key:
                self.genre_status_label.config(
                    text=f"Current Genre: {name} - {description}"
                )
                break
        
        self._log(f"Genre changed to: {genre_key}")
    
    def _update_volume(self, value):
        """Update master volume"""
        volume_percent = float(value)
        volume_normalized = volume_percent / 100.0
        self.synth.set_volume(volume_normalized)
        self.volume_label.config(text=f"{int(volume_percent)}%")
    
    def _build_genre_settings(self, frm):
        """Build genre selection and settings UI"""
        # Title
        title = ttk.Label(frm, text="Musical Genre Selection", font=('Arial', 14, 'bold'))
        title.pack(pady=10)
        
        # Description
        desc = ttk.Label(frm, text="Choose a musical style to customize the sound characteristics", 
                        font=('Arial', 10))
        desc.pack(pady=5)
        
        # Genre selection frame
        genre_frame = ttk.LabelFrame(frm, text="Available Genres", padding=15)
        genre_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Get available genres
        genres = self.synth.get_genre_list()
        self.current_genre_var = tk.StringVar(value='jazz')
        
        # Create radio buttons for each genre
        for i, (key, name, description) in enumerate(genres):
            frame = ttk.Frame(genre_frame)
            frame.pack(fill=tk.X, pady=8, padx=10)
            
            # Radio button
            rb = ttk.Radiobutton(
                frame, 
                text=name, 
                value=key, 
                variable=self.current_genre_var,
                command=lambda k=key: self._change_genre(k)
            )
            rb.pack(side=tk.LEFT, padx=5)
            
            # Description
            desc_label = ttk.Label(frame, text=f"  {description}", foreground='gray')
            desc_label.pack(side=tk.LEFT, padx=5)
        
        # Current status
        status_frame = ttk.LabelFrame(frm, text="Current Status", padding=10)
        status_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.genre_status_label = ttk.Label(
            status_frame, 
            text="Current Genre: Jazz - Smooth, warm tones with rich harmonics",
            font=('Arial', 10, 'italic'),
            foreground='blue'
        )
        self.genre_status_label.pack(pady=5)

    def _toggle_audio(self):
        if self.audio_enabled_var.get():
            self.mapper.audio_synth = self.synth
            self.mapper.imu_audio_enabled = True  # Enable IMU too
            self._log("Audio feedback enabled (including IMU)")
        else:
            self.synth.all_notes_off()
            self.mapper.audio_synth = None
            self.mapper.imu_audio_enabled = False
            self._log("Audio feedback disabled")

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
            # Check if this sensor is frozen
            if not self.fsr_freeze_vars[i].get():
                raw_adc = s.get()
                level = float(raw_adc) / 1023.0
                self.fsrs[i].set_raw(level)
            
            # Update value display
            current_val = int(s.get())
            self.fsr_value_labels[i].config(text=str(current_val))
            
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
        try:
            self.root.mainloop()
        finally:
            self.running = False
            # Clean up audio
            if self.synth:
                self.synth.close()
