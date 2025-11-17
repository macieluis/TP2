# rover/main.py
import threading
import rover_identity
from rover_identity import choose_rover_id, POSITION, BATTERY
from missionlink_client import start_missionlink
from telemetry_client import start_telemetry


def main():
    print(">>> main iniciou")
    choose_rover_id()

    # Funções que o TS vai usar para ir buscar estado *sempre atualizado*
    def get_pos():
        return rover_identity.POSITION

    def get_status():
        return "in_mission"   # o ML atualiza isto dinamicamente mais tarde
                              # mas TS só precisa saber “não-offline”

    def get_task():
        return None           # ML mete isto quando começar missão

    # a bateria é mutável → passar referência
    battery_ref = rover_identity

    # Thread do TelemetryStream
    ts_thread = threading.Thread(
        target=start_telemetry,
        args=(get_pos, get_status, get_task, battery_ref),
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
