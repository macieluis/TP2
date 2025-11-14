# rover/telemetry_client.py
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import socket, time, random
from common.codec import encode_msg
import rover_identity

SERVER = ("127.0.0.1", 6000)
SEQ = 1


def send(sock, action, payload):
    global SEQ
    pkt = encode_msg(1, 2, action, SEQ, payload)  # msg_type=2 → TelemetryStream
    sock.sendall(pkt)
    SEQ = (SEQ + 1) % 65536


def telemetry_loop(sock, status_provider):
    position = [random.uniform(0, 1), random.uniform(0, 1), 0]
    battery = 100.0
    speed = 1.0

    try:
        while True:
            status = status_provider()

            # Se offline/idle parado, movimento mínimo
            if status == "in_mission":
                position[0] += random.uniform(-0.3, 0.3)
                position[1] += random.uniform(-0.3, 0.3)
                speed = 1.0
                battery -= random.uniform(0.2, 0.6)
            else:
                speed = 0.0
                battery -= random.uniform(0.05, 0.2)

            if battery <= 0:
                battery = 0.0
                send(sock, 5, {"rover_id": rover_identity.ROVER_ID, "reason": "battery_low"})
                break

            payload = {
                "rover_id": rover_identity.ROVER_ID,
                "position": [round(position[0], 2), round(position[1], 2), 0],
                "battery": round(battery, 1),
                "status": status,
                "speed": speed,
                "timestamp": time.time(),
            }
            send(sock, 2, payload)
            time.sleep(5)

            # heartbeat ocasional
            if random.random() < 0.2:
                send(sock, 4, {"rover_id": rover_identity.ROVER_ID, "timestamp": time.time()})

    except KeyboardInterrupt:
        print(f"\n[{rover_identity.ROVER_ID}] TelemetryStream encerrado manualmente.")
        try:
            send(sock, 5, {"rover_id": rover_identity.ROVER_ID, "reason": "manual_disconnect"})
        except Exception:
            pass
    except (BrokenPipeError, ConnectionResetError):
        print(f"[{rover_identity.ROVER_ID}] Ligação TS perdida.")
    finally:
        sock.close()


def start_telemetry(status_provider):
    if rover_identity.ROVER_ID is None:
        raise RuntimeError("ROVER_ID não definido. Chama rover_identity.choose_rover_id() primeiro.")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(SERVER)
    print(f"[{rover_identity.ROVER_ID}] Ligado ao TelemetryStream.")

    send(sock, 1, {"rover_id": rover_identity.ROVER_ID, "timestamp": time.time()})  # connect
    telemetry_loop(sock, status_provider)
