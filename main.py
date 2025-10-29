from flask import Flask, send_file
import requests
from io import BytesIO
from PIL import Image
import time
import json

app = Flask(__name__)

MML_API_KEY = "6ca6d0d1-33bb-4cf4-8840-f6da4874929d"
WMTS_URL = "https://avoin-karttakuva.maanmittauslaitos.fi/avoin/wmts"
LAYER = "maastokartta"
TILEMATRIXSET = "ETRS-TM35FIN"
FORMAT = "image/png"

def xyz_to_wmts(z, x, y):
    # Invert Y for WMTS (TMS → WMTS)
    tile_row = (2 ** z - 1) - y
    tile_col = x
    return {
        "SERVICE": "WMTS",
        "REQUEST": "GetTile",
        "VERSION": "1.0.0",
        "LAYER": LAYER,
        "TILEMATRIXSET": TILEMATRIXSET,
        "TileMatrix": str(z),
        "TileRow": str(tile_row),
        "TileCol": str(tile_col),
        "FORMAT": FORMAT,
        "api-key": MML_API_KEY,
    }

@app.route("/tiles/<int:z>/<int:x>/<int:y>.png")
def proxy_tile(z, x, y):
    # REMOVE Y inversion
    tile_row = y
    tile_col = x
    wmts_url = (
        f"https://avoin-karttakuva.maanmittauslaitos.fi/avoin/wmts"
        f"?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0"
        f"&LAYER=maastokartta&TILEMATRIXSET=ETRS-TM35FIN"
        f"&TileMatrix={z}&TileRow={tile_row}&TileCol={tile_col}"
        f"&FORMAT=image/png&api-key=6ca6d0d1-33bb-4cf4-8840-f6da4874929d"
    )

    r = requests.get(wmts_url)
    if r.status_code != 200:
        return "Tile not found", 404
    return send_file(BytesIO(r.content), mimetype="image/png")



@app.route("/")
def home():
    return "<h3>✅ MML WMTS 512×512 Tile Proxy is running!</h3>"

if __name__ == "__main__":
    print("🚀 Running high-resolution MML proxy on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
