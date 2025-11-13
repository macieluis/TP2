# Flask API de observação


from flask import Flask, jsonify
from telemetry_server import telemetry

app = Flask(__name__)

@app.route("/telemetry")
def get_telemetry():
    return jsonify(telemetry)

@app.route("/rovers")
def get_rovers():
    return jsonify(list(telemetry.keys()))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
