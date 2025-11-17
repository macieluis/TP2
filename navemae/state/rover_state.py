import json
import os
import time
import threading

STATE_FILE = "rover_state.json"
_lock = threading.Lock()

# Estrutura interna:
# {
#   "R-001": {
#       "position": [x,y,z],
#       "battery": 100.0,
#       "status": "idle"/"in_mission"/"offline",
#       "speed": 0.0,
#       "last_telemetry": timestamp,
#       "mission_id": "M-123" | None,
#       "mission_progress": 0.0,
#       "mission_status": "assigned"/"in_progress"/"completed",
#       "last_mission_update": timestamp
#   },
#   ...
# }

rovers = {}


# ==========================
#  PERSISTÊNCIA
# ==========================

def _load_state():
    global rovers
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                rovers = json.load(f)
        except Exception:
            rovers = {}
    else:
        rovers = {}


def _save_state():
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(rovers, f, indent=2)
    except Exception:
        pass


_load_state()


# ==========================
#  GETTERS / SNAPSHOT
# ==========================

def get_snapshot():
    with _lock:
        return json.loads(json.dumps(rovers))


# ==========================
#  UPDATE TELEMETRY (TS)
# ==========================

def update_telemetry(rover_id, position, battery, status, speed):
    with _lock:
        r = rovers.setdefault(rover_id, {
            "position": [0.0, 0.0, 0.0],
            "battery": 100.0,
            "status": "idle",
            "speed": 0.0,
            "mission_id": None,
            "mission_progress": 0.0,
            "mission_status": None,
            "last_mission_update": None
        })

        r["position"] = position
        r["battery"] = battery
        r["status"] = status
        r["speed"] = speed
        r["last_telemetry"] = time.time()

        _save_state()


# ==========================
#  UPDATE MISSION (ML)
# ==========================

def update_mission(rover_id, mission_id, progress, mission_status, position):
    with _lock:
        r = rovers.setdefault(rover_id, {
            "position": [0.0, 0.0, 0.0],
            "battery": 100.0,
            "status": "idle",
            "speed": 0.0,
            "mission_id": None,
            "mission_progress": 0.0,
            "mission_status": None
        })

        r["mission_id"] = mission_id
        r["mission_progress"] = progress
        r["mission_status"] = mission_status
        r["position"] = position
        r["last_mission_update"] = time.time()

        if progress >= 100.0:
            r["status"] = "idle"
            r["mission_id"] = None

        _save_state()


# ==========================
#  HEARTBEAT
# ==========================

def touch_heartbeat(rover_id):
    with _lock:
        if rover_id not in rovers:
            return
        rovers[rover_id]["last_telemetry"] = time.time()
        _save_state()


# ==========================
#  TIMEOUTS (offline se sumir)
# ==========================

def apply_timeouts(timeout_sec=15):
    now = time.time()
    offline = []

    with _lock:
        for rid, r in rovers.items():
            last = r.get("last_telemetry")
            if last and now - last > timeout_sec:
                r["status"] = "offline"
                offline.append(rid)

        if offline:
            _save_state()


# ==========================
#  HELPERS
# ==========================

def mark_disconnected(rover_id):
    with _lock:
        if rover_id in rovers:
            rovers[rover_id]["status"] = "offline"
            _save_state()


def is_rover_alive(rover_id):
    with _lock:
        if rover_id not in rovers:
            return False
        return rovers[rover_id].get("status") != "offline"


def get_last_known_state(rover_id):
    with _lock:
        if rover_id not in rovers:
            return [0.0, 0.0, 0.0], 100.0

        pos = rovers[rover_id].get("position", [0.0, 0.0, 0.0])
        bat = rovers[rover_id].get("battery", 100.0)

        return pos, bat
