import sys, os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, jsonify, request
from flask_cors import CORS
from state.rover_state import get_snapshot, get_history_snapshot
from missionlink_server import add_pending_mission


app = Flask(__name__)
CORS(app)

@app.route("/api/state")
def get_state():
    """Retorna o estado atual dos rovers."""
    return jsonify(get_snapshot())

@app.route("/api/history")
def get_history():
    """Retorna o histórico de estados dos rovers."""
    
    return jsonify(get_history_snapshot())

@app.route("/api/missions", methods=["POST"])

def create_mission():
    """Endpoint para criar uma nova missão para um rover."""
    
    try:
        data = request.json
        
        rover_id = data.get("rover_id")
        
        if not rover_id:
            return jsonify({"error": "Rover ID em falta"}), 400

        # Passar os dados da Web diretamente para a fila
        # O MissionLinkClient é que vai lidar com a lógica
        
        add_pending_mission(rover_id, data)
        
        return jsonify({"status": "ok", "msg": "Recebido"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def start_api_server():
    """Inicia o servidor API."""
    
    app.run(host="0.0.0.0", port=8000, debug=False)
