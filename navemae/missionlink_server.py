import sys, os, socket, threading, time, random, signal
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from common.codec import encode_msg, decode_msg
from common.logger_ml import save_mission_event, print_mission_summary
from common.state import get_next_mission_id


SERVER_ADDR = ("0.0.0.0", 5000)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(SERVER_ADDR)

missions = {}
acks = set()
seq_counter = 1
mission_counter = 0
target_rover_id = None  # escolhido no arranque
rovers_last_addr = {}   # mapa rover_id → último addr conhecido
lock = threading.Lock()

def gen_seq():
    global seq_counter
    with lock:
        seq_counter += 1
        return seq_counter

def gen_mission_id():
    global mission_counter
    with lock:
        mission_counter += 1
        return f"M-{mission_counter:03d}"

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def send_message(addr, action, payload):
    seq = gen_seq()
    packet = encode_msg(1, 1, action, seq, payload)

    for attempt in range(3):
        sock.sendto(packet, addr)
        start = time.time()
        while time.time() - start < 2:
            if seq in acks:
                acks.remove(seq)
                log(f"ACK confirmado de {addr}")
                return True
            time.sleep(0.1)
        log(f"Timeout ({attempt+1}/3) → reenvio...")

    log(f"Falha: rover {addr} não respondeu ao ACK.")
    return False

def handle_request(addr, rover_id):
    global target_rover_id

    # guardar IP do rover (para futuras respostas)
    rovers_last_addr[rover_id] = addr

    # Se o utilizador escolheu um rover específico e este não é o mesmo, ignora
    if target_rover_id and rover_id != target_rover_id:
        log(f"Pedido ignorado de {rover_id} ({addr}) — alvo atual é {target_rover_id}")
        return

    mission_type = random.choice(["scan_area", "collect_sample", "analyze_environment"])
    mission_id = get_next_mission_id()

    base = {
        "mission_id": mission_id,
        "duration": random.choice([120, 180, 240]),
        "update_interval": random.choice([10, 15, 20]),
    }

    if mission_type == "scan_area":
        payload = {**base, "task": mission_type, "area": [[10, 10], [20, 20]], "resolution": 1.0}
    elif mission_type == "collect_sample":
        payload = {**base, "task": mission_type, "points": [[2, 3], [6, 7], [9, 4]], "sample_type": random.choice(["rock", "dust", "ice"])}
    else:
        payload = {**base, "task": mission_type, "area": [[5, 5], [15, 15]], "sensors": ["temperature", "radiation", "dust_level"]}

    if send_message(addr, 1, payload):
        missions[addr] = payload
        log(f"Missão {mission_id} ({mission_type}) atribuída a {rover_id}")
        save_mission_event(rover_id, mission_id, f"assigned ({mission_type})")


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

        if action == 6:  # request_mission
            rover_id = msg["payload"].get("rover_id", "UNKNOWN")
            log(f"Pedido de missão de {rover_id} ({addr})")
            threading.Thread(target=handle_request, args=(addr, rover_id), daemon=True).start()


        elif action == 3:  # mission_update
            m = msg["payload"]
            log(f"Update de {addr}: {m['mission_id']} → {m['progress']*100:.0f}%")
            save_mission_event(addr, m["mission_id"], "in_progress", m["progress"])
            if m["progress"] >= 1.0:
                log(f"Missão {m['mission_id']} concluída!")
                save_mission_event(addr, m["mission_id"], "completed")

        elif action == 2:  # ACK
            acks.add(msg["seq"])
            log(f"ACK direto de {addr}")

        else:
            log(f"Ação desconhecida {action} de {addr}")

def shutdown(sig, frame):
    print("\n[SERVER] A terminar...")
    print_mission_summary()
    sock.close()
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown)

if __name__ == "__main__":
    print("=== MissionLink Server ===")
    print("Escolhe o rover alvo (ex: R-001) ou ENTER para aceitar todos:")
    target_rover_id = input("> ").strip() or None
    print(f"Destino: {target_rover_id or 'todos os rovers'}")
    try:
        listener()
    except KeyboardInterrupt:
        print("\n[SERVER] Encerrado manualmente.")
        print_mission_summary()
        sock.close()

