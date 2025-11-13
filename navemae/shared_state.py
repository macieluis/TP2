# Armazena dados globais (missões, telemetria)

import json, threading, os, time

STATE_FILE = "navemae/data/telemetry.json"
_lock = threading.Lock()
telemetry_state = {}

def update_telemetry_state(rover_id, payload):
    with _lock:
        telemetry_state[rover_id] = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            **payload
        }
        _save_state()

def _save_state():
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(telemetry_state, f, indent=2)
