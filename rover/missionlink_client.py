# rover/missionlink_client.py
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import socket, time, threading, math, random
from common.codec import encode_msg, decode_msg
import rover_identity

SERVER = ("127.0.0.1", 5000)


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
    """Varrimento em zig-zag: caminho discreto (grid) + updates sincronizados ao update_interval."""
    print(f"[{rover_identity.ROVER_ID}] >>> Início da missão {mission_id} (SCAN AREA)")

    x1, y1 = area[0]
    x2, y2 = area[1]

    # suportar áreas em qualquer direção (x1>x2, y1>y2, etc.)
    sx = 1 if x2 >= x1 else -1
    sy = 1 if y2 >= y1 else -1

    # número de colunas/linhas (INCLUSIVO no limite)
    ncols = int(abs(x2 - x1) / resolution) + 1
    nrows = int(abs(y2 - y1) / resolution) + 1

    xs = [x1 + sx * i * resolution for i in range(ncols)]
    ys = [y1 + sy * j * resolution for j in range(nrows)]

    # construir caminho em zig-zag: linha 0 → esquerda→direita, linha 1 → direita→esquerda, ...
    path = []
    for j, y in enumerate(ys):
        row_xs = xs if j % 2 == 0 else list(reversed(xs))
        for x in row_xs:
            path.append((round(x, 1), round(y, 1)))

    total_steps = len(path)
    if total_steps <= 1:
        # caso degenerado (área minúscula)
        payload = {
            "mission_id": mission_id,
            "task": "scan_area",
            "progress": 1.0,
            "status": "completed",
            "position": [round(x2, 1), round(y2, 1)],
        }
        pkt = encode_msg(1, 1, 3, 0, payload)
        sock.sendto(pkt, SERVER)
        print(f"[{rover_identity.ROVER_ID}] {mission_id}: 100% (pos={x2:.1f},{y2:.1f})")
        print(f"[{rover_identity.ROVER_ID}] Missão {mission_id} concluída.")
        return

    # tempo por waypoint para perfazer 'duration'
    step_time = duration / (total_steps - 1)
    elapsed = 0.0
    next_update = 0.0

    for idx, (x, y) in enumerate(path):
        progress = idx / (total_steps - 1)

        # enviar/printar apenas quando bate no update_interval (ou no último ponto)
        if elapsed >= next_update or idx == total_steps - 1:
            payload = {
                "mission_id": mission_id,
                "task": "scan_area",
                "progress": round(progress, 2),
                "status": "in_progress" if idx < total_steps - 1 else "completed",
                "position": [x, y],
            }
            pkt = encode_msg(1, 1, 3, int(elapsed), payload)
            sock.sendto(pkt, SERVER)
            print(f"[{rover_identity.ROVER_ID}] {mission_id}: {progress*100:.0f}% (pos={x:.1f},{y:.1f})")
            next_update += interval

        # avançar no “relógio” da missão
        time.sleep(step_time)
        elapsed += step_time

    print(f"[{rover_identity.ROVER_ID}] Missão {mission_id} concluída.")


