from flask import Flask, send_file, jsonify
import requests
from io import BytesIO

app = Flask(__name__)

MML_API_KEY = "6ca6d0d1-33bb-4cf4-8840-f6da4874929d"
WMTS_URL = "https://avoin-karttakuva.maanmittauslaitos.fi/avoin/wmts"
LAYER = "maastokartta"
TILEMATRIXSET = "ETRS-TM35FIN"
FORMAT = "image/png"


def wmts_tile_url(z, x, y):
    """Return the full WMTS URL for the given tile coordinates."""
    return (
        f"{WMTS_URL}"
        f"?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0"
        f"&LAYER={LAYER}&TILEMATRIXSET={TILEMATRIXSET}"
        f"&TileMatrix={z}&TileRow={y}&TileCol={x}"
        f"&FORMAT={FORMAT}&api-key={MML_API_KEY}"
    )


@app.route("/tiles/<int:z>/<int:x>/<int:y>.png")
def proxy_tile(z, x, y):
    try:
        url = wmts_tile_url(z, x, y)
        print(f"Fetching tile: {url}")
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return send_file(BytesIO(r.content), mimetype="image/png")
    except requests.RequestException as e:
        print(f"Error fetching tile {z}/{x}/{y}: {e}")
        return "Tile not found", 404


@app.route("/")
def home():
    return "<h3>✅ MML WMTS 512×512 Tile Proxy is running!</h3>"


@app.route("/test-tiles")
def test_tiles():
    """Return a JSON list of sample tile URLs for testing in a map."""
    sample_tiles = []
    zoom_levels = [0, 5, 6]
    coords = [
        (0, 0),
        (12, 10),  # Approx. southern Finland at z=5
        (24, 16),  # Finland central at z=6
    ]
    for z, (x, y) in zip(zoom_levels, coords):
        sample_tiles.append({
            "z": z,
            "x": x,
            "y": y,
            "url": f"http://localhost:5000/tiles/{z}/{x}/{y}.png"
        })
    return jsonify(sample_tiles)


if __name__ == "__main__":
    print("🚀 Running high-resolution MML proxy on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
