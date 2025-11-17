# rover/missionlink_client.py
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import socket
import threading
import time
import json
import random
import rover_identity
from common.codec import encode_msg, decode_msg
from navemae.state.rover_state import (_load_state, _save_state)

ML_SERVER = ("127.0.0.1", 5000)
SEQ = 1
_current_mission = None
_status_lock = threading.Lock()
_rover_status = "idle"


def get_status():
    with _status_lock:
        return _rover_status


def set_status(s):
    with _status_lock:
        global _rover_status
        _rover_status = s


def send(sock, msg_type, payload):
    global SEQ
    pkt = encode_msg(1, 1, msg_type, SEQ, payload)  # ML → msg_type=1
    sock.sendto(pkt, ML_SERVER)
    SEQ = (SEQ + 1) % 65536


def handle_server_messages(sock):
    global _current_mission

    while True:
        try:
            data, addr = sock.recvfrom(4096)
            ok, header, payload = decode_msg(data)

            if not ok:
                print(f"[ML][{rover_identity.ROVER_ID}] ERRO checksum.")
                continue

            msg_type = header["action"]

            # 1 → new mission
            if msg_type == 1:
                _current_mission = payload
                print(f"[ML][{rover_identity.ROVER_ID}] Nova missão de {addr}: "
                      f"{payload['mission_id']}")
                for k, v in payload.items():
                    print(f"    - {k}: {v}")

                # Enviar ACK
                send(sock, 2, {
                    "rover_id": rover_identity.ROVER_ID,
                    "mission_id": payload["mission_id"]
                })
                print(f"[ML][{rover_identity.ROVER_ID}] ACK enviado para {payload['mission_id']}.")

                set_status("in_mission")

            # 3 → ACK final da nave-mãe
            elif msg_type == 3:
                print(f"[ML][{rover_identity.ROVER_ID}] ACK da nave-mãe confirmado.")

        except Exception as e:
            print(f"[ML][{rover_identity.ROVER_ID}] Erro ML: {e}")
            break


# ---------------------------------------------------------------------------------------
#   EXECUÇÃO DA MISSÃO
# ---------------------------------------------------------------------------------------

def run_mission(sock):
    """Executa a missão recebida, enviando updates no intervalo correto."""
    global _current_mission

    mission = _current_mission
    if mission is None:
        return

    m_id = mission["mission_id"]
    interval = mission["update_interval"]
    task = mission["task"]

    state = _load_state(rover_identity.ROVER_ID)
    pos = state["position"]

    print(f"[{rover_identity.ROVER_ID}] >>> Início da missão {m_id} ({task.upper()})")

    # Missão simples: mover + gerar dados
    progress = 0
    total_steps = mission["duration"] // interval

    for step in range(1, total_steps + 1):
        # Simular movimento
        pos[0] += random.uniform(-1.0, 1.0)
        pos[1] += random.uniform(-1.0, 1.0)

        # Simular leitura extra
        extra = {}
        if task == "analyze_environment":
            extra = {
                "temperature": round(random.uniform(-80, 0), 1),
                "radiation": round(random.uniform(1, 5), 2),
                "dust_level": round(random.uniform(0, 20), 1)
            }

        progress = round((step / total_steps) * 100, 1)

        # Enviar UPDATE
        send(sock, 4, {
            "rover_id": rover_identity.ROVER_ID,
            "mission_id": m_id,
            "progress": progress,
            "status": "in_progress",
            "position": pos.copy(),
            "extra": extra
        })

        print(f"[{rover_identity.ROVER_ID}] {m_id}: {progress}% pos({pos[0]:.1f},{pos[1]:.1f}) "
              f"{extra if task == 'analyze_environment' else ''}")

        time.sleep(interval)

    # Missão concluída
    send(sock, 5, {
        "rover_id": rover_identity.ROVER_ID,
        "mission_id": m_id,
        "progress": 100.0,
        "status": "completed",
        "position": pos.copy()
    })

    print(f"[{rover_identity.ROVER_ID}] Missão {m_id} concluída.")

    # Guardar posição final
    state["position"] = pos
    _save_state(rover_identity.ROVER_ID, state)

    set_status("idle")
    _current_mission = None


# ---------------------------------------------------------------------------------------
#   START
# ---------------------------------------------------------------------------------------

def start_missionlink():
    if rover_identity.ROVER_ID is None:
        raise RuntimeError("ROVER_ID não definido.")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1)

    # Enviar pedido de missão
    send(sock, 0, {"rover_id": rover_identity.ROVER_ID})
    print(f"[ML][{rover_identity.ROVER_ID}] Pedido de missão enviado.")

    threading.Thread(target=handle_server_messages, args=(sock,), daemon=True).start()

    # LOOP principal
    while True:
        try:
            if _current_mission is not None:
                run_mission(sock)
            time.sleep(0.2)

        except KeyboardInterrupt:
            print(f"\n[{rover_identity.ROVER_ID}] MissionLink encerrado manualmente.")
            break

        except Exception as e:
            print(f"[ML][{rover_identity.ROVER_ID}] Erro: {e}")
            break
