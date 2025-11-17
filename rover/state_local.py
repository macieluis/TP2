# rover/state_local.py
import json, os, time

_state = {
    "pos": [0.0, 0.0, 0.0],
    "batt": 100.0,
    "last_update": time.time()
}

FILE = None


def init(rover_id):
    global FILE
    FILE = f"rover_state_{rover_id}.json"
    if os.path.exists(FILE):
        load()
    else:
        save()   # inicializa


def load():
    global _state
    try:
        with open(FILE, "r") as f:
            _state = json.load(f)
    except:
        pass


def save():
    with open(FILE, "w") as f:
        json.dump(_state, f, indent=2)


def get_position():
    return _state["pos"]


def set_position(pos):
    _state["pos"] = [float(pos[0]), float(pos[1]), float(pos[2])]
    _state["last_update"] = time.time()


def get_battery():
    return _state["batt"]


def set_battery(v):
    _state["batt"] = max(0.0, min(100.0, float(v)))


# -------------------------
# BATERIA E CONSUMO
# -------------------------

CONSUMPTION = {
    "idle": 0.1,
    "scan_area": 0.1 + 0.05,
    "collect_sample": 0.1 + 0.1,
    "analyze_environment": 0.1 + 0.02
}

def consume_battery(duration_s, mission_type):
    """Subtrai bateria consoante a missão."""
    rate = CONSUMPTION.get(mission_type, 0.1)
    new_batt = _state["batt"] - (rate * duration_s)

    if new_batt < 20:
        # modo charging
        new_batt = min(100.0, new_batt + duration_s * 1.0)

    _state["batt"] = max(0.0, min(new_batt, 100.0))
    _state["last_update"] = time.time()
