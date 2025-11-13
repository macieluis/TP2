import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import socket, threading, struct
from common.codec import decode_msg
from common.logger_ts import save_telemetry
import time

HOST = "0.0.0.0"
PORT = 6000

connected_rovers = {}      # rover_id -> (conn, addr)
lock = threading.Lock()


def recv_exact(conn, n):
    data = b''
    while len(data) < n:
        chunk = conn.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Ligação terminou prematuramente")
        data += chunk
    return data


def handle_client(conn, addr):
    rover_id = None

    print(f"[TS] Ligação de {addr}")

    try:
        while True:
            # Lê cabeçalho fixo (8 bytes)
            header = recv_exact(conn, 8)
            version, msg_type, action, seq_hi, seq_lo, length, checksum = struct.unpack("!BBBHBBB", header)

            payload = recv_exact(conn, length)
            packet = header + payload

            try:
                msg = decode_msg(packet)
            except Exception as e:
                print(f"[TS] Erro a descodificar de {addr}: {e}")
                continue

            pl = msg["payload"]
            action = msg["action"]

            # --- AÇÕES ---
            if action == 1:     # connect
                rover_id = pl["rover_id"]

                with lock:
                    # Já existe outro com o mesmo ID?
                    if rover_id in connected_rovers:
                        print(f"[TS] ERRO: {rover_id} já está ligado! Fechando ligação.")
                        conn.close()
                        return

                    connected_rovers[rover_id] = (conn, addr)

                print(f"[TS] {rover_id} conectado.")

            elif action == 2:   # telemetry_update
                if rover_id:
                    print(f"[TS] {rover_id} → pos={pl['position']} | batt={pl['battery']}% | status={pl['status']} | speed={pl['speed']}")
                    save_telemetry(
                        rover_id,
                        pl["position"],
                        pl["battery"],
                        pl["status"],
                        pl["speed"]
                    )

            elif action == 4:   # heartbeat
                if rover_id:
                    print(f"[TS] Heartbeat de {rover_id}")

            elif action == 5:   # disconnect
                print(f"[TS] {rover_id} desconectou ({pl.get('reason','')})")
                break

            else:
                print(f"[TS] Ação desconhecida {action} de {rover_id}")

    except ConnectionError:
        print(f"[TS] Ligação perdida com {addr}")
    except Exception as e:
        print(f"[TS] Erro na ligação com {addr}: {e}")
    finally:
        if rover_id:
            with lock:
                connected_rovers.pop(rover_id, None)

        conn.close()
        print(f"[TS] Ligação encerrada: {addr}")


def start_server():
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
        print("\n[TS] Encerrado manualmente.")
    finally:
        srv.close()
        print("[TS] Servidor fechado.")


if __name__ == "__main__":
    start_server()
