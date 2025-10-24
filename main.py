from flask import Flask, request, jsonify, render_template, Response
import time
import json

app = Flask(__name__)

devices = {}

@app.route("/location", methods=["POST"])
def receive_location():
    data = request.json
    device_id = data.get("device", "unknown-device")
    devices[device_id] = {
        "lat": data.get("latitude"),
        "lon": data.get("longitude"),
        "heading": data.get("heading"),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    return jsonify({"status": "OK"})

@app.route("/stream")
def stream():
    def event_stream():
        last_state = ""
        while True:
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
    print("🌍 Real-Time GPS server running...")
    app.run(host="0.0.0.0", port=5000, debug=True)
