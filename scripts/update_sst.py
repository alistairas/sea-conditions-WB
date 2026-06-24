print("Script started", flush=True)

import json
print("json imported", flush=True)

import os
print("os imported", flush=True)

from datetime import datetime, timedelta, timezone
print("datetime, timedelta, timezone imported", flush=True)

import requests
print("requests imported", flush=True)

import time
print("time imported", flush=True)

import copernicusmarine
print("copernicusmarine imported", flush=True)

import xarray as xr
print("xarray imported", flush=True)

from pathlib import Path

DATASET_ID = "METOFFICE-GLO-SST-L4-NRT-OBS-SST-V2"
VARIABLE = "analysed_sst"

LAT = 55.0519527
LON = -1.4479198

weather_url = "https://api.open-meteo.com/v1/forecast"

params = {
    "latitude": LAT,
    "longitude": LON,
    "current": "temperature_2m,wind_speed_10m,wind_direction_10m,weather_code",
    "daily": "uv_index_max",
    "timezone": "Europe/London"
}

try:
    weather = requests.get(weather_url, params=params, timeout=20).json()
    current = weather["current"]
    daily = weather["daily"]
    uv_max = daily["uv_index_max"][0]
    print("Weather data fetched", flush=True)
except Exception as e:
    print(f"Weather fetch failed: {e}", flush=True)
    current = {
        "temperature_2m": None,
        "wind_speed_10m": None,
        "wind_direction_10m": None,
        "weather_code": None
    }
    uv_max = None
    
WEATHER_CODES = {
    0: "Clear",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Light rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Light snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Rain showers",
    81: "Heavy showers",
    82: "Violent showers",
    95: "Thunderstorm"
}

def uv_category(uv):
    if uv is None:
        return None
    elif uv < 3:
        return "Low"
    elif uv < 6:
        return "Moderate"
    elif uv < 8:
        return "High"
    elif uv < 11:
        return "Very High"
    else:
        return "Extreme"

def compass_direction(degrees):
    directions = [
        "N","NNE","NE","ENE",
        "E","ESE","SE","SSE",
        "S","SSW","SW","WSW",
        "W","WNW","NW","NNW"
    ]
    return directions[round(degrees / 22.5) % 16]

# Small offshore box around Whitley Bay
MIN_LAT = 55.00
MAX_LAT = 55.09
MIN_LON = -1.50
MAX_LON = -1.40

OUT_DIR = Path("copernicus-data")
OUT_FILE = "psc_sst.nc"

username = os.environ["COPERNICUS_USERNAME"]
password = os.environ["COPERNICUS_PASSWORD"]
print("Credentials found", flush=True)

end = datetime.now(timezone.utc).date() - timedelta(days=2)
start = end

print(f"Requesting from {start} to {end}", flush=True)

OUT_DIR.mkdir(exist_ok=True)

print("Starting Copernicus subset request...", flush=True)

for attempt in range(1, 4):
    try:
        print(f"Copernicus subset attempt {attempt}/3", flush=True)

        result = copernicusmarine.subset(
            dataset_id=DATASET_ID,
            variables=[VARIABLE, "analysis_error"],
            minimum_longitude=MIN_LON,
            maximum_longitude=MAX_LON,
            minimum_latitude=MIN_LAT,
            maximum_latitude=MAX_LAT,
            start_datetime=f"{start}T00:00:00",
            end_datetime=f"{end}T23:59:59",
            username=username,
            password=password,
            output_directory=str(OUT_DIR),
            output_filename=OUT_FILE,
            overwrite=True,
            disable_progress_bar=True,
        )

        print("Subset complete", flush=True)
        break

    except Exception as e:
        print(f"Copernicus subset attempt {attempt} failed: {e}", flush=True)

        if attempt == 3:
            raise

        time.sleep(60)

ds = xr.open_dataset(OUT_DIR / OUT_FILE)
print(ds["time"].values, flush=True)
print("Latitudes:", ds.latitude.values, flush=True)
print("Longitudes:", ds.longitude.values, flush=True)

sst = ds[VARIABLE].isel(time=-1)
nearest = sst.sel(latitude=LAT, longitude=LON, method="nearest")
print("Requested sample:", LAT, LON, flush=True)
print("Selected OSTIA cell:", float(nearest["latitude"].values), float(nearest["longitude"].values), flush=True)
sst_kelvin = float(nearest.values)
sst_c = round(sst_kelvin - 273.15, 1)
error = ds["analysis_error"].isel(time=-1)
nearest_error = error.sel(latitude=LAT, longitude=LON, method="nearest")
error_c = round(float(nearest_error.values), 1)
#sst_prev = ds[VARIABLE].isel(time=-2)
#nearest_prev = sst_prev.sel(latitude=LAT, longitude=LON, method="nearest")
#sst_prev_c = round(float(nearest_prev.values) - 273.15, 1)
#temp_change = round(sst_c - sst_prev_c, 1)

sst_time = str(ds["time"].values[-1])[:10]
actual_lat = float(nearest["latitude"].values)
actual_lon = float(nearest["longitude"].values)

data = {
    "version": 1,
    "sea_temp_c": sst_c,
#    "temp_change_24h": temp_change,
    "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    "source": "Copernicus Marine OSTIA NRT",
    "dataset": DATASET_ID,
    "variable": VARIABLE,
    "sst_date": sst_time,
    "location": "North Tyneside coast",
    "sample_area": "North Tyneside coast",
    "sample_lat": LAT,
    "sample_lon": LON,
    "actual_pixel_lat": actual_lat,
    "actual_pixel_lon": actual_lon,
    "sample_method": "Nearest OSTIA SST pixel to selected offshore point near Panama Swimming Club",
    "measurement": "Sea temperature",
    "units": "°C",
    "grid_resolution": "0.05 degrees",
    "analysis_error_c": error_c,
    "air_temp_c": current["temperature_2m"],
"wind_speed_kmh": current["wind_speed_10m"],
"wind_direction_deg": current["wind_direction_10m"],
"uv_max": uv_max,
"uv_category": uv_category(uv_max),
"weather_code": current["weather_code"],
"forecast": WEATHER_CODES.get(current["weather_code"], "Unknown") if current["weather_code"] is not None else None,
"wind_direction": compass_direction(current["wind_direction_10m"]) if current["wind_direction_10m"] is not None else None
}

history = []

try:
    with open("history.json", "r") as f:
        history = json.load(f)
except:
    pass

history = [h for h in history if h["date"] != sst_time]

temp_change = None

if len(history) > 0:
    previous_temp = history[-1]["sea_temp_c"]
    temp_change = round(sst_c - previous_temp, 1)

data["temp_change_24h"] = temp_change

history.append({
    "date": sst_time,
    "sea_temp_c": sst_c
})

history = history[-365:]

with open("history.json", "w") as f:
    json.dump(history, f, indent=2)

with open("data.json", "w") as f:
    json.dump(data, f, indent=2)