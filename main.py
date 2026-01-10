#!/usr/bin/env python3
"""
Entry point for the FSR + IMU -> MIDI simulator.
"""
import sys
from gui import App

def main():
    app = App()
    app.run()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
