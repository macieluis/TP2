import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import socket
import time
import random
from common.codec import encode_msg
from missionlink_client import set_status
import rover_identity

#SERVER = ("127.0.0.1", 6000) no pc
SERVER = ("10.0.3.20",6000)  # IP DA NAVE-MÃE NO CORE
SEQ = 1

def send(sock, action, payload):
    """Envia uma mensagem codificada para o servidor."""
    
    global SEQ
    
    pkt = encode_msg(
        version=1,
        msg_type=2,    # TelemetryStream
        action=action,
        seq=SEQ,
        payload=payload
    )
    
    sock.sendall(pkt)
    SEQ = (SEQ + 1) % 65536

#bateria consumo por segundo
CONSUMPTION = {
    "idle": 0.10,
    "in_mission": 0.10,
    "scan_area": 0.15,
    "collect_sample": 0.20,
    "analyze_environment": 0.12,
}

def compute_battery(batt, status, task, dt):
    """Calcula o novo nível de bateria com base no estado e tarefa atuais."""
    
    # Regra 1: Se o estado for "charging", carrega
    if status == "charging":
        
        return min(100.0, batt + (1.0 * dt))  # carrega 1%/s

    if batt <= 0:
        
        return 0.0

    # Regra 2: Se não estiver a carregar, consome
    base = CONSUMPTION.get(status, 0.10)
    extra = CONSUMPTION.get(task, 0.0)

    drain = (base + extra) * dt
    batt = max(0.0, batt - drain)
    
    return batt


def telemetry_loop(sock, get_current_position, get_current_status, get_current_task, battery_ref):
    """Loop principal do cliente de telemetria."""
    
    last = time.time()
    set_status_fn = set_status 
    
    # Adicionar um contador para evitar guardar em disco a cada 2s
    save_counter = 0

    try:
        
        while True:
            
            now = time.time()
            dt = now - last
            last = now

            pos = get_current_position()
            status_antes = get_current_status()
            task = get_current_task()

            # Atualiza bateria
            battery_ref.BATTERY = compute_battery(battery_ref.BATTERY, status_antes, task, dt)
            batt = round(battery_ref.BATTERY, 1)

            # LÓGICA DE ESTADO DA BATERIA
            if batt < 20 and status_antes == "idle":
                
                set_status_fn("charging")
                
            elif batt < 5 and status_antes == "in_mission":
                
                set_status_fn("charging")
                
            elif batt >= 100 and status_antes == "charging":
                set_status_fn("idle")
                
            
            status_final = get_current_status()

            payload = {
                "rover_id": rover_identity.ROVER_ID,
                "position": pos,
                "battery": batt,
                "speed": 1.0 if status_final == "in_mission" else 0.0,
                "status": status_final,
                "timestamp": now,
            }
            
            send(sock, 2, payload) # action=2 → telemetry update

            # Salva o estado para o disco a cada 10 ciclos (a cada 20 segundos)
            save_counter += 1
            
            if save_counter >= 10: 
                
                rover_identity.save_state()
                save_counter = 0
            

            # Heartbeat ocasional
            
            if random.random() < 0.15:
                send(sock, 4, {"rover_id": rover_identity.ROVER_ID, "timestamp": now})

            time.sleep(2)

    except KeyboardInterrupt:
        
        print(f"[{rover_identity.ROVER_ID}] TS encerrado manualmente.")
        
        try:
            
            send(sock, 5, {"rover_id": rover_identity.ROVER_ID, "reason": "manual_disconnect"})
        except:
            pass
        
    except (BrokenPipeError, ConnectionResetError):
        print(f"[{rover_identity.ROVER_ID}] Ligação TS perdida.")
        
    finally:
        # SALVA O ESTADO UMA ÚLTIMA VEZ NO FINAL
        rover_identity.save_state()
        sock.close()


def start_telemetry(get_pos, get_status, get_task, battery_ref):
    """Inicia o cliente de telemetria."""
    
    if rover_identity.ROVER_ID is None:
        
        raise RuntimeError("ROVER_ID não definido.")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(SERVER)

    print(f"[{rover_identity.ROVER_ID}] Ligado ao TelemetryStream.")

    send(sock, 1, {"rover_id": rover_identity.ROVER_ID, "timestamp": time.time()})  # CONNECT

    telemetry_loop(sock, get_pos, get_status, get_task, battery_ref)
