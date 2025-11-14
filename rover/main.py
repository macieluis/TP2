# rover/main.py
import threading
from rover_identity import choose_rover_id
import rover_identity
from telemetry_client import start_telemetry
from missionlink_client import start_missionlink


def main():
    choose_rover_id()

    threading.Thread(target=start_missionlink, daemon=True).start()

    try:
        start_missionlink()
    except KeyboardInterrupt:
        print(f"\n[{rover_identity.ROVER_ID}] Rover encerrado.")


if __name__ == "__main__":
    main()
