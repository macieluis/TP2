import socket
import threading
import time

from common.codec import decode_msg, encode_msg
from common.protocol_constants import (
    ML_REQUEST, ML_ACK, ML_UPDATE, ML_COMPLETE, ML_NEW_MISSION
)

from state.rover_state import (
    update_mission,
    get_last_known_state,
    is_rover_alive,
    mark_disconnected
)
from common.state import get_next_mission_id

ML_ADDR = ("0.0.0.0", 5000)


# =========================================================
#  FUNÇÃO PARA ENVIAR UMA MENSAGEM UDP PARA O ROVER
# =========================================================
def send_message(addr, msg_type, payload, rover_id):
    """
    msg_type:
      1 = new_mission
      2 = ack_of_ack
      3 = mission_update_confirmation
    """
    try:
        pkt = encode_msg(1, 1, msg_type, 0, payload)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(pkt, addr)
        sock.close()
        return True
    except Exception as e:
        print(f"[ML] ERRO ao enviar para {addr}: {e}")
        return False


# =========================================================
#  THREAD PARA LIDAR COM PEDIDO DE UM ROVER
# =========================================================

def handle_request(sock, data, addr):
    try:
        # =========================================================
        # CORREÇÃO: Aceder ao 'msg' diretamente
        # O decode_msg retorna um dicionário plano, ex:
        # { "version": 1, "action": 6, "payload": {...} }
        # =========================================================
        msg = decode_msg(data)
        payload = msg["payload"]
        action = msg["action"]
        # =========================================================

    except Exception as e:
        print(f"[ML] [{time.strftime('%H:%M:%S')}] ERRO a decodificar de {addr}: {e}")
        return

    rover_id = payload.get("rover_id", "UNKNOWN")

    # =====================================================
    # 6 — PEDIDO DE MISSÃO (ML_REQUEST)
    # =====================================================
    if action == ML_REQUEST:  # 6
        print(f"[ML] [{time.strftime('%H:%M:%S')}] Pedido de missão de {rover_id} ({addr})")

        # Criar uma missão de exemplo (podes tornar isto mais complexo)
        mission_id = get_next_mission_id()
        new_mission = {
            "mission_id": mission_id,
            "task": "scan_area", # Tarefa da Fase 1
            "area": [[0,0], [10,10]],
            "resolution": 1.0,
            "duration": 120,        # 2 minutos
            "update_interval": 15   # update a cada 15s
        }

        # Enviar a missão para o rover (action = 1, ML_NEW_MISSION)
        send_message(addr, ML_NEW_MISSION, new_mission, rover_id)
        print(f"[ML] [{time.strftime('%H:%M:%S')}] Missão {mission_id} (scan_area) atribuída a {rover_id}")

        # Guardar estado inicial da missão
        init_pos, _ = get_last_known_state(rover_id)
        update_mission(
            rover_id,
            mission_id,
            progress=0.0,
            mission_status="assigned",
            position=init_pos
        )
        return

    # =====================================================
    # 2 — ACK DO ROVER (ML_ACK)
    #    (Rover recebeu a missão)
    # =====================================================
    elif action == ML_ACK:  # 2
        mid = payload.get("mission_id")
        print(f"[ML] [{time.strftime('%H:%M:%S')}] ACK confirmado de {addr} para {mid}")

        # Atualiza o estado
        init_pos, _ = get_last_known_state(rover_id)
        update_mission(rover_id, mid, 0.0, "ack_received", init_pos)

        # Opcional: responder com ack_of_ack (o teu cliente espera isto)
        send_message(addr, ML_ACK, {"ok": True, "mission_id": mid}, rover_id)
        return

    # =====================================================
    # 3 — UPDATE DE MISSÃO (ML_UPDATE)
    # =====================================================
    elif action == ML_UPDATE: # 3
        mission_id = payload["mission_id"]
        progress = payload["progress"]
        mstatus = payload["status"]
        pos = payload.get("position") # .get() é mais seguro

        if pos:
            print(f"[ML] [{time.strftime('%H:%M:%S')}] Update de {addr}: {mission_id} → {progress:.1f}% ({mstatus}) pos={pos}")
            update_mission(
                rover_id,
                mission_id,
                progress,
                mstatus,
                pos
            )
        else:
             print(f"[ML] [{time.strftime('%H:%M:%S')}] Update (sem pos) de {addr}: {mission_id} → {progress:.1f}% ({mstatus})")

        # NOTA: O teu cliente não está a lidar com este ACK, mas não faz mal
        # send_message(addr, 3, {"received": mission_id}, rover_id)
        return

    # =====================================================
    # 7 — MISSÃO COMPLETA (ML_COMPLETE)
    # =====================================================
    elif action == ML_COMPLETE: # 7
        mission_id = payload["mission_id"]
        pos = payload.get("position")
        print(f"[ML] [{time.strftime('%H:%M:%S')}] Missão COMPLETA {mission_id} de {addr}")

        if pos:
            update_mission(rover_id, mission_id, 100.0, "completed", pos)

        # Opcional: ACK de conclusão
        # send_message(addr, 3, {"received": mission_id, "status": "completed"}, rover_id)
        return

    else:
        print(f"[ML] [{time.strftime('%H:%M:%S')}] Mensagem UDP desconhecida de {addr}: action={action}")
        
# =========================================================
#  SERVIDOR MISSIONLINK
# =========================================================
def start_missionlink():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(ML_ADDR)

    print(f"[ML] [{time.strftime('%H:%M:%S')}] MissionLink ativo em {ML_ADDR}")

    try:
        while True:
            data, addr = sock.recvfrom(4096)
            threading.Thread(target=handle_request, args=(sock, data, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("\n[ML] Encerrado manualmente.")
    finally:
        sock.close()
