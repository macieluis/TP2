import json, os, threading, time
from collections import defaultdict

LOG_FILE = "navemae/data/missions_log.json"
_lock = threading.Lock()

def _load_log():
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def _save_log(data):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def save_mission_event(rover_addr, mission_id, status, progress=None):
    """Guarda eventos de missão (atribuição, update, conclusão)"""
    with _lock:
        data = _load_log()
        event = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "rover": str(rover_addr),
            "mission_id": mission_id,
            "status": status,
        }
        if progress is not None:
            event["progress"] = round(progress * 100, 1)
        data.append(event)
        _save_log(data)

def print_mission_summary():
    """Mostra resumo simplificado no terminal"""
    data = _load_log()
    print("\n=== RESUMO DE MISSÕES ===")

    if not data:
        print("(Sem registos de missão)")
        return

    # Agrupa pelo mission_id
    latest = {}
    for e in data:
        latest[e["mission_id"]] = e  # guarda o evento mais recente

    completed = []
    active = []
    for mid, e in latest.items():
        if e["status"] == "completed":
            completed.append(e)
        elif "in_progress" in e["status"]:
            active.append(e)

    if completed:
        print("\n Missões concluídas:")
        for e in completed:
            print(f"  [{e['timestamp']}] {e['rover']} → {e['mission_id']} : COMPLETED")

    if active:
        print("\n Missões em curso (interrompidas):")
        for e in active:
            prog = e.get('progress', '?')
            print(f"  [{e['timestamp']}] {e['rover']} → {e['mission_id']} : {prog}% concluída")

    print()
