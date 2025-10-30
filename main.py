from flask import Flask, send_file, request
import requests
from io import BytesIO
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import numpy as np
from pyproj import Transformer

app = Flask(__name__)

MML_API_KEY = "6ca6d0d1-33bb-4cf4-8840-f6da4874929d"
WMTS_URL = "https://avoin-karttakuva.maanmittauslaitos.fi/avoin/wmts"
LAYER = "maastokartta"
TILEMATRIXSET = "ETRS-TM35FIN"
FORMAT = "image/png"

# Initialize the coordinate transformer (WGS84 to ETRS-TM35FIN)
transformer = Transformer.from_crs("EPSG:4326", "EPSG:3067", always_xy=True)

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
        r = requests.get(wmts_tile_url(z, x, y), timeout=10)
        r.raise_for_status()
        tile_bytes = BytesIO(r.content)

        # Reproject tile from ETRS-TM35FIN (EPSG:3067) -> WGS84 (EPSG:3857)
        with rasterio.MemoryFile(tile_bytes) as memfile:
            with memfile.open() as src:
                transform, width, height = calculate_default_transform(
                    src.crs, "EPSG:3857", src.width, src.height, *src.bounds
                )
                kwargs = src.meta.copy()
                kwargs.update({
                    "crs": "EPSG:3857",
                    "transform": transform,
                    "width": width,
                    "height": height
                })

                dst_array = np.empty((src.count, height, width), dtype=src.dtypes[0])
                for i in range(1, src.count + 1):
                    reproject(
                        source=rasterio.band(src, i),
                        destination=dst_array[i - 1],
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=transform,
                        dst_crs="EPSG:3857",
                        resampling=Resampling.bilinear
                    )

        # Convert the reprojected array back to PNG
        from PIL import Image
        img = Image.fromarray(dst_array.transpose(1, 2, 0))
        out_bytes = BytesIO()
        img.save(out_bytes, format="PNG")
        out_bytes.seek(0)

        return send_file(out_bytes, mimetype="image/png")

    except Exception as e:
        print(f"Error: {e}")
        return "Tile not found", 404

@app.route("/transform", methods=["POST"])
def transform_coordinates():
    data = request.json
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    if latitude is None or longitude is None:
        return {"error": "Missing latitude or longitude"}, 400

    try:
        x, y = transformer.transform(longitude, latitude)
        return {"x": x, "y": y}
    except Exception as e:
        print(f"Transformation error: {e}")
        return {"error": "Transformation failed"}, 500

@app.route("/")
def home():
    return "<h3>✅ MML WMTS Tile Proxy with WGS84 Reprojection and Coordinate Transformation running!</h3>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)