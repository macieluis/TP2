# navemae/main.py
import threading, time

from telemetry_server import start_telemetry_server
from missionlink_server import start_missionlink
from state.rover_state import get_snapshot, apply_timeouts
from common.logger_ml import print_mission_summary


def state_monitor():
    while True:
        time.sleep(5)
        apply_timeouts()
        snap = get_snapshot()
        print("\n===== ESTADO GLOBAL DOS ROVERS =====")
        if not snap:
            print("(sem rovers ainda)")
        else:
            for rid, info in snap.items():
                alive = "🟢" if info.get("alive") else "🔴"
                pos = info.get("position")
                batt = info.get("battery")
                status = info.get("status")
                mid = info.get("mission_id", "—")
                prog = info.get("mission_progress", 0.0)
                print(f"{alive} {rid}: pos={pos} | batt={batt}% | status={status} | missão={mid} ({prog*100:.0f}%)")
        print("====================================\n")


def main():
    print("[NM] A iniciar TelemetryStream e MissionLink...")

    t_ts = threading.Thread(target=start_telemetry_server, daemon=True)
    t_ts.start()

    t_state = threading.Thread(target=state_monitor, daemon=True)
    t_state.start()

    try:
        start_missionlink()  # bloqueia até Ctrl+C
    except KeyboardInterrupt:
        print("\n[SERVER] A terminar...")
    finally:
        print_mission_summary()


if __name__ == "__main__":
    main()
