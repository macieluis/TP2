# navemae/missionlink_server.py
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import socket, threading, time, random
from common.codec import encode_msg, decode_msg
from common.logger_ml import save_mission_event
from state.rover_state import update_mission

SERVER_ADDR = ("0.0.0.0", 5000)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(SERVER_ADDR)

missions = {}       # (rover_id) -> payload da missão
acks = set()        # seqs confirmados
seq_counter = 0
lock = threading.Lock()
current_target = None   # se quiseres limitar missões a 1 rover; senão ignora


def gen_seq():
    global seq_counter
    with lock:
        seq_counter = (seq_counter + 1) % 65536
        return seq_counter


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")


def send_message(addr, action, payload, rover_id):
    """Envia msg confiável (com ACK) para o rover."""
    seq = gen_seq()
    packet = encode_msg(1, 1, action, seq, payload)  # msg_type=1 → ML

    for attempt in range(3):
        sock.sendto(packet, addr)
        start = time.time()
        while time.time() - start < 2:  # 2s à espera do ACK
            if seq in acks:
                acks.remove(seq)
                log(f"ACK confirmado de {addr}")
                # estado inicial da missão
                update_mission(rover_id, payload["mission_id"], 0.0, "assigned")
                save_mission_event(addr, payload["mission_id"], "assigned")
                return True
            time.sleep(0.1)
        log(f"Timeout ({attempt+1}/3) → reenvio...")

    log(f"Falha: rover {addr} não respondeu ao ACK.")
    return False


def build_mission(rover_id):
    mission_type = random.choice(["scan_area", "collect_sample", "analyze_environment"])
    base_id = random.randint(1, 999)
    mission_id = f"M-{base_id:03d}"

    base = {
        "mission_id": mission_id,
        "duration": random.choice([120, 180, 240]),
        "update_interval": random.choice([10, 15, 20]),
    }

    if mission_type == "scan_area":
        payload = {
            **base,
            "task": "scan_area",
            "area": [[10, 10], [20, 20]],
            "resolution": 1.0
        }
    elif mission_type == "collect_sample":
        payload = {
            **base,
            "task": "collect_sample",
            "points": [[2, 3], [6, 7], [9, 4]],
            "sample_type": random.choice(["rock", "dust", "ice"])
        }
    else:
        payload = {
            **base,
            "task": "analyze_environment",
            "area": [[5, 5], [15, 15]],
            "sensors": ["temperature", "radiation", "dust_level"]
        }

    return payload, mission_type, mission_id


def handle_request(addr, rover_id):
    payload, mission_type, mission_id = build_mission(rover_id)
    if send_message(addr, 1, payload, rover_id):  # 1 = new_mission
        missions[rover_id] = payload
        log(f"Missão {mission_id} ({mission_type}) atribuída a {rover_id}")
        save_mission_event(addr, mission_id, f"assigned ({mission_type})")


def listener():
    log(f"MissionLink ativo em {SERVER_ADDR}")
    while True:
        try:
            data, addr = sock.recvfrom(4096)
            msg = decode_msg(data)
        except Exception as e:
            log(f"Mensagem inválida de {addr}: {e}")
            continue

        action = msg["action"]
        pl = msg["payload"]
        rover_id = pl.get("rover_id")

        if action == 6:  # request_mission
            log(f"Pedido de missão de {rover_id} ({addr})")
            threading.Thread(target=handle_request, args=(addr, rover_id), daemon=True).start()

        elif action == 3:  # mission_update
            m_id = pl["mission_id"]
            progress = pl.get("progress", 0.0)
            status = pl.get("status", "in_progress")
            log(f"Update de {addr}: {m_id} → {progress*100:.0f}% ({status})")

            # atualizar estado global
            if rover_id:
                update_mission(rover_id, m_id, progress, status)

            save_mission_event(addr, m_id, status, progress)
            if progress >= 1.0 or status == "completed":
                log(f"Missão {m_id} concluída!")
                save_mission_event(addr, m_id, "completed")

        elif action == 2:  # ACK
            acks.add(msg["seq"])
            log(f"ACK direto de {addr}")

        else:
            log(f"Ação desconhecida {action} de {addr}")


def start_missionlink():
    try:
        listener()
    except KeyboardInterrupt:
        print("\n[SERVER] MissionLink encerrado.")
        sock.close()
