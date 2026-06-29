import json
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

LAT = 55.034
LON = -1.432
TIDES_OUT = Path("data/tides.json")
CURVE_OUT = Path("data/tide_curve.json")
TIDES_OUT.parent.mkdir(exist_ok=True)

from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Europe/London")

today_local = datetime.now(LOCAL_TZ).replace(
    hour=0,
    minute=0,
    second=0,
    microsecond=0
)

start = today_local.astimezone(timezone.utc)
end = start + timedelta(days=7)

url = (
    "https://api.openwaters.io/tides/extremes"
    f"?latitude={LAT}"
    f"&longitude={LON}"
    f"&start={start.isoformat().replace('+00:00', 'Z')}"
    f"&end={end.isoformat().replace('+00:00', 'Z')}"
)

with urllib.request.urlopen(url, timeout=30) as response:
    raw = json.loads(response.read().decode("utf-8"))

curve_url = (
    "https://api.openwaters.io/tides/timeline"
    f"?latitude={LAT}"
    f"&longitude={LON}"
    f"&start={start.isoformat().replace('+00:00', 'Z')}"
    f"&end={end.isoformat().replace('+00:00', 'Z')}"
)

with urllib.request.urlopen(curve_url, timeout=30) as response:
    curve_raw = json.loads(response.read().decode("utf-8"))

print("Curve request start:", start.isoformat())
print("Curve request end:", end.isoformat())
print("Timeline points:", len(curve_raw.get("timeline", [])))

if curve_raw.get("timeline"):
    print("First curve point:", curve_raw["timeline"][0]["time"])
    print("Last curve point:", curve_raw["timeline"][-1]["time"])

CURVE_OUT.write_text(
    json.dumps({
        "location": "Whitley Bay / Cullercoats",
        "station": curve_raw["station"]["name"],
        "datum": curve_raw["datum"],
        "units": curve_raw["units"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "points": [
            {
                "time": item["time"],
                "height_m": round(item["level"], 2)
            }
            for item in curve_raw["timeline"]
        ]
    }, indent=2),
    encoding="utf-8"
)

payload = {
    "location": "Whitley Bay / Cullercoats",
    "latitude": LAT,
    "longitude": LON,
    "station": {
        "name": raw["station"]["name"],
        "id": raw["station"]["id"],
        "distance_km": round(raw["distance"], 2),
        "timezone": raw["station"]["timezone"],
        "datum": raw["datum"],
        "units": raw["units"],
        "license": raw["station"]["license"],
        "source": raw["station"]["source"],
    },
    "source": "Open Waters / Neaps tide predictions using TICON-4 harmonics",
    "source_url": "https://openwaters.io/api",
    "not_for_navigation": True,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "events": [
        {
            "time": item["time"],
            "label": item["label"],
            "type": "High" if item["high"] else "Low",
            "height_m": round(item["level"], 2),
        }
        for item in raw["extremes"]
    ],
}

TIDES_OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

print("Wrote data/tides.json and data/tide_curve.json")