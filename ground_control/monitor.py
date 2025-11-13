# ground_control.py
import requests, time

API = "http://navemae:8000/telemetry"

while True:
    try:
        r = requests.get(API)
        print(r.json())
        time.sleep(3)
    except:
        print("Sem ligação à Nave-Mãe.")
        time.sleep(5)
