import requests

class BearerAuth(requests.auth.AuthBase):
    def __init__(self, token):
        self.token = token
    def __call__(self, r):
        r.headers["authorization"] = "Bearer " + self.token
        return r

PROJECT_ID = 550  # TODO
USERNAME = "Anonymous"
session = requests.session()

print("begin online setup")

main_response = session.get("https://mg1.gis-net.co.il/PardesHanaKarkurGis/")
assert main_response.ok

login_response = session.post("https://mg1.gis-net.co.il/PardesHanaKarkurApi/api/auth/UserLogin", json={
    "userName": USERNAME,
    "userPassword": "",
    "projId": PROJECT_ID,
})
assert login_response.ok

token = login_response.json()
assert isinstance(token, str)
auth = BearerAuth(token)

lut_response = session.get(f"https://mg1.gis-net.co.il/PardesHanaKarkurApi/api/app/GetLutValues?projId={PROJECT_ID}", auth=auth)
assert lut_response.ok
lookup_table = lut_response.json()

first_toc_response = session.post("https://mg1.gis-net.co.il/PardesHanaKarkurApi/api/map/FirstLoadingMap", auth=auth, json={
    "mapSession": "",
    "mapName": "",
    "projId": PROJECT_ID,
})
assert first_toc_response.ok
first_toc = first_toc_response.json()

toc_response = session.post("https://mg1.gis-net.co.il/PardesHanaKarkurApi/api/map/getMapToc", auth=auth, json={
    "mapSession": first_toc["sessionId"],
    "mapName": first_toc["mapName"],
    "projId": PROJECT_ID,
})
assert toc_response.ok
toc = toc_response.json()

assert first_toc == toc

print("end online setup")

import random
import math
from typing import NamedTuple
from PIL import Image
from io import BytesIO

Bounds = NamedTuple("Bounds", [("min_x", float), ("max_x", float), ("min_y", float), ("max_y", float)])

# In map: y is low at the bottom (south) of the image
# In PIL: y is low at the top of the image

MAP_BOUNDS = Bounds(min_x=194602, max_x=201663, min_y=705553, max_y=712414)

INCH_PER_METER = 39.3700787
DPI = 96
WIDTH = 10_000
HEIGHT = 10_000
SCALE = 500
CENTER_X = 198199.77139954278
CENTER_Y = 709005.376344086
DELTA_X = WIDTH / DPI / INCH_PER_METER * SCALE
DELTA_Y = HEIGHT / DPI / INCH_PER_METER * SCALE
assert DELTA_X == DELTA_Y and abs(DELTA_X-1322.91666802)<1e-5


# img_response = session.get(f"https://mg1.gis-net.co.il/mapguide{PROJECT_ID}/mapagent/mapagent.fcgi", params={
#     "USERNAME": USERNAME,
#     "SEQ": 0.9600439442289928,  # TODO?
#     "OPERATION": "GETDYNAMICMAPOVERLAYIMAGE",
#     "VERSION": "2.0.0",
#     "LOCALE": "en",
#     "CLIENTAGENT": "ol.source.ImageMapGuide source",
#     "CLIP": 1,
#     "SETDISPLAYDPI": dpi,
#     "SETDISPLAYWIDTH": col_size,
#     "SETDISPLAYHEIGHT": row_size,
#     "SETVIEWSCALE": scale,
#     "SETVIEWCENTERX": center_x,
#     "SETVIEWCENTERY": center_y,
#     "MAPNAME": "PardesHanaKarkurGIS",
#     "FORMAT": "PNG",
#     "SESSION": toc["sessionId"],
#     "BEHAVIOR": 2,
#     "unique": random.randint(100, 999),
#     #hideLayers:,
#     #showLayers:,
# })


