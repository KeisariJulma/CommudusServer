from flask import Flask, request, jsonify, render_template, Response
import time
import json

app = Flask(__name__)

# Time in seconds after which a device is considered stale
DEVICE_TIMEOUT = 30

# Store devices: key = device name
devices = {}

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
            current_time = time.time()

            # Remove stale devices automatically
            stale = [n for n, info in devices.items() if current_time - info["timestamp"] > DEVICE_TIMEOUT]
            for n in stale:
                print(f"[STREAM] Removing stale: {n}")
                devices.pop(n)

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
