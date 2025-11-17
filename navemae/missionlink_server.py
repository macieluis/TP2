import socket
import threading
import time
from common.codec import decode_msg, encode_msg

from state.rover_state import (
    update_mission,
    get_last_known_state,
    is_rover_alive,
    mark_disconnected
)

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
        header, payload = decode_msg(data)
    except Exception:
        print(f"[ML] [{time.strftime('%H:%M:%S')}] ERRO a decodificar de {addr}")
        return

    msg_type = header["msg_type"]
    rover_id = payload.get("rover_id", "UNKNOWN")

    # =====================================================
    # 1 — PEDIDO DE MISSÃO
    # =====================================================
    if msg_type == 1:  # mission_request
        mission = payload.get("mission")

        print(f"[ML] [{time.strftime('%H:%M:%S')}] Pedido de missão de {rover_id} ({addr})")

        # Mandar ACK direto
        ack_payload = {"ack": mission["mission_id"], "rover_id": rover_id}
        send_message(addr, 2, ack_payload, rover_id)
        print(f"[ML] [{time.strftime('%H:%M:%S')}] ACK direto de {addr} para {mission['mission_id']}")

        # Guardar estado inicial da missão
        init_pos, _ = get_last_known_state(rover_id)
        update_mission(
            rover_id,
            mission["mission_id"],
            progress=0.0,
            mission_status="in_progress",
            position=init_pos
        )

        print(f"[ML] [{time.strftime('%H:%M:%S')}] Missão {mission['mission_id']} ({mission['task']}) atribuída a {rover_id}")
        return

    # =====================================================
    # 2 — ACK DO ROVER
    #    (Rover recebeu a missão)
    # =====================================================
    elif msg_type == 2:  # rover_ack
        mid = payload.get("mission_id")
        print(f"[ML] [{time.strftime('%H:%M:%S')}] ACK confirmado de {addr} para {mid}")

        # Opcional: responder com ack_of_ack
        send_message(addr, 2, {"ok": True}, rover_id)
        return

    # =====================================================
    # 3 — UPDATE DE MISSÃO
    # =====================================================
    elif msg_type == 3:
        mission_id = payload["mission_id"]
        progress = payload["progress"]
        mstatus = payload["status"]
        pos = payload["position"]

        print(f"[ML] [{time.strftime('%H:%M:%S')}] Update de {addr}: {mission_id} → {progress}% ({mstatus}) pos={pos}")

        update_mission(
            rover_id,
            mission_id,
            progress,
            mstatus,
            pos
        )

        # ACK do update
        send_message(addr, 3, {"received": mission_id}, rover_id)
        return

    else:
        print(f"[ML] [{time.strftime('%H:%M:%S')}] Mensagem UDP desconhecida de {addr}: tipo={msg_type}")


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
