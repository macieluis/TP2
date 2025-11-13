import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import socket, threading, time, struct
from common.codec import decode_msg

HOST = "0.0.0.0"
PORT = 6000
running = True


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
    try:
        while running:
            header = recv_exact(conn, 8)
            version, msg_type, action, seq_hi, seq_lo, length, checksum = struct.unpack("!BBBHBBB", header)
            payload = recv_exact(conn, length)
            packet = header + payload

            try:
                msg = decode_msg(packet)
            except Exception as e:
                print(f"[TS] Erro a decodificar de {addr}: {e}")
                continue

            pl = msg["payload"]
            action = msg["action"]

            if action == 1:
                print(f"[TS] {pl['rover_id']} conectado.")
            elif action == 2:
                print(f"[TS] {pl['rover_id']} → pos={pl['position']} | batt={pl['battery']}% | status={pl['status']} | speed={pl['speed']}")
            elif action == 4:
                print(f"[TS] Heartbeat de {pl['rover_id']}")
            elif action == 5:
                print(f"[TS] {pl['rover_id']} desconectou ({pl.get('reason','')})")
                break
            else:
                print(f"[TS] Ação desconhecida {action} de {pl.get('rover_id','?')}")

    except (ConnectionError, OSError):
        print(f"[TS] Ligação perdida com {addr}")
    except Exception as e:
        print(f"[TS] Erro na ligação {addr}: {e}")
    finally:
        conn.close()
        print(f"[TS] Ligação encerrada: {addr}")


def main():
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
        print("[TS] Servidor terminado.")
        

if __name__ == "__main__":
    main()
