import threading
import time

_lock = threading.Lock()

rovers = {}  # chave = rover_id → {pos, batt, mission, status, last_update, alive}

def update_telemetry(rover_id, position, battery, status, speed):
    with _lock:
        r = rovers.setdefault(rover_id, {})
        r["position"] = position
        r["battery"] = battery
        r["status"] = status
        r["speed"] = speed
        r["last_telemetry"] = time.time()
        r["alive"] = True


def update_mission(rover_id, mission_id, progress, mission_status):
    with _lock:
        r = rovers.setdefault(rover_id, {})
        r["mission_id"] = mission_id
        r["mission_progress"] = progress
        r["mission_status"] = mission_status
        r["last_mission_update"] = time.time()


def mark_disconnected(rover_id):
    with _lock:
        r = rovers.setdefault(rover_id, {})
        r["alive"] = False
        r["status"] = "offline"


def get_snapshot():
    with _lock:
        return {k: v.copy() for k, v in rovers.items()}

ROVER_TIMEOUT = 12   # segundos sem telemetria → rover marcado como OFFLINE

def apply_timeouts():
    """
    Marca rovers como 'offline' quando não enviam telemetria
    há mais de ROVER_TIMEOUT segundos.
    """
    now = time.time()

    for rid, st in list(rovers.items()):
        last = st.get("last_update", 0)

        if now - last > ROVER_TIMEOUT:
            st["status"] = "offline"