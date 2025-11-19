# navemae/missionlink_server.py
import sys, os
# Garante que encontra os módulos common/state
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import socket
import threading
import time
from common.codec import decode_msg, encode_msg
from common.protocol_constants import ML_REQUEST, ML_ACK, ML_UPDATE, ML_COMPLETE, ML_NEW_MISSION
from state.rover_state import update_mission, get_last_known_state
from common.state import get_next_mission_id

ML_ADDR = ("0.0.0.0", 5000)

# === LISTA DE ESPERA DE MISSÕES (Vindas da Web) ===
# Estrutura: { "R-001": { "task": "scan_area", ... } }
PENDING_MISSIONS = {} 
_pending_lock = threading.Lock()

def add_pending_mission(rover_id, mission_data):
    """Função chamada pela API para agendar uma missão."""
    with _pending_lock:
        PENDING_MISSIONS[rover_id] = mission_data
        print(f"[ML] Missão agendada para {rover_id}: {mission_data['task']}")

def send_message(addr, msg_type, payload, rover_id):
    try:
        pkt = encode_msg(1, 1, msg_type, 0, payload)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(pkt, addr)
        sock.close()
        return True
    except Exception as e:
        print(f"[ML] ERRO ao enviar para {addr}: {e}")
        return False

def handle_request(sock, data, addr):
    try:
        msg = decode_msg(data)
        payload = msg["payload"]
        action = msg["action"]
    except Exception as e:
        print(f"[ML] ERRO decode {addr}: {e}")
        return

    rover_id = payload.get("rover_id", "UNKNOWN")

    # =====================================================
    # 6 — PEDIDO DE MISSÃO (O Rover pede trabalho)
    # =====================================================
    if action == ML_REQUEST:
        print(f"[ML] Pedido de missão de {rover_id} ({addr})")

        mission_to_send = None
        
        # 1. Verificar se TU criaste uma missão na Web
        with _pending_lock:
            if rover_id in PENDING_MISSIONS:
                # Retirar a missão da fila
                base_data = PENDING_MISSIONS.pop(rover_id)
                
                # Gerar ID final e empacotar
                mid = get_next_mission_id()
                mission_to_send = {
                    "mission_id": mid,
                    "update_interval": 5, # Intervalo rápido para testes
                    **base_data
                }

        # 2. Se houver missão, envia. Se não, IGNORA (o rover tenta depois).
        if mission_to_send:
            send_message(addr, ML_NEW_MISSION, mission_to_send, rover_id)
            print(f"[ML] >>> Enviada missão {mission_to_send['mission_id']} ({mission_to_send['task']}) para {rover_id}")

            # Atualizar estado para "Atribuída"
            pos, _ = get_last_known_state(rover_id)
            update_mission(rover_id, mission_to_send['mission_id'], 0.0, "assigned", pos)
        else:
            # Opcional: print para debug, podes comentar se fizer muito spam
            print(f"[ML] Sem missões agendadas para {rover_id}. A ignorar.")
        
        return

    # =====================================================
    # 2 — ACK (Rover recebeu a missão)
    # =====================================================
    elif action == ML_ACK:
        mid = payload.get("mission_id")
        print(f"[ML] ACK confirmado de {rover_id} para {mid}")
        pos, _ = get_last_known_state(rover_id)
        update_mission(rover_id, mid, 0.0, "in_progress", pos)
        
        # Ack do Ack para fechar o handshake (opcional mas recomendado)
        send_message(addr, ML_ACK, {"ok": True}, rover_id)
        return

    # =====================================================
    # 3 — UPDATE (Progresso)
    # =====================================================
    elif action == ML_UPDATE:
        mid = payload["mission_id"]
        prog = payload["progress"]
        mstatus = payload["status"]
        pos = payload.get("position")
        
        if pos:
            update_mission(rover_id, mid, prog, mstatus, pos)
            print(f"[ML] Update {rover_id}: {mid} {prog:.0f}%")
        return

    # =====================================================
    # 7 — COMPLETE
    # =====================================================
    elif action == ML_COMPLETE:
        mid = payload["mission_id"]
        pos = payload.get("position")
        print(f"[ML] MISSÃO CONCLUÍDA {mid} ({rover_id})")
        if pos:
            update_mission(rover_id, mid, 100.0, "completed", pos)
        return

def start_missionlink():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(ML_ADDR)
    print(f"[ML] MissionLink ativo em {ML_ADDR}")
    
    while True:
        data, addr = sock.recvfrom(4096)
        threading.Thread(target=handle_request, args=(sock, data, addr), daemon=True).start()

if __name__ == "__main__":
    start_missionlink()