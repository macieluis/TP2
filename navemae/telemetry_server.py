# navemae/telemetry_server.py
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import socket, threading, struct
from common.codec import decode_msg
from state.rover_state import update_telemetry, mark_disconnected

HOST = "0.0.0.0"
PORT = 6000


def recv_exact(conn, n):
    data = b''
    while len(data) < n:
        chunk = conn.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Ligação terminada prematuramente")
        data += chunk
    return data


def handle_client(conn, addr):
    print(f"[TS] Ligação de {addr}")
    rover_id = None
    try:
        while True:
            header = recv_exact(conn, 8)
            version, msg_type, action, seq_hi, seq_lo, length, checksum = struct.unpack("!BBBHBBB", header)
            payload = recv_exact(conn, length)
            packet = header + payload

            try:
                msg = decode_msg(packet)
            except Exception as e:
                print(f"[TS] Erro a decodificar de {addr}: {e}")
                continue

            action = msg["action"]
            pl = msg["payload"]
            rover_id = pl.get("rover_id", rover_id)

            if action == 1:  # connect
                print(f"[TS] {pl['rover_id']} conectado.")
            elif action == 2:  # telemetry_update
                update_telemetry(
                    pl["rover_id"],
                    pl["position"],
                    pl["battery"],
                    pl["status"],
                    pl["speed"],
                )
                print(f"[TS] {pl['rover_id']} → pos={pl['position']} | batt={pl['battery']}% | status={pl['status']} | speed={pl['speed']}")
            elif action == 4:  # heartbeat
                print(f"[TS] Heartbeat de {pl['rover_id']}")
            elif action == 5:  # disconnect
                print(f"[TS] {pl['rover_id']} desconectou ({pl.get('reason','')})")
                mark_disconnected(pl["rover_id"])
                break
            else:
                print(f"[TS] Ação desconhecida {action} de {pl.get('rover_id','?')}")

    except ConnectionError:
        print(f"[TS] Ligação perdida com {addr}")
        if rover_id:
            mark_disconnected(rover_id)
    finally:
        conn.close()
        print(f"[TS] Ligação encerrada: {addr}")


def start_telemetry_server():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen()
    print(f"[TS] Servidor ativo em {HOST}:{PORT}")

    try:
        while True:
            conn, addr = srv.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("\n[TS] Servidor TS encerrado.")
    finally:
        srv.close()
