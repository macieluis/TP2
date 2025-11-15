# navemae/telemetry_server.py
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import socket
import threading
import struct
from common.codec import decode_msg
from state.rover_state import update_telemetry, mark_disconnected

HOST = "0.0.0.0"
PORT = 6000


def _handle_client(conn, addr):
    print(f"[TS] Ligação de {addr}")
    buf = b""
    rover_id = None

    try:
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk

            # framing: enquanto houver pelo menos cabeçalho
            while len(buf) >= 8:
                header = buf[:8]
                # mesmo formato do common.codec: "!BBBHBBB"
                version, msg_type, action, seq_hi, seq_lo, length, checksum = struct.unpack("!BBBHBBB", header)

                total_len = 8 + length
                if len(buf) < total_len:
                    # ainda não chegou o payload todo
                    break

                packet = buf[:total_len]
                buf = buf[total_len:]

                try:
                    msg = decode_msg(packet)
                except Exception as e:
                    print(f"[TS] ERRO ao decodificar de {addr}: {e}")
                    continue

                pl = msg["payload"]
                act = msg["action"]

                if act == 1:  # connect
                    rover_id = pl.get("rover_id", "?")
                    print(f"[TS] {rover_id} conectado.")

                elif act == 2:  # telemetry_update
                    rover_id = pl.get("rover_id", rover_id)
                    pos = pl.get("position")
                    batt = pl.get("battery")
                    status = pl.get("status")
                    speed = pl.get("speed")
                    ts = pl.get("timestamp")

                    # atualiza estado global
                    if rover_id is not None:
                        update_telemetry(rover_id, pos, batt, status, speed)

                    print(f"[TS] {rover_id} → pos={pos} | batt={batt}% | status={status} | speed={speed}")

                elif act == 4:  # heartbeat
                    rid = pl.get("rover_id", rover_id)
                    print(f"[TS] Heartbeat de {rid}")

                elif act == 5:  # disconnect
                    rid = pl.get("rover_id", rover_id)
                    print(f"[TS] {rid} desconectou ({pl.get('reason', '')})")
                    if rid:
                        mark_disconnected(rid)
                    return

                else:
                    rid = pl.get("rover_id", rover_id)
                    print(f"[TS] Ação desconhecida {act} de {rid}")

    except Exception as e:
        print(f"[TS] Erro na ligação {addr}: {e}")
    finally:
        conn.close()
        if rover_id:
            mark_disconnected(rover_id)
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
            threading.Thread(target=_handle_client, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("\n[TS] Servidor TS encerrado manualmente.")
    finally:
        srv.close()


if __name__ == "__main__":
    start_telemetry_server()
