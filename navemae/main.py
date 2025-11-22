# navemae/main.py
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import threading
import time
from missionlink_server import start_missionlink
from telemetry_server import start_telemetry_server
from state.rover_state import get_snapshot, apply_timeouts
from api_server import start_api_server

RUNNING = True

def printer_loop():
    """Imprime o estado global de forma limpa e sem spam."""
    while RUNNING:
        time.sleep(5)

        snapshot = get_snapshot()
        print("\n===== ESTADO GLOBAL DOS ROVERS =====")

        if not snapshot:
            print("(sem rovers ainda)")
        else:
            for rid, r in snapshot.items():
                pos = r.get("position")
                batt = r.get("battery")
                stat = r.get("status")
                mid = r.get("mission_id")
                prog = r.get("mission_progress")

                # === CORREÇÃO DE SEGURANÇA (2D vs 3D) ===
                if pos is None:
                    pos_s = "None"
                elif len(pos) >= 3:
                    pos_s = f"[{pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}]"
                elif len(pos) == 2:
                    pos_s = f"[{pos[0]:.1f}, {pos[1]:.1f}, 0.0]" # Assume Z=0
                else:
                    pos_s = str(pos)
                # ========================================

                batt_s = "None" if batt is None else f"{batt:.1f}%"
                prog_s = "-" if prog is None else f"{prog:.0f}%"
                mid_s  = "—" if mid is None else mid

                alive = r.get("alive", False) # Nota: 'alive' não está no state, usa-se status
                flag = "🟢" if stat != "offline" else "🔴"

                print(f"{flag} {rid}: pos={pos_s} | batt={batt_s} | status={stat} | missão={mid_s} ({prog_s})")

        print("====================================")


def main():
    global RUNNING
    print("[NM] A iniciar TelemetryStream e MissionLink...")

    # Servidor de telemetria TCP
    threading.Thread(target=start_telemetry_server, daemon=True).start()

    # Servidor ML UDP
    threading.Thread(target=start_missionlink, daemon=True).start()
    
    # API Web
    threading.Thread(target=start_api_server, daemon=True).start()

    # Thread de output organizado
    threading.Thread(target=printer_loop, daemon=True).start()

    try:
        while True:
            time.sleep(1)
            apply_timeouts()   # marca rovers offline se deixarem de enviar TS/ML
    except KeyboardInterrupt:
        RUNNING = False
        print("\n[NM] Encerrado manualmente.")


if __name__ == "__main__":
    main()