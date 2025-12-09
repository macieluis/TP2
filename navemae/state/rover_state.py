# navemae/state/rover_state.py
import json
import os
import time
import threading

STATE_FILE = "rover_state.json"
_lock = threading.Lock()
rovers = {}
GLOBAL_HISTORY = []

def _load_state():
    global rovers
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                rovers = json.load(f)
        except Exception: rovers = {}
    else: rovers = {}

def _save_state():
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(rovers, f, indent=2)
    except Exception: pass

_load_state()

def get_snapshot():
    with _lock:
        return json.loads(json.dumps(rovers))

def update_telemetry(rover_id, position, battery, status, speed):
    with _lock:
        r = rovers.setdefault(rover_id, {
            "position": [0.0, 0.0, 0.0], "battery": 100.0, "status": "idle",
            "speed": 0.0, "mission_id": None, "mission_progress": 0.0,
            "mission_status": None, "last_mission_update": None, "mission_details": {}
        })
        r["position"] = position
        r["battery"] = battery
        r["status"] = status
        r["speed"] = speed
        r["last_telemetry"] = time.time()
        _save_state()

def update_mission(rover_id, mission_id, progress, mission_status, position, extra_data=None):
    with _lock:
        r = rovers.setdefault(rover_id, {
            "position": [0.0, 0.0, 0.0], "battery": 100.0, "status": "idle",
            "speed": 0.0, "mission_id": None, "mission_progress": 0.0,
            "mission_status": None, "mission_details": {}
        })

        r["mission_id"] = mission_id
        r["mission_progress"] = progress
        r["mission_status"] = mission_status
        r["position"] = position
        r["last_mission_update"] = time.time()
        if extra_data:
            r["mission_details"] = extra_data
    
        if progress >= 100.0 or mission_status in ["completed", "aborted", "incomplete"]:
            
            # Guardar histórico do último resultado para a Web saber
            r["last_finished"] = {
                "id": mission_id,
                "status": mission_status,
                "ts": time.time() # Timestamp para evitar notificações repetidas
            }
            
            history_entry = {
                "mission_id": mission_id,
                "rover_id": rover_id,
                "task": r.get("mission_id", "???"), # O ID ainda está no estado
                "status": mission_status,
                "time": time.strftime("%H:%M:%S")
            }
            GLOBAL_HISTORY.insert(0, history_entry) # Adiciona no topo
            if len(GLOBAL_HISTORY) > 10:
                GLOBAL_HISTORY.pop() # Remove o mais antigo
            
            r["mission_id"] = None
            r["mission_progress"] = 0.0
            r["mission_details"] = {}
            # Se completou, volta a idle (se não estiver offline/charging)
            if r["status"] == "in_mission": 
                r["status"] = "idle"

        _save_state()

def touch_heartbeat(rover_id):
    with _lock:
        if rover_id in rovers:
            rovers[rover_id]["last_telemetry"] = time.time()
            _save_state()

def apply_timeouts(timeout_sec=15):
    now = time.time()
    offline = []
    with _lock:
        for rid, r in rovers.items():
            last = r.get("last_telemetry")
            if last and now - last > timeout_sec:
                r["status"] = "offline"
                offline.append(rid)
        if offline: _save_state()

def mark_disconnected(rover_id):
    with _lock:
        if rover_id in rovers:
            rovers[rover_id]["status"] = "offline"
            _save_state()

def is_rover_alive(rover_id):
    with _lock:
        if rover_id not in rovers: return False
        return rovers[rover_id].get("status") != "offline"

def get_last_known_state(rover_id):
    with _lock:
        if rover_id not in rovers: return [0.0, 0.0, 0.0], 100.0
        return rovers[rover_id].get("position", [0.0, 0.0, 0.0]), rovers[rover_id].get("battery", 100.0)
    
def get_history_snapshot():
    with _lock:
        return list(GLOBAL_HISTORY)