import json, os

FILE = os.path.join(os.path.dirname(__file__), "state.json")

# Estado em cache para evitar I/O constante
_state = {}

def load_state():
    global _state
    if not os.path.exists(FILE):
        _state = {}
        save_state()
    else:
        with open(FILE, "r") as f:
            _state = json.load(f)

def save_state():
    with open(FILE, "w") as f:
        json.dump(_state, f, indent=4)

def get_rover_state(rover_id):
    """Retorna {x, y, battery} para o rover."""
    if rover_id not in _state:
        _state[rover_id] = {"x": 0.0, "y": 0.0, "battery": 100.0}
        save_state()
    return _state[rover_id]

def update_rover_state(rover_id, x=None, y=None, battery=None):
    st = get_rover_state(rover_id)

    if x is not None: st["x"] = x
    if y is not None: st["y"] = y
    if battery is not None: st["battery"] = battery

    save_state()
