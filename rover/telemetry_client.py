import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import socket, time, random
from common.codec import encode_msg

SERVER = ("127.0.0.1", 6000)
SEQ = 1

VALID_ROVERS = ["R-001", "R-002", "R-003", "R-004"]


def choose_rover_id():
    print("Escolhe o Rover (R-001, R-002, R-003, R-004):")
    rid = input("> ").strip().upper()
    if rid not in VALID_ROVERS:
        print("Rover inválido.")
        sys.exit(1)
    return rid


def send(sock, action, payload):
    """Envia mensagem codificada e ignora erros se a socket já morreu."""
    global SEQ
    try:
        pkt = encode_msg(1, 2, action, SEQ, payload)
        sock.sendall(pkt)
        SEQ = (SEQ + 1) % 65536
    except (BrokenPipeError, ConnectionResetError):
        pass


def telemetry_loop(sock, ROVER_ID):
    position = [random.uniform(0, 10), random.uniform(0, 10), 0]
    speed = 1.0
    battery = 100.0

    try:
        while battery > 0:
            # Movimento
            position[0] += random.uniform(-0.5, 0.5)
            position[1] += random.uniform(-0.5, 0.5)
            battery -= random.uniform(0.2, 0.6)

            payload = {
                "rover_id": ROVER_ID,
                "position": [round(position[0], 2), round(position[1], 2), 0],
                "battery": round(battery, 1),
                "status": "in_mission",
                "speed": speed,
                "timestamp": time.time()
            }

            send(sock, 2, payload)
            time.sleep(5)

            # heartbeat ocasional
            if random.random() < 0.2:
                send(sock, 4, {"rover_id": ROVER_ID, "timestamp": time.time()})

        # bateria acabou
        send(sock, 5, {"rover_id": ROVER_ID, "reason": "battery_low"})

    except KeyboardInterrupt:
        print(f"\n[{ROVER_ID}] Encerrado manualmente.")
        send(sock, 5, {"rover_id": ROVER_ID, "reason": "manual_disconnect"})

    except (BrokenPipeError, ConnectionResetError):
        print(f"[{ROVER_ID}] Ligação perdida.")

    finally:
        try:
            sock.close()
        except:
            pass


def main():
    ROVER_ID = choose_rover_id()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(SERVER)

    print(f"[{ROVER_ID}] Ligado ao TelemetryStream.")

    send(sock, 1, {"rover_id": ROVER_ID, "timestamp": time.time()})
    telemetry_loop(sock, ROVER_ID)


if __name__ == "__main__":
    main()
