# rover/main.py
import threading
from rover_identity import choose_rover_id
import rover_identity
from telemetry_client import start_telemetry
from missionlink_client import start_missionlink, get_mission_status  # já tens isto

def main():
    print(">>> main iniciou")
    choose_rover_id()

    # thread para TS (status vem do MissionLink)
    threading.Thread(
        target=start_telemetry,
        args=(get_mission_status,),   # task_provider podes deixar None por agora
        daemon=True
    ).start()

    # MissionLink mantém o programa vivo
    try:
        start_missionlink()
    except KeyboardInterrupt:
        print(f"\n[{rover_identity.ROVER_ID}] Rover encerrado.")


if __name__ == "__main__":
    main()
