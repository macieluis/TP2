# rover/missionlink_client.py
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import socket, time, threading, math, random
from common.codec import encode_msg, decode_msg
from state_manager import get_rover_state, update_rover_state
import rover_identity

SERVER = ("127.0.0.1", 5000)

_current_status = "idle"

def get_mission_status():
    return _current_status

last_position = [0, 0, 0]

def update_last_position(x, y):
    global last_position
    last_position = [round(x,2), round(y,2), 0]


def battery_consumption(task):
    base = 0.1
    extra = {
        "scan_area": 0.05,
        "collect_sample": 0.1,
        "analyze_environment": 0.02,
    }.get(task, 0)
    return base + extra


def send_request(sock):
    """Pede uma nova missão à Nave-Mãe."""
    payload = {"rover_id": rover_identity.ROVER_ID}
    pkt = encode_msg(1, 1, 6, 1, payload)  # 6 = request_mission
    sock.sendto(pkt, SERVER)
    print(f"[{rover_identity.ROVER_ID}] Pedido de missão enviado.")


def send_ack(sock, seq, mission_id):
    """Confirma receção da missão."""
    payload = {"mission_id": mission_id}
    pkt = encode_msg(1, 1, 2, seq, payload)  # 2 = ACK
    sock.sendto(pkt, SERVER)
    print(f"[{rover_identity.ROVER_ID}] ACK enviado.")


# ---- EXECUÇÃO DAS MISSÕES ----

def execute_scan_area(sock, mission_id, duration, interval, area, resolution):
    global _current_status
    task = "scan_area"
    _current_status = "in_mission"

    st = get_rover_state(rover_identity.ROVER_ID)
    pos_x, pos_y = st["x"], st["y"]
    battery = st["battery"]

    drain = battery_consumption(task)

    print(f"[{rover_identity.ROVER_ID}] >>> Início da missão {mission_id} ({task.upper()})")
    
    x1, y1 = area[0]
    x2, y2 = area[1]

    sx = 1 if x2 >= x1 else -1
    sy = 1 if y2 >= y1 else -1

    ncols = int(abs(x2 - x1) / resolution) + 1
    nrows = int(abs(y2 - y1) / resolution) + 1

    xs = [x1 + sx * i * resolution for i in range(ncols)]
    ys = [y1 + sy * j * resolution for j in range(nrows)]

    path = []
    for j, y in enumerate(ys):
        row = xs if j % 2 == 0 else list(reversed(xs))
        for x in row:
            path.append((round(x,1), round(y,1)))

    total_steps = len(path)
    step_time = duration / (total_steps - 1)

    elapsed = 0
    next_update = 0

    for idx, (x, y) in enumerate(path):

        # atualizar posição
        pos_x, pos_y = x, y
        update_rover_state(rover_identity.ROVER_ID, pos_x, pos_y)

        # consumo de bateria
        battery -= drain * step_time
        if battery < 0:
            battery = 0
        update_rover_state(rover_identity.ROVER_ID, battery=battery)

        # modo offline
        if battery <= 0:
            print(f"[{rover_identity.ROVER_ID}] ❌ Bateria esgotada! Rover offline.")
            _current_status = "offline"
            return

        # modo charging
        if battery < 20:
            print(f"[{rover_identity.ROVER_ID}] 🔋 Bateria baixa. A carregar...")
            while battery < 100:
                time.sleep(1)
                battery += 1.0
                update_rover_state(rover_identity.ROVER_ID, battery=battery)
            print(f"[{rover_identity.ROVER_ID}] 🔋 Carregado a 100%!")

        progress = idx / (total_steps - 1)

        if elapsed >= next_update or idx == total_steps - 1:
            payload = {
                "mission_id": mission_id,
                "task": task,
                "progress": round(progress, 2),
                "status": "in_progress" if idx < total_steps - 1 else "completed",
                "position": [pos_x, pos_y]
            }
            pkt = encode_msg(1,1,3,int(elapsed),payload)
            sock.sendto(pkt, SERVER)

            next_update += interval

        time.sleep(step_time)
        elapsed += step_time

    print(f"[{rover_identity.ROVER_ID}] ✔ Missão {mission_id} concluída.")
    _current_status = "idle"


