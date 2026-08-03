import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

LAT = 55.034
LON = -1.432
TIDES_OUT = Path("data/tides.json")
CURVE_OUT = Path("data/tide_curve.json")
TIDES_OUT.parent.mkdir(exist_ok=True)

def fetch_json(url, timeout=30, retries=3):
    headers = {
        "User-Agent": "sea-conditions-WB/1.0 (+https://alistairas.github.io/sea-conditions-WB/)",
        "Accept": "application/json",
    }

    last_error = None

    for attempt in range(1, retries + 1):
        request = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))

        except urllib.error.HTTPError as error:
            last_error = error

            # 403 may be bot/rate-limit/policy related, so retry gently.
            # 429 and 5xx are also worth retrying.
            if error.code in (403, 429, 500, 502, 503, 504):
                wait_seconds = attempt * 10
                print(
                    f"HTTP {error.code} from API on attempt {attempt}/{retries}. "
                    f"Waiting {wait_seconds}s before retry."
                )
                time.sleep(wait_seconds)
                continue

            raise

        except urllib.error.URLError as error:
            last_error = error
            wait_seconds = attempt * 10
            print(
                f"Network error on attempt {attempt}/{retries}: {error}. "
                f"Waiting {wait_seconds}s before retry."
            )
            time.sleep(wait_seconds)

    raise RuntimeError(f"Could not fetch API data after {retries} attempts: {last_error}")

from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Europe/London")

from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Europe/London")


def existing_tide_files_available():
    return TIDES_OUT.exists() and CURVE_OUT.exists()


def build_tides():
    today_local = datetime.now(LOCAL_TZ).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    start = today_local.astimezone(timezone.utc)
    end = start + timedelta(days=8)

    start_param = start.isoformat().replace("+00:00", "Z")
    end_param = end.isoformat().replace("+00:00", "Z")

    url = (
        "https://api.openwaters.io/tides/extremes"
        f"?latitude={LAT}"
        f"&longitude={LON}"
        f"&start={start_param}"
        f"&end={end_param}"
    )

    curve_url = (
        "https://api.openwaters.io/tides/timeline"
        f"?latitude={LAT}"
        f"&longitude={LON}"
        f"&start={start_param}"
        f"&end={end_param}"
    )

    print("Tide request start:", start.isoformat())
    print("Tide request end:", end.isoformat())

    raw = fetch_json(url)
    curve_raw = fetch_json(curve_url)

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


try:
    build_tides()

except Exception as error:
    print(f"WARNING: tide build failed: {error}")

    if existing_tide_files_available():
        print("Keeping existing tide data files so the site can continue to build.")
    else:
        print("No existing tide data files found, so the build must fail.")
        raise