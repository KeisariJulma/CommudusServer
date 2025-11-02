from flask import Flask, request, jsonify, render_template, Response
import time
import json
from threading import Lock

app = Flask(__name__)

# Store devices: key = device name
devices = {}
lock = Lock()  # thread-safe access for SSE

@app.route("/location", methods=["POST"])
def receive_location():
    """
    Regular location update from device.
    """
    data = request.json or {}
    name = data.get("name")
    if not name:
        return jsonify({"status": "ERROR", "message": "Missing device name"}), 400

    timestamp = time.time()
    with lock:
        devices[name] = {
            "id": name,
            "lat": data.get("latitude") or data.get("lat"),
            "lon": data.get("longitude") or data.get("lon"),
            "heading": data.get("heading"),
            "timestamp": timestamp,
            "name": name
        }

    return jsonify({"status": "OK"})


@app.route("/location/stop", methods=["POST"])
def stop_sharing():
    """
    Device explicitly stops sharing location.
    """
    data = request.json or {}
    name = data.get("name")
    if not name:
        return jsonify({"status": "ERROR", "message": "Missing device name"}), 400

    with lock:
        if name in devices:
            devices.pop(name)
            print(f"[STOP] Device {name} removed from map")

    return jsonify({"status": "OK"})


@app.route("/stream")
def stream():
    """
    SSE stream of device locations.
    """
    def event_stream():
        last_state = ""
        while True:
            with lock:
                current_state = json.dumps(devices)

            # Only send new state
            if current_state != last_state:
                last_state = current_state
                yield f"data: {current_state}\n\n"

            time.sleep(1)

    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/map")
def show_map():
    return render_template("map.html")


if __name__ == "__main__":
    print("🌍 GPS server running: multiple devices supported by name")
    app.run(host="0.0.0.0", port=5000, debug=True)
