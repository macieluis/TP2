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

from common.codec import decode_msg, HEADER_SIZE
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
            # =========================================================
            # CORREÇÃO: Ler o cabeçalho de 8 bytes primeiro
            # =========================================================
            header_data = conn.recv(HEADER_SIZE)
            if not header_data:
                break
            
            # Descobrir o tamanho do payload a partir do cabeçalho
            # O 'length' está no formato '!BBB(HH)B', por isso está nos bytes 5 e 6
            # Vamos assumir que o decode_msg trata de tudo se lhe dermos o pacote completo
            
            # Obter o 'length' do payload (bytes 5 e 6 do header, formato 'H')
            msg_len = struct.unpack("!H", header_data[5:7])[0]

            # Agora, ler o resto da mensagem (o payload JSON)
            data = conn.recv(msg_len)
            if not data:
                break

            # Reconstruir o pacote completo e decodificar
            full_packet = header_data + data
            msg = decode_msg(full_packet) # Usar o codec

            # =========================================================
            # FIM DA CORREÇÃO
            # =========================================================

            if msg is None:
                print(f"[TS] ERRO a decodificar {addr}: Checksum inválido")
                continue

            # =========================================================
            # CORREÇÃO 2: Usar 'action' em vez de 'msg_type'
            # =========================================================
            action = msg["action"] # <--- USAR "action"
            payload = msg["payload"]

            # ──────────────────────────────────────────────────────────────
            #  1 → CONNECT
            # ──────────────────────────────────────────────────────────────
            if action == 1: # TS_CONNECT
                rover_id = payload["rover_id"]
                print(f"[TS] {rover_id} conectado.")
                # ... (o resto do código está OK)
                update_telemetry(
                    rover_id=rover_id,
                    position=payload.get("position", [0.0, 0.0, 0.0]), # Adiciona default
                    battery=payload.get("battery", 100.0),      # Adiciona default
                    status="idle",
                    speed=0.0,
                )
                continue

            # ──────────────────────────────────────────────────────────────
            #  2 → TELEMETRY UPDATE
            # ──────────────────────────────────────────────────────────────
            if action == 2: # TS_UPDATE
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
            if action == 4: # TS_HEARTBEAT
                rover_id = payload["rover_id"]
                touch_heartbeat(rover_id)
                print(f"[TS] Heartbeat de {rover_id}")
                continue

            # ──────────────────────────────────────────────────────────────
            #  5 → DISCONNECT
            # ──────────────────────────────────────────────────────────────
            if action == 5: # TS_DISCONNECT
                rover_id = payload["rover_id"]
                print(f"[TS] {rover_id} → Disconnect ({payload.get('reason', '')})")
                break

    except ConnectionResetError:
        print(f"[TS] Ligação perdida com {addr}")
    except ValueError as e: # <--- Capturar erros de decode
        print(f"[TS] Erro de protocolo (Value) {addr}: {e}")
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