def execute_collect_sample(sock, mission_id, duration, interval, points, sample_type):
    print(f"[{rover_identity.ROVER_ID}] >>> Início da missão {mission_id} (COLLECT SAMPLE)")
    pos = [random.uniform(0, 5), random.uniform(0, 5)]
    total_points = len(points)

    route = [pos] + points
    dists = [((route[i+1][0] - route[i][0])**2 + (route[i+1][1] - route[i][1])**2)**0.5
             for i in range(len(route)-1)]
    total_dist = sum(dists)

    move_time_total = duration * 0.85  # 85% a mover, 15% a recolher
    collect_time_each = (duration - move_time_total) / total_points
    speed = total_dist / move_time_total if move_time_total > 0 else 0.0

    elapsed = 0.0
    next_update = 0.0
    collected = 0
    current_segment = 0
    collecting_mode = False
    collecting_point = None

    while elapsed < duration and current_segment < len(points):
        target = points[current_segment]

        # se está a recolher, não se move até o próximo update_interval
        if collecting_mode:
            if elapsed >= next_update:
                progress = min(elapsed / duration, 1)
                payload = {
                    "mission_id": mission_id,
                    "task": "collect_sample",
                    "progress": round(progress, 2),
                    "status": "recolhendo",
                    "position": [round(pos[0], 1), round(pos[1], 1)],
                    "current_point": collecting_point,
                    "sample_type": sample_type,
                }
                pkt = encode_msg(1, 1, 3, int(elapsed), payload)
                sock.sendto(pkt, SERVER)
                print(f"[{rover_identity.ROVER_ID}] {mission_id}: {progress*100:.0f}% recolhendo em {collecting_point}")
                collected += 1
                collecting_mode = False
                current_segment += 1
                next_update += interval  # volta ao ciclo normal
            time.sleep(1)
            elapsed += 1
            continue

        # calcular movimento até o ponto
        dx = target[0] - pos[0]
        dy = target[1] - pos[1]
        dist = (dx**2 + dy**2)**0.5

        if dist < 0.1:  # chegou ao ponto
            collecting_mode = True
            collecting_point = target
            # mantém posição fixa e espera até próximo update_interval
        else:
            # movimento normal
            if dist > 0 and speed > 0:
                step = min(speed, dist)
                pos[0] += dx / dist * step
                pos[1] += dy / dist * step

        # enviar update apenas no tempo certo
        if elapsed >= next_update or elapsed >= duration:
            progress = min(elapsed / duration, 1)
            status = "recolhendo" if collecting_mode else "movendo"
            payload = {
                "mission_id": mission_id,
                "task": "collect_sample",
                "progress": round(progress, 2),
                "status": status,
                "position": [round(pos[0], 1), round(pos[1], 1)],
                "current_point": target,
                "sample_type": sample_type,
            }
            pkt = encode_msg(1, 1, 3, int(elapsed), payload)
            sock.sendto(pkt, SERVER)
            print(
                f"[{rover_identity.ROVER_ID}] {mission_id}: {progress*100:.0f}% {status} "
                f"(pos={pos[0]:.1f},{pos[1]:.1f}) → alvo {target}"
            )
            next_update += interval

        time.sleep(1)
        elapsed += 1

    # garantir update final a 100%
    payload = {
        "mission_id": mission_id,
        "task": "collect_sample",
        "progress": 1.0,
        "status": "completed",
        "position": [round(pos[0], 1), round(pos[1], 1)],
        "sample_type": sample_type,
    }
    pkt = encode_msg(1, 1, 3, int(elapsed), payload)
    sock.sendto(pkt, SERVER)
    print(f"[{rover_identity.ROVER_ID}] {mission_id}: 100% completed em {pos}")
    if collected < len(points):
        print(
            f"[{rover_identity.ROVER_ID}] ⚠️ Missão {mission_id} terminou antes de recolher todas as amostras "
            f"({collected}/{len(points)})"
        )
    else:
        print(
            f"[{rover_identity.ROVER_ID}] ✅ Todas as amostras recolhidas com sucesso ({collected}/{len(points)})"
        )


def execute_analyze_environment(sock, mission_id, duration, interval, area, sensors):
    """Analisa ambiente com movimento circular e variação realista (ciclo diurno estável)."""
    steps = duration // interval
    print(f"[{rover_identity.ROVER_ID}] >>> Início da missão {mission_id} (ANALYZE ENVIRONMENT)")

    base_temp = -50
    temp_amplitude = 30  # variação máxima de ±15 °C em torno do base_temp
    base_rad = 2.5
    rad_amplitude = 1.5

    for i in range(1, steps + 1):
        angle = (i / steps) * 2 * math.pi
        # movimento circular dentro da área (hardcoded para [10,10] +- raio, como já tinhas)
        x = 10 + 2.5 * math.cos(angle)
        y = 10 + 2.5 * math.sin(angle)

        # ciclo solar suave
        sun = (math.cos(angle - math.pi/2) + 1) / 2  # valor entre 0 e 1
        data = {}

        if "temperature" in sensors:
            temp = base_temp + temp_amplitude * math.cos(angle - math.pi/4)
            data["temperature"] = round(temp, 1)
        if "radiation" in sensors:
            rad = base_rad + rad_amplitude * sun
            data["radiation"] = round(rad, 2)
        if "dust_level" in sensors:
            dust = (1 - sun) * 60 + random.uniform(-3, 3)
            data["dust_level"] = round(max(0, min(100, dust)), 1)

        progress = i / steps
        payload = {
            "mission_id": mission_id,
            "task": "analyze_environment",
            "progress": progress,
            "position": [x, y],
            "data": data,
            "status": "analyzing"
        }
        pkt = encode_msg(1, 1, 3, i, payload)
        sock.sendto(pkt, SERVER)

        print(f"[{rover_identity.ROVER_ID}] {mission_id}: {progress*100:.0f}% pos({x:.1f},{y:.1f}) {data}")
        time.sleep(interval)

    print(f"[{rover_identity.ROVER_ID}] Missão {mission_id} concluída.")


def execute_mission(sock, payload):
    task = payload.get("task", "")
    mission_id = payload["mission_id"]
    duration = payload.get("duration", 120)
    interval = payload.get("update_interval", 10)

    if task == "scan_area":
        execute_scan_area(sock, mission_id, duration, interval, payload["area"], payload.get("resolution", 1.0))
    elif task == "collect_sample":
        execute_collect_sample(sock, mission_id, duration, interval, payload["points"],
                               payload.get("sample_type", "rock"))
    elif task == "analyze_environment":
        execute_analyze_environment(sock, mission_id, duration, interval,
                                    payload.get("area", []), payload.get("sensors", []))
    else:
        print(f"[{rover_identity.ROVER_ID}] Tipo de missão desconhecido: {task}")


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
