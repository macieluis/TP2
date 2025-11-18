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
from common.protocol_constants import (
    ML_REQUEST, ML_ACK, ML_UPDATE, ML_COMPLETE, ML_NEW_MISSION
)

ML_SERVER = ("127.0.0.1", 5000)
SEQ = 1
_current_mission = None
_status_lock = threading.Lock()
_rover_status = "idle"


_status_lock = threading.Lock()
_rover_status = "idle" # "idle", "in_mission", "charging"


def get_status():
    """Retorna o estado global atual do rover."""
    with _status_lock:
        return _rover_status


def set_status(s):
    """Define o estado global do rover, com regras de prioridade."""
    global _rover_status
    with _status_lock:
        # Regra 1: Se estiver a carregar, IGNORA um pedido para "in_mission".
        if _rover_status == "charging" and s == "in_mission":
            return  # Continua a carregar

        # Regra 2: Se estiver a carregar, só pode sair para "idle" (bateria cheia)
        if _rover_status == "charging" and s == "idle":
            _rover_status = "idle"
            return

        # Regra 3: Se o novo estado é "charging", define-o imediatamente.
        if s == "charging":
            _rover_status = "charging"
            return
            
        # Outros casos (ex: idle -> in_mission)
        _rover_status = s

def get_current_task():
    """Retorna a 'task' da missão atual, se existir."""
    if _current_mission is None:
        return None
    return _current_mission.get("task")

def send(sock, action_code, payload): # Mudei o nome da var para 'action_code'
    global SEQ
    pkt = encode_msg(
        version=1,
        msg_type=1,         # 1 = MSG_TYPE_MISSIONLINK
        action=action_code, 
        seq=SEQ,
        payload=payload
    )
    sock.sendto(pkt, ML_SERVER)
    SEQ = (SEQ + 1) % 65536


