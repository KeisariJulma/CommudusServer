from flask import Flask, request, jsonify, render_template, Response, send_file
import time
import json
import requests
from io import BytesIO

app = Flask(__name__)

# --- Device tracking ---
DEVICE_TIMEOUT = 30
devices = {}

@app.route("/location", methods=["POST"])
def receive_location():
    data = request.json or {}
    print(f"[RECEIVED] {data}")

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

    # Remove stale devices
    stale = [n for n, info in devices.items() if timestamp - info["timestamp"] > DEVICE_TIMEOUT]
    for n in stale:
        print(f"[STALE] Removing: {n}")
        devices.pop(n)

    return jsonify({"status": "OK"})

@app.route("/stream")
def stream():
    def event_stream():
        last_state = ""
        while True:
            current_time = time.time()

            # Remove stale devices
            stale = [n for n, info in devices.items() if current_time - info["timestamp"] > DEVICE_TIMEOUT]
            for n in stale:
                print(f"[STREAM] Removing stale: {n}")
                devices.pop(n)

            current_state = json.dumps(devices)
            if current_state != last_state:
                last_state = current_state
                print(f"[STREAM] Sending: {current_state}")
                yield f"data: {current_state}\n\n"

            time.sleep(1)

    return Response(event_stream(), mimetype="text/event-stream")

@app.route("/map")
def show_map():
    return render_template("map.html")

# --- MML WMTS → XYZ tile proxy ---
MML_API_KEY = "4cbea972-9a49-4c45-a1d0-0f2046f81ff0"
WMTS_URL = "https://avoin-karttakuva.maanmittauslaitos.fi/avoin/wmts"
LAYER = "maastokartta_3857"
TILEMATRIXSET = "WebMercatorQuad"
FORMAT = "image/png"

def xyz_to_wmts(z, x, y):
    # WMTS WebMercatorQuad y = (2^z - 1) - y
    tile_row = (2 ** z - 1) - y
    tile_col = x
    return {
        "SERVICE": "WMTS",
        "REQUEST": "GetTile",
        "VERSION": "1.0.0",
        "LAYER": "maastokartta_3857",
        "TILEMATRIXSET": "WebMercatorQuad",
        "TileMatrix": str(z),
        "TileRow": str(tile_row),
        "TileCol": str(tile_col),
        "FORMAT": "image/png",
        "api-key": MML_API_KEY,
    }


@app.route("/tiles/<int:z>/<int:x>/<int:y>.png")
def proxy_tile(z, x, y):
    params = xyz_to_wmts(z, x, y)
    r = requests.get(WMTS_URL, params=params)
    if r.status_code != 200:
        return "Tile not found", 404
    return send_file(BytesIO(r.content), mimetype="image/png")

if __name__ == "__main__":
    print("🌍 GPS + tile proxy server running")
    app.run(host="0.0.0.0", port=5000, debug=True)
