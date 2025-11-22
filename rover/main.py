# rover/main.py
import threading
import rover_identity
from rover_identity import choose_rover_id

# Agora já deve funcionar porque a função existe no missionlink_client
from missionlink_client import start_missionlink, get_status, get_current_task
from telemetry_client import start_telemetry

def main():
    print(">>> main iniciou")
    choose_rover_id()

    def get_pos(): return rover_identity.POSITION
    battery_ref = rover_identity

    # Thread do TelemetryStream
    ts_thread = threading.Thread(
        target=start_telemetry,
        args=(get_pos, get_status, get_current_task, battery_ref),
        daemon=True
    )
    ts_thread.start()

    # MissionLink corre no main thread
    try:
        start_missionlink()
    except KeyboardInterrupt:
        print(f"[{rover_identity.ROVER_ID}] MissionLink encerrado manualmente.")

if __name__ == "__main__":
    main()