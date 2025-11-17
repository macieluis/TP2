# rover/main.py
import threading
import rover_identity
from rover_identity import choose_rover_id

# Importa as funções de estado REAIS do missionlink
from missionlink_client import start_missionlink, get_status, get_current_task

from telemetry_client import start_telemetry


def main():
    print(">>> main iniciou")
    choose_rover_id()

    # Função para obter a posição (está ok, pois POSITION é global)
    def get_pos():
        return rover_identity.POSITION

    # Referência ao módulo para alterar a bateria
    battery_ref = rover_identity

    # Thread do TelemetryStream
    ts_thread = threading.Thread(
        target=start_telemetry,
        args=(
            get_pos,
            get_status,         # <--- Usa a função importada de missionlink_client
            get_current_task,   # <--- Usa a função importada de missionlink_client
            battery_ref
        ),
        daemon=True
    )
    ts_thread.start()

    # MissionLink corre no main thread
    try:
        start_missionlink()
    except KeyboardInterrupt:
        print(f"[{rover_identity.ROVER_ID}] MissionLink encerrado manually.")


if __name__ == "__main__":
    main()