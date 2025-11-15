# rover/telemetry_client.py
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import socket
import time
import random
from common.codec import encode_msg
import rover_identity

SERVER = ("127.0.0.1", 6000)
SEQ = 1

# Consumos (em % de bateria por segundo)
BASE_DRAIN = 0.1
TASK_DRAIN = {
    "scan_area": 0.05,
    "collect_sample": 0.10,
    "analyze_environment": 0.02,
    "idle": 0.0,
    "charging": -1.0,   # carrega 1%/s
}


def _next_seq():
    global SEQ
    s = SEQ
    SEQ = (SEQ + 1) % 65536
    return s


def _send(sock, action, payload):
    # msg_type = 2 → TelemetryStream
    pkt = encode_msg(1, 2, action, _next_seq(), payload)
    sock.sendall(pkt)


def telemetry_loop(sock, status_provider, task_provider=None):
    """
    status_provider(): devolve string ('idle', 'in_mission', 'charging', 'offline', ...)
    task_provider(): devolve nome da task atual ('scan_area', 'collect_sample', 'analyze_environment') ou None
    """

    # aqui podias no futuro ler de ficheiro para manter posição/bateria entre execuções
    position = [0.0, 0.0, 0]   # x, y, z
    battery = 100.0
    speed = 0.0

    try:
        # mensagem connect
        _send(sock, 1, {"rover_id": rover_identity.ROVER_ID, "timestamp": time.time()})
        print(f"[{rover_identity.ROVER_ID}] Ligado ao TelemetryStream.")

        while True:
            status = status_provider() or "idle"

            # descobrir task actual (se o ML quiser dizer, senão assume genérico)
            task = None
            if task_provider is not None:
                task = task_provider()
            if task is None:
                task = "scan_area" if status == "in_mission" else "idle"

            # consumo base
            drain = BASE_DRAIN

            # consumo adicional pela tarefa
            drain += TASK_DRAIN.get(task, 0.0)

            # charging sobrescreve: carrega
            if status == "charging":
                drain = TASK_DRAIN["charging"]

            # movimento simples: só se estiver em missão
            if status == "in_mission":
                position[0] += random.uniform(-0.3, 0.3)
                position[1] += random.uniform(-0.3, 0.3)
                speed = 1.0
            else:
                speed = 0.0

            # atualiza bateria
            battery -= drain
            if status == "charging":
                if battery >= 100.0:
                    battery = 100.0
                    status = "idle"
            else:
                if battery < 0:
                    battery = 0

            # se ficar muito baixa, entra em charging automaticamente
            if battery < 20.0 and status not in ("charging", "offline"):
                status = "charging"

            # se chegar a 0, morre
            if battery <= 0 and status != "offline":
                status = "offline"

            payload = {
                "rover_id": rover_identity.ROVER_ID,
                "position": [round(position[0], 2), round(position[1], 2), position[2]],
                "battery": round(battery, 1),
                "status": status,
                "speed": speed,
                "timestamp": time.time(),
            }
            _send(sock, 2, payload)

            # se offline, manda disconnect e termina
            if status == "offline":
                _send(sock, 5, {
                    "rover_id": rover_identity.ROVER_ID,
                    "reason": "battery_empty"
                })
                print(f"[{rover_identity.ROVER_ID}] Bateria esgotada, rover offline.")
                break

            # heartbeat opcional
            if random.random() < 0.2:
                _send(sock, 4, {"rover_id": rover_identity.ROVER_ID, "timestamp": time.time()})

            time.sleep(1)

    except KeyboardInterrupt:
        print(f"\n[{rover_identity.ROVER_ID}] TelemetryStream encerrado manualmente.")
        try:
            _send(sock, 5, {"rover_id": rover_identity.ROVER_ID, "reason": "manual_disconnect"})
        except Exception:
            pass
    except (BrokenPipeError, ConnectionResetError):
        print(f"[{rover_identity.ROVER_ID}] Ligação TS perdida.")
    finally:
        sock.close()


def start_telemetry(status_provider, task_provider=None):
    if rover_identity.ROVER_ID is None:
        raise RuntimeError("ROVER_ID não definido. Chama rover_identity.choose_rover_id() primeiro.")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(SERVER)
    telemetry_loop(sock, status_provider, task_provider)
