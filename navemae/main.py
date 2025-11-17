# navemae/main.py
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import threading
import time
from missionlink_server import start_missionlink
from telemetry_server import start_telemetry_server
from state.rover_state import get_snapshot, apply_timeouts

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

                pos_s = "None" if pos is None else f"[{pos[0]}, {pos[1]}, {pos[2]}]"
                batt_s = "None" if batt is None else f"{batt:.1f}%"
                prog_s = "-" if prog is None else f"{prog:.0f}%"
                mid_s  = "—" if mid is None else mid

                alive = r.get("alive", False)
                flag = "🟢" if alive else "🔴"

                print(f"{flag} {rid}: pos={pos_s} | batt={batt_s} | status={stat} | missão={mid_s} ({prog_s})")

        print("====================================")


def main():
    global RUNNING
    print("[NM] A iniciar TelemetryStream e MissionLink...")

    # Servidor de telemetria TCP
    threading.Thread(target=start_telemetry_server, daemon=True).start()

    # Servidor ML UDP
    threading.Thread(target=start_missionlink, daemon=True).start()

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
