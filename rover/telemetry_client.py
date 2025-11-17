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


def send(sock, action, payload):
    global SEQ
    pkt = encode_msg(
        version=1,
        msg_type=2,    # TelemetryStream
        action=action,
        seq=SEQ,
        payload=payload
    )
    sock.sendall(pkt)
    SEQ = (SEQ + 1) % 65536


# ===============================
#  BATERIA: modelo realista
# ===============================

CONSUMPTION = {
    "idle": 0.10,
    "in_mission": 0.10,
    "scan_area": 0.15,
    "collect_sample": 0.20,
    "analyze_environment": 0.12,
}

def compute_battery(batt, status, task, dt):
    if batt <= 0:
        return 0.0

    if batt < 20:
        return min(100.0, batt + (1.0 * dt))  # carrega 1%/s

    base = CONSUMPTION.get(status, 0.10)
    extra = CONSUMPTION.get(task, 0.0)

    drain = (base + extra) * dt
    batt = max(0.0, batt - drain)
    return batt


# ==========================================================
#   TELEMETRY LOOP
#   posição = exatamente a mesma que o MissionLink usa
# ==========================================================

def telemetry_loop(sock, get_current_position, get_current_status, get_current_task, battery_ref):
    """
    Rover não calcula posição aqui.  
    Apenas envia a posição atual *decidida pelo MissionLink* (via missionlink_client).
    """
    last = time.time()

    try:
        while True:
            now = time.time()
            dt = now - last
            last = now

            # Posição, estado e tarefa atual vindos do ML
            pos = get_current_position()
            status = get_current_status()
            task = get_current_task()

            # Atualiza bateria
            battery_ref["value"] = compute_battery(battery_ref["value"], status, task, dt)
            batt = round(battery_ref["value"], 1)

            payload = {
                "rover_id": rover_identity.ROVER_ID,
                "position": pos,
                "battery": batt,
                "speed": 1.0 if status == "in_mission" else 0.0,
                "status": status,
                "timestamp": now,
            }
            send(sock, 2, payload)   # action=2 → telemetry update

            # Heartbeat ocasional
            if random.random() < 0.15:
                send(sock, 4, {"rover_id": rover_identity.ROVER_ID, "timestamp": now})

            time.sleep(2)

    except KeyboardInterrupt:
        print(f"[{rover_identity.ROVER_ID}] TS encerrado manualmente.")
        try:
            send(sock, 5, {"rover_id": rover_identity.ROVER_ID, "reason": "manual_disconnect"})
        except:
            pass
    except (BrokenPipeError, ConnectionResetError):
        print(f"[{rover_identity.ROVER_ID}] Ligação TS perdida.")
    finally:
        sock.close()


# ==========================================================
#   START TELEMETRY CLIENT
# ==========================================================

def start_telemetry(get_pos, get_status, get_task, battery_ref):
    if rover_identity.ROVER_ID is None:
        raise RuntimeError("ROVER_ID não definido.")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(SERVER)

    print(f"[{rover_identity.ROVER_ID}] Ligado ao TelemetryStream.")

    send(sock, 1, {"rover_id": rover_identity.ROVER_ID, "timestamp": time.time()})  # CONNECT

    telemetry_loop(sock, get_pos, get_status, get_task, battery_ref)
