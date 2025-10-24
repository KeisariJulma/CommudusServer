from flask import Flask, request, jsonify, render_template, Response
import time
import json

app = Flask(__name__)

DEVICE_TIMEOUT = 30  # seconds

# In-memory storage: device_id -> {lat, lon, heading, timestamp, name}
devices = {}

@app.route("/location", methods=["POST"])
def receive_location():
    data = request.json
    device_id = data.get("device", "unknown-device")
    name = data.get("name", device_id)
    timestamp = time.time()

    try:
        lat = float(data.get("latitude", 0))
        lon = float(data.get("longitude", 0))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "msg": "Invalid coordinates"}), 400

    devices[device_id] = {
        "lat": lat,
        "lon": lon,
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
    """SSE endpoint for live updates"""
    def event_stream():
        last_state = ""
        while True:
            current_time = time.time()
            stale_ids = [d for d, info in devices.items() if current_time - info["timestamp"] > DEVICE_TIMEOUT]
            for d in stale_ids:
                devices.pop(d)

            state = json.dumps(devices)
            if state != last_state:
                last_state = state
                yield f"data: {state}\n\n"
            time.sleep(1)

    return Response(event_stream(), mimetype="text/event-stream")

@app.route("/map")
def show_map():
    return render_template("map.html")

if __name__ == "__main__":
    print("🌍 Real-Time GPS server running...")
    app.run(host="0.0.0.0", port=5000, debug=True)
