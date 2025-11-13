import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import socket, time, random
from common.codec import encode_msg

SERVER = ("127.0.0.1", 6000)
ROVER_ID = f"R-{random.randint(1,4)}"
SEQ = 1


def send(sock, action, payload):
    global SEQ
    pkt = encode_msg(1, 2, action, SEQ, payload)
    sock.sendall(pkt)
    SEQ = (SEQ + 1) % 65536


def telemetry_loop(sock):
    position = [random.uniform(0, 10), random.uniform(0, 10), 0]
    speed = 1.0
    battery = 100.0

    try:
        while battery > 0:
            # Simula movimento
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

            send(sock, 2, payload)  # telemetry_update
            time.sleep(5)

            # heartbeat ocasional
            if random.random() < 0.2:
                send(sock, 4, {"rover_id": ROVER_ID, "timestamp": time.time()})

        send(sock, 5, {"rover_id": ROVER_ID, "reason": "battery_low"})

    except KeyboardInterrupt:
        print(f"\n[{ROVER_ID}] Encerrado manualmente.")
        send(sock, 5, {"rover_id": ROVER_ID, "reason": "manual_disconnect"})
    except (BrokenPipeError, ConnectionResetError):
        print(f"[{ROVER_ID}] Ligação perdida.")
    finally:
        sock.close()


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(SERVER)
    print(f"[{ROVER_ID}] Ligado ao TelemetryStream.")

    send(sock, 1, {"rover_id": ROVER_ID, "timestamp": time.time()})  # connect
    telemetry_loop(sock)


if __name__ == "__main__":
    main()
