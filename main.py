from flask import Flask, send_file
import requests
from io import BytesIO
from PIL import Image
import time
import json

app = Flask(__name__)

MML_API_KEY = "4cbea972-9a49-4c45-a1d0-0f2046f81ff0"
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

@app.route("/tiles512/<int:z>/<int:x>/<int:y>.png")
def proxy_tile_512(z, x, y):
    """Combine 4 256x256 tiles into a single 512x512 tile."""
    tiles = []
    for dy in (0, 1):
        row = []
        for dx in (0, 1):
            params = xyz_to_wmts(z + 1, x * 2 + dx, y * 2 + dy)
            r = requests.get(WMTS_URL, params=params, timeout=5)
            if r.status_code == 200:
                row.append(Image.open(BytesIO(r.content)))
            else:
                row.append(Image.new("RGBA", (256, 256), (255, 255, 255, 0)))
        tiles.append(row)

    big = Image.new("RGBA", (512, 512))
    for j, row in enumerate(tiles):
        for i, img in enumerate(row):
            big.paste(img, (i * 256, j * 256))

    bio = BytesIO()
    big.save(bio, format="PNG")
    bio.seek(0)
    return send_file(bio, mimetype="image/png")

@app.route("/")
def home():
    return "<h3>✅ MML WMTS 512×512 Tile Proxy is running!</h3>"

if __name__ == "__main__":
    print("🚀 Running high-resolution MML proxy on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
