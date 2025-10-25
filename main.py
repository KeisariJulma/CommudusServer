from flask import Flask, request, jsonify, Response, render_template
import time
import json

app = Flask(__name__)

DEVICE_TIMEOUT = 30  # seconds
devices = {}

@app.route("/location", methods=["POST"])
def receive_location():
    data = request.json
    device_id = data.get("name", "unknown-device")  # use name as unique id
    devices[device_id] = {
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "heading": data.get("heading"),
        "timestamp": time.time(),
        "name": device_id
    }

    # Remove stale devices
    now = time.time()
    stale = [k for k, v in devices.items() if now - v["timestamp"] > DEVICE_TIMEOUT]
    for k in stale:
        devices.pop(k)

    return jsonify({"status": "OK"})


@app.route("/stream")
def stream():
    """SSE: push all devices to clients"""
    def event_stream():
        last_state = ""
        while True:
            now = time.time()
            stale = [k for k, v in devices.items() if now - v["timestamp"] > DEVICE_TIMEOUT]
            for k in stale:
                devices.pop(k)

            current_state = json.dumps(devices)
            if current_state != last_state:
                last_state = current_state
                yield f"data: {current_state}\n\n"
            time.sleep(1)
    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/map")
def show_map():
    return render_template("map.html")  # See below


if __name__ == "__main__":
    print("🌍 Real-Time GPS server running...")
    app.run(host="0.0.0.0", port=5000, debug=True)