def execute_collect_sample(sock, mission_id, duration, interval, points, sample_type):
    global _current_status
    task = "collect_sample"
    _current_status = "in_mission"

    st = get_rover_state(rover_identity.ROVER_ID)
    pos_x, pos_y = st["x"], st["y"]
    battery = st["battery"]
    drain = battery_consumption(task)

    print(f"[{rover_identity.ROVER_ID}] >>> Início da missão {mission_id} ({task.upper()})")

    total_points = len(points)
    current_segment = 0
    elapsed = 0
    next_update = 0

    # velocidade fictícia (tu tinhas esta lógica)
    speed = 0.3

    while elapsed < duration and current_segment < total_points:

        target = points[current_segment]
        tx, ty = target

        dx = tx - pos_x
        dy = ty - pos_y
        dist = (dx**2 + dy**2)**0.5

        if dist < 0.2:
            # recolha
            print(f"[{rover_identity.ROVER_ID}] Recolhendo amostra em {target}...")
            for _ in range(3):
                time.sleep(1)
                elapsed += 1

                battery -= drain
                if battery <= 0:
                    update_rover_state(rover_identity.ROVER_ID, battery=0)
                    print(f"[{rover_identity.ROVER_ID}] ❌ Rover sem bateria.")
                    _current_status = "offline"
                    return

                update_rover_state(rover_identity.ROVER_ID, battery=battery)

            current_segment += 1

        else:
            # movimento
            step = min(speed, dist)
            pos_x += dx/dist * step
            pos_y += dy/dist * step

            update_rover_state(rover_identity.ROVER_ID, x=pos_x, y=pos_y)

            time.sleep(1)
            elapsed += 1

            battery -= drain
            if battery <= 0:
                update_rover_state(rover_identity.ROVER_ID, battery=0)
                print(f"[{rover_identity.ROVER_ID}] ❌ Rover sem bateria.")
                _current_status = "offline"
                return

            if battery < 20:
                print(f"[{rover_identity.ROVER_ID}] 🔋 Bateria baixa. A carregar...")
                while battery < 100:
                    time.sleep(1)
                    battery += 1
                    update_rover_state(rover_identity.ROVER_ID, battery=battery)
                print(f"[{rover_identity.ROVER_ID}] 🔋 Carregado.")

            update_rover_state(rover_identity.ROVER_ID, battery=battery)

        # enviar update à nave-mãe
        if elapsed >= next_update:
            progress = elapsed / duration
            payload = {
                "mission_id": mission_id,
                "task": task,
                "progress": round(progress, 2),
                "status": "in_progress",
                "position": [round(pos_x,1), round(pos_y,1)],
                "current_point": target
            }
            pkt = encode_msg(1,1,3,int(elapsed),payload)
            sock.sendto(pkt, SERVER)
            next_update += interval

    # final
    payload = {
        "mission_id": mission_id,
        "task": task,
        "progress": 1.0,
        "status": "completed",
        "position": [round(pos_x,1), round(pos_y,1)],
        "sample_type": sample_type
    }
    pkt = encode_msg(1,1,3,int(elapsed),payload)
    sock.sendto(pkt, SERVER)

    print(f"[{rover_identity.ROVER_ID}] ✔ Missão {mission_id} concluída.")
    _current_status = "idle"


