# rover/rover_identity.py
ROVER_ID = None

VALID_ROVERS = ["R-001", "R-002", "R-003", "R-004"]

def choose_rover_id():
    global ROVER_ID
    print("Escolhe o Rover (R-001, R-002, R-003, R-004):")
    rid = input("> ").strip().upper()
    if rid not in VALID_ROVERS:
        print("Rover inválido.")
        raise SystemExit(1)
    ROVER_ID = rid
    return ROVER_ID
