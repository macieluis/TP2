# rover/rover_identity.py
import os
import json

from typing import Optional
ROVER_ID: Optional[str] = None #no core

#ROVER_ID: str | None = None NO PC


# estado "real" do rover (usado por ML e TS)
POSITION = [0.0, 0.0, 0.0]   # x, y, z
BATTERY = 100.0              # em percentagem
SPEED = 0.0                  # m/s (aprox.)

STATE_DIR = "rover_data"


def _state_file():
    if ROVER_ID is None:
        return None
    os.makedirs(STATE_DIR, exist_ok=True)
    return os.path.join(STATE_DIR, f"state_{ROVER_ID}.json")


def load_state():
    """Carrega última posição e bateria deste rover (se existir)."""
    global POSITION, BATTERY

    path = _state_file()
    if not path or not os.path.exists(path):
        POSITION = [0.0, 0.0, 0.0]
        BATTERY = 100.0
        return

    try:
        with open(path, "r") as f:
            data = json.load(f)
        POSITION = data.get("position", [0.0, 0.0, 0.0])
        BATTERY = float(data.get("battery", 100.0))
    except Exception:
        # se o ficheiro estiver marado, começa default
        POSITION = [0.0, 0.0, 0.0]
        BATTERY = 100.0


def save_state():
    """Guarda posição e bateria atuais em disco."""
    path = _state_file()
    if not path:
        return

    data = {
        "position": POSITION,
        "battery": BATTERY,
    }
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        # aqui não vale a pena rebentar o rover só porque não conseguiu gravar
        pass


VALID_ROVERS = ["R-001", "R-002", "R-003", "R-004"]


def choose_rover_id():
    """Pergunta o rover ao utilizador e carrega o estado desse rover."""
    global ROVER_ID

    print("Escolhe o Rover (R-001, R-002, R-003, R-004):")
    rid = input("> ").strip().upper()
    if rid not in VALID_ROVERS:
        print("Rover inválido.")
        raise SystemExit(1)

    ROVER_ID = rid
    load_state()
    print(f"[{ROVER_ID}] Estado inicial: pos={POSITION} | batt={BATTERY:.1f}%")
