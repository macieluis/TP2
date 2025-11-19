# navemae/api_server.py
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, jsonify, request
from flask_cors import CORS
from state.rover_state import get_snapshot
# Importar a função para agendar missões
from missionlink_server import add_pending_mission

app = Flask(__name__)
CORS(app) # Habilita CORS para permitir pedidos do index.html

@app.route("/api/state")
def get_state():
    """Retorna o estado global (para o monitor)."""
    return jsonify(get_snapshot())

@app.route("/api/missions", methods=["POST"])
def create_mission():
    """Recebe comandos da Interface Web e agenda no MissionLink."""
    try:
        data = request.json
        rover_id = data.get("rover_id")
        task = data.get("task")
        
        if not rover_id or not task:
            return jsonify({"error": "Faltam dados (rover_id ou task)"}), 400

        # Configurar parâmetros base da missão
        mission_data = {
            "task": task,
            "duration": 60 # Duração padrão (segundos)
        }

        # Parâmetros específicos por tipo de missão
        if task == "scan_area":
            mission_data["area"] = [[0,0], [10,10]]
            mission_data["resolution"] = 1.0
        elif task == "collect_sample":
            mission_data["points"] = [[2,2], [5,5], [8,2]]
            mission_data["sample_type"] = "rock"
        elif task == "analyze_environment":
            mission_data["sensors"] = ["temperature", "radiation"]

        # COLOCAR NA FILA DO MISSIONLINK
        add_pending_mission(rover_id, mission_data)
        
        return jsonify({"status": "ok", "msg": f"Missão {task} agendada para {rover_id}"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def start_api_server():
    # host="0.0.0.0" permite acesso externo (necessário para o CORE)
    app.run(host="0.0.0.0", port=8000, debug=False)

if __name__ == "__main__":
    print("[API] A iniciar em modo isolado...")
    start_api_server()