print("Script started", flush=True)

import json
print("json imported", flush=True)

import os
print("os imported", flush=True)

from datetime import datetime, timedelta, timezone
print("datetime, timedelta, timezone imported", flush=True)

import copernicusmarine
print("copernicusmarine imported", flush=True)

import xarray as xr
print("xarray imported", flush=True)

from pathlib import Path

DATASET_ID = "METOFFICE-GLO-SST-L4-NRT-OBS-SST-V2"
VARIABLE = "analysed_sst"

LAT = 55.044
LON = -1.445

# Small offshore box around PSC
MIN_LAT = 55.02
MAX_LAT = 55.07
MIN_LON = -1.50
MAX_LON = -1.40

OUT_DIR = Path("copernicus-data")
OUT_FILE = "psc_sst.nc"

username = os.environ["COPERNICUS_USERNAME"]
password = os.environ["COPERNICUS_PASSWORD"]
print("Credentials found", flush=True)

end = datetime.now(timezone.utc).date() - timedelta(days=1)
start = end

OUT_DIR.mkdir(exist_ok=True)

print("Starting Copernicus subset request...", flush=True)

result = copernicusmarine.subset(
    dataset_id=DATASET_ID,
    variables=[VARIABLE],
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

ds = xr.open_dataset(OUT_DIR / OUT_FILE)

sst = ds[VARIABLE].isel(time=-1)
nearest = sst.sel(latitude=LAT, longitude=LON, method="nearest")
sst_kelvin = float(nearest.values)
sst_c = round(sst_kelvin - 273.15, 1)

sst_time = str(ds["time"].values[-1])[:10]
actual_lat = float(nearest["latitude"].values)
actual_lon = float(nearest["longitude"].values)

data = {
    "version": 1,
    "sea_temp_c": sst_c,
    "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    "source": "Copernicus Marine OSTIA NRT",
    "dataset": DATASET_ID,
    "variable": VARIABLE,
    "sst_date": sst_time,
    "location": "Whitley Bay, near PSC",
    "sample_lat": LAT,
    "sample_lon": LON,
    "actual_pixel_lat": actual_lat,
    "actual_pixel_lon": actual_lon,
    "sample_method": "Nearest valid offshore SST pixel close to Panama Swimming Club"
}

with open("data.json", "w") as f:
    json.dump(data, f, indent=2)