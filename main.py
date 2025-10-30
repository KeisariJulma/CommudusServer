from flask import Flask, send_file, request
import os
import math
import requests
import threading

app = Flask(__name__)

# ---------------- Configuration ----------------
CACHE_DIR = "cached_tiles"
API_KEY = "5f712d8a0bf7423a8b220414c9ac2b91"

# Default zoom levels to pre-cache around user
ZOOM_LEVELS = [13, 14]  # adjust as needed
RADIUS_KM = 5  # radius around user to pre-cache tiles

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

def get_bounding_box(lat, lon, radius_km=RADIUS_KM):
    """Approximate bounding box in degrees around a point"""
    delta_deg = radius_km / 111  # ~1 deg = 111 km
    min_lat = lat - delta_deg
    max_lat = lat + delta_deg
    min_lon = lon - delta_deg
    max_lon = lon + delta_deg
    return min_lat, min_lon, max_lat, max_lon

def precache_around(lat, lon, zoom_levels=ZOOM_LEVELS, radius_km=RADIUS_KM):
    min_lat, min_lon, max_lat, max_lon = get_bounding_box(lat, lon, radius_km)
    for z in zoom_levels:
        x_min, y_max = latlon_to_tile(min_lat, min_lon, z)
        x_max, y_min = latlon_to_tile(max_lat, max_lon, z)
        for x in range(x_min, x_max + 1):
            for y in range(y_min, y_max + 1):
                download_tile(z, x, y)

def precache_async(lat, lon):
    """Run pre-cache in a background thread"""
    thread = threading.Thread(target=precache_around, args=(lat, lon))
    thread.start()

# ---------------- Flask Route ----------------
@app.route("/tiles/<int:z>/<int:x>/<int:y>.png")
def get_tile(z, x, y):
    # Optional: user location via query string
    user_lat = request.args.get("lat", type=float)
    user_lon = request.args.get("lon", type=float)

    # Start pre-caching around user in background
    if user_lat is not None and user_lon is not None:
        precache_async(user_lat, user_lon)

    # Serve cached tile if exists
    tile_path = os.path.join(CACHE_DIR, str(z), str(x), f"{y}.png")
    os.makedirs(os.path.dirname(tile_path), exist_ok=True)
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
    print("Starting Flask tile server...")
    app.run(host="0.0.0.0", port=5000)
