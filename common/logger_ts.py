import json, os, threading, time

LOG_FILE = "navemae/data/telemetry_log.json"
_lock = threading.Lock()

def _load_log():
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def _save_log(data):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def save_telemetry(rover_id, position, battery, status, speed):
    """Guarda entrada simples de telemetria."""
    event = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "rover": rover_id,
        "position": position,
        "battery": battery,
        "status": status,
        "speed": speed,
    }
    with _lock:
        data = _load_log()
        data.append(event)
        _save_log(data)

def print_telemetry_summary(limit=20):
    data = _load_log()
    print("\n=== ÚLTIMOS REGISTOS DE TELEMETRIA ===")
    for e in data[-limit:]:
        print(f"[{e['timestamp']}] {e['rover']} pos={e['position']} batt={e['battery']} status={e['status']}")
