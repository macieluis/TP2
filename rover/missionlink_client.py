import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import socket
import threading
import time
import math
import random
import rover_identity
from common.codec import encode_msg, decode_msg
from common.protocol_constants import ML_REQUEST, ML_ACK, ML_UPDATE, ML_COMPLETE, ML_NEW_MISSION

ML_SERVER =("10.0.3.20",5000) #IP DA NAVE-MÃE NO CORE
#ML_SERVER = ("127.0.0.1", 5000) no pc

SEQ = 1
_current_mission = None
_status_lock = threading.Lock()
_rover_status = "idle"
SPEED = 1.0 

def get_status():
    """Devolve o estado atual do rover."""
    with _status_lock: return _rover_status

def set_status(s):
    """Define o estado atual do rover."""
    
    global _rover_status
    with _status_lock:
        if _rover_status == "charging" and s != "idle" and s != "charging": return 
        _rover_status = s

def get_current_task():
    """Devolve a tarefa atual do rover (ou None)."""
    
    if _current_mission is None: return None
    
    return _current_mission.get("task")

def send(sock, action, payload):
    """Envia uma mensagem codificada para o servidor MissionLink."""
    
    global SEQ
    pkt = encode_msg(1, 1, action, SEQ, payload)
    sock.sendto(pkt, ML_SERVER)
    SEQ = (SEQ + 1) % 65536

def handle_server_messages(sock):
    """Thread que lida com mensagens recebidas do servidor MissionLink."""
    
    global _current_mission
    
    while True:
        
        try:
            
            data, _ = sock.recvfrom(4096)
            msg = decode_msg(data)
            if msg["action"] == ML_NEW_MISSION:
                
                _current_mission = msg["payload"]
                print(f"[ML] Nova Missão: {msg['payload']['mission_id']}")
                send(sock, ML_ACK, {"rover_id": rover_identity.ROVER_ID, "mission_id": msg["payload"]["mission_id"]})
                set_status("in_mission")
        except: continue


def navigate_waypoints(sock, m_id, waypoints, duration, interval, desc="A mover"):
    """Navega por uma série de waypoints em dado tempo, enviando updates."""
    
    start_time = time.time()
    
    # Garante que curr_pos tem sempre 3 coordenadas
    curr_pos = list(rover_identity.POSITION)
    while len(curr_pos) < 3: curr_pos.append(0.0)

    if not waypoints: return True

    for target in waypoints:
        
        while True:
            
            if get_status() == "charging": return False
            
            if time.time() - start_time > duration:
                print(f"⚠️ TIMEOUT na missão {m_id}!")
                return False

            dx = target[0] - curr_pos[0]
            dy = target[1] - curr_pos[1]
            dist = math.sqrt(dx**2 + dy**2)

            if dist < 0.1:
                curr_pos[0] = target[0]
                curr_pos[1] = target[1]
                break 

            step = SPEED * interval 
            if step > dist: step = dist
            
            curr_pos[0] += dx * (step/dist)
            curr_pos[1] += dy * (step/dist)
            
            rover_identity.POSITION = list(curr_pos)
            
            elapsed = time.time() - start_time
            progress = min(99.0, (elapsed / duration) * 100)

            # MENSAGEM VISUAL PARA A WEB
            display_msg = f"{desc} -> [{target[0]:.1f}, {target[1]:.1f}]"

            send(sock, ML_UPDATE, {
                "rover_id": rover_identity.ROVER_ID, "mission_id": m_id,
                "progress": round(progress, 1), "status": "in_progress", 
                "position": curr_pos, 
                "extra": {"display": display_msg} 
            })
            
            time.sleep(interval)
            
    return True

