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
from common.protocol_constants import ML_REQUEST, ML_ACK, ML_UPDATE, ML_COMPLETE, ML_NEW_MISSION

ML_SERVER = ("127.0.0.1", 5000) # ATENÇÃO: Mudar para IP da Nave no CORE
SEQ = 1
_current_mission = None
_status_lock = threading.Lock()
_rover_status = "idle"

# === GESTÃO DE ESTADO ===
def get_status():
    with _status_lock:
        return _rover_status

def set_status(s):
    global _rover_status
    with _status_lock:
        # Regra: Se estiver a carregar, só sai para idle se bateria cheia
        if _rover_status == "charging" and s != "idle" and s != "charging":
            return 
        _rover_status = s

def get_current_task():
    if _current_mission is None: return None
    return _current_mission.get("task")

# === COMUNICAÇÃO ===
def send(sock, action_code, payload):
    global SEQ
    pkt = encode_msg(1, 1, action_code, SEQ, payload)
    sock.sendto(pkt, ML_SERVER)
    SEQ = (SEQ + 1) % 65536

def handle_server_messages(sock):
    """Thread que escuta respostas da Nave-Mãe."""
    global _current_mission

    while True:
        try:
            data, addr = sock.recvfrom(4096)
            msg = decode_msg(data)
            payload = msg["payload"]
            action = msg["action"]

            # 1 → RECEBER NOVA MISSÃO
            if action == ML_NEW_MISSION:
                _current_mission = payload
                print(f"[ML] Nova missão recebida: {payload['mission_id']} ({payload['task']})")
                
                # Enviar ACK
                send(sock, ML_ACK, { 
                    "rover_id": rover_identity.ROVER_ID,
                    "mission_id": payload["mission_id"]
                })
                set_status("in_mission")

            # 2 → RECEBER CONFIRMAÇÃO DE ACK
            elif action == ML_ACK:
                # print("[ML] Handshake completo.")
                pass

        except socket.timeout:
            continue # Timeout normal, continua a escutar
        except Exception as e:
            print(f"[ML] Erro na escuta: {e}")
            break

# === EXECUÇÃO DAS MISSÕES (Scan, Collect, Analyze) ===
def run_mission(sock):
    global _current_mission
    mission = _current_mission
    if mission is None: return

    m_id = mission["mission_id"]
    interval = mission["update_interval"]
    task = mission["task"]
    duration = mission["duration"]
    
    # Verificar bateria antes de começar
    if get_status() == "charging":
        print(f"[{rover_identity.ROVER_ID}] Bateria baixa. A abortar missão {m_id}.")
        _current_mission = None
        return

    print(f"[{rover_identity.ROVER_ID}] >>> A executar {m_id} ({task.upper()})...")
    
    # Variáveis de estado local
    pos = rover_identity.POSITION
    progress = 0.0
    
    try:
        # --- LÓGICA: SCAN_AREA ---
        if task == "scan_area":
            area = mission.get("area", [[0,0], [10,10]])
            resolution = mission.get("resolution", 1.0)
            min_x, min_y = area[0]
            max_x, max_y = area[1]
            
            pos[0], pos[1] = min_x, min_y
            direction = 1
            num_lines = int((max_y - min_y) / resolution) + 1
            
            for i in range(num_lines):
                if get_status() == "charging": break # Abortar se bateria morrer
                
                pos[0] = max_x if direction == 1 else min_x
                progress = min(100.0, ((pos[1] - min_y) / (max_y - min_y)) * 100)
                
                send(sock, ML_UPDATE, {
                    "rover_id": rover_identity.ROVER_ID, "mission_id": m_id, 
                    "progress": progress, "status": "in_progress", "position": pos.copy()
                })
                print(f"[{rover_identity.ROVER_ID}] {m_id}: {progress:.1f}% Linha {i+1}")
                
                time.sleep(interval)
                
                if i < num_lines - 1:
                    pos[1] += resolution
                    direction *= -1
            progress = 100.0

        # --- LÓGICA: COLLECT_SAMPLE ---
        elif task == "collect_sample":
            points = mission.get("points", [])
            total = len(points)
            
            for i, p in enumerate(points):
                if get_status() == "charging": break
                
                pos[0], pos[1] = p[0], p[1]
                progress = ((i + 1) / total) * 100
                
                send(sock, ML_UPDATE, {
                    "rover_id": rover_identity.ROVER_ID, "mission_id": m_id,
                    "progress": progress, "status": "in_progress", "position": pos.copy(),
                    "extra": {"sample": mission.get("sample_type")}
                })
                print(f"[{rover_identity.ROVER_ID}] {m_id}: {progress:.1f}% Ponto {i+1}")
                time.sleep(interval)
            progress = 100.0

        # --- LÓGICA: ANALYZE_ENVIRONMENT ---
        elif task == "analyze_environment":
            steps = max(1, duration // interval)
            for i in range(steps):
                if get_status() == "charging": break
                
                pos[0] += random.uniform(-0.5, 0.5)
                pos[1] += random.uniform(-0.5, 0.5)
                progress = ((i + 1) / steps) * 100
                
                extra = { "temp": round(random.uniform(-20, 30),1) }
                
                send(sock, ML_UPDATE, {
                    "rover_id": rover_identity.ROVER_ID, "mission_id": m_id,
                    "progress": progress, "status": "in_progress", "position": pos.copy(),
                    "extra": extra
                })
                print(f"[{rover_identity.ROVER_ID}] {m_id}: {progress:.1f}% Analisando...")
                time.sleep(interval)
            progress = 100.0

    except Exception as e:
        print(f"[ERRO] Falha na missão: {e}")

    # Se foi interrompida por bateria
    if get_status() == "charging":
        print(f"[{rover_identity.ROVER_ID}] Missão PAUSADA/CANCELADA (Carregamento).")
        _current_mission = None
        return

    # Conclusão Sucesso
    send(sock, ML_COMPLETE, {
        "rover_id": rover_identity.ROVER_ID, "mission_id": m_id,
        "progress": 100.0, "status": "completed", "position": pos.copy()
    })
    print(f"[{rover_identity.ROVER_ID}] Missão {m_id} CONCLUÍDA.")
    
    rover_identity.POSITION = pos
    rover_identity.save_state()
    
    set_status("idle")
    _current_mission = None

# === START ===
def start_missionlink():
    if rover_identity.ROVER_ID is None: raise RuntimeError("ID em falta")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0) # 2 segundos timeout para o recvfrom não bloquear para sempre

    # Iniciar listener em background
    t = threading.Thread(target=handle_server_messages, args=(sock,), daemon=True)
    t.start()

    print("[ML] Cliente iniciado. À espera de missões...")

    # LOOP PRINCIPAL
    while True:
        try:
            # 1. Tem missão? Executa.
            if _current_mission is not None:
                run_mission(sock)
            
            # 2. Não tem? Pede.
            elif get_status() == "idle":
                # Envia pedido
                send(sock, ML_REQUEST, {"rover_id": rover_identity.ROVER_ID})
                
                # Espera 3 segundos. Se a Nave tiver algo, 'handle_server_messages' 
                # vai receber e atualizar '_current_mission' durante este sleep.
                time.sleep(3)

            # 3. A carregar? Espera.
            elif get_status() == "charging":
                time.sleep(2)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Erro loop: {e}")
            time.sleep(1)

if __name__ == "__main__":
    # Apenas para teste isolado, normalmente chamado pelo main.py
    rover_identity.ROVER_ID = "R-TEST"
    start_missionlink()