def handle_server_messages(sock):
    global _current_mission

    while True:
        try:
            data, addr = sock.recvfrom(4096)
            
            # =========================================================
            # CORREÇÃO: decode_msg retorna um único dicionário
            # =========================================================
            msg = decode_msg(data)
            payload = msg["payload"]
            action = msg["action"]
            # Se o decode falhar (checksum, etc.), ele levanta uma exceção

            # =========================================================
            # CORREÇÃO 2: Verificar a 'action' correta
            # =========================================================

            # 1 → new mission (Enviada pela Nave-Mãe)
            if action == ML_NEW_MISSION: # Ação 1
                _current_mission = payload
                print(f"[ML][{rover_identity.ROVER_ID}] Nova missão de {addr}: "
                      f"{payload['mission_id']}")
                for k, v in payload.items():
                    print(f"    - {k}: {v}")

                # Enviar ACK (Ação 2)
                send(sock, ML_ACK, { 
                    "rover_id": rover_identity.ROVER_ID,
                    "mission_id": payload["mission_id"]
                })
                print(f"[ML][{rover_identity.ROVER_ID}] ACK enviado para {payload['mission_id']}.")

                set_status("in_mission") # <--- Define o estado para 'in_mission'

            # 2 → ACK do ACK (Enviado pela Nave-Mãe)
            elif action == ML_ACK: # Ação 2
                print(f"[ML][{rover_identity.ROVER_ID}] ACK da nave-mãe confirmado.")

        except socket.timeout:
            continue
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
    duration = mission["duration"]

    # Usar a posição global do rover
    pos = rover_identity.POSITION
    
    if get_status() == "charging":
        print(f"[{rover_identity.ROVER_ID}] Bateria a carregar, missão {m_id} não pode começar.")
        _current_mission = None
        return

    print(f"[{rover_identity.ROVER_ID}] >>> Início da missão {m_id} ({task.upper()})")

    # -----------------------------------------------------------------
    # Lógica de Movimento Específica da Missão
    # -----------------------------------------------------------------
    
    progress = 0.0
    
    # -----------------------------------------
    # TAREFA: SCAN_AREA (com lógica zig-zag)
    # -----------------------------------------
    if task == "scan_area":
        try:
            area_coords = mission["area"]
            resolution = mission["resolution"]
            min_x, min_y = area_coords[0][0], area_coords[0][1]
            max_x, max_y = area_coords[1][0], area_coords[1][1]

            pos[0], pos[1] = min_x, min_y
            direction = 1  # 1 = direita, -1 = esquerda
            
            num_lines = int((max_y - min_y) / resolution) + 1
            if num_lines <= 0: num_lines = 1
            
            # O 'update_interval' aqui dita o tempo por *linha*
            for i in range(num_lines):
                pos[0] = max_x if direction == 1 else min_x
                
                progress = round(((pos[1] - min_y) / (max_y - min_y)) * 100, 1)
                progress = max(0.0, min(100.0, progress))

                send(sock, 3, { # ML_UPDATE
                    "rover_id": rover_identity.ROVER_ID,
                    "mission_id": m_id, "progress": progress, "status": "in_progress",
                    "position": pos.copy(), "extra": {}
                })
                print(f"[{rover_identity.ROVER_ID}] {m_id}: {progress}% (linha {i+1}/{num_lines}) pos({pos[0]:.1f},{pos[1]:.1f})")
                
                # VERIFICAÇÃO 2: Parar a missão se a bateria ficar baixa
                if get_status() == "charging":
                    print(f"[{rover_identity.ROVER_ID}] Missão {m_id} interrompida (bateria baixa).")
                    _current_mission = None
                    return # Sai da função run_mission
        
                time.sleep(interval) 
                
                if i < num_lines - 1:
                    pos[1] += resolution
                    direction *= -1
            
            progress = 100.0

        except Exception as e:
            print(f"[{rover_identity.ROVER_ID}] ERRO na execução de scan_area: {e}")

    # -----------------------------------------
    # TAREFA: COLLECT_SAMPLE (com lógica de pontos)
    # -----------------------------------------
    elif task == "collect_sample":
        try:
            points_to_visit = mission["points"]
            num_points = len(points_to_visit)
            if num_points == 0: raise ValueError("Lista de 'points' está vazia.")

            # O 'update_interval' aqui dita o tempo por *ponto*
            for i, point in enumerate(points_to_visit):
                pos[0], pos[1] = point[0], point[1]
                if len(point) > 2: pos[2] = point[2]

                progress = round(((i + 1) / num_points) * 100, 1)

                send(sock, 3, { # ML_UPDATE
                    "rover_id": rover_identity.ROVER_ID,
                    "mission_id": m_id, "progress": progress, "status": "in_progress",
                    "position": pos.copy(),
                    "extra": {
                       "sample_type": mission.get("sample_type", "unknown"),
                       "last_point": point
                    }
                })
                print(f"[{rover_identity.ROVER_ID}] {m_id}: {progress}% (ponto {i+1}/{num_points}) pos({pos[0]:.1f},{pos[1]:.1f})")

                time.sleep(interval)

            progress = 100.0

        except Exception as e:
            print(f"[{rover_identity.ROVER_ID}] ERRO na execução de collect_sample: {e}")

    # -----------------------------------------
    # TAREFA: ANALYZE_ENVIRONMENT (com dados de sensores)
    # -----------------------------------------
    elif task == "analyze_environment":
        try:
            total_steps = duration // interval
            if total_steps <= 0: total_steps = 1
            sensors_to_read = mission.get("sensors", [])

            for step in range(1, total_steps + 1):
                # Movimento aleatório (como no teu relatório)
                pos[0] += random.uniform(-0.5, 0.5)
                pos[1] += random.uniform(-0.5, 0.5)

                progress = round((step / total_steps) * 100, 1)
                
                # Gerar dados de sensores (como no teu relatório)
                extra_data = {}
                if "temperature" in sensors_to_read:
                    extra_data["temperature"] = round(random.uniform(-80, 20), 1)
                if "radiation" in sensors_to_read:
                    extra_data["radiation"] = round(random.uniform(0.5, 5.0), 2)
                if "dust_level" in sensors_to_read:
                    extra_data["dust_level"] = round(random.uniform(0, 100), 1)

                send(sock, 3, { # ML_UPDATE
                    "rover_id": rover_identity.ROVER_ID,
                    "mission_id": m_id, "progress": progress, "status": "in_progress",
                    "position": pos.copy(), "extra": extra_data
                })
                
                print(f"[{rover_identity.ROVER_ID}] {m_id}: {progress}% pos({pos[0]:.1f},{pos[1]:.1f}) data={extra_data}")
                
                time.sleep(interval)
            
            progress = 100.0

        except Exception as e:
            print(f"[{rover_identity.ROVER_ID}] ERRO na execução de analyze_environment: {e}")

    # -----------------------------------------
    # TAREFA DESCONHECIDA (Fallback)
    # -----------------------------------------
    else:
        print(f"[{rover_identity.ROVER_ID}] {m_id}: Tarefa '{task}' desconhecida. A abortar.")
        progress = 0.0 # Indica falha

    # -----------------------------------------------------------------
    # Missão concluída
    # -----------------------------------------------------------------
    print(f"[{rover_identity.ROVER_ID}] Missão {m_id} concluída.")
    
    send(sock, 7, { # ML_COMPLETE = 7
        "rover_id": rover_identity.ROVER_ID,
        "mission_id": m_id,
        "progress": 100.0,
        "status": "completed",
        "position": pos.copy()
    })

    # Guardar posição final no ficheiro local
    rover_identity.save_state()

    set_status("idle")
    _current_mission = None
    # -----------------------------------------------------------------
    # Missão concluída
    # -----------------------------------------------------------------
    send(sock, 7, { # ML_COMPLETE = 7
        "rover_id": rover_identity.ROVER_ID,
        "mission_id": m_id,
        "progress": progress, # Envia o progresso final (100.0 ou 0 se falhou)
        "status": "completed",
        "position": pos.copy()
    })

    print(f"[{rover_identity.ROVER_ID}] Missão {m_id} concluída.")

    # Guardar posição final no ficheiro local
    rover_identity.save_state()

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
    send(sock, ML_REQUEST, {"rover_id": rover_identity.ROVER_ID}) # 6
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
