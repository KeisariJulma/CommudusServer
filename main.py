from flask import Flask, send_file
import os
import math
import requests

app = Flask(__name__)

# ---------------- Configuration ----------------
CACHE_DIR = "cached_tiles"  # folder to store tiles
API_KEY = "5f712d8a0bf7423a8b220414c9ac2b91"

# Bounding box for pre-caching (lat/lon)
MIN_LAT, MIN_LON = 59.5, 19.0  # southwest corner
MAX_LAT, MAX_LON = 70.1, 31.5  # northeast corner

# Zoom levels to pre-cache
ZOOM_LEVELS = [10, 11, 12, 13]  # adjust as needed

os.makedirs(CACHE_DIR, exist_ok=True)


# ---------------- Helper Functions ----------------
def latlon_to_tile(lat, lon, zoom):
    """Convert latitude/longitude to tile numbers"""
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    xtile = int((lon + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile


def download_tile(z, x, y):
    tile_path = os.path.join(CACHE_DIR, str(z), str(x), f"{y}.png")
    os.makedirs(os.path.dirname(tile_path), exist_ok=True)
    if os.path.exists(tile_path):
        return  # already cached

    url = f"https://tile.thunderforest.com/outdoors/{z}/{x}/{y}.png?apikey={API_KEY}"
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(tile_path, "wb") as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        print(f"Downloaded tile {z}/{x}/{y}")
    else:
        print(f"Failed to download tile {z}/{x}/{y}")


def precache_region():
    """Pre-download all tiles in the bounding box for specified zoom levels"""
    for z in ZOOM_LEVELS:
        x_min, y_max = latlon_to_tile(MIN_LAT, MIN_LON, z)
        x_max, y_min = latlon_to_tile(MAX_LAT, MAX_LON, z)

        print(f"Pre-caching zoom {z}, X: {x_min}-{x_max}, Y: {y_min}-{y_max}")

        for x in range(x_min, x_max + 1):
            for y in range(y_min, y_max + 1):
                download_tile(z, x, y)

    print("Pre-caching complete!")


# ---------------- Flask Route ----------------
@app.route("/tiles/<int:z>/<int:x>/<int:y>.png")
def get_tile(z, x, y):
    # Local cache path
    tile_path = os.path.join(CACHE_DIR, str(z), str(x), f"{y}.png")
    os.makedirs(os.path.dirname(tile_path), exist_ok=True)

    # If tile is cached, return it
    if os.path.exists(tile_path):
        return send_file(tile_path, mimetype="image/png")

    # Otherwise, fetch from Thunderforest and cache it
    url = f"https://tile.thunderforest.com/outdoors/{z}/{x}/{y}.png?apikey={API_KEY}"
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(tile_path, "wb") as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        return send_file(tile_path, mimetype="image/png")
    else:
        return "Tile not found", 404


# ---------------- Main ----------------
if __name__ == "__main__":
    print("Starting pre-cache...")
    precache_region()  # Pre-download tiles on startup
    print("Starting Flask server...")
    app.run(host="0.0.0.0", port=5000)
