import sys, os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import socket
import threading
import struct
import time

from common.codec import decode_msg, HEADER_SIZE, encode_msg
from common.protocol_constants import TS_ERROR
from state.rover_state import (
    update_telemetry,
    mark_disconnected,
    touch_heartbeat,
)

HOST = "0.0.0.0"
PORT = 6000

_active_conns_lock = threading.Lock()

_ACTIVE_CONNECTIONS = {}

def handle_client(conn, addr):
    """Lida com a ligação de um cliente (rover)."""
    
    rover_id = None
    print(f"[TS] Ligação de {addr}")

    try:
        while True:
            # =========================================================
            # Ler o cabeçalho de 8 bytes primeiro
            # =========================================================
            header_data = conn.recv(HEADER_SIZE)
            
            if not header_data:
                break
            
            # Descobrir o tamanho do payload a partir do cabeçalho
            # O 'length' está no formato '!BBB(HH)B', por isso está nos bytes 5 e 6
            # Vamos assumir que o decode_msg trata de tudo se lhe dermos o pacote completo
            
            # Obter o 'length' do payload (bytes 5 e 6 do header, formato 'H')
            msg_len = struct.unpack("!H", header_data[5:7])[0]

            # Agora, ler o resto da mensagem (o payload)
            data = conn.recv(msg_len)
            
            if not data:
                break

            # Reconstruir o pacote completo e decodificar
            full_packet = header_data + data
            msg = decode_msg(full_packet) # Usar o codec

            if msg is None:
                
                print(f"[TS] ERRO a decodificar {addr}: Checksum inválido")
                continue

            action = msg["action"] 
            payload = msg["payload"]

            
            #  1  CONNECT
            
            if action == 1:
                
                rover_id = payload["rover_id"]
                print(f"[TS] {rover_id} a tentar conectar.")

                # LÓGICA DE CONCORRÊNCIA
                with _active_conns_lock:
                    
                    if rover_id in _ACTIVE_CONNECTIONS:
                        
                        old_conn = _ACTIVE_CONNECTIONS[rover_id]
                        print(f"[TS] A expulsar sessão antiga de {rover_id}.")
                        try:
                            # Tentar enviar TS_ERROR = 6
                            err_pkt = encode_msg(1, 2, TS_ERROR, 0, {"error": "new_session"})
                            old_conn.sendall(err_pkt)
                            
                        except Exception:
                            
                            pass # Sessão antiga pode já estar morta
                        
                        old_conn.close()
                    
                    
                    _ACTIVE_CONNECTIONS[rover_id] = conn # Guardar nova conexão
                    
                update_telemetry(
                    rover_id=rover_id,
                    position=payload.get("position", [0.0, 0.0, 0.0]), # Adiciona default
                    battery=payload.get("battery", 100.0),      # Adiciona default
                    status="idle",
                    speed=0.0,
                )
                continue

            
            #  2  TELEMETRY UPDATE
            
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

            
            #  4  HEARTBEAT
            
            if action == 4: # TS_HEARTBEAT
                rover_id = payload["rover_id"]
                touch_heartbeat(rover_id)
                print(f"[TS] Heartbeat de {rover_id}")
                continue

           
            #  5 → DISCONNECT
           
            if action == 5: # TS_DISCONNECT
                rover_id = payload["rover_id"]
                print(f"[TS] {rover_id} → Disconnect ({payload.get('reason', '')})")
                break

    except ConnectionResetError:
        
        print(f"[TS] Ligação perdida com {addr}")
        
    except ValueError as e: 
        print(f"[TS] Erro de protocolo (Value) {addr}: {e}")
        
    except Exception as e:
        print(f"[TS] Erro na ligação {addr}: {e}")

    finally:
        if rover_id:
            
            mark_disconnected(rover_id)
            
            # Libertar o "lugar"
            with _active_conns_lock:
                # Só apaga se esta for a conexão ativa (evita race conditions)
                if _ACTIVE_CONNECTIONS.get(rover_id) == conn:
                    
                    del _ACTIVE_CONNECTIONS[rover_id]
        
        conn.close()
        
        print(f"[TS] Ligação encerrada: {addr}")
        

def start_telemetry_server():
    """Inicia o servidor de telemetria."""
    
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen()

    print(f"[TS] Servidor ativo em {HOST}:{PORT}")

    while True:
        
        conn, addr = srv.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
