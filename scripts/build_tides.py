import json
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

LAT = 55.034
LON = -1.432
OUT = Path("data/tides.json")

start = datetime.now(timezone.utc)
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

OUT.parent.mkdir(exist_ok=True)

payload = {
    "location": "Whitley Bay / Cullercoats",
    "station_note": "Nearest Open Waters tide station to Cullercoats coordinates",
    "latitude": LAT,
    "longitude": LON,
    "source": "Open Waters / Neaps tide predictions",
    "source_url": "https://openwaters.io/api",
    "not_for_navigation": True,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "raw": raw,
}

OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print("Wrote data/tides.json")