def select_layers(toc: dict, layers: list[str]):
    to_add = []
    to_remove = []

    for layer in toc["layers"]:
        if not layer["visible"] and layer["layerName"] in layers:
            to_add.append(layer["uniqueId"])
            print("ADD   ", layer)
        if layer["visible"] and layer["layerName"] not in layers:
            to_remove.append(layer["uniqueId"])
            print("REMOVE", layer)

    img_response = session.get(f"https://mg1.gis-net.co.il/mapguide{PROJECT_ID}/mapagent/mapagent.fcgi", params={
        "USERNAME": USERNAME,
        "SEQ": 0.9600439442289928,  # TODO?
        "OPERATION": "GETDYNAMICMAPOVERLAYIMAGE",
        "VERSION": "2.0.0",
        "LOCALE": "en",
        "CLIENTAGENT": "ol.source.ImageMapGuide source",
        "CLIP": 1,
        "SETDISPLAYDPI": DPI,
        "SETDISPLAYWIDTH": 5,
        "SETDISPLAYHEIGHT": 5,
        "SETVIEWSCALE": 500,
        "SETVIEWCENTERX": CENTER_X,
        "SETVIEWCENTERY": CENTER_Y,
        "MAPNAME": "PardesHanaKarkurGIS",
        "FORMAT": "PNG",
        "SESSION": toc["sessionId"],
        "BEHAVIOR": 2,
        "unique": random.randint(100, 999),
        "hideLayers": ",".join(to_remove),
        "showLayers": ",".join(to_add),
    })
    assert img_response.ok

select_layers(toc, ["Mivnim"])

def download_map(session: requests.Session, *, bounds=MAP_BOUNDS, max_width=10_000, max_height=10_000, dpi=96, scale=500) -> Image.Image:
    pixel_to_meter = scale / dpi / INCH_PER_METER

    pixel_width  = math.ceil((bounds.max_y - bounds.min_y) / pixel_to_meter)
    pixel_height = math.ceil((bounds.max_x - bounds.min_x) / pixel_to_meter)

    #result = Image.new("RGB", (pixel_width, pixel_height))

    num_rows = math.ceil(pixel_height / max_height)
    num_cols = math.ceil(pixel_width / max_width)
    last_row_size = pixel_height - (num_rows-1)*max_height
    last_col_size = pixel_width  - (num_cols-1)*max_width

    for row in range(num_rows):
        for col in range(num_cols):
            row_size = last_row_size if row == (num_rows-1) else max_height
            col_size = last_col_size if col == (num_cols-1) else max_width
            row_center_offset = row*max_height + row_size/2
            col_center_offset = col*max_width + col_size/2
            center_x = bounds.min_x + pixel_to_meter*row_center_offset
            center_y = bounds.min_y + pixel_to_meter*col_center_offset

            print(f"get {row+1},{col+1} out of {num_rows},{num_cols}", flush=True)

            img_response = session.get(f"https://mg1.gis-net.co.il/mapguide{PROJECT_ID}/mapagent/mapagent.fcgi", params={
                "USERNAME": USERNAME,
                "SEQ": 0.9600439442289928,  # TODO?
                "OPERATION": "GETDYNAMICMAPOVERLAYIMAGE",
                "VERSION": "2.0.0",
                "LOCALE": "en",
                "CLIENTAGENT": "ol.source.ImageMapGuide source",
                "CLIP": 1,
                "SETDISPLAYDPI": dpi,
                "SETDISPLAYWIDTH": col_size,
                "SETDISPLAYHEIGHT": row_size,
                "SETVIEWSCALE": scale,
                "SETVIEWCENTERX": center_x,
                "SETVIEWCENTERY": center_y,
                "MAPNAME": "PardesHanaKarkurGIS",
                "FORMAT": "PNG",
                "SESSION": toc["sessionId"],
                "BEHAVIOR": 2,
                "unique": random.randint(100, 999),
                #hideLayers:,
                #showLayers:,
            })
            assert img_response.ok

            image = Image.open(BytesIO(img_response.content))
            image.save(open(f'/tmp/tile-{row}-{col}.png', 'wb'), 'png')
            #result.paste(image, (col*max_width, (num_rows-row-1)*max_height))
    
    #return result

res = download_map(session)
#res.save(open('/tmp/result.png', 'wb'), 'png')
