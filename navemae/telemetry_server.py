# ============================
# TelemetryStream - Nave-Mãe
# TCP (porta 6000)
# ============================
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import socket
import threading
import struct
import time

from common.codec import decode_msg
from state.rover_state import (
    update_telemetry,
    mark_disconnected,
    touch_heartbeat,
)

HOST = "0.0.0.0"
PORT = 6000


def handle_client(conn, addr):
    rover_id = None
    print(f"[TS] Ligação de {addr}")

    try:
        while True:
            header = conn.recv(4)
            if not header:
                break

            msg_len = struct.unpack("!I", header)[0]
            data = conn.recv(msg_len)
            if not data:
                break

            msg = decode_msg(header + data)

            if msg is None:
                print(f"[TS] ERRO a decodificar {addr}: Checksum inválido")
                continue

            msg_type = msg["msg_type"]
            payload = msg["payload"]

            # ──────────────────────────────────────────────────────────────
            #  1 → CONNECT
            # ──────────────────────────────────────────────────────────────
            if msg_type == 1:
                rover_id = payload["rover_id"]
                print(f"[TS] {rover_id} conectado.")

                update_telemetry(
                    rover_id=rover_id,
                    position=[0.0, 0.0, 0.0],
                    battery=100.0,
                    status="idle",
                    speed=0.0,
                )
                continue

            # ──────────────────────────────────────────────────────────────
            #  2 → TELEMETRY UPDATE
            # ──────────────────────────────────────────────────────────────
            if msg_type == 2:
                rover_id = payload["rover_id"]

                update_telemetry(
                    rover_id=rover_id,
                    position=payload["position"],
                    battery=payload["battery"],
                    status=payload["status"],
                    speed=payload["speed"],
                )

                print(f"[TS] {rover_id} → pos={payload['position']} | "
                      f"batt={payload['battery']}% | status={payload['status']} | speed={payload['speed']}")
                continue

            # ──────────────────────────────────────────────────────────────
            #  4 → HEARTBEAT
            # ──────────────────────────────────────────────────────────────
            if msg_type == 4:
                rover_id = payload["rover_id"]
                touch_heartbeat(rover_id)
                print(f"[TS] Heartbeat de {rover_id}")
                continue

            # ──────────────────────────────────────────────────────────────
            #  5 → DISCONNECT
            # ──────────────────────────────────────────────────────────────
            if msg_type == 5:
                rover_id = payload["rover_id"]
                print(f"[TS] {rover_id} → Disconnect ({payload.get('reason', '')})")
                break

    except ConnectionResetError:
        print(f"[TS] Ligação perdida com {addr}")

    except Exception as e:
        print(f"[TS] Erro na ligação {addr}: {e}")

    finally:
        if rover_id:
            mark_disconnected(rover_id)
        conn.close()
        print(f"[TS] Ligação encerrada: {addr}")


def start_telemetry_server():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen()

    print(f"[TS] Servidor ativo em {HOST}:{PORT}")

    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