def execute_analyze_environment(sock, mission_id, duration, interval, area, sensors):
    global _current_status
    task = "analyze_environment"
    _current_status = "in_mission"

    st = get_rover_state(rover_identity.ROVER_ID)
    pos_x, pos_y = st["x"], st["y"]
    battery = st["battery"]
    drain = battery_consumption(task)

    print(f"[{rover_identity.ROVER_ID}] >>> Início da missão {mission_id} (ANALYZE)")

    steps = max(1, duration // interval)

    for i in range(1, steps + 1):

        # posição circular realista
        angle = (i / steps) * 2 * math.pi
        pos_x = 10 + 2.5 * math.cos(angle)
        pos_y = 10 + 2.5 * math.sin(angle)

        update_rover_state(rover_identity.ROVER_ID, x=pos_x, y=pos_y)

        # bateria
        battery -= drain * interval
        if battery <= 0:
            update_rover_state(rover_identity.ROVER_ID, battery=0)
            print(f"[{rover_identity.ROVER_ID}] ❌ Ficou sem bateria.")
            _current_status = "offline"
            return

        if battery < 20:
            print(f"[{rover_identity.ROVER_ID}] 🔋 Bateria baixa. A carregar...")
            while battery < 100:
                time.sleep(1)
                battery += 1
                update_rover_state(rover_identity.ROVER_ID, battery=battery)
            print(f"[{rover_identity.ROVER_ID}] 🔋 Carregado.")

        update_rover_state(rover_identity.ROVER_ID, battery=battery)

        # dados ambientais
        sun = (math.cos(angle - math.pi/2) + 1) / 2
        data = {}

        if "temperature" in sensors:
            data["temperature"] = round(-50 + 30 * math.cos(angle), 1)
        if "radiation" in sensors:
            data["radiation"] = round(2.5 + 1.5 * sun, 2)
        if "dust_level" in sensors:
            data["dust_level"] = round((1-sun)*60 + random.uniform(-3,3), 1)

        progress = i / steps

        payload = {
            "mission_id": mission_id,
            "task": task,
            "progress": progress,
            "status": "analyzing",
            "position": [round(pos_x,1), round(pos_y,1)],
            "data": data
        }

        pkt = encode_msg(1,1,3,i,payload)
        sock.sendto(pkt, SERVER)

        time.sleep(interval)

    print(f"[{rover_identity.ROVER_ID}] ✔ Missão {mission_id} concluída.")
    _current_status = "idle"


def execute_mission(sock, payload):
    global _current_status     # <-- IMPORTANTE

    task = payload.get("task", "")
    mission_id = payload["mission_id"]
    duration = payload.get("duration", 120)
    interval = payload.get("update_interval", 10)

    _current_status = "in_mission"

    if task == "scan_area":
        execute_scan_area(sock, mission_id, duration, interval,
                          payload["area"], payload.get("resolution", 1.0))

    elif task == "collect_sample":
        execute_collect_sample(sock, mission_id, duration, interval,
                               payload["points"], payload.get("sample_type", "rock"))

    elif task == "analyze_environment":
        execute_analyze_environment(sock, mission_id, duration, interval,
                                    payload.get("area", []),
                                    payload.get("sensors", []))
    else:
        print(f"[{rover_identity.ROVER_ID}] Tipo de missão desconhecido: {task}")

    _current_status = "idle"


def missionlink_listener(sock):
    """Recebe mensagens da Nave-Mãe e despacha execuções."""
    while True:
        try:
            data, _ = sock.recvfrom(4096)
        except KeyboardInterrupt:
            print(f"\n[{rover_identity.ROVER_ID}] MissionLink encerrado manualmente.")
            break

        msg = decode_msg(data)

        if msg["action"] == 1:  # new_mission
            payload = msg["payload"]
            print(f"[{rover_identity.ROVER_ID}] Nova missão: {payload}")
            for k, v in payload.items():
                print(f"    - {k}: {v}")

            send_ack(sock, msg["seq"], payload["mission_id"])

            threading.Thread(
                target=execute_mission,
                args=(sock, payload),
                daemon=True
            ).start()


def start_missionlink():
    """Arranca o cliente MissionLink para o ROVER_ID já escolhido."""
    if rover_identity.ROVER_ID is None:
        raise RuntimeError("ROVER_ID não definido. Chama rover_identity.choose_rover_id() primeiro.")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    send_request(sock)
    try:
        missionlink_listener(sock)
    finally:
        sock.close()


# modo standalone (testar só ML)
if __name__ == "__main__":
    from rover_identity import choose_rover_id
    choose_rover_id()
    start_missionlink()