def run_mission(sock):
    """Executa a missão atualmente atribuída ao rover."""
    
    global _current_mission
    m = _current_mission
    if m is None: return

    m_id = m["mission_id"]
    task = m["task"]
    duration = float(m.get("duration", 60))
    interval = float(m.get("update_interval", 5))
    
    print(f">>> INICIAR {task} ({duration}s)")
    
    success = False
    start_time = time.time()

    try:
        # 1. SCAN AREA
        
        if task == "scan_area":
            
            area = m.get("area", [[0,0],[10,10]])
            res = float(m.get("resolution", 1.0))
            waypoints = []
            min_x, min_y = area[0]
            max_x, max_y = area[1]
            
            # Ponto inicial
            waypoints.append([min_x, min_y])
            
            lines = int((max_y - min_y) / res) + 1
            d = 1
            cy = min_y
            
            for _ in range(lines):
                
                tx = max_x if d==1 else min_x
                waypoints.append([tx, cy])
                if cy < max_y: 
                    cy = min(max_y, cy + res)
                    waypoints.append([tx, cy])
                d *= -1
            
            # Usa a navegação genérica com mensagem personalizada
            success = navigate_waypoints(sock, m_id, waypoints, duration, interval, "Mapeando")

        
        # 2. COLLECT SAMPLE
        
        elif task == "collect_sample":
            
            points = m.get("points", [])
            stype = m.get("sample_type", "rock")
            
            curr_pos = list(rover_identity.POSITION)
            while len(curr_pos) < 3: curr_pos.append(0.0)

            # 1. Calcular tempo necessário de viagem (Total Distance)
            
            total_dist = 0
            temp_p = list(curr_pos)
            
            for p in points:
                d = math.sqrt((p[0]-temp_p[0])**2 + (p[1]-temp_p[1])**2)
                total_dist += d
                temp_p = list(p)
            
            travel_time = total_dist / SPEED
            
            # 2. O tempo que sobra é dividido para "trabalhar" em cada ponto
            
            work_time = max(0, duration - travel_time)
            
            time_per_point = work_time / len(points) if points else 0
            
            print(f"[INFO] Viagem: {travel_time:.1f}s | Recolha/ponto: {time_per_point:.1f}s")

            for i, target in enumerate(points):
                
                if get_status() == "charging": break
                if (time.time() - start_time) > duration: break

                # FASE A: Viajar até ao ponto
                while True:
                    
                    dx = target[0] - curr_pos[0]
                    dy = target[1] - curr_pos[1]
                    dist = math.sqrt(dx**2 + dy**2)
                    if dist < 0.1: 
                        curr_pos[0], curr_pos[1] = target[0], target[1]
                        break 
                    
                    step = SPEED * interval
                    if step > dist: step = dist
                    
                    curr_pos[0] += dx * (step/dist)
                    curr_pos[1] += dy * (step/dist)
                    
                    rover_identity.POSITION = list(curr_pos)
                    
                    elapsed = time.time() - start_time
                    progress = min(99.0, (elapsed / duration) * 100)
                    
                    # Mensagem: "A ir para Ponto X"
                    
                    send(sock, ML_UPDATE, {
                        "rover_id": rover_identity.ROVER_ID, "mission_id": m_id,
                        "progress": round(progress, 1), "status": "moving", "position": curr_pos,
                        "extra": {"display": f"A ir para Ponto {i+1}..."} 
                    })
                    
                    time.sleep(interval)

                # FASE B: Recolher (Gastar o tempo extra aqui)
                
                collect_start = time.time()
                
                while (time.time() - collect_start) < time_per_point:
                    
                    if get_status() == "charging": break
                    if (time.time() - start_time) > duration: break
                    
                    elapsed = time.time() - start_time
                    progress = min(99.0, (elapsed / duration) * 100)
                    
                    # Mensagem: "A recolher [Tipo]..."
                    send(sock, ML_UPDATE, {
                        "rover_id": rover_identity.ROVER_ID, "mission_id": m_id,
                        "progress": round(progress, 1), "status": "collecting", "position": curr_pos,
                        "extra": {"display": f"A recolher {stype}...", "sample": stype}
                    })
                    
                    remaining_work = time_per_point - (time.time() - collect_start)
                    time.sleep(min(interval, remaining_work))

            if (time.time() - start_time) <= (duration + 5) and get_status() != "charging":
                success = True

        
        # 3. ANALYZE ENVIRONMENT
        
        elif task == "analyze_environment":
            
            sensors = m.get("sensors", [])
            start_t = time.time()
            
            while (time.time() - start_t) < duration:
                
                if get_status() == "charging": success=False; break
                
                # A. Movimento Constante (Trigonometria)
                # Garante velocidade = 1.0 m/s em qualquer direção
                step_distance = SPEED * interval
                angle = random.uniform(0, 2 * math.pi)
                
                rover_identity.POSITION[0] += math.cos(angle) * step_distance
                rover_identity.POSITION[1] += math.sin(angle) * step_distance
                
                # Manter Z=0
                if len(rover_identity.POSITION) < 3: rover_identity.POSITION.append(0.0)
                
                # B. Cálculo do Progresso
                
                elapsed = time.time() - start_t
                progress = min(99.0, (elapsed / duration) * 100)
                
                # C. GERAÇÃO DE DADOS (Matemática: Senos e Cossenos)
                
                x, y = rover_identity.POSITION[0], rover_identity.POSITION[1]
                t_now = time.time()
                extra_data = {}
                msg_parts = []
                
                if "temperature" in sensors:
                    val = 20.0 + 10.0 * math.sin(x / 5.0) + 5.0 * math.cos(y / 5.0)
                    extra_data["temp"] = round(val, 1)
                    msg_parts.append(f"{val:.1f}C")
                    

                if "radiation" in sensors:
                    
                    dist_origin = math.sqrt(x**2 + y**2)
                    val = 10.0 + (dist_origin / 2.0) + 5.0 * math.sin(t_now)
                    extra_data["rad"] = round(val, 2)
                    msg_parts.append(f"{val:.1f}Rad")

                if "dust_level" in sensors:
                    
                    val = 50.0 + 20.0 * math.cos(x * y) + random.uniform(-5, 5)
                    extra_data["dust"] = round(max(0, val), 1)
                
                # D. Enviar para a Web
                if not msg_parts: msg_parts.append("Analisando...")
                extra_data["display"] = " | ".join(msg_parts)

                send(sock, ML_UPDATE, {
                    "rover_id": rover_identity.ROVER_ID, "mission_id": m_id,
                    "progress": round(progress, 1), "status": "in_progress", 
                    "position": rover_identity.POSITION, "extra": extra_data
                })
                time.sleep(interval)
            
            if get_status() != "charging": success = True

    except Exception as e: print(f"Erro: {e}")


    final_status = "completed" if success else "incomplete"
    
    if not success and get_status() == "charging":
        
        final_status = "aborted"
        print(f"[{rover_identity.ROVER_ID}] Missão ABORTADA (Bateria).")
    
    # Garante 3D no envio final
    pos_final = list(rover_identity.POSITION)
    
    while len(pos_final) < 3: pos_final.append(0.0)

    send(sock, ML_COMPLETE, {
        "rover_id": rover_identity.ROVER_ID, "mission_id": m_id,
        "progress": 100 if success else 0, 
        "status": final_status,
        "position": pos_final
    })
    
    print(f"\n[{rover_identity.ROVER_ID}] 🏁 MISSÃO {m_id} CONCLUÍDA ({final_status.upper()}).\n")
    
    rover_identity.save_state()
    
    if get_status() != "charging": set_status("idle")
    _current_mission = None

def start_missionlink():
    """Inicia o cliente MissionLink."""
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)
    
    threading.Thread(target=handle_server_messages, args=(sock,), daemon=True).start()
    
    print("[ML] Cliente iniciado. À espera de missões...")

    while True:
        
        try:
            
            if _current_mission: run_mission(sock)
            
            elif get_status() == "idle":
                send(sock, ML_REQUEST, {"rover_id": rover_identity.ROVER_ID})
                time.sleep(3)
            elif get_status() == "charging": time.sleep(2)
            
        except: break