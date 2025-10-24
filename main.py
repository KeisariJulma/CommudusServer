from flask import Flask, request, jsonify, render_template, Response
import time
import json
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # allow cross-origin requests for testing from other devices

# Device timeout in seconds
DEVICE_TIMEOUT = 30

# In-memory storage for devices
# Each device will have: lat, lon, heading, timestamp, name
devices = {}

@app.route("/location", methods=["POST"])
def receive_location():
    data = request.json
    device_id = data.get("device", "unknown-device")
    name = data.get("name", device_id)
    timestamp = time.time()

    devices[device_id] = {
        "lat": data.get("latitude"),
        "lon": data.get("longitude"),
        "heading": data.get("heading"),
        "timestamp": timestamp,
        "name": name
    }

    # Remove stale devices
    stale_ids = [d for d, info in devices.items() if timestamp - info["timestamp"] > DEVICE_TIMEOUT]
    for d in stale_ids:
        devices.pop(d)

    return jsonify({"status": "OK"})

@app.route("/stream")
def stream():
    """SSE endpoint for streaming live devices"""
    def event_stream():
        last_state = ""
        while True:
            current_time = time.time()
            # Remove stale devices
            stale_ids = [d for d, info in devices.items() if current_time - info["timestamp"] > DEVICE_TIMEOUT]
            for d in stale_ids:
                devices.pop(d)

            current_state = json.dumps(devices)
            if current_state != last_state:
                last_state = current_state
                yield f"data: {current_state}\n\n"
            time.sleep(1)
    return Response(event_stream(), mimetype="text/event-stream")

@app.route("/map")
def show_map():
    return render_template("map.html")

if __name__ == "__main__":
    print("🌍 Real-Time GPS server running on port 5000...")
    app.run(host="0.0.0.0", port=5000, debug=True)
