from flask import Flask, send_file, jsonify
import requests
from io import BytesIO

app = Flask(__name__)

MML_API_KEY = "6ca6d0d1-33bb-4cf4-8840-f6da4874929d"
WMTS_URL = "https://avoin-karttakuva.maanmittauslaitos.fi/avoin/wmts"
LAYER = "maastokartta"
TILEMATRIXSET = "WGS84"  # <-- changed from ETRS-TM35FIN
FORMAT = "image/png"

def wmts_tile_url(z, x, y):
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
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return send_file(BytesIO(r.content), mimetype="image/png")
    except requests.RequestException:
        return "Tile not found", 404

@app.route("/")
def home():
    return "<h3>✅ MML WMTS WGS84 Tile Proxy is running!</h3>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
